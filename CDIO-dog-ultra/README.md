# CDIO-dog-ultra

基于 **Raspberry Pi Pico 2（RP2350）与 MicroPython** 的四足机械狗课程项目，通过增强有限状态机（AFSM）完成自主探索、超声波避障、红色目标检测和光照模拟充电。

课程：**4FTC2135-0105-2025 · Robot Design and Build Project B**。

本仓库整合 `CDIO-dog-pro`、`CDIO-dog-pro-max` 与最终提交文件。根目录的 [`main.py`](main.py) 是最终运行入口；历史代码和设计文档分别保留，便于查看项目演进。

## 功能

- **自主探索**：4 相位舵机步态，正常探索与低电量模式使用不同步进周期。
- **分级避障**：扫描左、前、右三个方向，根据距离选择轻微调整、转向或脱困。
- **红色目标检测**：TCS3200 比较 RGB 通道脉宽，连续两次确认后结束任务。
- **模拟低电量与充电**：探索 2 分钟后降速；遇强光停止，持续照射 1 分钟后重新探索。
- **任务与故障状态**：发现目标后停止并闪灯；脱困计数达到上限后进入 `FAULT_STOP`。
- **运动标定**：独立交互工具测试前进、微调、转向和脱困，方便调整步幅与时间参数。

## 文件导航

