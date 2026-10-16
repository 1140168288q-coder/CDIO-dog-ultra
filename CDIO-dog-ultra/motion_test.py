# =============================================================================
# Motion Calibration Tool — Raspberry Pi Pico 2 — MicroPython
# =============================================================================
# Interactive calibration: pick a test → observe → adjust params → re-run
# Repeat until satisfied. Exit to see final optimized parameters.
# Gait & steering match main.py: 4-phase wave + Differential Arc Steering
# =============================================================================

import utime
import machine

# =============================================================================
# SECTION 1 — TUNABLE PARAMETERS (mirrors main.py Section 2)
# =============================================================================

ARC             = 15
STEP_FAST       = 150    # Forward step interval (ms) — Explore speed
STEP_SLOW       = 300    # Forward step interval (ms) — Low Charge speed
TEST_DURATION   = 4000   # Default test duration (ms)

# Forward drift correction — phase speed per side
LEFT_PHASE_SPEED  = 1.0
RIGHT_PHASE_SPEED = 0.97

# Veer — single-side motion parameters (relative to forward)
VEER_FREQ_FACTOR   = 2
VEER_STRIDE_FACTOR = 1.8


# Turn — single-side motion parameters (relative to forward)
TURN_FREQ_FACTOR   = 3
TURN_STRIDE_FACTOR = 1.3

# Reverse — stride and frequency multipliers
REVERSE_FREQ_FACTOR   = 1.2
REVERSE_STRIDE_FACTOR = 1.2

# Behaviour durations (ms)
VEER_DURATION = 6000
TURN_DURATION = 10000
TURN_HOLD     = 80

# Recovery
REVERSE_MS       = 5000
RECOVERY_TURN_MS = 10000

PARAM_INFO = {
    "ARC":              ("forward sweep amplitude (degrees)",        10,  60),
    "STEP_FAST":        ("step interval — Explore speed (ms)",      80,  500),
    "STEP_SLOW":        ("step interval — Low Charge speed (ms)",   150, 800),
    "TEST_DURATION":    ("default test duration (ms)",              2000, 10000),
    "VEER_FREQ_FACTOR": ("moving side frequency multiplier in veer", 1.0, 3.0),
    "VEER_STRIDE_FACTOR": ("moving side stride multiplier in veer", 1.0, 3.0),
    "TURN_FREQ_FACTOR": ("moving side frequency multiplier in turn", 1.0, 3.0),
    "TURN_STRIDE_FACTOR": ("moving side stride multiplier in turn", 1.0, 3.0),
    "REVERSE_FREQ_FACTOR": ("frequency multiplier for reverse", 0.5, 3.0),
    "REVERSE_STRIDE_FACTOR": ("stride multiplier for reverse", 0.5, 3.0),
    "VEER_DURATION":    ("veer sustain (ms)",                       500,  10000),
    "TURN_DURATION":    ("turn sustain (ms)",                       2000, 20000),
    "TURN_HOLD":        ("pause after stopping legs before turn (ms)", 0, 200),
    "REVERSE_MS":       ("reverse duration in recovery (ms)",       300,  10000),
    "RECOVERY_TURN_MS": ("turn duration in recovery (ms)",          500,  20000),
}

# =============================================================================
# SECTION 2 — PIN MAPPING & SERVO CONSTANTS
# =============================================================================

PIN_RF = 10
PIN_RR = 9
PIN_LF = 21
PIN_LR = 22
PIN_US = 7

SERVO_FREQ   = 50
MIN_DUTY     = 1638
MAX_DUTY     = 8192
MID_ANGLE    = 90
SERVO_OFFSETS = [0, 0, 15, 0, 0]  # [RF, RR, LF, LR, US]

# =============================================================================
# SECTION 3 — GAIT TABLES (4-phase wave + Differential Arc Steering)
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
    _set_servo(_pwm_rf, MID_ANGLE, 0)
    _set_servo(_pwm_rr, MID_ANGLE, 1)
    _set_servo(_pwm_lf, MID_ANGLE, 2)
    _set_servo(_pwm_lr, MID_ANGLE, 3)


def _actual_angle(raw, idx):
    a = raw + SERVO_OFFSETS[idx]
    return max(0, min(180, a))


def init_hardware():
    global _pwm_rf, _pwm_rr, _pwm_lf, _pwm_lr, _pwm_us

    def _pwm(pin, name):
        if pin is None:
            return None
        p = machine.PWM(machine.Pin(pin))
        p.freq(SERVO_FREQ)
        return p

    _pwm_rf = _pwm(PIN_RF, "RF")
    _pwm_rr = _pwm(PIN_RR, "RR")
    _pwm_lf = _pwm(PIN_LF, "LF")
    _pwm_lr = _pwm(PIN_LR, "LR")
    _pwm_us = _pwm(PIN_US, "US")
    if _pwm_us:
        _set_servo(_pwm_us, 90, 4)
    stop_legs()


# =============================================================================
# SECTION 5 — GAIT RUNNER
# =============================================================================

