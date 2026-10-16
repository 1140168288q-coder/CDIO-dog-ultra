# =============================================================================
# AFSM Robot Dog Controller — Raspberry Pi Pico 2 (RP2350) — MicroPython
# Course: 4FTC2135-0105-2025 Robot Design and Build Project B, Assignment 2
# =============================================================================
# 顶层 Mission State: START → EXPLORE ↔ LOW_CHARGE ↔ CHARGING → TARGET_DETECTED
# 避障 Behaviour:   FORWARD | TURN_L/R | VEER_L/R | RECOVERY
# 优先级: Target Detection > Obstacle Avoidance > Charging Logic > Forward
# =============================================================================

import utime
import machine

# =============================================================================
# SECTION 1 — PIN MAPPING
# =============================================================================
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

# =============================================================================
# SECTION 2 — TUNABLE PARAMETERS
# =============================================================================

# Servo PWM
SERVO_FREQ = 50
MIN_DUTY   = 1638      # 0°  = 0.5 ms pulse
MAX_DUTY   = 8192      # 180° = 2.5 ms pulse
# Per-servo trim: [RF, RR, LF, LR, US]
SERVO_OFFSETS = [0, 5, 12, 5, 0]

# Gait geometry
MID_ANGLE = 90
ARC       = 15         # Forward sweep amplitude (degrees)

# Forward drift correction — phase speed per side
LEFT_PHASE_SPEED  = 1
RIGHT_PHASE_SPEED = 1

# Veer — single-side motion parameters (relative to forward)
VEER_FREQ_FACTOR   = 2  # Moving side frequency multiplier
VEER_STRIDE_FACTOR = 1.8  # Moving side stride multiplier

# Turn — single-side motion parameters (relative to forward)
TURN_FREQ_FACTOR   = 3   # Moving side frequency multiplier
TURN_STRIDE_FACTOR = 1.3  # Moving side stride multiplier

# Reverse — stride and frequency multipliers
REVERSE_FREQ_FACTOR   = 1.2
REVERSE_STRIDE_FACTOR = 1.2

# Behaviour durations (ms)
VEER_DURATION = 6000
TURN_DURATION = 12000
TURN_HOLD     = 80

# Step timing (ms)
STEP_FAST   = 150      # Explore forward speed
STEP_SLOW   = 300      # Low Charge forward speed
REVERSE_MS       = 6000      # Reverse duration in Recovery
RECOVERY_TURN_MS = 12000     # Turn duration in Recovery

# Ultrasonic scan
SCAN_ANGLES = [150, 85, 20]   # [LD, FD, RD] pan servo angles
SCAN_FAST   = 150             # ms between scan phases (Explore)
SCAN_SLOW   = 300             # ms between scan phases (Low Charge)

# Obstacle thresholds (cm)
DIST_CLEAR  = 15   # >= 15: path clear, go Forward
DIST_TURN   = 10   # <  10: major blockage, stop + Turn
DIST_DANGER =  5   # <   5: dangerously close, Recovery

# Mission timers (ms)
EXPLORE_MS = 120_000   # 2 min Explore → Low Charge
CHARGE_MS  =  60_000   # 1 min Charging → Explore
BLINK_MS        = 500    # LED toggle in Target Detected
FAULT_BLINK_MS  = 100    # Fast LED toggle in Fault Stop
DEBUG_MS   =    500    # Terminal debug monitor interval

# Sensor tuning
LDR_THRESHOLD  = 60_000
RED_THRESHOLD  = 300
US_TIMEOUT     = 12_000     # µs echo timeout (~2 m)
TCS_TIMEOUT_US = 5_000      # µs timeout per TCS3200 channel
RED_CHECK_MS   = 100        # ms between TCS3200 checks
LDR_CHECK_MS   = 200        # ms between LDR checks

# Safety counters
TURN_MAX     = 3   # Failed turns → Recovery
RECOVERY_MAX = 3   # Recoveries → Fault Stop

