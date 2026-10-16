# =============================================================================
# AFSM Robot Dog — Raspberry Pi Pico 2 
# Course: 4FTC2135-0105-2025 Robot Design and Build Project B
# =============================================================================
# Mission:   EXPLORE  LOW_CHARGE  CHARGING  TARGET_DETECTED
# Behaviour: FORWARD | TURN_L/R | VEER_L/R | RECOVERY
# Priority:  Target-Detection > Obstacle Avoidance > Low-charged & Charging logic > Forward
# =============================================================================

import utime
import machine

# =========================
# Constants
# =========================

# --- Pin Mapping ---
PIN_RF         = 10
PIN_RR         = 9
PIN_LF         = 21
PIN_LR         = 22
PIN_US_SERVO   = 7
PIN_LDR        = 28
PIN_TRIG       = 18
PIN_ECHO       = 13
PIN_TCS_S2     = 16
PIN_TCS_S3     = 17
PIN_TCS_OUT    = 14
PIN_TCS_LED    = 15
PIN_STATUS_LED = 1

# --- Servo ---
SERVO_FREQ = 50
MIN_DUTY   = 1638       # 0 deg  = 0.5 ms pulse
MAX_DUTY   = 8192       # 180 deg = 2.5 ms pulse
SERVO_OFFSETS = [0, 5, 12, 5, 0]   # [RF, RR, LF, LR, US]

# --- Gait geometry ---
MID_ANGLE = 90
ARC       = 15          # sweep amplitude (degrees)

# --- Step timing (ms) ---
STEP_FAST = 150         # Explore speed
STEP_SLOW = 300         # Low Charge speed

# --- Avoidance factors ---
VEER_FREQ_FACTOR   = 2
VEER_STRIDE_FACTOR = 1.8
TURN_FREQ_FACTOR   = 3
TURN_STRIDE_FACTOR = 1.3
REVERSE_FREQ_FACTOR   = 1.2
REVERSE_STRIDE_FACTOR = 1.2

# --- Avoidance durations (ms) ---
VEER_DURATION    = 6000
TURN_DURATION    = 12000
TURN_HOLD        = 80
REVERSE_MS       = 6000
RECOVERY_TURN_MS = 12000

# --- Ultrasonic scan ---
SCAN_ANGLES = [150, 85, 20]   # LD, FD, RD
SCAN_FAST   = 150
SCAN_SLOW   = 300

# --- Obstacle thresholds (cm) ---
DIST_CLEAR  = 15
DIST_TURN   = 10
DIST_DANGER =  5

# --- Mission timers (ms) ---
EXPLORE_MS = 120_000
CHARGE_MS  =  60_000
BLINK_MS   = 500

# --- Sensor tuning ---
LDR_THRESHOLD  = 60_000
RED_THRESHOLD  = 300
US_TIMEOUT     = 12_000
TCS_TIMEOUT_US = 5_000
RED_CHECK_MS   = 100
LDR_CHECK_MS   = 200

# --- Safety counters ---
TURN_MAX     = 3
RECOVERY_MAX = 3

# =========================
# Hardware Setup
# =========================

# -- Leg servos --
_pwm_rf = machine.PWM(machine.Pin(PIN_RF)); _pwm_rf.freq(SERVO_FREQ)
_pwm_rr = machine.PWM(machine.Pin(PIN_RR)); _pwm_rr.freq(SERVO_FREQ)
_pwm_lf = machine.PWM(machine.Pin(PIN_LF)); _pwm_lf.freq(SERVO_FREQ)
_pwm_lr = machine.PWM(machine.Pin(PIN_LR)); _pwm_lr.freq(SERVO_FREQ)
_pwm_us = machine.PWM(machine.Pin(PIN_US_SERVO)); _pwm_us.freq(SERVO_FREQ)

# -- LDR light sensor --
_adc_ldr = machine.ADC(machine.Pin(PIN_LDR))

# -- HC-SR04 ultrasonic --
_pin_trig = machine.Pin(PIN_TRIG, machine.Pin.OUT)
_pin_echo = machine.Pin(PIN_ECHO, machine.Pin.IN)

