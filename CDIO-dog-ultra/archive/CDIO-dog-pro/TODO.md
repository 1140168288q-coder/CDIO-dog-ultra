# TODO.md — 项目开发计划

> 本计划基于 CLAUDE.md 约束严格制定。AI 后续开发时可自主推进以下步骤，
> 可自主搜索资料、调用可用 skill、上网查询 MicroPython 文档，
> 但必须严格遵循 CLAUDE.md 和 README.md 的所有规则。

---

## Phase 1: 基础模块搭建

### 1.1 创建 pins.py
- [x] 定义所有 GPIO 占位框架（!! 用户需填写实际编号 !!）
- [x] 自动初始化硬件对象，填写后即可使用
- [x] 确保不在其他文件中硬编码 GPIO

### 1.2 创建 config.py
- [x] 定义时间常量（EXPLORE_DURATION, CHARGE_DURATION）
- [x] 定义传感器 threshold（[需标定] 标注）
- [x] 定义步态参数（ARC, STEP_TIME, WALK_STEPS）
- [x] 定义扫描参数（SCAN_ANGLES, OBSTACLE_DIST）

### 1.3 创建 sensors.py
- [x] 实现 `read_ldr()` / `read_ldr_avg()`
- [x] 实现 `get_distance(samples=5)`
- [x] 实现 `get_averaged_colour()` + `is_red_detected()`
- [x] 实现 `is_bright_light()`
- [x] 实现 `US_Scan(now)`（non-blocking）

### 1.4 创建 movement.py
- [x] 实现 `set_position(servo, angle)`
- [x] 实现 `initialize()` / `stop()`
- [x] 实现 `walk(now)`（non-blocking）
- [x] 实现 `turn(direction, now)`（左转/右转）

---

## Phase 2: AFSM 状态机实现

### 2.1 创建 afsm.py
- [x] 定义状态常量
- [x] 实现 `set_state()` / `get_state()`
- [x] 实现计时器 `explore_elapsed()` / `charge_elapsed()`

### 2.2 创建 states.py
- [x] 实现 `handle_explore(now)`
- [x] 实现 `handle_low_charge(now)`
- [x] 实现 `handle_charging(now)`
- [x] 实现 `handle_target_detected(now)`

### 2.3 实现 obstacle avoidance
- [x] 实现 `handle_obstacle_avoidance(now)`（在 states.py 中）
- [x] 避障在 EXPLORE / LOW_CHARGE 优先执行
- [x] CHARGING 状态不执行避障

---

## Phase 3: 主循环集成

### 3.1 创建 main.py
- [x] 导入所有模块，初始化，主循环完整

### 3.2 创建 utils.py
- [x] LED 非阻塞闪烁（`blink_led` / `led_off` / `led_on`）

---

## Phase 4: 调试与优化

### 4.1 单模块测试
- [ ] 测试 sensors.py 各函数
- [ ] 测试 movement.py 步态稳定性
- [ ] 测试状态切换逻辑

### 4.2 集成测试
- [ ] 完整 AFSM 流程测试
- [ ] explore → low_charge 转换（2 分钟计时）
- [ ] low_charge → charging 转换（检测高亮光源）
- [ ] charging → explore 转换（1 分钟计时）
- [ ] charging → low_charge 转换（光照中断）
- [ ] 任意状态 → target_detected（检测红色）
- [ ] 避障全程有效测试

### 4.3 演示准备
- [ ] 调整参数确保演示稳定
- [ ] 录制 3 分钟演示视频（展示所有状态）
- [ ] 确认代码 optimised，无冗余

---

## Phase 5: 提交

### 5.1 代码整理
- [ ] 确认所有文件结构符合 CLAUDE.md 规范
- [ ] 确认代码注释简洁
- [ ] 确认无硬编码 GPIO
- [ ] 确认 non-blocking 设计

### 5.2 提交
- [ ] Canvas 提交 Python 代码文件
- [ ] 上传 3 分钟演示视频 或 实验室现场演示

---

## 注意事项

* 每个 Phase 完成后可进行回顾，但不要过度重构
* 遇到硬件问题优先参考 reference/ 中的测试代码
* 步态参数（arc, step_time）需要实际硬件调试
* LDR threshold 需要实际环境标定
* 颜色传感器阈值需要对着实际红色目标标定
* 始终保持代码"像学生做的"而不是"像 AI 生成的"
