import utime
import afsm
import config
import movement
import states

# ============================================================
# main.py — 主循环（程序入口）
# ============================================================
# 上电后依次执行：
#   1. 所有舵机回到中位（让机器狗站直）
#   2. 初始化 AFSM（增强有限状态机），进入 explore（探索）状态
#   3. 进入主循环，根据当前状态分发到对应的处理函数
# ============================================================

try:
    movement.initialize()
    utime.sleep_ms(config.INIT_SETTLE_MS)   # 上电后短暂等待，让舵机有时间稳定到中位
    afsm.init()
    print("[main] Robot started. State:", afsm.get_state())

    while True:
        now = utime.ticks_ms()              # 获取当前时间戳（毫秒），所有函数使用 non-blocking 方式
        state = afsm.get_state()

        if state == afsm.EXPLORE:
            states.handle_explore(now)       # 探索状态：边前进边扫描，检测障碍物和红色目标

        elif state == afsm.LOW_CHARGE:
            states.handle_low_charge(now)    # 低电量状态：继续探索，同时等待充电光源出现

        elif state == afsm.CHARGING:
            states.handle_charging(now)      # 充电状态：完全停止，等待光照持续 1 分钟

        elif state == afsm.TARGET_DETECTED:
            states.handle_target_detected(now)  # 目标检测状态：停止 + LED 闪烁，任务完成

except KeyboardInterrupt:
    movement.stop()
    states.led_off()
    print("[main] Stopped.")
