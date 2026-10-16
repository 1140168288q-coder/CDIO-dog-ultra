"""
Generate AFSM Reference Documentation - Word document
Based primarily on the drawio diagram (page with Veer states)
"""
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import nsdecls
from docx.oxml import parse_xml
import os

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AFSM_Documentation.docx")

doc = Document()

# --- Basic style ---
style = doc.styles['Normal']
style.font.name = 'Calibri'
style.font.size = Pt(11)
style.paragraph_format.space_after = Pt(4)
style.paragraph_format.line_spacing = 1.15

for lvl in [1, 2, 3]:
    h = doc.styles[f'Heading {lvl}']
    h.font.name = 'Calibri'
    h.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    h.font.size = Pt({1: 16, 2: 13, 3: 11.5}[lvl])
    h.font.bold = True

for sec in doc.sections:
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.5)
    sec.right_margin = Cm(2.5)


def add_table(doc, headers, rows, font_size=Pt(9.5)):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = 'Light Grid Accent 1'
    for i, hdr in enumerate(headers):
        t.rows[0].cells[i].text = hdr
        for p in t.rows[0].cells[i].paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.font.bold = True
                r.font.size = font_size
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            t.rows[ri + 1].cells[ci].text = val
            for p in t.rows[ri + 1].cells[ci].paragraphs:
                for r in p.runs:
                    r.font.size = font_size
    doc.add_paragraph()
    return t


def add_code(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F0F0F0" w:val="clear"/>')
    p._p.get_or_add_pPr().append(shd)
    r = p.add_run(text)
    r.font.name = 'Consolas'
    r.font.size = Pt(9.5)


# ============================================================
# TITLE
# ============================================================
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run("AFSM Diagram and Description")
r.font.size = Pt(18)
r.font.bold = True
r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)

doc.add_paragraph()

# ============================================================
# 1. AFSM STATE DIAGRAM
# ============================================================
doc.add_heading("1. AFSM State Diagram", level=1)
doc.add_paragraph(
    "The AFSM state diagram is organised into three groups: #Mission States, "
    "#Higher Priority Interrupt (Obstacle Avoidance), and #Normal Behavior. "
    "The diagram uses solid lines for primary state transitions with guard conditions, "
    "dashed lines for parallel/concurrent activation, and red thick lines for the "
    "highest-priority transition (red_detected → Target Detected)."
)

diagram_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ASFM pro max ultra.drawio.png")
if os.path.exists(diagram_path):
    from docx.shared import Inches
    doc.add_picture(diagram_path, width=Inches(6.5))
    last_paragraph = doc.paragraphs[-1]
    last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph()

# ============================================================
# 2. STATE DESCRIPTIONS
# ============================================================
doc.add_heading("2. State Descriptions", level=1)

doc.add_heading("2.1 Mission States", level=2)

add_table(doc,
    ["State", "Description"],
    [
        ["Start",
         "Initialisation state. All hardware is initialised (servos, HC-SR04, TCS3200, "
         "LDR, LED), the scan servo is centred, and all timers are reset. Unconditionally "
         "transitions to Explore once initialisation is complete."],
        ["Explore",
         "Normal exploration mode. The robot walks forward (Forward sub-state, full speed) "
         "while continuously scanning for obstacles (Scan sub-state, always on). The TCS3200 "
         "colour sensor checks for a red target. A 2-minute explore timer starts on entry. "
         "Exit: red_detected → Target Detected; explore_timer >= 2 min → Low Charge."],
        ["Low Charge",
         "Simulated low-battery mode entered after 2 minutes of exploration without finding "
         "the red target. The robot continues exploring at reduced speed (Forward, lower speed) "
         "with Scan still active. LDR monitoring for high-intensity light is now enabled. Red "
         "target detection remains active. "
         "Exit: LDR > threshold → Charging; red_detected → Target Detected."],
        ["Charging",
         "Simulated charging state. The robot stops all movement and remains stationary. "
         "Monitors LDR continuously. Obstacle avoidance is NOT active in this state. "
         "Exit: charging_timer >= 1 min & light still present → Explore; "
         "light interrupted before 1 min → Low Charge."],
        ["Target Detected",
         "Terminal state with the highest priority. Triggered when the TCS3200 detects a "
         "red patch. The robot stops all movement immediately, and the on-board LED blinks "
         "continuously (non-blocking, 500 ms interval). No outgoing transitions."],
    ],
    font_size=Pt(9.5)
)

