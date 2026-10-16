import machine
import utime
import pins
import config
from movement import set_position

# ============================================================
# sensors.py — 传感器读取（超声波、颜色、光敏）
# 所有传感器操作逻辑严格参考老师的 classroom_code.py
# ============================================================

# ------------------------------------------------------------
# 超声波测距（多次采样取平均，提高稳定性）
# 逻辑来源：classroom_code.py 中的 get_distance()
# !! [可微调] 采样次数 (samples) 越多越准，但延迟也越大；每次采样约 10ms
# ------------------------------------------------------------
def get_distance(samples=None):
    sample_count = samples or config.US_DISTANCE_SAMPLES
    total_pulse_time = 0
    valid_samples    = 0

    for _ in range(sample_count):
        pins.US_TRIG.value(0)
        utime.sleep_us(2)
        # Trig 脚发出 10 微秒的高电平脉冲
        pins.US_TRIG.value(1)
        utime.sleep_us(10)
        pins.US_TRIG.value(0)

        # 12000us 约等于 2 米范围的超时时间；没收到回波会返回 -2 或 -1
        pulse = machine.time_pulse_us(pins.US_ECHO, 1, config.US_ECHO_TIMEOUT_US)
        if pulse > 0:
            total_pulse_time += pulse
            valid_samples    += 1
        # 每次采样之间短暂延迟，让声波消散后再发下一次
        utime.sleep_ms(config.US_SAMPLE_GAP_MS)

    if valid_samples == 0:
        return 100  # 没有收到任何有效回波，返回 100cm 表示安全

    avg_pulse_time = total_pulse_time / valid_samples
    # 声速约 0.0343 cm/us
    # 距离 = (时间 × 声速) ÷ 2（来回双程）
    distance = (avg_pulse_time * 0.0343) / 2
    return distance

# ------------------------------------------------------------
# 超声波多角度扫描（non-blocking 非阻塞方式，与步态交替执行）
# 逻辑来源：classroom_code.py 中的 US_Scan()
# 工作方式：偶数步 → 在当前角度测量距离
#          奇数步 → 将扫描舵机转到下一个角度
# 返回 True 表示本次成功测了一次距离
# !! [可微调] 扫描角度列表在 config.SCAN_ANGLES 中修改
# ------------------------------------------------------------
distances     = [100, 100, 100, 100]  # 四个扫描角度的距离缓存，单位 cm，初始默认 100
_scan_index   = 1   # 从第二个角度(90°)开始，因为初始化时 US_Servo 已归中到 90°
_scan_counter = 0
_last_scan_ms = 0

def US_Scan(now):
    global _scan_index, _scan_counter, _last_scan_ms

    if utime.ticks_diff(now, _last_scan_ms) > config.US_SCAN_INTERVAL_MS:
        if _scan_counter % 2 == 0:
            # 偶数步：在当前位置测量距离并保存
            distances[_scan_index] = get_distance()
            _scan_index   = (_scan_index + 1) % 4
            _scan_counter += 1
            _last_scan_ms  = now
            return True  # 本次测量了新距离值
        else:
            # 奇数步：把扫描舵机转到下一个预定角度
            set_position(pins.US_Servo, config.SCAN_ANGLES[_scan_index])
            _scan_counter += 1
            _last_scan_ms  = now
            return False  # 本次未测量，舵机在转动中

    return False

# ------------------------------------------------------------
# LDR 读取（单次）
# 逻辑来源：classroom_code.py read_ldr()
# 返回 raw 16-bit 值（0~65535）
# ------------------------------------------------------------
def read_ldr(samples=None):
    sample_count = samples or config.LDR_SAMPLES
    total = 0
    for _ in range(sample_count):
        total += pins.LDR.read_u16()
    return total // sample_count

# ------------------------------------------------------------
# 是否检测到高亮光源
# !! [需人工调试] 阈值在 config.LDR_BRIGHT_THRESHOLD 修改
# 标定步骤：运行 reference/ldr_test.py，遮住/照亮传感器，
#           用手电直照值和环境值的中间数设为 threshold
# ------------------------------------------------------------
def is_bright_light(value=None):
    v = value if value is not None else read_ldr()
    return v > config.LDR_BRIGHT_THRESHOLD

# ------------------------------------------------------------
# TCS3200 颜色传感器读取（多次采样取平均，提高稳定性）
# 逻辑来源：classroom_code.py / color_sensor_test.py 中的 get_averaged_colour()
# !! [需人工调试] 如果颜色读数不稳定，可增大采样次数或加长 sleep_ms 等待时间
# ------------------------------------------------------------
def _read_colour_pulse():
    pulse = machine.time_pulse_us(pins.COLOR_OUT, 1, config.COLOR_PULSE_TIMEOUT_US)
    if pulse <= 0:
        return config.COLOR_PULSE_TIMEOUT_US
    return pulse

def get_averaged_colour(samples=None):
    n = samples or config.COLOR_SAMPLES

    # 1. 打开传感器补光 LED，等待光线稳定
    pins.COLOR_LED.on()
    utime.sleep_ms(config.COLOR_LED_SETTLE_MS)

    total_r = total_g = total_b = 0

    try:
        for _ in range(n):
            # 红色通道：S2 低电平, S3 低电平
            pins.COLOR_S2.low(); pins.COLOR_S3.low()
            total_r += _read_colour_pulse()

            # 蓝色通道：S2 低电平, S3 高电平
            pins.COLOR_S2.low(); pins.COLOR_S3.high()
            total_b += _read_colour_pulse()

            # 绿色通道：S2 高电平, S3 高电平
            pins.COLOR_S2.high(); pins.COLOR_S3.high()
            total_g += _read_colour_pulse()

            utime.sleep_ms(config.COLOR_SAMPLE_GAP_MS)

    finally:
        # 2. 无论是否出错，最终都要关闭补光 LED
        pins.COLOR_LED.off()

    return total_r // n, total_g // n, total_b // n

# ------------------------------------------------------------
# 是否检测到红色目标
# 逻辑来源：color_sensor_test.py is_red()
# 红色特征：R 脉冲短（值小），明显小于 G 和 B
# !! [需人工调试] config.COLOR_RED_MARGIN 控制灵敏度（参考值 50）
#   - 总是误报红色 → 增大 margin（如改为 80）
#   - 检测不到红色 → 减小 margin（如改为 30）
# ------------------------------------------------------------
_last_colour_check_ms = 0
_last_red_detected    = False

def is_red_detected():
    global _last_colour_check_ms, _last_red_detected
    now = utime.ticks_ms()
    if utime.ticks_diff(now, _last_colour_check_ms) < config.COLOR_CHECK_INTERVAL_MS:
        return _last_red_detected

    _last_colour_check_ms = now
    r, g, b = get_averaged_colour()
    margin = config.COLOR_RED_MARGIN
    _last_red_detected = r < (g - margin) and r < (b - margin)
    return _last_red_detected
