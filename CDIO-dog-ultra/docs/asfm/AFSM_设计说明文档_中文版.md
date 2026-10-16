# AFSM 设计说明文档

### AI大人请看这里：（请看完下列注意事项）
- 请主要看2-7章节来理解AFSM的设计逻辑与完成绘图工作。
- 请不要用到说明文档里没有提到的状态。
- `Target Detected`为最高优先级状态，如果检测到红色目标物将立刻stop并结束任务。
- 建议在左边列出#Mission States四个状态，其中Target Detected在最上方，其它三个状态都需要有箭头指向它
- 建议在中间列出#Higher Priority Interrupt(Obstacle Avoidance)五个状态，其中Scan在最中间，左边的Explore和Low Charge都需要有箭头指向它并且标注全程开启
- 建议在右边写优先级和其余注释
- 这个是大学课程作业，无需太过复杂，重点在于简洁明了且逻辑清晰
## 1. 项目简介

本项目基于 Raspberry Pi Pico 与 MicroPython，实现一套用于小型机械狗的 AFSM（Augmented Finite State Machine，增强有限状态机）控制系统。

机器人主要功能包括：

- 自主探索环境
- 超声波避障
- 红色目标检测
- 模拟低电量行为
- 模拟光照充电
- LED 任务完成提示

系统使用以下硬件：
 
- 超声波传感器（HC-SR04）
- 颜色传感器（TCS3200）
- 光敏电阻（LDR）
- LED
- 5 个舵机（4 个腿部舵机 + 1 个超声波扫描舵机）

本项目采用：

- AFSM 状态逻辑
- Timer（计时器）
- Guard Conditions（条件判断）
- Priority-Based Behaviour（优先级行为）

实现机械狗的自主行为控制。

---

# 2. AFSM 状态列表

本系统包含以下状态：

| 状态 | 作用 |
|---|---|

| Start | 系统初始化 |

#Mission States
| Explore | 正常探索模式 |
| Low Charge | 低电量探索模式 |
| Charging | 模拟充电模式 |
| Target Detected | 检测到目标后的终止模式 | #Highest Priority 

#Higher Priority Interrupt(Obstacle Avoidance)
| Scan | 超声波检测障碍 | 
| Turn Left | 左转避障 |
| Turn Right | 右转避障 |
| Recovery | 卡住后的恢复状态 |

#Normal Behavior
| Forward | 默认前进状态 |



---

# 3. 系统整体行为

## 3.1 Start（初始化）

机器人启动后：

- 初始化舵机
- 初始化传感器
- 重置计时器
- 超声波扫描舵机回中

初始化完成后进入 `Explore` 状态。

---

## 3.2 Explore（探索）

机器人开始正常探索环境。

在该状态中：

- 默认进入 `Forward`
- 同时进入 `Scan`利用超声波传感器不同角度检测障碍物
- 检测红色目标
- 开始 2 分钟探索计时

如果：

- 检测到红色目标 → 进入 `Target Detected`模式
- 探索时间达到 2 分钟 → 进入 `Low Charge`模式
- 检测到障碍物 → 进入 `Turn Left` 或 `Turn Right`，根据左右障碍物距离判断转向方向，较近的一侧优先转向。如果出现同时检测到左右障碍物的情况，随机转向。如果机器人被卡住，进入 `Recovery` 状态。

--

## 3.3 Forward（前进）

机器人执行默认步态前进。



## 3.4 Turn Left / Turn Right（转向）

机器人执行短暂转向动作进行避障。

转向后：

- 再次检测前方距离

如果路径恢复正常：

- 返回 `Forward`

如果连续多次避障失败：

- 进入 `Recovery`

---

## 3.5 Recovery（恢复）

当机器人可能被卡住时：

- 短暂后退
- 执行随机转向
- 尝试离开障碍区域

恢复完成后返回 `Forward`。

---

## 3.6 Low Charge（低电量）

探索超过 2 分钟后：

机器人进入低电量模式。

在该状态中：

