# CLAUDE.md

> **AI 严格执行：本文件为项目核心约束文档，AI 不允许私自更改或违背任何条目。**

---

# 项目概述

本项目是一个大学 CDIO 机器人课程项目。

课程编号：4FTC2135-0105-2025 - Robot Design and Build Project B

项目使用：

* Raspberry Pi Pico / Pico 2
* MicroPython（通过 Thonny IDE 开发部署）
* AFSM（Augmented Finite State Machine，增强有限状态机）

机器人主体为：

基于舵机动作的小型机械狗。

机器人尺寸约为：

12cm × 8cm × 6cm

项目核心目标：

* obstacle avoidance（避障）— 最高优先级
* exploration（探索）
* low charge（低电量状态）
* charging（模拟充电状态）
* target detected（目标检测）
* 基于 AFSM 的状态控制
* 稳定的课堂演示效果

本项目是：

"结构清晰、适合课堂展示的大学课程项目"

不是：

* 企业级机器人平台
* 工业机器人系统
* AI Agent Framework
* 高级机器人研究项目

代码设计优先级：

1. 稳定性
2. 可解释性
3. 易调试
4. 课堂演示效果
5. 清晰 AFSM 逻辑

避免：

* 过度设计
* 复杂抽象层
* 企业级架构
* 高级机器人学
* AI 味太重

---

# 硬件说明

## 主控

* Raspberry Pi Pico / Pico 2
* 使用 MicroPython
* 通过 Thonny IDE 开发
* 代码保存为 main.py 时上电自动运行

---

## 传感器

### 超声波传感器（HC-SR04）

用途：

* obstacle avoidance（避障）

注意：

* 使用升级版模块
* Echo 输出无需分压
* GPIO 由学生自行接线，在 pins.py 中定义
* 使用 `machine.time_pulse_us(echo, 1, 12000)` 测量脉冲
* 推荐 5 次采样取平均值滤波
* 超时设 12000us（约 2 米范围）
* 距离公式：`distance = (avg_pulse_time * 0.0343) / 2`

超声波扫描舵机：

* 使用 US_Servo 进行多角度扫描
* 扫描角度数组：`[5, 90, 175, 90]`
* 扫描与步态交替执行，避免同时操作（降低峰值功耗）

---

### TCS3200 颜色传感器

用途：

* 红色目标检测

硬件连接（参考 colour sensor details.docx 与课件）：

* S0 → 3V3（OUT）
* S1 → GND
* 其余 GPIO（S2, S3, OUT, LED）由学生自行接线，在 pins.py 中定义

工作原理：

* TCS3200 是 light-to-frequency converter
* 通过 S2/S3 选择滤波器通道
* 使用 `time_pulse_us(signal, 1)` 测量脉冲宽度
* 短脉冲 = 高频率 = 颜色分量强
* 长脉冲 = 低频率 = 颜色分量弱

红色检测逻辑（参考 color_sensor_reader.py）：

* `r < (g - 50) and r < (b - 50)` 表示红色
* 检测前必须 `led_pin.on()`，检测后 `led_pin.off()`
* 推荐 10 次采样取平均

Claude 不允许写死颜色传感器 GPIO。

---

### LDR 光敏传感器

用途：

* simulated charging detection（模拟充电检测）

硬件结构（参考 LDR Details.docx）：

* LDR 一端接 3V3(OUT)（Pin 36，不是 VBUS）
* 另一端接 ADC pin（具体 GPIO 在 pins.py 定义）
* 10kΩ 电阻从 ADC pin 接 GND
* 可选：0.1µF 电容并联 10kΩ 电阻（滤波）

读取方式：

* `ldr = ADC(Pin(X))` — X 为实际接线 ADC pin
* `ldr.read_u16()` 返回 0-65535
* 百分比：`percent = round((value / 65535) * 100, 1)`

注意：

* 不允许硬编码固定 threshold
* 推荐使用 calibration
* 推荐使用平均值滤波
* 参考 threshold 范围：60000-61500（需实际标定）

---

### LED

用途：

* target detected 状态闪烁

硬件：

* 使用 200Ω-330Ω 限流电阻
* 注意 LED 极性：anode（长脚）接 GPIO，cathode（短脚）接 GND

---

# 舵机系统

机器人使用：