def _step_debug(table, idx):
    s = table[idx]
    print("RF:{}  RR:{}  LF:{}  LR:{}".format(
        _actual_angle(s[0], 0),
        _actual_angle(s[1], 1),
        _actual_angle(s[2], 2),
        _actual_angle(s[3], 3),
    ))


def _run_gait_loop(table, interval_ms, duration_ms, label):
    """Core non-blocking gait loop for a single table."""
    idx = 0
    last = utime.ticks_ms()
    t0 = utime.ticks_ms()
    step = 0

    while utime.ticks_diff(utime.ticks_ms(), t0) < duration_ms:
        now = utime.ticks_ms()
        if utime.ticks_diff(now, last) >= interval_ms:
            last = now
            _apply_step(table[idx])
            print("  [{:<12s}] step={:<3d}  ".format(label, step + 1), end="")
            _step_debug(table, idx)
            idx = (idx + 1) % len(table)
            step += 1
        utime.sleep_ms(5)

    stop_legs()


def run_forward_test(step_interval=None):
    """Run forward gait for TEST_DURATION ms — per-side phase speed."""
    if step_interval is None:
        step_interval = STEP_FAST

    build_gait_tables()
    step_l = int(step_interval / LEFT_PHASE_SPEED)
    step_r = int(step_interval / RIGHT_PHASE_SPEED)
    idx_l = 0
    idx_r = 0
    last_l = utime.ticks_ms()
    last_r = utime.ticks_ms()
    t0 = utime.ticks_ms()
    step = 0

    while utime.ticks_diff(utime.ticks_ms(), t0) < TEST_DURATION:
        now = utime.ticks_ms()
        if utime.ticks_diff(now, last_l) >= step_l:
            last_l = now
            s = FORWARD_STEPS[idx_l]
            _set_servo(_pwm_lf, s[2], 2)
            _set_servo(_pwm_lr, s[3], 3)
            idx_l = (idx_l + 1) % len(FORWARD_STEPS)
        if utime.ticks_diff(now, last_r) >= step_r:
            last_r = now
            s = FORWARD_STEPS[idx_r]
            _set_servo(_pwm_rf, s[0], 0)
            _set_servo(_pwm_rr, s[1], 1)
            idx_r = (idx_r + 1) % len(FORWARD_STEPS)
        step += 1
        if step % 20 == 0:
            print("  [FORWARD] L_speed={:.2f} L_idx={}  R_speed={:.2f} R_idx={}".format(
                LEFT_PHASE_SPEED, idx_l, RIGHT_PHASE_SPEED, idx_r))
        utime.sleep_ms(5)

    stop_legs()


def run_veer_test(direction):
    """direction: 'LEFT' or 'RIGHT' — single-side motion, 1.3x freq & 1.2x stride."""
    build_gait_tables()
    table = VEER_L_STEPS if direction == "LEFT" else VEER_R_STEPS
    label = "VEER_" + direction

    stop_legs()
    step_interval = int(STEP_FAST / VEER_FREQ_FACTOR)
    _run_gait_loop(table, step_interval, VEER_DURATION, label)


def run_turn_test(direction):
    """direction: 'LEFT' or 'RIGHT' — single-side motion, 1.5x freq & stride."""
    build_gait_tables()
    table = TURN_L_STEPS if direction == "LEFT" else TURN_R_STEPS
    label = "TURN_" + direction

    stop_legs()
    print("  [Hold {}ms for stability...]".format(TURN_HOLD))
    utime.sleep_ms(TURN_HOLD)

    step_interval = int(STEP_FAST / TURN_FREQ_FACTOR)
    _run_gait_loop(table, step_interval, TURN_DURATION, label)


def run_recovery_test():
    """Reverse escape → random single-side turn → stop."""
    print("  [Phase 1] Reverse escape...")
    reverse_interval = int(STEP_FAST / REVERSE_FREQ_FACTOR)
    _run_gait_loop(REVERSE_STEPS, reverse_interval, REVERSE_MS, "REVERSE")

    build_gait_tables()
    direction = "LEFT" if (utime.ticks_us() & 1) else "RIGHT"
    table = TURN_L_STEPS if direction == "LEFT" else TURN_R_STEPS
    label = "RECOVERY_" + direction
    step_interval = int(STEP_FAST / TURN_FREQ_FACTOR)
    print("  [Phase 2] Single-side turn (random: {}, interval={}ms)...".format(direction, step_interval))
    _run_gait_loop(table, step_interval, RECOVERY_TURN_MS, label)
    print("  [Phase 3] Stopped (observe position)")


# =============================================================================
# SECTION 6 — INTERACTIVE MENU
# =============================================================================

MENU = """
+--------------------------------------------------+
|        MOTION CALIBRATION TOOL                    |
|        (Differential Arc Steering)                |
+--------------------------------------------------+
|  1  FORWARD        (straight-line stability)      |
|  2  VEER LEFT      (leftward arc, moderate diff)  |
|  3  VEER RIGHT     (rightward arc, moderate diff) |
|  4  TURN LEFT      (leftward arc, extreme diff)   |
|  5  TURN RIGHT     (rightward arc, extreme diff)  |
|  6  RECOVERY       (reverse + turn + stop)        |
|                                                  |
|  P  Print current parameters                     |
|  E  Edit a parameter                             |
|  Q  Quit & show final parameters                 |
+--------------------------------------------------+"""