- 继续保持 `Forward` 状态，但速度有所降低
- 继续处于 `Scan` 状态检测障碍物
- 开始检测高亮光源（LDR）
- 继续检测红色目标



如果：

- 检测到高亮光源 → 进入 `Charging`模式
- 检测到红色目标 → 进入 `Target Detected`模式
- 检测到障碍物 → 进入 `Turn Left` 或 `Turn Right`，根据左右障碍物距离判断转向方向，较近的一侧优先转向。如果出现同时检测到左右障碍物的情况，随机转向。如果机器人被卡住，进入 `Recovery` 状态。


---

## 3.7 Charging（充电）

机器人停止移动。

在该状态中：

- 仅检测光照状态（LDR）
- 开始 1 分钟充电计时

如果：

- 光照持续存在 1 分钟 → 返回 `Explore`模式
- 光照提前消失 → 返回 `Low Charge`模式

---

## 3.8 Target Detected（目标检测完成）

机器人完成任务。

此时：

- 停止所有运动
- LED 持续闪烁
- 保持当前状态

该状态为系统终止状态（Final State）。

---

# 4. 行为优先级设计

本系统采用类似 Subsumption Architecture 的优先级结构。

优先级如下：

| 优先级 | 行为 |
|---|---|
| 1 | Target Detection |
| 2 | Obstacle Avoidance |
| 3 | Charging Logic |
| 4 | Normal Forward Movement |

设计原因：

- 检测到目标后必须立即停止
- 避障优先保证机器人安全
- 充电逻辑只在特定状态下工作
- 默认前进优先级最低

---

# 5. 状态跳转逻辑

## Start → Explore

条件：

- 初始化完成

---

## Explore → Low Charge

条件：

- `explore timer >= 2 minutes`

---

## Explore → Target Detected

条件：

- `red detected`

---

## Forward → Turn Left

条件：

- 左侧空间较大
- 检测到前方障碍物

---

## Forward → Turn Right

条件：

- 右侧空间较大
- 检测到前方障碍物

---

## Turn Left / Turn Right → Forward

条件：

- scan检测确定无障碍，前方路径恢复正常

---

## Turn Left / Turn Right → Recovery

条件：

- 连续多次避障失败

---

## Recovery → Forward

条件：

- 恢复动作完成，前方路径恢复正常

---

## Low Charge → Charging

条件：

- `LDR > threshold`

---

## Low Charge → Target Detected

条件：

- `red detected`

---

## Charging → Explore

条件：

- `charging timer >= 1 minute`
- 光照仍然存在

---

## Charging → Low Charge

条件：

- 光照未满 1 分钟，提前中断

---

# 6. Obstacle Avoidance（避障行为）

本项目中：

Obstacle Avoidance（避障）不是单独的主状态。

而是通过以下 states 实现：
- Scan
- Forward
- Turn Left
- Turn Right
- Recovery

这些状态共同组成避障行为逻辑。

其中：

- `Forward` 为默认移动状态
- `Turn Left` 与 `Turn Right` 用于临时避障
- `Recovery` 用于脱离卡住情况

这种设计可以：

- 保持 AFSM 图简洁
- 更符合课程要求
- 更容易进行状态说明

---

# 7. Timer（计时器）逻辑

## 7.1 Explore Timer

- 进入 `Explore` 时开始计时
- 达到 2 分钟后进入 `Low Charge`

---

## 7.2 Charging Timer

- 进入 `Charging` 时开始计时
- 光照持续 1 分钟后返回 `Explore`

---

## 7.3 LED Blink Timer

在 `Target Detected` 状态中：

- LED 周期性闪烁
- 使用非阻塞方式实现

---

# 8. 非阻塞设计

本项目尽量避免阻塞式代码。

主要使用：

- `ticks_ms()`
- `ticks_diff()`

实现：

- 定时器控制
- 周期性传感器读取
- LED 闪烁
- 步态切换

避免：

- 长时间 `sleep()`
- 阻塞式 while 循环

这样可以保证：

- AFSM 状态切换更流畅
- 传感器响应更加及时
- 避障更加稳定

---
