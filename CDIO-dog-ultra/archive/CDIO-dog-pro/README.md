# AFSM Robotic Dog Project

> **AI 严格执行：本文件为项目说明文档，AI 不允许私自更改或违背其内容。**

基于 Raspberry Pi Pico 与 MicroPython 的 CDIO 机械狗课程项目。

课程编号：4FTC2135-0105-2025 - Robot Design and Build Project B

---

# 项目简介

本项目是一个基于：

* Raspberry Pi Pico / Pico 2
* MicroPython
* AFSM（Augmented Finite State Machine）

实现的小型机械狗课程项目。

机器人通过：

* 超声波避障（最高优先级）
* 红色目标检测（TCS3200 颜色传感器）
* 光照检测（LDR + 10kΩ 分压）
* AFSM 状态机控制
* 舵机步态控制（四步态 gait）

实现自主探索与行为切换。

本项目重点：

* AFSM 状态机设计
* non-blocking embedded programming
* 模块化代码结构
* 稳定课堂演示
* 简洁可靠的 gait movement

---

# 项目功能

当前项目目标包括：

| 功能 | 说明 |
| --- | --- |
| obstacle avoidance | 超声波多角度扫描避障，最高优先级 |
| exploration | 自主探索 2 分钟，可选 random walk 或直行 |
| low charge state | 2 分钟探索后进入低电量，继续探索同时检测光源 |
| charging state | 高亮光照下停止 1 分钟模拟充电 |
| target detected state | 检测到红色目标后停止并闪烁 LED |
| servo-based gait | 四步态 step array 行走控制 |

---

# 硬件组成

## 主控

* Raspberry Pi Pico / Pico 2
* MicroPython 运行环境
* Thonny IDE 开发

---

## 传感器

### 超声波传感器（HC-SR04）

用途：

* obstacle avoidance

说明：

* 使用升级版模块，Echo 输出无需分压
* 5 次采样取平均值
* 配合扫描舵机（US_Servo）多角度检测
* 扫描角度：5°, 90°, 175°, 90°

---

### TCS3200 颜色传感器

用途：

* 红色目标检测

说明：

* S0 → 3V3, S1 → GND（频率缩放固定）
* 其余引脚（S2, S3, OUT, LED）在 pins.py 中定义
* `time_pulse_us` 测量脉冲宽度
* 10 次采样取平均
* 检测时 LED 开启，完成后关闭

---

### LDR 光敏传感器

用途：

* 模拟充电检测

硬件结构：

* LDR 接 3V3(OUT)
* 10kΩ 电阻接 GND
* ADC pin 读取中间电压（具体 pin 在 pins.py 定义）
* 可选 0.1µF 滤波电容

---

### LED

用途：

* target detected 状态闪烁

硬件：

* 使用 200Ω-330Ω 限流电阻
* 注意极性（anode 接 GPIO）

---

## 舵机系统

机器人使用：

* 4 个腿部舵机（50Hz PWM）
* 1 个超声波扫描舵机

运动方式：

* servo-based robotic dog
* discrete gait movement（四步态 step array）
* timer-based non-blocking 控制

本项目不使用：

* 轮式驱动 / differential drive
* inverse kinematics
* 高级 gait 数学模型

---

# 项目结构

```text
project/
│
├── main.py          # 主循环与 AFSM 逻辑
├── pins.py          # 所有 GPIO 定义
├── config.py        # 配置常量
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

# 状态机设计

本项目基于 AFSM（Augmented Finite State Machine）。

主要状态包括：

| State | Description | 退出条件 |
| --- | --- | --- |
| explore | 正常探索环境 | 2 分钟超时 → low_charge；检测红色 → target_detected |
| low_charge | 低电量探索 | 高亮光源 → charging；检测红色 → target_detected |
| charging | 高亮光照下停止充电 | 1 分钟完成 → explore；光照中断 → low_charge |
| target_detected | 停止并闪烁 LED | 终止状态 |

全局行为（所有模式）：obstacle avoidance 始终激活。

---

# AFSM 逻辑

## Explore State

机器人正常移动并探索（random walk / 直行）。

持续约 2 分钟后：

* transition → low_charge

除非：

* 提前检测到红色目标 → target_detected

---

## Low Charge State

机器人继续探索。

同时检测：

* 红色目标 → target_detected
* 高亮光源 → charging（停止移动）

不主动寻找光源，只在遇到时响应。

---

## Charging State

机器人在高亮环境中保持停止。

持续约 1 分钟后：

* 返回 explore state

如果光照提前消失：

* 返回 low_charge state

---

## Target Detected State

当检测到红色目标：

* 机器人立即停止
* LED 开始闪烁
* Mission complete

---

# 编程设计原则

项目重点：

* non-blocking programming（`ticks_ms` + `ticks_diff`）
* modular design（每个模块职责单一）
* clear AFSM logic（状态转换清晰可画图）
* classroom demonstration stability

代码设计优先：

* readability
* simplicity
* maintainability
* explainability

避免：

* overengineering
* enterprise architecture
* complex robotics frameworks

---

# GPIO 配置

所有 GPIO 统一在 `pins.py` 中配置，由学生根据实际接线自行定义。

需要定义的引脚类别：

* 4 个腿部舵机
* 1 个超声波扫描舵机
* 超声波 Trig / Echo
* 颜色传感器 S2 / S3 / OUT / LED
* LDR ADC
* 状态 LED

禁止在业务逻辑中硬编码 GPIO。

---

# reference 文件夹说明

`reference/` 文件夹中保存：

* `classroom_code.py` — 老师课堂综合代码（不可修改）
* 各传感器/舵机独立测试文件
* 课件笔记与作业要求汇总

这些代码用于：

* 硬件调试
* GPIO 测试
* 传感器验证
* 步态验证

正式项目代码在此基础上整理为模块化 AFSM 结构。

---

# 开发说明

推荐开发顺序：

1. 完成单个硬件测试（逐一验证传感器）
2. 完成 gait movement（稳定行走）
3. 完成 obstacle avoidance（避障逻辑）
4. 完成 AFSM 状态切换
5. 完成整体 integration 与演示调试

---

# 注意事项

由于机器人尺寸较小（约 12cm × 8cm × 6cm）：

* 不建议大幅度舵机动作（arc ≤ 26°）
* 不建议激进 gait movement
* 不建议所有舵机同时快速运动
* 步态与扫描交替执行避免功耗过高

项目重点应保持：

* 稳定
* 可演示
* 易调试
* 结构清晰

---

# 项目目标

本项目目标不是构建复杂工业机器人。

而是完成一个：

**"结构清晰、逻辑合理、适合课堂展示的 AFSM 机械狗课程项目"**

提交要求：

* Canvas 提交 Python 代码文件
* 3 分钟演示视频 或 实验室现场演示