VERBOSE_LOG = True

# =============================================================================
# SECTION 3 — GAIT TABLES
# Each row: (RF, RR, LF, LR) raw servo angles (offsets applied in _apply_step)
#
# Forward / Reverse: 4-phase wave — each leg 90° out of phase, smooth sweep.
# Veer / Turn:      Differential Arc Steering — both derived from FORWARD_STEPS
#                    by suppressing one side's stride. Veer uses moderate
#                    asymmetry (0.6x); Turn uses extreme asymmetry (0.15x).
#                    No separate torque topology. Yaw accumulates over time.
# =============================================================================

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

    # ---- Forward: 4-phase wave gait ----
    _a = MID_ANGLE - ARC // 2
    _b = MID_ANGLE - ARC // 6
    _c = MID_ANGLE + ARC // 6
    _d = MID_ANGLE + ARC // 2

    FORWARD_STEPS = [
         (_d, _a, _c, _b),
         (_c, _d, _d, _c),
         (_b, _c, _a, _d),
         (_a, _b, _b, _a),
    ]
    
    REVERSE_STEPS = [
         (_a, _d, _b, _c),
         (_b, _a, _a, _b),
         (_c, _b, _d, _a),
         (_d, _c, _c, _d),
    ]
    REVERSE_STEPS = [(MID_ANGLE + int((rf - MID_ANGLE) * REVERSE_STRIDE_FACTOR),
                      MID_ANGLE + int((rr - MID_ANGLE) * REVERSE_STRIDE_FACTOR),
                      MID_ANGLE + int((lf - MID_ANGLE) * REVERSE_STRIDE_FACTOR),
                      MID_ANGLE + int((lr - MID_ANGLE) * REVERSE_STRIDE_FACTOR))
                     for (rf, rr, lf, lr) in REVERSE_STEPS]

    # ---- Turn: one side stopped, other side at 1.5x stride ----
    def _turn_steps(moving_side):
        result = []
        for s in FORWARD_STEPS:
            rf, rr, lf, lr = s
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

    # ---- Veer: one side stopped, other side at 1.2x stride ----
    def _veer_steps(moving_side):
        result = []
        for s in FORWARD_STEPS:
            rf, rr, lf, lr = s
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

# =============================================================================
# SECTION 4 — HARDWARE INIT
# =============================================================================
_pwm_rf = _pwm_rr = _pwm_lf = _pwm_lr = _pwm_us = None
_adc_ldr = None
_pin_trig = _pin_echo = None
_pin_s2 = _pin_s3 = _pin_tcs_out = _pin_tcs_led = None
_pin_led = None


def log(msg):
    if VERBOSE_LOG:
        print(msg)


def init_hardware():
    global _pwm_rf, _pwm_rr, _pwm_lf, _pwm_lr, _pwm_us
    global _adc_ldr, _pin_trig, _pin_echo
    global _pin_s2, _pin_s3, _pin_tcs_out, _pin_tcs_led, _pin_led

    def _pwm(pin, name):
        if pin is None:
            print("[WARN]", name, "pin not set")
            return None
        p = machine.PWM(machine.Pin(pin))
        p.freq(SERVO_FREQ)
        return p

    _pwm_rf = _pwm(PIN_RF, "RF")
    _pwm_rr = _pwm(PIN_RR, "RR")
    _pwm_lf = _pwm(PIN_LF, "LF")
    _pwm_lr = _pwm(PIN_LR, "LR")
    _pwm_us = _pwm(PIN_US_SERVO, "US")

    if PIN_LDR is not None:
        _adc_ldr = machine.ADC(machine.Pin(PIN_LDR))

    if PIN_TRIG is not None and PIN_ECHO is not None:
        _pin_trig = machine.Pin(PIN_TRIG, machine.Pin.OUT)
        _pin_echo = machine.Pin(PIN_ECHO, machine.Pin.IN)

    if None not in (PIN_TCS_S2, PIN_TCS_S3, PIN_TCS_OUT, PIN_TCS_LED):
        _pin_s2 = machine.Pin(PIN_TCS_S2, machine.Pin.OUT)
        _pin_s3 = machine.Pin(PIN_TCS_S3, machine.Pin.OUT)
        _pin_tcs_out = machine.Pin(PIN_TCS_OUT, machine.Pin.IN)
        _pin_tcs_led = machine.Pin(PIN_TCS_LED, machine.Pin.OUT)
        _pin_tcs_led.value(0)

    if PIN_STATUS_LED is not None:
        _pin_led = machine.Pin(PIN_STATUS_LED, machine.Pin.OUT)
        _pin_led.value(0)

    if _pwm_us:
        _set_servo(_pwm_us, 90, 4)
    log("[INIT] Hardware ready")