PARAM_ORDER = [
    "ARC", "STEP_FAST", "STEP_SLOW", "TEST_DURATION",
    "VEER_FREQ_FACTOR", "VEER_STRIDE_FACTOR",
    "TURN_FREQ_FACTOR", "TURN_STRIDE_FACTOR",
    "REVERSE_FREQ_FACTOR", "REVERSE_STRIDE_FACTOR",
    "VEER_DURATION", "TURN_DURATION", "TURN_HOLD",
    "REVERSE_MS", "RECOVERY_TURN_MS",
]


def print_params():
    print()
    print("  CURRENT PARAMETERS:")
    print("  -------------------")
    for name in PARAM_ORDER:
        val = _get_param(name)
        desc, lo, hi = PARAM_INFO[name]
        if isinstance(val, float):
            print("  {:<22s} = {:<8.2f}  # {}  [range: {}..{}]".format(name, val, desc, lo, hi))
        else:
            print("  {:<22s} = {:<8}  # {}  [range: {}..{}]".format(name, val, desc, lo, hi))
    print()


def _get_param(name):
    return globals()[name]


def _set_param(name, val):
    globals()[name] = val


def edit_param():
    print_params()
    print("  Valid names: " + ", ".join(PARAM_INFO.keys()))
    print()
    print("  Type a parameter name to change it.")
    print("  Type 'done' (or just press Enter) when finished.")
    while True:
        try:
            name = input("  param > ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            return

        if name == "DONE" or name == "":
            build_gait_tables()
            print("  Parameter editing done. Gait tables rebuilt.")
            break

        if name not in PARAM_INFO:
            print("  Unknown '{}'. Valid names: {}".format(
                name, ", ".join(PARAM_INFO.keys())))
            continue

        desc, lo, hi = PARAM_INFO[name]
        current = _get_param(name)
        print("  {} = {}  # {}  [range: {}..{}]".format(name, current, desc, lo, hi))
        try:
            raw = input("  new value > ").strip()
            if raw == "":
                continue
            if isinstance(current, float):
                val = float(raw)
            else:
                val = int(raw)
            if val < lo or val > hi:
                print("  WARNING: {}={} is outside typical range [{}..{}]".format(name, val, lo, hi))
                confirm = input("  Set anyway? (y=yes / n=cancel): ").strip().lower()
                if confirm != "y":
                    continue
            _set_param(name, val)
            build_gait_tables()
            print("  -> {} = {}  (gait tables rebuilt)".format(name, val))
        except (ValueError, EOFError):
            print("  Invalid input, try again.")


# =============================================================================
# SECTION 7 — MAIN
# =============================================================================

def main():
    init_hardware()
    utime.sleep_ms(300)

    print()
    print("=" * 50)
    print("  MOTION CALIBRATION TOOL")
    print("  Differential Arc Steering — matches main.py")
    print("=" * 50)

    while True:
        print(MENU)
        try:
            choice = input("  Your choice > ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n  Interrupted.")
            break

        if choice == "Q":
            break

        elif choice == "P":
            print_params()
            continue

        elif choice == "E":
            edit_param()
            continue

        if choice not in ("1", "2", "3", "4", "5", "6"):
            print("  Invalid. Type 1-6 to run a test, P/E/Q for other actions.")
            utime.sleep_ms(500)
            continue

        test_map = {
            "1": ("FORWARD",    lambda: run_forward_test()),
            "2": ("VEER_LEFT",  lambda: run_veer_test("LEFT")),
            "3": ("VEER_RIGHT", lambda: run_veer_test("RIGHT")),
            "4": ("TURN_LEFT",  lambda: run_turn_test("LEFT")),
            "5": ("TURN_RIGHT", lambda: run_turn_test("RIGHT")),
            "6": ("RECOVERY",   run_recovery_test),
        }

        name, func = test_map[choice]

        while True:
            print()
            print("=" * 50)
            print("  Running: {} TEST".format(name))
            print("=" * 50)
            utime.sleep_ms(500)

            func()

            print()
            print("  --- {} TEST COMPLETE ---".format(name))
            print()

            try:
                print("  ----------------------------------------")
                print("  y = ACCEPT this result, back to menu")
                print("  n = TUNE parameters, then RE-RUN test")
                print("  q = QUIT and show final parameters")
                resp = input("  Your choice (y/n/q): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if resp == "y":
                print("  [OK] {} calibration accepted.".format(name))
                break
            elif resp == "q":
                print()
                return
            else:
                print()
                print("  ----------------------------------------")
                print("  TUNE parameters below, then re-run test.")
                print("  (Type 'done' or press Enter when ready.)")
                edit_param()

    # --- Final output ---
    print()
    print("=" * 50)
    print("  FINAL CALIBRATED PARAMETERS")
    print("=" * 50)
    print_params()
    print("  Copy these values into main.py Section 2.")
    print("=" * 50)


main()