doc.add_heading("2.2 Obstacle Avoidance States (Higher Priority Interrupt)", level=2)
doc.add_paragraph(
    "These states together form the obstacle avoidance behaviour (Priority 2). "
    "Scan and Forward run in parallel during Explore and Low Charge. "
    "Internal priority within obstacle avoidance: Recovery > Turn > Veer."
)

add_table(doc,
    ["State", "Description"],
    [
        ["Scan",
         "Uses the HC-SR04 ultrasonic sensor on a scanning servo to measure distances in "
         "three directions: FD (front, 90°), LD (left, 30°), and RD (right, 150°). "
         "Always active during Explore and Low Charge (parallel, dashed line). Feeds distance "
         "data to the obstacle avoidance decision logic. "
         "Exit: FD >= 15 cm & LD/RD clear → Forward; obstacle detected → Turn or Veer; "
         "all directions blocked → Recovery."],
        ["Forward",
         "Default walking gait using four leg servos. Lowest priority behaviour (Priority 4). "
         "Full speed in Explore, reduced speed in Low Charge. Activated as a parallel sub-state "
         "by Explore and Low Charge. "
         "Exit: obstacle & left larger → Turn/Veer Left; obstacle & right larger → Turn/Veer Right; "
         "stuck → Recovery."],
        ["Turn Left",
         "90-degree left turn manoeuvre. Triggered when an obstacle is detected ahead and the "
         "left side has more clearance (LD > RD). After completing the turn, the scan re-checks "
         "the forward path. "
         "Exit: path clear → Forward/Scan; still blocked → Veer Left/Right; "
         "turn_count >= 3 → Recovery."],
        ["Turn Right",
         "90-degree right turn manoeuvre. Triggered when an obstacle is detected ahead and the "
         "right side has more clearance (RD > LD). After completing the turn, the scan re-checks "
         "the forward path. "
         "Exit: path clear → Forward/Scan; still blocked → Veer Left/Right; "
         "turn_count >= 3 → Recovery."],
        ["Veer Left",
         "15–30 degree slight left turn. Triggered when the right side has less clearance "
         "after a Turn Left, or when a minor adjustment is needed (RD > LD with obstacle ahead). "
         "This is a smoother, smaller correction than a full turn. "
         "Exit: veering complete → Scan/Forward; still blocked → Turn; "
         "turn_count >= 3 → Recovery."],
        ["Veer Right",
         "15–30 degree slight right turn. Triggered when the left side has less clearance "
         "after a Turn Right, or when a minor adjustment is needed (LD > RD with obstacle ahead). "
         "This is a smoother, smaller correction than a full turn. "
         "Exit: veering complete → Scan/Forward; still blocked → Turn; "
         "turn_count >= 3 → Recovery."],
        ["Recovery",
         "Safety state triggered when the robot is stuck: three consecutive failed avoidance "
         "attempts (turn_count >= 3), or all three ultrasonic directions are blocked "
         "(LD < 10 & RD < 10 & FD < 10), or any direction is dangerously close "
         "(LD < 5 or RD < 5 or FD < 5). The robot reverses for approximately 1 second, "
         "then performs a random turn. "
         "Exit: recovery complete & path clear → Scan/Forward; "
         "recovery_count >= 3 → Fault Stop (awaiting human intervention)."],
    ],
    font_size=Pt(9.5)
)

