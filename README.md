2D Fighter V2 - CPU AI Integration
A professional 2D fighting game engine built with Pygame, featuring a state-of-the-art input buffer system, separate hitbox/hurtbox/pushbox collision, attack sub-states (startup/active/recovery), hitstop, and a fully integrated CPU opponent.

Features
Input Buffer System: 12-frame input history to prevent dropped inputs.
Frame Data: True to form startup, active, and recovery frames for all attacks.
CPU AI Opponent: A behavior-tree-inspired AI that reads distance, reacts to attacks, blocks mixups, punishes recovery frames, and executes combos.
Multiple Difficulties: Cycle through Easy, Medium, Hard, and Brutal modes.
Prerequisites
Python 3.8 or higher
Pygame
Installation
Ensure Python is installed on your system.
Install Pygame using pip:
pip install pygame
How to Run
Navigate to the directory containing these files and run:

bash

python main.py
Controls (Player 1)
Key
Action
Arrow Keys	Move (Left/Right), Jump (Up), Crouch (Down)
A	Punch
S	Kick
Left Shift	Hold for Full Power (Heavy) attack
Up/Down + A/S	Alter attack height (High/Low)
TAB	Cycle CPU Difficulty
R	Reset Match
ESC	Quit

Architecture
constants.py: Contains all game physics, colors, enums (States, Attack Heights), dataclasses (InputState, AttackData), and the AttackDatabase.
fighter.py: The Fighter class handles state machines, physics, rendering, and collision. The InputBuffer class handles input history and rising-edge detection (registering a button press vs a hold).
ai_controller.py: The AIController evaluates the "OpponentReading" (distance, state) to make decisions. It simulates human reaction times, pattern recognition, and combo execution.
main.py: The Game class orchestrates the main loop, passes keyboard inputs to P1, passes AIController inputs to P2, and handles rendering.