# -- TCS3200 colour sensor --
_pin_s2 = machine.Pin(PIN_TCS_S2, machine.Pin.OUT)
_pin_s3 = machine.Pin(PIN_TCS_S3, machine.Pin.OUT)
_pin_tcs_out = machine.Pin(PIN_TCS_OUT, machine.Pin.IN)
_pin_tcs_led = machine.Pin(PIN_TCS_LED, machine.Pin.OUT)
_pin_tcs_led.value(0)

# -- Status LED --
_pin_led = machine.Pin(PIN_STATUS_LED, machine.Pin.OUT)
_pin_led.value(0)


# =========================
# Servo Control
# =========================

def _set_servo(pwm, angle, offset_idx=None):
    """Convert angle to PWM duty and write, with optional trim offset."""
    if pwm is None:
        return
    if offset_idx is not None:
        angle += SERVO_OFFSETS[offset_idx]
    angle = max(0, min(180, angle))
    pwm.duty_u16(int(MIN_DUTY + (angle / 180.0) * (MAX_DUTY - MIN_DUTY)))


def _apply_step(step):
    """Write one gait-table row to all four leg servos."""
    _set_servo(_pwm_rf, step[0], 0)
    _set_servo(_pwm_rr, step[1], 1)
    _set_servo(_pwm_lf, step[2], 2)
    _set_servo(_pwm_lr, step[3], 3)


def stop_legs():
    """Set all legs to neutral position."""
    _set_servo(_pwm_rf, MID_ANGLE, 0)
    _set_servo(_pwm_rr, MID_ANGLE, 1)
    _set_servo(_pwm_lf, MID_ANGLE, 2)
    _set_servo(_pwm_lr, MID_ANGLE, 3)


def init_hardware():
    """Centre pan servo and print ready."""
    _set_servo(_pwm_us, 90, 4)
    print("[INIT] Hardware ready")


# =========================
# Gait Tables
# =========================
# Forward: 4-phase wave gait — each leg 90 deg out of phase.
# Turn / Veer: Differential Arc Steering — one side stopped,
#   the other at amplified stride, yaw accumulates over time.
# Reverse: time-reversed forward with stride scaling.

FORWARD_STEPS = []
REVERSE_STEPS = []
TURN_L_STEPS  = []
TURN_R_STEPS  = []
VEER_L_STEPS  = []
VEER_R_STEPS  = []