| 路径 | 内容 |
|---|---|
| [`main.py`](main.py) | 最终自主控制程序，部署到 Pico 2 后上电运行 |
| [`motion_test.py`](motion_test.py) | 交互式运动标定工具，单独运行 |
| [`reference/final-variants/main_debug.py`](reference/final-variants/main_debug.py) | 原 `main (1).py`，保留运行日志、左右侧速度参数与故障闪灯的另一版本 |
| [`reference/classroom_code.py`](reference/classroom_code.py) | 最终文件夹内的课堂整合参考代码 |
| [`docs/asfm/`](docs/asfm/) | 原 AFSM 图纸、PNG、Word 说明、课程要求与示例 |
| [`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md) | 最终实现细节及代码、标定工具和早期文档的差异 |
| [`archive/CDIO-dog-pro/`](archive/CDIO-dog-pro/) | pro 仓库最后一次提交的完整文件快照 |
| [`archive/CDIO-dog-pro-max/`](archive/CDIO-dog-pro-max/) | pro-max 仓库最后一次提交的完整文件快照 |
| [`docs/MIGRATION.md`](docs/MIGRATION.md) | 合并来源及历史提交说明 |
| [`docs/migration-manifest.json`](docs/migration-manifest.json) | 原文件与新位置的对应关系及校验值 |

AFSM 原始设计图（各版本的具体差异见实现说明）：

![AFSM 原始设计图](docs/asfm/ASFM%20pro%20max%20ultra.drawio.png)

## 硬件与引脚

控制器使用 4 个腿部舵机、1 个超声波扫描舵机、HC-SR04、TCS3200、LDR 和状态 LED。以下为最终 `main.py` 中的 **GPIO 编号（GP）**，不是开发板物理脚序号。

| 部件 | 常量 | GPIO |
|---|---|---:|
| 右前腿 RF | `PIN_RF` | GP10 |
| 右后腿 RR | `PIN_RR` | GP9 |
| 左前腿 LF | `PIN_LF` | GP21 |
| 左后腿 LR | `PIN_LR` | GP22 |
| 超声波扫描舵机 | `PIN_US_SERVO` | GP7 |
| LDR 模拟输入 | `PIN_LDR` | GP28 / ADC2 |
| HC-SR04 Trig | `PIN_TRIG` | GP18 |
| HC-SR04 Echo | `PIN_ECHO` | GP13 |
| TCS3200 S2 | `PIN_TCS_S2` | GP16 |
| TCS3200 S3 | `PIN_TCS_S3` | GP17 |
| TCS3200 OUT | `PIN_TCS_OUT` | GP14 |
| TCS3200 照明 LED | `PIN_TCS_LED` | GP15 |
| 外接状态 LED | `PIN_STATUS_LED` | GP1 |

舵机 PWM 为 **50 Hz**，脉宽映射使用 `duty_u16(1638–8192)`。最终舵机微调为 `[0, 5, 12, 5, 0]`，顺序为 RF、RR、LF、LR、US。供电、共地与传感器信号电平需符合实际模块和 Pico 2 的规格。

## 快速运行

1. 给 Pico 2 安装适配 RP2350 的 MicroPython 固件，在 Thonny 中选择对应解释器和串口。
2. 按上表核对接线，检查 `main.py` 顶部的引脚、舵机微调和传感器阈值。
3. 将根目录 **`main.py`** 保存到设备根目录，重启后开始自主任务。运行只依赖 MicroPython 内置的 `machine` 与 `utime`，不需要安装 pip 包。
4. 需要调整步态时，先在 Thonny 中停止自主程序，再单独运行 **`motion_test.py`**，按菜单测试与调参。
5. 标定结果需手动同步到 `main.py`，再重新保存到设备。标定工具的默认微调和部分时长与主程序不同，详见[实现说明](docs/IMPLEMENTATION.md)。

`main.py` 和标定工具都在文件末尾直接调用 `main()`，打开运行会操作硬件；普通电脑上的 CPython 不提供 `machine` 与 `utime`。

## AFSM 任务逻辑

| 状态 | 行为 | 转换条件 |
|---|---|---|
| `START` | 初始化硬件与扫描舵机 | 初始化完成 → `EXPLORE` |
| `EXPLORE` | 正常前进、扫描、检测红色 | 120 秒 → `LOW_CHARGE`；红色确认 → `TARGET_DETECTED` |
| `LOW_CHARGE` | 降速前进、扫描、检测红色与光照 | LDR ≥ 60000 → `CHARGING`；红色确认 → `TARGET_DETECTED` |
| `CHARGING` | 腿部归中、状态 LED 常亮、监测光照 | 持续光照 60 秒 → `EXPLORE`；光照不足 → `LOW_CHARGE`；红色确认 → `TARGET_DETECTED` |
| `TARGET_DETECTED` | 腿部归中，状态 LED 与颜色传感器 LED 每 500 ms 切换一次 | 终止状态，需人工重启 |
| `FAULT_STOP` | 腿部归中，LED 熄灭 | 终止状态，需人工检查并重启 |

每轮循环首先检查红色目标，`TARGET_DETECTED` 与 `FAULT_STOP` 除外，因此最终代码在模拟充电时也会检测红色。

### 扫描与避障

扫描角度按 **LD / FD / RD = 150° / 85° / 20°** 配置，执行顺序为 **FD → LD → FD → RD**。每个位置分为舵机移动、等待后测距两个阶段，阶段间隔在探索时为 150 ms，低电量时为 300 ms。

避障只在 `EXPLORE`、`LOW_CHARGE` 的 `FORWARD` 行为中，根据新前向读数判定；转向、微调和脱困执行期间暂停扫描，动作完成后恢复前进与扫描。

| 判定顺序 | 条件 | 动作 |
|---:|---|---|
| 1 | 三方向都 < 10 cm，或任一方向 < 5 cm，或 `turn_count >= 3` | `RECOVERY` |
| 2 | 前方 < 10 cm | `TURN_LEFT` / `TURN_RIGHT` |
| 3 | 10 cm ≤ 前方 < 15 cm | `VEER_LEFT` / `VEER_RIGHT` |
| 4 | 前方 ≥ 15 cm，且未命中更高优先级条件 | 保持 `FORWARD`，清零 `turn_count` |

方向优先选择左右距离中空间较大的一侧；相等时由 `ticks_us()` 最低位选择方向。每次 Turn 完成后增加 `turn_count`；Veer 不增加该计数。进入 Recovery 时先增加 `recovery_count`，第三次请求直接进入 `FAULT_STOP`，前两次执行后退与转向。

## 默认参数

| 项目 | 最终 `main.py` 默认值 |
|---|---|
| 前进步进周期 | Explore 150 ms；Low Charge 300 ms |
| 步态幅度 `ARC` | 15° |
| 微调持续时间 | 6000 ms |
| 转向持续时间 | 12000 ms，前置保持 80 ms |
| 脱困动作 | 后退 6000 ms + 转向 12000 ms |
| LDR 阈值 | 60000，按环境标定 |
| 红色判定 | `r < g - 300` 且 `r < b - 300`，连续两次确认 |
| 颜色读取间隔 | 100 ms |
| LDR 读取间隔 | 200 ms |
| 单次超声波超时 | 12000 µs；超时返回 100 cm |
| 单通道颜色读取超时 | 5000 µs |

## 实现范围与验证

低电量由探索计时模拟，充电由光照与计时模拟。转向角度取决于机身、地面和标定参数，程序采用定时步态控制。扫描、步态与状态切换使用 `ticks_ms()` / `ticks_diff()` 协作调度；传感器脉宽读取带超时，主循环还包含 5 ms 短延时。

本次整合保持最终控制代码及历史文件内容不变，完成文件哈希核对、Python 语法检查和 Git 历史完整性检查。硬件行为需在实际 Pico 2 与机械狗上验证。

## 项目演进

| 版本 | 内容与定位 |
|---|---|
| pro | `main / afsm / states / movement / sensors / pins / config` 模块化实现与组件参考 |
| pro-max | 单文件 AFSM 控制程序、综合调试工具与课堂参考 |
| ultra | 以本地最终 `main.py` 为入口，加入运动标定、另一控制版本、完整 AFSM 材料与两个历史项目 |

原始 6 次提交保留于 `history/CDIO-dog-pro` 与 `history/CDIO-dog-pro-max` 分支，并作为整合提交的祖先。历史快照用于参考，部署以根目录最终代码为准。
