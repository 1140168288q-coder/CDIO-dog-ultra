import utime

# ============================================================
# afsm.py — AFSM（增强有限状态机）核心
# 负责管理状态切换、计时器，不包含任何传感器或舵机操作
# ============================================================
# 四个状态的名称常量（state constants）
EXPLORE         = 'explore'          # 探索状态
LOW_CHARGE      = 'low_charge'       # 低电量状态
CHARGING        = 'charging'         # 充电状态
TARGET_DETECTED = 'target_detected'  # 目标检测状态（终止状态）

# 当前主状态，初始为 explore
_state = EXPLORE

# 各阶段计时器的起始时间戳（毫秒 ms），用于 non-blocking 计时
_explore_start_ms = 0   # 探索阶段开始时间
_charge_start_ms  = 0   # 充电阶段开始时间
_state_enter_ms   = 0   # 进入当前状态的时间（调试用）

# ------------------------------------------------------------
# 状态查询：返回当前状态名
# ------------------------------------------------------------
def get_state():
    return _state

# ------------------------------------------------------------
# 状态切换（统一入口，所有状态变更都走这里，方便调试时打印日志）
# ------------------------------------------------------------
def set_state(new_state):
    global _state, _explore_start_ms, _charge_start_ms, _state_enter_ms
    if new_state == _state:
        return  # 相同状态不重复切换
    print(f"[AFSM] {_state} → {new_state}")  # 打印状态切换日志，方便课堂演示时观察
    _state = new_state

    # 进入新状态时，顺手重置对应的计时器
    now = utime.ticks_ms()
    _state_enter_ms = now
    if new_state == EXPLORE:
        _explore_start_ms = now  # 重新开始探索计时（从充电完成返回时使用）
    elif new_state == CHARGING:
        _charge_start_ms  = now  # 重新开始充电计时

# ------------------------------------------------------------
# 计时器查询（non-blocking 方式，用 ticks_diff 计算已过时间）
# ------------------------------------------------------------
def explore_elapsed(now):
    """返回当前 explore 阶段已经持续了多少毫秒"""
    return utime.ticks_diff(now, _explore_start_ms)

def charge_elapsed(now):
    """返回当前 charging 阶段已经持续了多少毫秒"""
    return utime.ticks_diff(now, _charge_start_ms)

def state_elapsed(now):
    """返回当前状态已持续的毫秒数，主要用于调试观察"""
    return utime.ticks_diff(now, _state_enter_ms)

# ------------------------------------------------------------
# 初始化（上电时调用一次，将状态机设为探索状态）
# ------------------------------------------------------------
def init():
    global _state, _explore_start_ms, _charge_start_ms, _state_enter_ms
    now = utime.ticks_ms()
    _state = EXPLORE
    _explore_start_ms = now
    _charge_start_ms  = now
    _state_enter_ms   = now
    print("[AFSM] init -> explore")