def build_gait_tables():
    global FORWARD_STEPS, REVERSE_STEPS
    global TURN_L_STEPS, TURN_R_STEPS
    global VEER_L_STEPS, VEER_R_STEPS

    pos_back     = MID_ANGLE - ARC // 2
    pos_mid_back = MID_ANGLE - ARC // 6
    pos_mid_fwd  = MID_ANGLE + ARC // 6
    pos_fwd      = MID_ANGLE + ARC // 2

    FORWARD_STEPS = [
        (pos_fwd,      pos_back,     pos_mid_fwd,  pos_mid_back),
        (pos_mid_fwd,  pos_fwd,      pos_fwd,      pos_mid_fwd),
        (pos_mid_back, pos_mid_fwd,  pos_back,     pos_fwd),
        (pos_back,     pos_mid_back, pos_mid_back, pos_back),
    ]

    REVERSE_STEPS = [
        (pos_back,     pos_fwd,      pos_mid_back, pos_mid_fwd),
        (pos_mid_back, pos_back,     pos_back,     pos_mid_back),
        (pos_mid_fwd,  pos_mid_back, pos_fwd,      pos_back),
        (pos_fwd,      pos_mid_fwd,  pos_mid_fwd,  pos_fwd),
    ]
    REVERSE_STEPS = [(MID_ANGLE + int((rf - MID_ANGLE) * REVERSE_STRIDE_FACTOR),
                      MID_ANGLE + int((rr - MID_ANGLE) * REVERSE_STRIDE_FACTOR),
                      MID_ANGLE + int((lf - MID_ANGLE) * REVERSE_STRIDE_FACTOR),
                      MID_ANGLE + int((lr - MID_ANGLE) * REVERSE_STRIDE_FACTOR))
                     for (rf, rr, lf, lr) in REVERSE_STEPS]

    def _turn_steps(moving_side):
        result = []
        for rf, rr, lf, lr in FORWARD_STEPS:
            if moving_side == 'R':
                rf = MID_ANGLE + int((rf - MID_ANGLE) * TURN_STRIDE_FACTOR)
                rr = MID_ANGLE + int((rr - MID_ANGLE) * TURN_STRIDE_FACTOR)
                lf = lr = MID_ANGLE
            else:
                lf = MID_ANGLE + int((lf - MID_ANGLE) * TURN_STRIDE_FACTOR)
                lr = MID_ANGLE + int((lr - MID_ANGLE) * TURN_STRIDE_FACTOR)
                rf = rr = MID_ANGLE
            result.append((rf, rr, lf, lr))
        return result

    TURN_L_STEPS = _turn_steps('R')
    TURN_R_STEPS = _turn_steps('L')

    def _veer_steps(moving_side):
        result = []
        for rf, rr, lf, lr in FORWARD_STEPS:
            if moving_side == 'R':
                rf = MID_ANGLE + int((rf - MID_ANGLE) * VEER_STRIDE_FACTOR)
                rr = MID_ANGLE + int((rr - MID_ANGLE) * VEER_STRIDE_FACTOR)
                lf = lr = MID_ANGLE
            else:
                lf = MID_ANGLE + int((lf - MID_ANGLE) * VEER_STRIDE_FACTOR)
                lr = MID_ANGLE + int((lr - MID_ANGLE) * VEER_STRIDE_FACTOR)
                rf = rr = MID_ANGLE
            result.append((rf, rr, lf, lr))
        return result

    VEER_L_STEPS = _veer_steps('R')
    VEER_R_STEPS = _veer_steps('L')


build_gait_tables()


# =========================
# Sensors
# =========================

def get_distance():
    """Single HC-SR04 reading in cm. Returns 100 on timeout."""
    _pin_trig.value(0)
    utime.sleep_us(2)
    _pin_trig.value(1)
    utime.sleep_us(10)
    _pin_trig.value(0)
    p = machine.time_pulse_us(_pin_echo, 1, US_TIMEOUT)
    if p > 0:
        return round((p * 0.0343) / 2.0, 1)
    return 100


def _read_tcs(s2, s3):
    """Read one TCS3200 colour channel. Lower value = stronger colour."""
    _pin_s2.value(s2)
    _pin_s3.value(s3)
    val = machine.time_pulse_us(_pin_tcs_out, 0, TCS_TIMEOUT_US)
    return val if val >= 0 else TCS_TIMEOUT_US


def read_ldr():
    """Read LDR ADC value. Higher = brighter."""
    return _adc_ldr.read_u16()


# =========================
# State Machine
# =========================

# --- State & Behaviour Enums ---
M_START      = "START"
M_EXPLORE    = "EXPLORE"
M_LOW_CHARGE = "LOW_CHARGE"
M_CHARGING   = "CHARGING"
M_TARGET     = "TARGET_DETECTED"
M_FAULT      = "FAULT_STOP"

B_FORWARD  = "FORWARD"
B_TURN_L   = "TURN_LEFT"
B_TURN_R   = "TURN_RIGHT"
B_VEER_L   = "VEER_LEFT"
B_VEER_R   = "VEER_RIGHT"
B_RECOVERY = "RECOVERY"

# --- State Variables ---
mission   = M_START
behaviour = B_FORWARD

ld = 100; fd = 100; rd = 100   # latest ultrasonic readings (cm)

# Mission timers
explore_start  = 0
charging_start = 0

# Gait state
gait         = FORWARD_STEPS
step_idx     = 0
step_ms      = 0
manoeuvre_ms = 0

# Per-side phase tracking for forward wave gait
phase_l    = 0
phase_r    = 0
phase_ms_l = 0
phase_ms_r = 0

# Scan state — cycles FD -> LD -> FD -> RD
SCAN_SEQ     = [1, 0, 1, 2]
scan_seq     = 0
scan_phase   = 0
scan_last_ms = 0

