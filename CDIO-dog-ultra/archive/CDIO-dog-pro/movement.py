import utime
import pins
import config

# ============================================================
# movement.py — 舵机控制与步态（走路、转向、停止）
# 所有舵机操作逻辑严格参考老师的 classroom_code.py
# ============================================================

_SERVO_OFFSETS = {
    pins.RF_Servo: config.RF_SERVO_OFFSET,
    pins.RR_Servo: config.RR_SERVO_OFFSET,
    pins.LF_Servo: config.LF_SERVO_OFFSET,
    pins.LR_Servo: config.LR_SERVO_OFFSET,
    pins.US_Servo: config.US_SERVO_OFFSET,
}

# ------------------------------------------------------------
# 舵机角度设定（核心函数，所有舵机统一使用）
# 逻辑来源：classroom_code.py 中的 set_position()
# 与课堂代码完全兼容，duty（占空比）计算公式勿修改
# ------------------------------------------------------------
def set_position(servo, angle):
    # TODO: 需人工硬件校准
    # 如果某条腿的舵机安装存在机械偏差，请在 config.py 中调整对应 offset，不要改这里的公式。
    angle += _SERVO_OFFSETS.get(servo, 0)
    if angle < 0:
        angle = 0
    elif angle > 180:
        angle = 180
    min_duty = 1638  # 0°  = 0.5 ms pulse
    max_duty = 8192  # 180° = 2.5 ms pulse
    duty = int(min_duty + (angle / 180) * (max_duty - min_duty))
    servo.duty_u16(duty)

# ------------------------------------------------------------
# 初始化：所有舵机归中
# 逻辑来源：classroom_code.py initialize()
# ------------------------------------------------------------
def initialize():
    set_position(pins.RR_Servo, config.SERVO_NEUTRAL_ANGLE)
    set_position(pins.LR_Servo, config.SERVO_NEUTRAL_ANGLE)
    set_position(pins.RF_Servo, config.SERVO_NEUTRAL_ANGLE)
    set_position(pins.LF_Servo, config.SERVO_NEUTRAL_ANGLE)
    set_position(pins.US_Servo, config.SERVO_NEUTRAL_ANGLE)

# ------------------------------------------------------------
# 停止行走：所有腿部舵机回到中位（机器狗站直不动）
# ------------------------------------------------------------
def stop():
    set_position(pins.RF_Servo, config.SERVO_NEUTRAL_ANGLE)
    set_position(pins.RR_Servo, config.SERVO_NEUTRAL_ANGLE)
    set_position(pins.LF_Servo, config.SERVO_NEUTRAL_ANGLE)
    set_position(pins.LR_Servo, config.SERVO_NEUTRAL_ANGLE)

# ------------------------------------------------------------
# 前进步态（non-blocking 非阻塞方式，用 timer 控制节奏）
# 逻辑来源：classroom_code.py 中的 walk()
# 舵机执行顺序：RF → RR → LF → LR（与 config.WALK_STEPS 一致）
# !! [可微调] 步态快慢和幅度在 config.py 中修改 STEP_TIME / ARC
# !! [需人工调试] 如果行走时向左偏或右偏，在 config.WALK_STEPS 中
#               微调某一条腿的角度（±2~5°），直到走直为止
# !! [需人工调试] 如果某个舵机方向装反了，将该腿步态值改为 (180 - 原值)
# ------------------------------------------------------------
_current_step = 0
_last_step_ms = 0

def walk(now):
    global _current_step, _last_step_ms
    if utime.ticks_diff(now, _last_step_ms) > config.STEP_TIME:
        _last_step_ms = now
        s = config.WALK_STEPS[_current_step]
        # 顺序：RF, RR, LF, LR（对应 WALK_STEPS 中 s[0]~s[3]）
        set_position(pins.RF_Servo, s[0])
        set_position(pins.RR_Servo, s[1])
        set_position(pins.LF_Servo, s[2])
        set_position(pins.LR_Servo, s[3])
        _current_step = (_current_step + 1) % len(config.WALK_STEPS)

# ------------------------------------------------------------
# 原地转向（non-blocking 非阻塞方式，timer 控制节奏）
# 转向逻辑：左转时右侧腿向前推、左侧腿向后拉，右转则相反
# !! [需人工调试] 如果实际转向方向反了，去 states.py 里交换 'left' 和 'right'
# !! [可微调] TURN_ARC 控制转向幅度，增大则转弯更猛，减小则转弯更缓
# ------------------------------------------------------------
_TURN_ARC = config.TURN_ARC

_t1 = int(config.SERVO_NEUTRAL_ANGLE - _TURN_ARC)
_t2 = int(config.SERVO_NEUTRAL_ANGLE + _TURN_ARC)

# 左转步态：右侧腿向前推（角度大于 90°），左侧腿向后拉（角度小于 90°）
_LEFT_STEPS = [
    (_t2, _t1, _t1, _t2),  # RF前, RR后, LF后, LR前
    (config.SERVO_NEUTRAL_ANGLE, config.SERVO_NEUTRAL_ANGLE,
     config.SERVO_NEUTRAL_ANGLE, config.SERVO_NEUTRAL_ANGLE),
    (_t1, _t2, _t2, _t1),
    (config.SERVO_NEUTRAL_ANGLE, config.SERVO_NEUTRAL_ANGLE,
     config.SERVO_NEUTRAL_ANGLE, config.SERVO_NEUTRAL_ANGLE),
]

# 右转步态：左侧腿向前推，右侧腿向后拉
_RIGHT_STEPS = [
    (_t1, _t2, _t2, _t1),
    (config.SERVO_NEUTRAL_ANGLE, config.SERVO_NEUTRAL_ANGLE,
     config.SERVO_NEUTRAL_ANGLE, config.SERVO_NEUTRAL_ANGLE),
    (_t2, _t1, _t1, _t2),
    (config.SERVO_NEUTRAL_ANGLE, config.SERVO_NEUTRAL_ANGLE,
     config.SERVO_NEUTRAL_ANGLE, config.SERVO_NEUTRAL_ANGLE),
]

_turn_step    = 0
_last_turn_ms = 0
_current_dir  = None

def turn(direction, now):
    """direction: 'left' 或 'right'"""
    global _turn_step, _last_turn_ms, _current_dir
    if _current_dir != direction:
        _turn_step   = 0
        _current_dir = direction

    if utime.ticks_diff(now, _last_turn_ms) <= config.STEP_TIME:
        return

    _last_turn_ms = now
    steps = _LEFT_STEPS if direction == 'left' else _RIGHT_STEPS
    s = steps[_turn_step]
    set_position(pins.RF_Servo, s[0])
    set_position(pins.RR_Servo, s[1])
    set_position(pins.LF_Servo, s[2])
    set_position(pins.LR_Servo, s[3])
    _turn_step = (_turn_step + 1) % len(steps)