# ============================================================
# 3. TRANSITION TABLE
# ============================================================
doc.add_heading("3. Transition Table", level=1)

doc.add_heading("3.1 Mission State Transitions", level=2)

add_table(doc,
    ["Source", "Target", "Condition", "Description"],
    [
        ["Start", "Explore", "init_complete",
         "Hardware initialised, servos centred, timers reset."],
        ["Explore", "Low Charge", "explore_timer >= 2 min",
         "2-minute exploration timer expired without red target."],
        ["Explore", "Target Detected", "red_detected",
         "TCS3200 detects red patch. Immediate stop + LED blink."],
        ["Low Charge", "Charging", "LDR > threshold",
         "High-intensity light detected — robot stops to simulate charging."],
        ["Low Charge", "Target Detected", "red_detected",
         "TCS3200 detects red patch in low-battery mode."],
        ["Charging", "Explore", "charging_timer >= 1 min & light_present",
         "Full 1-minute charge under continuous light."],
        ["Charging", "Low Charge", "light_interrupted (timer < 1 min)",
         "Light removed before charge complete."],
    ]
)

doc.add_heading("3.2 Obstacle Avoidance Transitions", level=2)

add_table(doc,
    ["Source", "Target", "Condition", "Description"],
    [
        ["Explore", "Forward", "default entry (parallel)",
         "Explore activates Forward at full speed."],
        ["Explore", "Scan", "always on (parallel)",
         "Explore activates Scan for continuous ultrasonic detection."],
        ["Low Charge", "Forward", "default entry, lower speed (parallel)",
         "Low Charge activates Forward at reduced speed."],
        ["Low Charge", "Scan", "always on, lower frequency (parallel)",
         "Low Charge activates Scan."],
        ["Scan", "Turn Left", "FD < 15 cm & LD > RD",
         "Obstacle ahead, left side has more clearance."],
        ["Scan", "Turn Right", "FD < 15 cm & RD > LD",
         "Obstacle ahead, right side has more clearance."],
        ["Scan", "Veer Left", "obstacle & RD > LD (minor adjustment)",
         "Slight left correction needed."],
        ["Scan", "Veer Right", "obstacle & LD > RD (minor adjustment)",
         "Slight right correction needed."],
        ["Scan", "Recovery", "LD<10 & RD<10 & FD<10, or "
         "LD<5 or RD<5 or FD<5, or turn_count>=3",
         "All directions blocked, dangerously close, or repeated failures."],
        ["Turn Left", "Scan", "complete turning",
         "Turn finished, re-scan environment."],
        ["Turn Left", "Recovery", "turn_count >= 3",
         "Three consecutive failed left turns."],
        ["Turn Left", "Veer Right", "RD > LD",
         "After turn, right side needs minor correction."],
        ["Turn Right", "Scan", "complete turning",
         "Turn finished, re-scan environment."],
        ["Turn Right", "Recovery", "turn_count >= 3",
         "Three consecutive failed right turns."],
        ["Turn Right", "Veer Left", "LD > RD",
         "After turn, left side needs minor correction."],
        ["Veer Left", "Scan", "complete veering",
         "Veering finished, re-scan environment."],
        ["Veer Left", "Recovery", "turn_count >= 3",
         "Repeated veer failures."],
        ["Veer Right", "Scan", "complete veering",
         "Veering finished, re-scan environment."],
        ["Veer Right", "Recovery", "turn_count >= 3",
         "Repeated veer failures."],
        ["Recovery", "Scan", "recovery complete & path clear",
         "Backup + random turn completed, path now clear."],
        ["Recovery", "Fault Stop", "recovery_count >= 3",
         "Robot is completely stuck — awaiting human intervention."],
        ["*Any obstacle state", "Forward", "path clear",
         "When path is confirmed clear, return to default forward movement."],
    ]
)