# Sensor rate-limiters
red_last_ms = 0
ldr_last_ms = 0
red_confirm = False

# LED blink state (Target Detected)
led_on      = False
led_last_ms = 0

# Safety counters
turn_count     = 0
recovery_count = 0


# --- Helper ---

def _set_led(val):
    _pin_led.value(val)


# --- State Transitions ---

def _return_to_forward():
    """Reset behaviour to Forward and re-init scan + gait state."""
    global behaviour, gait, step_idx, step_ms
    global phase_l, phase_r, phase_ms_l, phase_ms_r
    global scan_seq, scan_phase, scan_last_ms

    behaviour = B_FORWARD
    gait = FORWARD_STEPS
    step_idx = 0
    step_ms = utime.ticks_ms()
    phase_l = 0; phase_r = 0
    phase_ms_l = utime.ticks_ms()
    phase_ms_r = utime.ticks_ms()
    scan_seq = 0; scan_phase = 0
    scan_last_ms = utime.ticks_ms()


def goto_explore():
    global mission, explore_start, turn_count, recovery_count
    mission = M_EXPLORE
    explore_start = utime.ticks_ms()
    turn_count = 0
    recovery_count = 0
    _return_to_forward()
    _set_led(0)
    print("[STATE] -> Explore")


def goto_low_charge():
    global mission, turn_count, recovery_count
    mission = M_LOW_CHARGE
    turn_count = 0
    recovery_count = 0
    _return_to_forward()
    _set_led(0)
    print("[STATE] -> Low Charge")


def goto_charging():
    global mission, charging_start
    mission = M_CHARGING
    charging_start = utime.ticks_ms()
    stop_legs()
    _set_led(1)
    _pin_tcs_led.value(0)
    print("[STATE] -> Charging")


def goto_target():
    global mission, led_on, led_last_ms
    mission = M_TARGET
    led_on = False
    led_last_ms = utime.ticks_ms()
    stop_legs()
    _set_led(0)
    _pin_tcs_led.value(0)
    print("[STATE] -> TARGET DETECTED")


def _goto_fault():
    global mission
    mission = M_FAULT
    stop_legs()
    _set_led(0)
    _pin_tcs_led.value(0)
    print("[STATE] -> FAULT STOP")


# =========================
# Obstacle Avoidance
# =========================

def scan_update(now):
    """Run one step of the scan FSM. Returns True when a new FD reading lands."""
    global scan_seq, scan_phase, scan_last_ms, ld, fd, rd

    interval = SCAN_FAST if mission == M_EXPLORE else SCAN_SLOW
    if utime.ticks_diff(now, scan_last_ms) < interval:
        return False
    scan_last_ms = now

    if scan_phase == 0:
        _set_servo(_pwm_us, SCAN_ANGLES[SCAN_SEQ[scan_seq]], 4)
        scan_phase = 1
        return False
    else:
        cur = SCAN_SEQ[scan_seq]
        dist = get_distance()
        if cur == 0:    ld = dist
        elif cur == 1:  fd = dist
        else:           rd = dist
        is_fd = (cur == 1)
        scan_seq = (scan_seq + 1) % 4
        scan_phase = 0
        return is_fd


def _pick_dir(left, right):
    """Pick turn/veer direction from LD vs RD. Tie-break with LSB of tick."""
    if ld > rd:    return left
    if rd > ld:    return right
    return left if (utime.ticks_us() & 1) else right


def evaluate_obstacle():
    """Decide avoidance action. Priority: Recovery > Turn > Veer."""
    global turn_count

    boxed  = (ld < DIST_TURN and rd < DIST_TURN and fd < DIST_TURN)
    danger = (ld < DIST_DANGER or rd < DIST_DANGER or fd < DIST_DANGER)

    if boxed or danger or turn_count >= TURN_MAX:
        _start_recovery()
        return

    if fd < DIST_TURN:
        _start_turn(_pick_dir(B_TURN_L, B_TURN_R))
        return

    if fd < DIST_CLEAR:
        _start_veer(_pick_dir(B_VEER_L, B_VEER_R))
        return

    turn_count = 0


