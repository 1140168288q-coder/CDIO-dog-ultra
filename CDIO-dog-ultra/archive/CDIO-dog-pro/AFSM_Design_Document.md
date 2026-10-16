# AFSM Design Document

## 1. Coursework Requirement Analysis

This project must implement an AFSM controller for a small servo-based robotic dog using:

- Raspberry Pi Pico / Pico 2
- MicroPython
- ultrasonic sensor
- TCS3200 colour sensor
- LDR
- LED

The coursework requires the robot to:

1. avoid obstacles in every active state except `charging`
2. explore for 2 minutes in `explore`
3. change to `low_charge` after 2 minutes if no red target is found
4. continue exploring in `low_charge`
5. stop and enter `charging` when a high light intensity is detected in `low_charge`
6. stay in `charging` for 1 minute while light remains present
7. return to `explore` after successful charging
8. return to `low_charge` if charging is interrupted
9. stop and blink LED in `target_detected`

For coursework requirement 1, the AFSM must stay simple and easy to read. The best design is to use only the required four states and keep transition conditions short and clear.

## 2. Overall System Behaviour

### Startup Behaviour

- initialise all servos to neutral position
- wait briefly for servo stabilisation
- reset AFSM timers
- enter `explore`

### Explore Behaviour

- perform simple forward walking gait
- run ultrasonic scan at intervals
- if obstacle is in front, turn left or right
- check colour sensor for red target
- if 2-minute explore timer expires, change to `low_charge`

### Low Charge Behaviour

- continue the same exploration behaviour
- still avoid obstacles
- still check for red target
- monitor LDR for strong light
- if strong light is detected, stop and enter `charging`

### Charging Behaviour

- stop all movement
- do not perform obstacle avoidance
- monitor LDR continuously
- remain in charging while light is still present
- if charging reaches 1 minute, return to `explore`
- if light is interrupted early, return to `low_charge`

### Target Detected Behaviour

- stop immediately
- blink status LED
- remain in this final state

## 3. AFSM State List

| State | Purpose | Entry Condition | Exit Condition | Timer Usage | Sensor Dependency | Movement Behaviour |
|---|---|---|---|---|---|---|
| `explore` | normal exploration | startup complete or charging completed | red detected, or explore time reaches 2 minutes | `explore timer` | ultrasonic, colour sensor | walk forward by default, turn if obstacle |
| `low_charge` | continue exploration under low charge logic | `explore` timer expires | red detected, or bright light detected | no dedicated state timer | ultrasonic, colour sensor, LDR | walk forward by default, turn if obstacle |
| `charging` | simulated charging under light source | bright light detected in `low_charge` | 1-minute charge completed, or light interrupted | `charging timer` | LDR | stop |
| `target_detected` | mission complete indication | red target detected in `explore` or `low_charge` | no exit condition | `blink timer` | colour sensor for entry, LED for output | stop and blink LED |

## 4. Transition Design

### Transition Priority

To make the logic easy for the teacher to understand, the transition and behaviour priority should be presented as:

1. obstacle avoidance
2. target detected
3. charging logic
4. normal exploration movement

Explanation:

- obstacle avoidance is highest because robot safety comes first
- target detection is next because the robot must stop as soon as the mission target is found
- charging logic is lower than target detection because charging is only relevant in low charge and charging contexts
- normal walking is the default behaviour only when no higher-priority condition is active

### Transition List

- `Start -> Explore`
  - condition: initialisation complete

- `Explore -> Target Detected`
  - condition: `red_detected == True`

- `Explore -> Low Charge`
  - condition: `explore_elapsed >= 2 minutes`

- `Low Charge -> Target Detected`
  - condition: `red_detected == True`

- `Low Charge -> Charging`
  - condition: `ldr_value > bright_threshold`

- `Charging -> Explore`
  - condition: `charge_elapsed >= 1 minute` and light still present

- `Charging -> Low Charge`
  - condition: `ldr_value <= bright_threshold`

Important note:

- obstacle avoidance does not need a separate AFSM state
- it is better shown as a high-priority behaviour inside `explore` and `low_charge`
- this keeps the diagram simple and avoids unnecessary crossing arrows

## 5. Timer Logic

### Explore Timer

- starts when entering `explore`
- resets each time the robot re-enters `explore`
- triggers transition to `low_charge` after 2 minutes

### Charging Timer

- starts when entering `charging`
- if light remains present for 1 minute, transition to `explore`
- if light disappears early, discard charging and return to `low_charge`

### Scan Timing

- ultrasonic scan uses timed scheduling
- scan servo movement and ultrasonic reading alternate
- this reduces power spikes and avoids scanning at the same time as every gait step

### Blink Timing

- LED blink uses timed scheduling in `target_detected`
- LED toggles periodically without blocking the main loop

### Non-Blocking Method

The controller should use:

- `utime.ticks_ms()`
- `utime.ticks_diff()`
- short scheduled actions

The controller should avoid:

- long `sleep()`
- blocking `while` loops
- waiting loops for sensor polling

Short hardware pulse measurement calls are acceptable, but they should use limited sample counts and timeout values.

## 6. Movement Logic

### Gait Sequence

- use a simple four-step gait
- each step updates the four leg servos once
- gait timing is controlled by `STEP_TIME`
- gait amplitude is controlled by `ARC`

### Turning Logic

- turning uses a simple left-turn or right-turn pose sequence
- the robot compares left and right measured distances
- it turns toward the side with more free space

### Obstacle Turning Behaviour

- if front distance is below threshold, walking is overridden by turning
- turning is treated as a local behaviour, not as a separate AFSM state

### Ultrasonic Scanning Behaviour

- scan angles: `[5, 90, 175, 90]`
- store distance values for left, front, right, and return-to-centre positions
- use these readings for obstacle avoidance decisions

This design is suitable for a servo-based robotic dog and avoids unnecessary advanced robotics methods such as inverse kinematics, path planning, or SLAM.

## 7. Draw.io Diagram Helper

### State Nodes

- `Start / Initialisation`
- `Explore`
- `Low Charge`
- `Charging`
- `Target Detected`

### Transition Arrows

- `Start -> Explore`
  - label: `initialise servos / reset timers`

- `Explore -> Low Charge`
  - label: `explore timer >= 2 min`

- `Explore -> Target Detected`
  - label: `red detected`

- `Low Charge -> Charging`
  - label: `LDR > threshold`

- `Low Charge -> Target Detected`
  - label: `red detected`

- `Charging -> Explore`
  - label: `charge timer >= 1 min and light present`

- `Charging -> Low Charge`
  - label: `light interrupted`

### State Box Notes

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

## 8. Implementation Notes for Current Project

The current project structure is already suitable for coursework:

- `main.py` for main loop
- `afsm.py` for state and timer storage
- `states.py` for AFSM behaviour
- `movement.py` for gait and turning
- `sensors.py` for sensor reading
- `config.py` for tunable parameters
- `pins.py` for GPIO mapping

This is simple enough for a student coursework project and should not be expanded into a larger framework.

## 9. Manual Tuning Reminder

The following items require hardware testing and tuning:

- servo neutral angles and offsets
- gait step timing
- gait amplitude
- turn amplitude
- ultrasonic obstacle threshold
- ultrasonic scan interval
- LDR threshold
- colour detection threshold
- colour sampling interval
- LED blink interval

These values are intentionally centralised in `config.py`.