# =============================================================================
# SECTION 5 — SERVO HELPERS
# =============================================================================
def _set_servo(pwm, angle, offset_idx=None):
    if pwm is None:
        return
    if offset_idx is not None:
        angle += SERVO_OFFSETS[offset_idx]
    angle = max(0, min(180, angle))
    pwm.duty_u16(int(MIN_DUTY + (angle / 180.0) * (MAX_DUTY - MIN_DUTY)))


def _apply_step(step):
    _set_servo(_pwm_rf, step[0], 0)
    _set_servo(_pwm_rr, step[1], 1)
    _set_servo(_pwm_lf, step[2], 2)
    _set_servo(_pwm_lr, step[3], 3)


def stop_legs():
    """All legs to neutral stand."""
    _set_servo(_pwm_rf, MID_ANGLE, 0)
    _set_servo(_pwm_rr, MID_ANGLE, 1)
    _set_servo(_pwm_lf, MID_ANGLE, 2)
    _set_servo(_pwm_lr, MID_ANGLE, 3)


# =============================================================================
# SECTION 6 — SENSOR FUNCTIONS
# =============================================================================
def get_distance():
    """Single HC-SR04 reading in cm. Returns 100 on timeout / no sensor."""
    if _pin_trig is None:
        return 100
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
    """Read TCS3200 channel. Returns pulse width (smaller = stronger colour)."""
    _pin_s2.value(s2)
    _pin_s3.value(s3)
    val = machine.time_pulse_us(_pin_tcs_out, 0, TCS_TIMEOUT_US)
    return val if val >= 0 else TCS_TIMEOUT_US


def read_ldr():
    return _adc_ldr.read_u16() if _adc_ldr else 0


# =============================================================================
# SECTION 7 — STATES
# =============================================================================
# Mission states
M_START      = "START"
M_EXPLORE    = "EXPLORE"
M_LOW_CHARGE = "LOW_CHARGE"
M_CHARGING   = "CHARGING"
M_TARGET     = "TARGET_DETECTED"
M_FAULT      = "FAULT_STOP"

# Behaviour states (active in Explore / Low Charge)
B_FORWARD  = "FORWARD"
B_TURN_L   = "TURN_LEFT"
B_TURN_R   = "TURN_RIGHT"
B_VEER_L   = "VEER_LEFT"
B_VEER_R   = "VEER_RIGHT"
B_RECOVERY = "RECOVERY"

mission   = M_START
behaviour = B_FORWARD

# Scan readings (cm)
ld = 100; fd = 100; rd = 100

# =============================================================================
# SECTION 8 — TIMERS & STATE VARIABLES
# =============================================================================
# Mission timers
explore_start  = 0
charging_start = 0

# Gait state
gait_table   = FORWARD_STEPS
gait_index   = 0
gait_steps   = 0       # steps executed in current behaviour
gait_last_ms = 0
manoeuvre_ms = 0       # start time of current Turn/Veer/Recovery

# Per-side gait phase (forward drift correction)
gait_idx_l  = 0
gait_idx_r  = 0
gait_ms_l   = 0
gait_ms_r   = 0