def _start_turn(target):
    global behaviour, gait, step_idx, step_ms, manoeuvre_ms
    behaviour = target
    gait = TURN_L_STEPS if target == B_TURN_L else TURN_R_STEPS
    step_idx = 0
    step_ms = utime.ticks_ms()
    manoeuvre_ms = utime.ticks_ms()
    stop_legs()


def _start_veer(target):
    global behaviour, gait, step_idx, step_ms, manoeuvre_ms
    behaviour = target
    gait = VEER_L_STEPS if target == B_VEER_L else VEER_R_STEPS
    step_idx = 0
    step_ms = utime.ticks_ms()
    manoeuvre_ms = utime.ticks_ms()
    stop_legs()


def _start_recovery():
    """Reverse then random turn. Escalates to Fault Stop after max retries."""
    global behaviour, recovery_count
    global gait, step_idx, step_ms, manoeuvre_ms

    recovery_count += 1
    if recovery_count >= RECOVERY_MAX:
        _goto_fault()
        return

    behaviour = B_RECOVERY
    gait = REVERSE_STEPS
    step_idx = 0
    step_ms = utime.ticks_ms()
    manoeuvre_ms = utime.ticks_ms()
    stop_legs()
    print("[RECOVERY] count={}".format(recovery_count))


# =========================
# Movement Handlers
# =========================

def handle_forward(now):
    """Wave gait: left and right sides advance independently."""
    global phase_l, phase_r, phase_ms_l, phase_ms_r

    base_step = STEP_FAST if mission == M_EXPLORE else STEP_SLOW

    if utime.ticks_diff(now, phase_ms_l) >= base_step:
        phase_ms_l = now
        s = FORWARD_STEPS[phase_l]
        _set_servo(_pwm_lf, s[2], 2)
        _set_servo(_pwm_lr, s[3], 3)
        phase_l = (phase_l + 1) % len(FORWARD_STEPS)

    if utime.ticks_diff(now, phase_ms_r) >= base_step:
        phase_ms_r = now
        s = FORWARD_STEPS[phase_r]
        _set_servo(_pwm_rf, s[0], 0)
        _set_servo(_pwm_rr, s[1], 1)
        phase_r = (phase_r + 1) % len(FORWARD_STEPS)


def handle_turn(now):
    """Turn in place: brief hold, then step turn gait for TURN_DURATION."""
    global step_idx, step_ms

    if utime.ticks_diff(now, manoeuvre_ms) < TURN_HOLD:
        return

    if utime.ticks_diff(now, manoeuvre_ms) >= TURN_HOLD + TURN_DURATION:
        global turn_count
        turn_count += 1
        _return_to_forward()
        return

    base_step = STEP_FAST if mission == M_EXPLORE else STEP_SLOW
    step_time = int(base_step / TURN_FREQ_FACTOR)
    if utime.ticks_diff(now, step_ms) >= step_time:
        step_ms = now
        _apply_step(gait[step_idx])
        step_idx = (step_idx + 1) % len(gait)


def handle_veer(now):
    """Veer: step veer gait for VEER_DURATION, then return to forward."""
    global step_idx, step_ms

    if utime.ticks_diff(now, manoeuvre_ms) >= VEER_DURATION:
        _return_to_forward()
        return

    base_step = STEP_FAST if mission == M_EXPLORE else STEP_SLOW
    step_time = int(base_step / VEER_FREQ_FACTOR)
    if utime.ticks_diff(now, step_ms) >= step_time:
        step_ms = now
        _apply_step(gait[step_idx])
        step_idx = (step_idx + 1) % len(gait)


