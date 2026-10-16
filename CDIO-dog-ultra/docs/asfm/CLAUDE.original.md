# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

University coursework project implementing an AFSM (Augmented Finite State Machine) for a small robotic dog controlled by Raspberry Pi Pico (MicroPython). The robot autonomously explores, avoids obstacles via ultrasonic sensor, detects a red target via colour sensor, and simulates battery charging via light sensor.

## Key Commands

- Generate documentation Word file: `python generate_doc.py`
- Output goes to `AFSM_Documentation_v2.docx` (can be renamed to `AFSM_Documentation.docx`)

Requires `python-docx` package.

## AFSM Architecture

10 states in 3 groups:

**Mission States:** Start → Explore → Low Charge → Charging, plus terminal state Target Detected (highest priority, immediate stop + LED blink).

**Obstacle Avoidance (Higher Priority Interrupt):** Scan (always-on concurrent sub-behaviour), Forward (default movement), Turn Left / Turn Right (avoidance), Recovery (stuck recovery). These run in parallel with Explore and Low Charge via dashed-line concurrent activation.

**Normal Behavior:** Forward is the lowest-priority default gait.

Priority order: Target Detection (1) > Obstacle Avoidance (2) > Charging Logic (3) > Normal Movement (4).

## Critical Design Constraints

- Target Detected is the highest priority — red detection preempts everything and is a terminal state
- Obstacle avoidance is NOT active during Charging state
- All timing uses non-blocking `ticks_ms()` / `ticks_diff()` — no `sleep()` or blocking loops
- Turn direction decided by comparing left vs right ultrasonic distances; equal clearance → random
- 3 consecutive failed avoidance attempts triggers Recovery
- Explore timer: 2 min → Low Charge. Charging timer: 1 min under continuous light → back to Explore
- Speed is reduced in Low Charge mode

## Documentation Files

- `AFSM_设计说明文档_中文版.md` — Chinese design spec (authoritative for state logic, sections 2–7)
- `ASFM_Documentation.md` — English documentation with Mermaid diagrams and student exercises
- `generate_doc.py` — Python script generating the Word document with full AFSM documentation
- `ASFM pro max ultra.drawio` — Draw.io state diagram
- Two PDF examples of AFSM diagrams

When updating documentation, the Chinese md file is the source of truth for state behavior. The generate_doc.py script contains the most detailed English descriptions and transition tables.