# Scan state — cycles FD→LD→FD→RD (SCAN_SEQ)
SCAN_SEQ     = [1, 0, 1, 2]  # indices into SCAN_ANGLES
scan_seq     = 0       # position in SCAN_SEQ
scan_phase   = 0       # 0=move servo, 1=measure
scan_last_ms = 0

# Sensor rate-limiters
red_last_ms  = 0
ldr_last_ms  = 0
red_confirm  = False   # TCS3200 simple double-confirm

# LED blink
led_on       = False
led_last_ms  = 0
fault_led_on = False
fault_led_ms = 0

# Safety counters
turn_count     = 0
recovery_count = 0

# Debug monitor
prev_mission   = ""
prev_behaviour = ""
debug_last_ms  = 0

# =============================================================================
# SECTION 9 — SCAN UPDATE
# Cycles FD → LD → FD → RD. Returns True when a new FD reading is ready.
# =============================================================================
def scan_update(now):
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
        if cur == 0:
            ld = dist
        elif cur == 1:
            fd = dist
        else:
            rd = dist
        is_fd = (cur == 1)
        scan_seq = (scan_seq + 1) % 4
        scan_phase = 0
        return is_fd


# =============================================================================
# SECTION 10 — OBSTACLE DECISION
# Priority: Recovery > Turn > Veer > Forward
# =============================================================================
def _pick_dir(left, right):
    """Pick direction based on LD vs RD. Tie-break with LSB of ticks_us."""
    if ld > rd:
        return left
    if rd > ld:
        return right
    return left if (utime.ticks_us() & 1) else right


def evaluate_obstacle():
    global turn_count

    boxed  = (ld < DIST_TURN and rd < DIST_TURN and fd < DIST_TURN)
    danger = (ld < DIST_DANGER or rd < DIST_DANGER or fd < DIST_DANGER)

    # Priority 1: Recovery
    if boxed or danger or turn_count >= TURN_MAX:
        log("[OBSTACLE] Recovery: boxed={} danger={} turn={}".format(
            boxed, danger, turn_count))
        _start_recovery()
        return

    # Priority 2: Turn (stop + rotate)
    if fd < DIST_TURN:
        log("[OBSTACLE] Turn: FD={} < {}".format(fd, DIST_TURN))
        _start_turn(_pick_dir(B_TURN_L, B_TURN_R))
        return

    # Priority 3: Veer (moving adjustment)
    if fd < DIST_CLEAR:
        log("[OBSTACLE] Veer: FD={} < {}".format(fd, DIST_CLEAR))
        _start_veer(_pick_dir(B_VEER_L, B_VEER_R))
        return

    # Clear path — reset turn counter
    turn_count = 0


def _start_turn(target):
    global behaviour, gait_table, gait_index, gait_steps, gait_last_ms, manoeuvre_ms
    behaviour = target
    gait_table = TURN_L_STEPS if target == B_TURN_L else TURN_R_STEPS
    gait_index = 0
    gait_steps = 0
    gait_last_ms = utime.ticks_ms()
    manoeuvre_ms = utime.ticks_ms()
    stop_legs()
    log("[AVOID] -> " + target)


def _start_veer(target):
    global behaviour, gait_table, gait_index, gait_steps, gait_last_ms, manoeuvre_ms
    behaviour = target
    gait_table = VEER_L_STEPS if target == B_VEER_L else VEER_R_STEPS
    gait_index = 0
    gait_steps = 0
    gait_last_ms = utime.ticks_ms()
    manoeuvre_ms = utime.ticks_ms()
    stop_legs()
    log("[AVOID] -> " + target)


def _start_recovery():
    global behaviour, recovery_count
    global gait_table, gait_index, gait_steps, gait_last_ms, manoeuvre_ms

    recovery_count += 1
    if recovery_count >= RECOVERY_MAX:
        _goto_fault()
        return

    behaviour = B_RECOVERY
    gait_table = REVERSE_STEPS
    gait_index = 0
    gait_steps = 0
    gait_last_ms = utime.ticks_ms()
    manoeuvre_ms = utime.ticks_ms()
    stop_legs()
    log("[AVOID] -> RECOVERY (count={})".format(recovery_count))