def handle_recovery(now):
    """Recovery: reverse, then random turn, then return to forward."""
    global gait, step_idx, step_ms

    elapsed = utime.ticks_diff(now, manoeuvre_ms)
    base_step = STEP_FAST if mission == M_EXPLORE else STEP_SLOW

    # Phase 1: reverse away from obstacle
    if elapsed < REVERSE_MS:
        step_time = int(base_step / REVERSE_FREQ_FACTOR)
        if utime.ticks_diff(now, step_ms) >= step_time:
            step_ms = now
            _apply_step(gait[step_idx])
            step_idx = (step_idx + 1) % len(gait)
        return

    # Switch to random turn after reverse completes
    if gait == REVERSE_STEPS:
        gait = TURN_L_STEPS if (utime.ticks_us() & 1) else TURN_R_STEPS
        step_idx = 0
        step_ms = now
        print("[RECOVERY] reverse done, random turn")
        return

    # Phase 2: turn to new heading
    turn_elapsed = elapsed - REVERSE_MS
    if turn_elapsed >= RECOVERY_TURN_MS:
        _return_to_forward()
        return

    step_time = int(base_step / TURN_FREQ_FACTOR)
    if utime.ticks_diff(now, step_ms) >= step_time:
        step_ms = now
        _apply_step(gait[step_idx])
        step_idx = (step_idx + 1) % len(gait)


# =========================
# Target Detection & Charge Monitor
# =========================

def check_red(now):
    """TCS3200 red detection with double-confirm to suppress false positives."""
    global red_last_ms, red_confirm

    if utime.ticks_diff(now, red_last_ms) < RED_CHECK_MS:
        return False
    red_last_ms = now

    _pin_tcs_led.value(1)
    r = _read_tcs(0, 0)
    g = _read_tcs(1, 1)
    b = _read_tcs(0, 1)
    _pin_tcs_led.value(0)

    detected = (r < g - RED_THRESHOLD) and (r < b - RED_THRESHOLD)
    if detected:
        if red_confirm:
            red_confirm = False
            return True
        red_confirm = True
    else:
        red_confirm = False
    return False


def _poll_ldr(now):
    """Rate-limited LDR read. Returns None if not due yet."""
    global ldr_last_ms
    if utime.ticks_diff(now, ldr_last_ms) < LDR_CHECK_MS:
        return None
    ldr_last_ms = now
    return read_ldr()


def _handle_led_blink(now):
    """Non-blocking LED toggle at BLINK_MS interval."""
    global led_on, led_last_ms
    if utime.ticks_diff(now, led_last_ms) >= BLINK_MS:
        led_last_ms = now
        led_on = not led_on
        val = 1 if led_on else 0
        _set_led(val)
        _pin_tcs_led.value(val)


def _handle_charging(now):
    """Monitor LDR in Charging state. Light lost -> Low Charge; time up -> Explore."""
    ldr = _poll_ldr(now)
    if ldr is not None and ldr < LDR_THRESHOLD:
        goto_low_charge()
        return
    if utime.ticks_diff(now, charging_start) >= CHARGE_MS:
        if read_ldr() >= LDR_THRESHOLD:
            goto_explore()
        else:
            goto_low_charge()


# =========================
# Main Loop
# =========================

def main():
    init_hardware()
    print("[START]")

    while True:
        now = utime.ticks_ms()

        # Priority 1: red target detection (skip in terminal states)
        if mission not in (M_TARGET, M_FAULT):
            if check_red(now):
                goto_target()
                continue

        # Mission state dispatch
        if mission == M_START:
            goto_explore()

        elif mission == M_TARGET:
            _handle_led_blink(now)

        elif mission == M_FAULT:
            pass

        elif mission == M_CHARGING:
            _handle_charging(now)

        elif mission in (M_EXPLORE, M_LOW_CHARGE):
            if behaviour == B_FORWARD:
                if scan_update(now):
                    evaluate_obstacle()

            if mission == M_LOW_CHARGE:
                ldr = _poll_ldr(now)
                if ldr is not None and ldr >= LDR_THRESHOLD:
                    goto_charging()
                    continue

            if mission == M_EXPLORE:
                if utime.ticks_diff(now, explore_start) >= EXPLORE_MS:
                    goto_low_charge()
                    continue

            if behaviour == B_FORWARD:
                handle_forward(now)
            elif behaviour in (B_TURN_L, B_TURN_R):
                handle_turn(now)
            elif behaviour in (B_VEER_L, B_VEER_R):
                handle_veer(now)
            elif behaviour == B_RECOVERY:
                handle_recovery(now)

        utime.sleep_ms(5)


main()
