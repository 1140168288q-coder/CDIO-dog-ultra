# AFSM 设计说明文档（中文版）

## 1. Coursework 要求分析

本项目需要为一只小型机械狗实现一个 AFSM（Augmented Finite State Machine，增强有限状态机）控制器。硬件平台包括：

- Raspberry Pi Pico / Pico 2
- MicroPython
- ultrasonic sensor（超声波传感器，用于避障）
- TCS3200 colour sensor（颜色传感器，用于检测红色目标）
- LDR（光敏电阻，用于检测高亮光源）
- LED（发光二极管，用于目标检测后的闪烁提示）

根据 coursework requirement，机器人必须完成以下任务：

1. 在除 `charging` 之外的所有活动状态中进行 obstacle avoidance（避障）
2. 在 `explore` 状态中持续探索 2 分钟
3. 如果 2 分钟内没有检测到红色目标，则从 `explore` 转入 `low_charge`
4. 在 `low_charge` 状态中继续探索
5. 在 `low_charge` 状态下，如果检测到高亮光源，则停止并进入 `charging`
6. 在 `charging` 状态下，如果光源持续存在 1 分钟，则回到 `explore`
7. 如果充电过程中光源中断，则从 `charging` 回到 `low_charge`
8. 如果在 `explore` 或 `low_charge` 中检测到红色目标，则进入 `target_detected`
9. 在 `target_detected` 状态中，机器人必须停止，并让 LED 闪烁

对于作业要求 1，最重要的不是“状态越多越高级”，而是：

- 状态数量合理
- transition（状态跳转）条件简单
- timer（计时器）逻辑清楚
- priority（优先级）一眼能看懂
- 状态图容易画，老师容易理解

因此，本项目最适合采用 4 个主状态的 AFSM 设计，而不是继续增加额外状态。

## 2. 系统整体行为说明

### 启动阶段

机器人上电后，会先执行以下流程：

- 所有腿部舵机回到中立位置
- 超声波扫描舵机回到中间角度
- 稍微等待一下，让舵机稳定
- 初始化 AFSM 计时器
- 进入 `explore` 状态

### Explore（探索）阶段

在 `explore` 状态中，机器人会：

- 使用简单四步态向前移动
- 让超声波舵机按固定角度扫描
- 根据超声波距离进行 obstacle avoidance（避障）
- 使用颜色传感器检测红色目标
- 持续累计 explore timer（探索计时器）

如果在探索时检测到红色目标，则立即进入 `target_detected`。  
如果探索满 2 分钟仍未检测到红色目标，则进入 `low_charge`。

### Low Charge（低电量）阶段

在 `low_charge` 状态中，机器人仍然继续探索，但会额外监测 LDR 光照强度。

这一阶段的行为是：

- 继续执行与 `explore` 类似的前进和避障
- 继续检测红色目标
- 继续检测高亮光源

如果先检测到红色目标，则进入 `target_detected`。  
如果检测到高亮光源，则停止并进入 `charging`。

注意：

- 机器人不会主动去“找充电器”
- 只有当它已经走到高亮光源下方时，才会进入 `charging`

### Charging（充电）阶段

在 `charging` 状态中，机器人停止移动，只做两件事：

- 检查高亮光源是否还存在
- 计算 charging timer（充电计时器）是否达到 1 分钟

如果光源持续存在并达到 1 分钟，则回到 `explore`。  
如果光源在 1 分钟之前中断，则回到 `low_charge`。

在这个状态中：

- 不执行步态
- 不执行避障
- 不进行探索

### Target Detected（目标检测到）阶段

在 `target_detected` 状态中，机器人执行任务完成提示：

- 立即停止
- LED 周期性闪烁
- 保持在该状态，不再退出

这是一个终止状态（final state），用于表示 mission complete（任务完成）。

## 3. 状态列表

| 状态 | 作用 | 进入条件 | 退出条件 | 计时器 | 依赖传感器 | 运动行为 |
|---|---|---|---|---|---|---|
| `explore` | 正常探索环境 | 启动完成，或 charging 结束后返回 | 红色目标检测到；探索满 2 分钟 | `explore timer` | ultrasonic、colour sensor | 默认前进，有障碍就转向 |
| `low_charge` | 低电量下继续探索 | `explore` 满 2 分钟 | 红色目标检测到；高亮光源检测到 | 无独立主计时器 | ultrasonic、colour sensor、LDR | 默认前进，有障碍就转向 |
| `charging` | 模拟充电 | `low_charge` 下检测到高亮光源 | 充电满 1 分钟；或光源中断 | `charging timer` | LDR | 停止 |
| `target_detected` | 任务完成提示 | 在 `explore` 或 `low_charge` 中检测到红色目标 | 无退出条件 | `blink timer` | 颜色传感器触发进入，LED 输出提示 | 停止并闪烁 LED |

## 4. Transition（状态跳转）说明

### 优先级设计

为了让 AFSM 图容易理解，推荐把逻辑优先级明确写成：

1. obstacle avoidance（避障）
2. target detected（目标检测）
3. charging logic（充电逻辑）
4. normal movement（默认前进）

这样设计的原因是：

- obstacle avoidance 最高，因为 robot safety first（机器人安全第一）
- target detected 第二，因为检测到目标后必须尽快停止
- charging logic 第三，因为它只在特定状态下才会触发
- normal movement 最后，因为它只是默认行为

### 具体状态跳转

- `Start -> Explore`
  - 条件：初始化完成