def _return_to_forward():
    """Reset behaviour to Forward and start a fresh scan cycle."""
    global behaviour, gait_table, gait_index, gait_steps, gait_last_ms
    global gait_idx_l, gait_idx_r, gait_ms_l, gait_ms_r
    global scan_seq, scan_phase, scan_last_ms
    behaviour = B_FORWARD
    gait_table = FORWARD_STEPS
    gait_index = 0
    gait_steps = 0
    gait_last_ms = utime.ticks_ms()
    gait_idx_l = 0
    gait_idx_r = 0
    gait_ms_l = utime.ticks_ms()
    gait_ms_r = utime.ticks_ms()
    scan_seq = 0       # Start with FD (SCAN_SEQ[0] = 1 = FD)
    scan_phase = 0
    scan_last_ms = utime.ticks_ms()
    log("[AVOID] -> FORWARD")


# =============================================================================
# SECTION 11 — MOVEMENT HANDLERS
# =============================================================================
def handle_forward(now):
    global gait_idx_l, gait_idx_r, gait_ms_l, gait_ms_r
    base_step = STEP_FAST if mission == M_EXPLORE else STEP_SLOW
    step_l = int(base_step / LEFT_PHASE_SPEED)
    step_r = int(base_step / RIGHT_PHASE_SPEED)

    if utime.ticks_diff(now, gait_ms_l) >= step_l:
        gait_ms_l = now
        s = FORWARD_STEPS[gait_idx_l]
        _set_servo(_pwm_lf, s[2], 2)
        _set_servo(_pwm_lr, s[3], 3)
        gait_idx_l = (gait_idx_l + 1) % len(FORWARD_STEPS)

    if utime.ticks_diff(now, gait_ms_r) >= step_r:
        gait_ms_r = now
        s = FORWARD_STEPS[gait_idx_r]
        _set_servo(_pwm_rf, s[0], 0)
        _set_servo(_pwm_rr, s[1], 1)
        gait_idx_r = (gait_idx_r + 1) % len(FORWARD_STEPS)


def handle_turn(now):
    global gait_index, gait_last_ms

    # Hold period — legs already stopped by _start_turn
    if utime.ticks_diff(now, manoeuvre_ms) < TURN_HOLD:
        return

    # Duration-based exit
    if utime.ticks_diff(now, manoeuvre_ms) >= TURN_HOLD + TURN_DURATION:
        global turn_count
        turn_count += 1
        _return_to_forward()
        return

    base_step = STEP_FAST if mission == M_EXPLORE else STEP_SLOW
    step_time = int(base_step / TURN_FREQ_FACTOR)
    if utime.ticks_diff(now, gait_last_ms) >= step_time:
        gait_last_ms = now
        _apply_step(gait_table[gait_index])
        gait_index = (gait_index + 1) % len(gait_table)


def handle_veer(now):
    global gait_index, gait_last_ms

    if utime.ticks_diff(now, manoeuvre_ms) >= VEER_DURATION:
        _return_to_forward()
        return

    base_step = STEP_FAST if mission == M_EXPLORE else STEP_SLOW
    step_time = int(base_step / VEER_FREQ_FACTOR)
    if utime.ticks_diff(now, gait_last_ms) >= step_time:
        gait_last_ms = now
        _apply_step(gait_table[gait_index])
        gait_index = (gait_index + 1) % len(gait_table)