* 4 个腿部舵机
* 1 个超声波扫描舵机

当前硬件连接：

* RR_Servo（Right Rear）
* LR_Servo（Left Rear）
* RF_Servo（Right Forward）
* LF_Servo（Left Forward）
* US_Servo（Ultrasonic）

所有舵机 GPIO 由学生自行接线，在 pins.py 中定义。

舵机控制参数：

* PWM 频率：50Hz（标准 hobby servo）
* duty_u16 范围：1638（0°）到 8192（180°）
* 中立位：90°（duty ≈ 4915）
* `set_position` 函数使用线性插值计算 duty

```python
def set_position(servo, angle):
    min_duty = 1638  # 0° = 0.5 ms pulse
    max_duty = 8192  # 180° = 2.5 ms pulse
    duty = int(min_duty + (angle / 180) * (max_duty - min_duty))
    servo.duty_u16(duty)
```

机器人为：

* servo-based robotic dog
* 基于离散 gait 的机械狗

不是：

* 轮式机器人
* differential drive 小车

禁止实现：

* inverse kinematics
* 高级 gait 数学模型
* 高级机器人框架
* SLAM
* path planning

---

## 步态设计（参考 步态设计笔记.docx 与 classroom_code.py）

### 四步态行走（推荐）

使用 step array + timer-based 切换：

```python
arc = 18  # 或 26（classroom_code 使用 26）
mid_point = 90
one = int(mid_point - arc/2)
two = int(mid_point - arc/6)
three = int(mid_point + arc/6)
four = int(mid_point + arc/2)

steps = [
    (four, one, three, two),   # Step 1
    (three, four, four, three), # Step 2
    (two, three, one, four),   # Step 3
    (one, two, two, one)       # Step 4
]
```

* step_time：200-300ms 之间（根据稳定性调整）
* 使用 `utime.ticks_ms()` + `ticks_diff()` 实现 non-blocking

### Trot Gait（备选参考）

* 对角腿同步：LF+RR 同相，RF+LR 反相
* 使用 `180 - angle` 实现对称运动
* 角度范围：60°-120°

推荐运动方式：

* simple pose sequence
* timed gait movement
* small servo angle changes

---

# 物理结构限制（非常重要）

机器人尺寸非常小。

因此：

所有运动设计必须优先考虑：

* 稳定性
* 可重复性
* 低功耗
* 课堂演示可靠性

禁止：

* 大角度剧烈动作
* 所有舵机同时剧烈运动
* 高频扫描动作
* 激进动态运动
* 步态与超声波扫描同时执行（避免峰值功耗过高）

推荐：

* 小步幅动作（arc ≤ 26°）
* 平滑动作
* 简单 gait
* 慢速稳定 movement

超声波扫描建议：

* 低频扫描
* 不要持续高速左右摆动
* 与步态交替执行

---

# Coursework 行为规则

## AFSM 要求

机器人必须实现：

* explore state
* low charge state
* charging state
* target detected state

并使用：

* transitions
* timers
* obstacle avoidance

---

## 评分标准（作业要求2）

* Controller design（25%）：检测条件和状态设计
* Optimised design（25%）：不含冗余代码
* Demonstration（25%）：演示清晰完整，展示所有状态
* Submission（25%）：代码格式正确

---

# obstacle avoidance 优先级

obstacle avoidance 永远最高优先级。

robot safety first。

在任何状态（除 charging state）都必须执行避障。

---

# Explore State

机器人正常探索。

探索行为可以是：

* random walk
* moving straight
* 其他自定义探索策略

探索时间达到 2 分钟后：

* transition → low_charge

除非：

* 提前检测到红色目标 → target_detected

探索期间持续使用颜色传感器检测红色目标。

---

# Low Charge State

机器人继续探索（同时检测红色目标）。

如果检测到高亮光源（LDR 值超过 threshold）：

* 停止移动
* 进入 charging state

如果检测到红色目标：

* 进入 target_detected state

禁止：

* 主动寻找充电器
* 导航到光源
* 路径规划
* 高级导航行为

---

# Charging State

机器人在高亮光源下保持停止。

持续 1 分钟后：

* 返回 explore state（计时器重置）

如果光照提前中断（LDR 值低于 threshold）：

* 返回 low_charge state

充电期间不执行避障（机器人已停止）。

---

# Target Detected State

