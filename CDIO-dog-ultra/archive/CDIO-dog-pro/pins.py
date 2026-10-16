from machine import Pin, PWM, ADC

# ============================================================
# pins.py — 所有 GPIO 统一定义
# ============================================================
# 当前预填值来源：classroom_code.py + color_sensor_test.py
#
# !! 使用前请核对每个 GPIO 是否与你的实际接线一致 !!
# !! 如不一致，修改下方对应的数字即可，其余代码无需改动 !!
# ============================================================

# ------------------------------------------------------------
# 舵机 GPIO（来源：classroom_code.py）
# !! [需核对] 按实际接线修改
# ------------------------------------------------------------
_RR_PIN       = 0   # Right Rear  舵机   !! [需核对]
_LR_PIN       = 1   # Left Rear   舵机   !! [需核对]
_RF_PIN       = 2   # Right Front 舵机   !! [需核对]
_LF_PIN       = 3   # Left Front  舵机   !! [需核对]
_US_SERVO_PIN = 4   # 超声波扫描舵机      !! [需核对]

# ------------------------------------------------------------
# 超声波传感器 GPIO（来源：classroom_code.py）
# !! [需核对] 按实际接线修改
# ------------------------------------------------------------
_US_TRIG_PIN = 14   # Trig  !! [需核对]
_US_ECHO_PIN = 15   # Echo  !! [需核对]

# ------------------------------------------------------------
# TCS3200 颜色传感器 GPIO（来源：color_sensor_test.py）
# S0 → 3V3，S1 → GND（硬件固定，不在此定义）
# !! [需核对] 按实际接线修改
# ------------------------------------------------------------
_COLOR_S2_PIN  = 10  # S2  !! [需核对]
_COLOR_S3_PIN  = 11  # S3  !! [需核对]
_COLOR_OUT_PIN = 12  # OUT !! [需核对]
_COLOR_LED_PIN = 13  # LED !! [需核对]

# ------------------------------------------------------------
# LDR ADC GPIO（来源：classroom_code.py）
# 注意：只有 GP26 / GP27 / GP28 支持 ADC
# !! [需核对] 按实际接线修改
# ------------------------------------------------------------
_LDR_ADC_PIN = 26   # LDR ADC0  !! [需核对]

# ------------------------------------------------------------
# 状态指示 LED GPIO
# !! [需核对] 按实际接线修改（若使用板载 LED 则填 25）
# ------------------------------------------------------------
_STATUS_LED_PIN = 25  # 状态 LED  !! [需核对]（板载 LED = 25）

# ============================================================
# 以下代码自动初始化硬件对象，无需修改
# ============================================================

# 舵机对象（50Hz 标准频率，所有舵机统一频率）
RR_Servo = PWM(Pin(_RR_PIN))        # 右后腿舵机（Right Rear）
LR_Servo = PWM(Pin(_LR_PIN))        # 左后腿舵机（Left Rear）
RF_Servo = PWM(Pin(_RF_PIN))        # 右前腿舵机（Right Forward）
LF_Servo = PWM(Pin(_LF_PIN))        # 左前腿舵机（Left Forward）
US_Servo = PWM(Pin(_US_SERVO_PIN))  # 超声波扫描舵机（Ultrasonic Sensor Servo）

for _s in (RR_Servo, LR_Servo, RF_Servo, LF_Servo, US_Servo):
    _s.freq(50)

# 超声波传感器引脚
US_TRIG = Pin(_US_TRIG_PIN, Pin.OUT)
US_ECHO = Pin(_US_ECHO_PIN, Pin.IN)

# 颜色传感器引脚
COLOR_S2  = Pin(_COLOR_S2_PIN,  Pin.OUT)
COLOR_S3  = Pin(_COLOR_S3_PIN,  Pin.OUT)
COLOR_OUT = Pin(_COLOR_OUT_PIN, Pin.IN)
COLOR_LED = Pin(_COLOR_LED_PIN, Pin.OUT)

# LDR
LDR = ADC(Pin(_LDR_ADC_PIN))

# 状态 LED
STATUS_LED = Pin(_STATUS_LED_PIN, Pin.OUT)