def handle_recovery(now):
    global gait_table, gait_index, gait_last_ms

    elapsed = utime.ticks_diff(now, manoeuvre_ms)
    base_step = STEP_FAST if mission == M_EXPLORE else STEP_SLOW

    # Phase 1: Reverse for REVERSE_MS, then switch to random turn
    if elapsed < REVERSE_MS:
        step_time = int(base_step / REVERSE_FREQ_FACTOR)
        if utime.ticks_diff(now, gait_last_ms) >= step_time:
            gait_last_ms = now
            _apply_step(gait_table[gait_index])
            gait_index = (gait_index + 1) % len(gait_table)
        return

    if gait_table == REVERSE_STEPS:
        gait_table = TURN_L_STEPS if (utime.ticks_us() & 1) else TURN_R_STEPS
        gait_index = 0
        gait_last_ms = now
        log("[RECOVERY] Reverse done, random turn")
        return

    # Phase 2: Turn for RECOVERY_TURN_MS, then return to forward
    turn_elapsed = elapsed - REVERSE_MS
    if turn_elapsed >= RECOVERY_TURN_MS:
        _return_to_forward()
        return

    step_time = int(base_step / TURN_FREQ_FACTOR)
    if utime.ticks_diff(now, gait_last_ms) >= step_time:
        gait_last_ms = now
        _apply_step(gait_table[gait_index])
        gait_index = (gait_index + 1) % len(gait_table)


# =============================================================================
# SECTION 12 — MISSION TRANSITIONS
# =============================================================================
def _set_led(val):
    if _pin_led:
        _pin_led.value(val)


def goto_explore():
    global mission, explore_start, turn_count, recovery_count
    mission = M_EXPLORE
    explore_start = utime.ticks_ms()
    turn_count = 0
    recovery_count = 0
    _return_to_forward()
    _set_led(0)
    log("[STATE] -> Explore")


def goto_low_charge():
    global mission, turn_count, recovery_count
    mission = M_LOW_CHARGE
    turn_count = 0
    recovery_count = 0
    _return_to_forward()
    _set_led(0)
    log("[STATE] -> Low Charge")


def goto_charging():
    global mission, charging_start
    mission = M_CHARGING
    charging_start = utime.ticks_ms()
    stop_legs()
    _set_led(1)
    if _pin_tcs_led:
        _pin_tcs_led.value(0)
    log("[STATE] -> Charging")


def goto_target():
    global mission, led_on, led_last_ms
    mission = M_TARGET
    led_on = False
    led_last_ms = utime.ticks_ms()
    stop_legs()
    _set_led(0)
    if _pin_tcs_led:
        _pin_tcs_led.value(0)
    log("[STATE] -> TARGET DETECTED")


def _goto_fault():
    global mission, fault_led_on, fault_led_ms
    mission = M_FAULT
    fault_led_on = False
    fault_led_ms = utime.ticks_ms()
    stop_legs()
    _set_led(0)
    if _pin_tcs_led:
        _pin_tcs_led.value(0)
    log("[STATE] -> FAULT STOP (awaiting intervention)")


# =============================================================================
# SECTION 13 — DEBUG MONITOR
# Non-blocking periodic terminal output for debugging & demo
# =============================================================================
SCAN_LABELS = {0: "LEFT (150)", 1: "FRONT (85)", 2: "RIGHT (20)"}


def _warn(msg):
    print("[WARNING] " + msg)