p = doc.add_paragraph()
r = p.add_run("Note: ")
r.font.bold = True
r.font.size = Pt(9.5)
r2 = p.add_run(
    "If LD = RD, the robot turns or veers randomly. "
    "All obstacle avoidance states share the turn_count counter, which resets to 0 "
    "when the robot returns to Forward. Recovery has its own recovery_count."
)
r2.font.size = Pt(9.5)

# ============================================================
# 4. PRIORITY & TIMERS
# ============================================================
doc.add_heading("4. Priority & Timers", level=1)

doc.add_heading("4.1 Priority Table", level=2)

add_table(doc,
    ["Priority", "Behaviour", "States", "Note"],
    [
        ["1 (Highest)", "Target Detection", "Target Detected",
         "Red detected → immediate stop, preempts everything."],
        ["2", "Obstacle Avoidance",
         "Scan, Turn Left, Turn Right, Veer Left, Veer Right, Recovery",
         "Active in Explore and Low Charge only (NOT in Charging). "
         "Internal priority: Recovery > Turn > Veer."],
        ["3", "Charging Logic", "Charging, Low Charge",
         "LDR-based light detection and simulated charging."],
        ["4 (Lowest)", "Normal Movement", "Forward",
         "Default walking gait, most easily interrupted."],
    ]
)

doc.add_heading("4.2 Timers", level=2)

add_table(doc,
    ["Timer", "Duration", "Trigger", "Action"],
    [
        ["Explore Timer", "2 minutes", "Entry to Explore",
         "Timer expires → transition to Low Charge."],
        ["Charging Timer", "1 minute", "Entry to Charging",
         "Timer expires & light present → return to Explore; "
         "light interrupted before 1 min → return to Low Charge."],
        ["LED Blink Timer", "500 ms toggle", "Entry to Target Detected",
         "Non-blocking LED toggle using ticks_ms()."],
        ["Turn Count", "count >= 3", "Each failed avoidance attempt",
         "Triggers Recovery state. Resets on return to Forward."],
        ["Recovery Count", "count >= 3", "Each Recovery entry",
         "Triggers Fault Stop (awaiting human intervention)."],
    ]
)

# ============================================================
# 5. PSEUDOCODE
# ============================================================
doc.add_heading("5. Pseudocode", level=1)
doc.add_paragraph(
    "The pseudocode below describes the four main mission states, "
    "following the style shown in the assignment brief."
)

doc.add_heading("5.1 Explore State", level=2)
add_code(doc, """\
if State == "Explore"
    while explore_timer != 2 min AND target != found
        # Parallel: Forward (full speed) + Scan (always on)
        if object_detection == False
            go forward (full speed)
        else
            avoid_obstacle()  # Turn / Veer / Recovery
    if target == found
        change state to "Target Detected"
    else
        reset explore timer to 0
        change state to "Low Charge\"""")

doc.add_heading("5.2 Low Charge State", level=2)
add_code(doc, """\
if State == "Low Charge"
    while target != found
        # Parallel: Forward (reduced speed) + Scan (always on) + LDR check
        if LDR > threshold
            change state to "Charging"
        if object_detection == False
            go forward (reduced speed)
        else
            avoid_obstacle()  # Turn / Veer / Recovery
    if target == found
        change state to "Target Detected\"""")

doc.add_heading("5.3 Charging State", level=2)
add_code(doc, """\
if State == "Charging"
    # Robot is stationary, no obstacle avoidance
    while charging_timer != 1 min
        if light interrupted
            change state to "Low Charge"
    # charging_timer == 1 min AND light still present
    reset explore timer to 0
    change state to "Explore\"""")

doc.add_heading("5.4 Target Detected State", level=2)
add_code(doc, """\
if State == "Target Detected"
    stop all movement
    while True
        blink LED every 500 ms  # non-blocking
    # Terminal state — no further transitions""")

# ============================================================
# SAVE
# ============================================================
doc.save(OUTPUT_PATH)
print(f"Saved: {OUTPUT_PATH}")