检测到红色目标后：

* 必须立即停止
* LED 必须闪烁

禁止继续移动。

这是终止状态（Mission complete）。

---

# 编程规则

## non-blocking 编程

必须优先使用：

* `utime.ticks_ms()`
* `utime.ticks_diff()`
* timer-based logic

禁止：

* 长时间 `sleep()`
* blocking while loop（除非在充电等待中使用短 sleep 轮询）

sensor polling 不允许阻塞主循环。

主循环结构参考（来自 classroom_code.py）：

```python
while True:
    now = utime.ticks_ms()
    walk(now)
    US_Scan(now)
    ldr_value = read_ldr()
    # state logic here...
```

---

## 代码结构参考

所有函数（来自课堂代码）在正式项目中必须保持兼容：

* `set_position(servo, angle)` — 舵机角度设定
* `initialize()` — 所有舵机回中
* `read_ldr()` — LDR 读取
* `get_distance(samples=5)` — 超声波测距
* `US_Scan(now)` — 超声波扫描
* `walk(now)` — 步态执行
* `get_averaged_colour(samples=10)` — 颜色读取

---

# GPIO 管理规则

禁止：

* 在业务逻辑中硬编码 GPIO

所有 GPIO：

必须统一放在：

`pins.py`

参考 GPIO 分配：

所有 GPIO 由学生根据实际接线自行定义，统一写入 pins.py。

代码中不允许出现任何硬编码的 GPIO 编号。

pins.py 应包含以下引脚定义（具体编号由学生填写）：

* 4 个腿部舵机 pin
* 1 个超声波扫描舵机 pin
* 超声波 Trig / Echo pin
* 颜色传感器 S2 / S3 / OUT / LED pin
* LDR ADC pin
* 状态 LED pin

注意：以上仅为需要定义的引脚类别，实际编号以学生接线为准。

---

# 代码风格

优先：

* readable code
* short functions
* simple logic
* clear transitions

避免：

* deeply nested logic
* unnecessary abstraction
* complex OOP
* enterprise architecture

代码应该：

像"优秀大学生课程项目"。

而不是：

企业机器人系统。

---

# 推荐项目结构

```text
project/
│
├── main.py          # 主循环与 AFSM 逻辑
├── pins.py          # 所有 GPIO 定义
├── config.py        # 配置常量（threshold、timing 等）
├── sensors.py       # 传感器读取函数
├── movement.py      # 步态与舵机控制
├── states.py        # 状态处理函数
├── afsm.py          # AFSM 状态机框架
├── utils.py         # 工具函数
│
├── reference/
│   ├── classroom_code.py       # 老师课堂综合代码（保留原始）
│   ├── ultrasonic_test.py      # 超声波测试
│   ├── ldr_test.py             # LDR 测试
│   ├── color_sensor_test.py    # 颜色传感器测试
│   ├── servo_test.py           # 舵机步态测试
│   ├── course_notes.md         # 课件笔记汇总
│   └── assignment_requirements.md  # 作业要求汇总
```

---

# reference 文件夹规则

reference/ 文件夹中保存：

老师上课提供的测试代码。

Claude 必须：

* 学习 reference 中的硬件操作方式
* 保持兼容的代码风格
* 在此基础上整理 AFSM 项目结构
* 保留原始代码逻辑和专业术语

禁止：

* 完全推翻老师测试代码逻辑
* 使用与 reference 完全不同的硬件控制方式
* 修改 classroom_code.py

---

# AI 协作规则

修改代码前：

* 先分析现有结构
* 简短说明修改计划
* 避免无意义重构

生成代码时：

* transition 必须清晰
* 注释保持简洁
* 优先课堂演示稳定性
* 优先可解释性
* 必须使用与 reference 代码兼容的函数接口

Claude 必须始终思考：

* "这个逻辑是否容易画成 AFSM 图？"
* "老师是否容易理解这个状态转换？"
* "这个实现是否适合课堂演示？"
* "这个结构是否像真实学生项目？"
* "代码是否 optimised、不含冗余？"

---

# 开发哲学

整个项目应该保持：

"简单、稳定、清晰、适合演示"

而不是：

"复杂、炫技、企业化"

本项目目标是：

稳定完成 coursework 要求，
并保持良好的 AFSM 逻辑与代码结构。