def debug_monitor(now):
    global prev_mission, prev_behaviour, debug_last_ms

    if utime.ticks_diff(now, debug_last_ms) < DEBUG_MS:
        return
    debug_last_ms = now

    # --- State change detection ---
    if mission != prev_mission:
        if prev_mission:
            print("[STATE CHANGE]")
            print("  {} -> {}".format(prev_mission, mission))
        prev_mission = mission
    if behaviour != prev_behaviour:
        if prev_behaviour:
            print("[BEHAVIOUR CHANGE]")
            print("  {} -> {}".format(prev_behaviour, behaviour))
        prev_behaviour = behaviour

    # --- Sensor validation warnings ---
    if fd <= 0 or ld <= 0 or rd <= 0:
        _warn("Invalid ultrasonic reading (distance <= 0)")
    if fd >= 100 and ld >= 100 and rd >= 100:
        _warn("All ultrasonic readings at max (sensor disconnected?)")

    # --- Periodic status block ---
    bar = "=" * 50
    print(bar)
    print("MISSION   : {}".format(mission))
    print("BEHAVIOUR : {}".format(behaviour))
    print()
    print("FD : {:.1f} cm".format(fd))
    print("LD : {:.1f} cm".format(ld))
    print("RD : {:.1f} cm".format(rd))
    print()
    ldr_val = read_ldr()
    print("LDR : {}".format(ldr_val))
    print("RED : {}".format(red_confirm))
    print()
    print("STEP : {}".format(gait_index))
    print("SCAN : {}".format(SCAN_LABELS.get(SCAN_SEQ[scan_seq], "?")))
    print(bar)


# =============================================================================
# SECTION 14 — MAIN LOOP
# =============================================================================
def check_red(now):
    """Simple TCS3200 red detection with double-confirm.
    Returns True only when two consecutive readings both detect red."""
    global red_last_ms, red_confirm

    if _pin_tcs_led is None:
        return False
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
    global ldr_last_ms
    if utime.ticks_diff(now, ldr_last_ms) < LDR_CHECK_MS:
        return None
    ldr_last_ms = now
    return read_ldr()


def _handle_led_blink(now):
    global led_on, led_last_ms
    if utime.ticks_diff(now, led_last_ms) >= BLINK_MS:
        led_last_ms = now
        led_on = not led_on
        val = 1 if led_on else 0
        _set_led(val)
        if _pin_tcs_led:
            _pin_tcs_led.value(val)


def _handle_fault_blink(now):
    global fault_led_on, fault_led_ms
    if utime.ticks_diff(now, fault_led_ms) >= FAULT_BLINK_MS:
        fault_led_ms = now
        fault_led_on = not fault_led_on
        _set_led(1 if fault_led_on else 0)


def _handle_charging(now):
    ldr = _poll_ldr(now)
    if ldr is not None and ldr < LDR_THRESHOLD:
        log("[CHARGE] Light lost -> Low Charge")
        goto_low_charge()
        return
    if utime.ticks_diff(now, charging_start) >= CHARGE_MS:
        if read_ldr() >= LDR_THRESHOLD:
            log("[CHARGE] Complete -> Explore")
            goto_explore()
        else:
            log("[CHARGE] No light -> Low Charge")
            goto_low_charge()


def main():
    init_hardware()
    log("[STATE] -> Start")

    while True:
        
        now = utime.ticks_ms()

        # --- Runtime debug monitor (non-blocking, ~500ms interval) ---
        debug_monitor(now)

        # --- Priority 1: Red target detection ---
        if mission not in (M_TARGET, M_FAULT):
            if check_red(now):
                goto_target()
                continue

        # --- Mission state dispatch ---
        if mission == M_START:
            goto_explore()

        elif mission == M_TARGET:
            _handle_led_blink(now)

        elif mission == M_FAULT:
            _handle_fault_blink(now)

        elif mission == M_CHARGING:
            _handle_charging(now)

        elif mission in (M_EXPLORE, M_LOW_CHARGE):
            # Scan + obstacle evaluation (only when moving forward)
            if behaviour == B_FORWARD:
                if scan_update(now):
                    log("[SCAN] LD={} FD={} RD={}".format(ld, fd, rd))
                    evaluate_obstacle()

            # Low Charge: monitor LDR for charging opportunity
            if mission == M_LOW_CHARGE:
                ldr = _poll_ldr(now)
                if ldr is not None and ldr >= LDR_THRESHOLD:
                    goto_charging()
                    continue

            # Explore: timer -> Low Charge
            if mission == M_EXPLORE:
                if utime.ticks_diff(now, explore_start) >= EXPLORE_MS:
                    goto_low_charge()
                    continue

            # Behaviour dispatch
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
