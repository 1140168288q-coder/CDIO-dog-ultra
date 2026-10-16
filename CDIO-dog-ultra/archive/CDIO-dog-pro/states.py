import config
import afsm
import sensors
import movement
import utime
import pins

# ============================================================
# states.py — 各状态的行为处理函数
# 每个 handle_xxx(now) 函数对应一个 AFSM 状态的具体行为
# ============================================================
# 行为优先级（从高到低）：
#   避障（obstacle avoidance） > 目标检测（target detected） > 充电逻辑 > 正常前进
# ============================================================

_led_last_ms = 0
_led_state   = False

def blink_led(now):
    global _led_last_ms, _led_state
    if utime.ticks_diff(now, _led_last_ms) >= config.LED_BLINK_INTERVAL:
        _led_state = not _led_state
        pins.STATUS_LED.value(_led_state)
        _led_last_ms = now

def led_off():
    global _led_state
    _led_state = False
    pins.STATUS_LED.value(0)

def get_avoidance_turn_direction():
    """根据扫描结果决定转向方向，不直接执行动作。"""
    front_dist = sensors.distances[1]   # 90° 正前方
    left_dist  = sensors.distances[0]   # 5°  左侧
    right_dist = sensors.distances[2]   # 175° 右侧

    if front_dist < config.OBSTACLE_DIST:
        if left_dist >= right_dist:
            return 'left'
        return 'right'

    return None

# ------------------------------------------------------------
# 探索状态（Explore State）
# 目的：正常探索环境，执行前进步态、超声波扫描与红色目标检测
# 入口：上电初始化完成，或充电满 1 分钟后返回
# 出口：
#   - 检测到红色目标 → 进入 target_detected（目标检测状态）
#   - 探索持续满 2 分钟 → 进入 low_charge（低电量状态）
# 计时：使用 explore timer（探索计时器）
# 传感器：超声波（避障） + 颜色传感器（红色目标检测）
# 运动：障碍物存在时优先转向避障，否则正常前进
# ------------------------------------------------------------
def handle_explore(now):
    sensors.US_Scan(now)
    turn_direction = get_avoidance_turn_direction()

    # 1. 避障为最高优先级：有障碍物就转向，但不阻止本回合继续检查状态切换条件
    if turn_direction is not None:
        movement.turn(turn_direction, now)

    # 2. 检查是否检测到红色目标 → 进入目标检测状态
    if sensors.is_red_detected():
        movement.stop()
        afsm.set_state(afsm.TARGET_DETECTED)
        return

    # 3. 检查探索是否超时（满 2 分钟）→ 进入低电量状态
    if afsm.explore_elapsed(now) >= config.EXPLORE_DURATION:
        movement.stop()
        afsm.set_state(afsm.LOW_CHARGE)
        return

    # 4. 默认行为：没有障碍物时才正常前进
    if turn_direction is None:
        movement.walk(now)

# ------------------------------------------------------------
# 低电量状态（Low Charge State）
# 目的：低电量下继续探索（检测红色目标），同时被动等待充电光源出现
# 入口：探索状态满 2 分钟后自动进入
# 出口：
#   - 检测到红色目标 → 进入 target_detected（目标检测状态）
#   - 检测到高亮光源 → 进入 charging（充电状态）
# 计时：无独立计时器（依靠充电光源触发切换）
# 传感器：超声波（避障） + 颜色传感器（红色目标） + LDR（光敏，检测充电光）
# 运动：障碍物存在时优先转向避障，否则正常前进
# ------------------------------------------------------------
def handle_low_charge(now):
    sensors.US_Scan(now)
    turn_direction = get_avoidance_turn_direction()

    # 1. 避障为最高优先级：有障碍物就转向
    if turn_direction is not None:
        movement.turn(turn_direction, now)

    # 2. 检查是否检测到红色目标 → 进入目标检测状态
    if sensors.is_red_detected():
        movement.stop()
        afsm.set_state(afsm.TARGET_DETECTED)
        return

    # 3. 检查是否检测到高亮光源 → 进入充电状态
    ldr_val = sensors.read_ldr()
    if sensors.is_bright_light(ldr_val):
        movement.stop()
        afsm.set_state(afsm.CHARGING)
        return

    # 4. 默认行为：没有障碍物时才正常前进
    if turn_direction is None:
        movement.walk(now)

# ------------------------------------------------------------
# 充电状态（Charging State）
# 目的：模拟充电过程，机器人完全停止不动
# 入口：低电量状态下检测到高亮光源
# 出口：
#   - 光照中断（光源移开）→ 返回 low_charge（低电量状态）
#   - 持续照满 1 分钟 → 返回 explore（探索状态，计时器重置）
# 计时：使用 charging timer（充电计时器）
# 传感器：LDR（光敏传感器，持续监测光照是否还在）
# 运动：完全停止（不走路、不扫描）
# ------------------------------------------------------------
def handle_charging(now):
    ldr_val = sensors.read_ldr()

    # 光照中断（光源亮度不足）→ 回到低电量状态
    if not sensors.is_bright_light(ldr_val):
        afsm.set_state(afsm.LOW_CHARGE)
        return

    # 充电完成（光照持续满 1 分钟）→ 返回探索状态
    if afsm.charge_elapsed(now) >= config.CHARGE_DURATION:
        led_off()
        afsm.set_state(afsm.EXPLORE)
        return

    # 保持停止不动（不走路、不扫描超声波、不做其他动作）
    # movement.stop() 在进入充电状态时已经调用，此处无需重复

# ------------------------------------------------------------
# 目标检测状态（Target Detected State）
# 目的：任务完成提示，机器人停止并闪烁 LED
# 入口：探索状态或低电量状态中检测到红色目标
# 出口：无（终止状态，任务完成）
# 计时：使用 LED blink timer（闪烁计时器）
# 传感器：无持续依赖（此时不再读取传感器）
# 运动：完全停止 + LED 不停闪烁
# ------------------------------------------------------------
def handle_target_detected(now):
    movement.stop()
    blink_led(now)