- `Explore -> Target Detected`
  - 条件：`red_detected == True`

- `Explore -> Low Charge`
  - 条件：`explore_elapsed >= 2 minutes`

- `Low Charge -> Target Detected`
  - 条件：`red_detected == True`

- `Low Charge -> Charging`
  - 条件：`ldr_value > threshold`

- `Charging -> Explore`
  - 条件：`charge_elapsed >= 1 minute` 且光照仍存在

- `Charging -> Low Charge`
  - 条件：`ldr_value <= threshold`

补充说明：

- obstacle avoidance 不需要单独画成一个主状态
- 更适合把它写在 `explore` 和 `low_charge` 状态框内部，作为“最高优先级行为”
- 这样状态图更简洁，也更容易讲解

## 5. Timer（计时器）逻辑

### Explore Timer

- 进入 `explore` 时开始计时
- 每次重新进入 `explore` 时重新清零
- 达到 2 分钟后转到 `low_charge`

### Charging Timer

- 进入 `charging` 时开始计时
- 若高亮持续 1 分钟，则转回 `explore`
- 若中途光照消失，则提前回到 `low_charge`

### Scan Timing（扫描节奏）

- 超声波扫描不是一直高速左右摆动
- 而是按定时节奏依次移动到指定角度并读取距离
- 扫描与步态交替进行，可以降低峰值功耗

### Blink Timing（闪烁节奏）

- 在 `target_detected` 状态中，LED 按固定时间间隔翻转亮灭
- 不使用阻塞延时，而是用时间差判断

### 如何避免 blocking（阻塞）

本项目应该优先使用：

- `utime.ticks_ms()`
- `utime.ticks_diff()`
- 定时调度的小动作

应尽量避免：

- 长时间 `sleep()`
- 阻塞式 `while` 循环
- 为等待某个传感器结果而卡住主循环

需要说明的是：

- 像 `time_pulse_us()` 这样的硬件测量函数本身会有短时间等待
- 这是 MicroPython 硬件读取里的正常情况
- 但可以通过控制 sample 数量和 timeout（超时）来降低影响

## 6. Movement Logic（运动逻辑）说明

### Gait Sequence（步态序列）

机器人使用简单的四步态：

- 每次只执行一个步态步骤
- 按固定 `STEP_TIME` 节奏切换
- 每个步骤更新 4 个腿部舵机的角度

这种方式的优点是：

- 简单
- 稳定
- 容易调试
- 适合课堂展示

### Turning Logic（转向逻辑）

如果前方有障碍物：

- 比较左侧和右侧距离
- 哪边更空，就往哪边转

转向不是复杂的导航算法，只是简单的 servo turning sequence（舵机转向动作序列）。

### Obstacle Turning Behaviour（避障转向行为）

当超声波判断前方距离小于阈值时：

- 正常 walk（前进）会被 turn（转向）覆盖
- 但主状态仍然保持在 `explore` 或 `low_charge`

这点很重要，因为：

- 避障是行为优先级，不一定要单独成为主状态

### Scanning Behaviour（扫描行为）

超声波扫描舵机使用固定角度数组：

- `[5, 90, 175, 90]`

含义可以理解为：

- 左侧
- 正前方
- 右侧
- 回中

这些读数用于后续的 obstacle avoidance 决策。

## 7. 适合 draw.io 直接画图的辅助信息

### 状态节点

- `Start / Initialisation`
- `Explore`
- `Low Charge`
- `Charging`
- `Target Detected`

### 箭头与条件标签

- `Start -> Explore`
  - `initialise servos / reset timers`

- `Explore -> Low Charge`
  - `explore timer >= 2 min`

- `Explore -> Target Detected`
  - `red detected`

- `Low Charge -> Charging`
  - `LDR > threshold`

- `Low Charge -> Target Detected`
  - `red detected`

- `Charging -> Explore`
  - `charge timer >= 1 min and light present`

- `Charging -> Low Charge`
  - `light interrupted`

### 每个状态框里可写的简短说明

- `Explore`
  - walk forward
  - ultrasonic scan
  - obstacle avoidance
  - red detection
  - 2-minute timer

- `Low Charge`
  - continue exploring
  - obstacle avoidance
  - red detection
  - LDR monitoring

- `Charging`
  - stop
  - no obstacle avoidance
  - LDR monitoring
  - 1-minute timer

- `Target Detected`
  - stop
  - LED blink
  - mission complete

## 8. 当前项目实现建议

目前项目的文件结构已经比较适合 coursework：

- `main.py`：主循环
- `afsm.py`：状态和计时器
- `states.py`：状态行为处理
- `movement.py`：步态和转向
- `sensors.py`：传感器读取
- `config.py`：可调参数集中管理
- `pins.py`：GPIO 统一管理

这个结构已经足够清晰，不建议继续拆分更多文件，也不建议做复杂 framework 化。

## 9. Manual Tuning Reminder（人工调试提醒）

以下内容都需要实际硬件调试：

- servo neutral angle（舵机中位角）
- servo offset（舵机偏移补偿）
- gait timing（步态节奏）
- gait amplitude（步幅）
- turn amplitude（转向幅度）
- ultrasonic threshold（超声波避障阈值）
- ultrasonic scan interval（超声波扫描节奏）
- LDR threshold（光照阈值）
- colour threshold（颜色判定阈值）
- colour sampling interval（颜色检测间隔）
- LED blink interval（LED 闪烁节奏）

这些参数已经集中在 `config.py` 中，后续调试时建议优先修改这里。
