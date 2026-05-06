"""
Input Handler — manages raw button inputs, input buffering, and motion detection.
Combines the old InputBuffer with MotionDetector into a unified system.
"""

from collections import deque
from typing import Optional, List

import pygame

from constants import InputState, BufferedInput, INPUT_BUFFER_SIZE, INPUT_BUFFER_ON_WAKEUP
from motion_input import MotionDetector


class InputHandler:
    """
    Unified input system that handles:
    1. Reading raw keyboard / AI inputs
    2. Detecting rising edges (button press vs hold)
    3. Input buffering for attacks
    4. Motion detection for special moves
    """

    def __init__(self, player_id: int = 1):
        self.player_id = player_id
        self.size = INPUT_BUFFER_SIZE

        # Raw input history for rising-edge detection
        self.buffer: deque[InputState] = deque(maxlen=self.size)

        # Buffered attack inputs
        self.buffered_attacks: List[BufferedInput] = []

        # Frame counter
        self.current_frame = 0

        # Motion detection
        self.motion_detector = MotionDetector()

        # Key mapping (can be customized per player)
        self.key_map = self._get_default_keymap(player_id)

        # The last input state (for AI injection)
        self._last_input = InputState()

    def _get_default_keymap(self, player_id: int) -> dict:
        """Return the default key mapping for a player."""
        if player_id == 1:
            return {
                "left": pygame.K_LEFT,
                "right": pygame.K_RIGHT,
                "up": pygame.K_UP,
                "down": pygame.K_DOWN,
                "punch": pygame.K_a,
                "kick": pygame.K_s,
                "special": pygame.K_d,
                "heavy": pygame.K_LSHIFT,
            }
        else:
            return {
                "left": pygame.K_KP4,
                "right": pygame.K_KP6,
                "up": pygame.K_KP8,
                "down": pygame.K_KP5,
                "punch": pygame.K_KP1,
                "kick": pygame.K_KP2,
                "special": pygame.K_KP3,
                "heavy": pygame.K_RSHIFT,
            }

    def set_keymap(self, keymap: dict):
        """Customize the key mapping."""
        self.key_map = keymap

    def read_keyboard(self, keys_pressed) -> InputState:
        """Read input from pygame keyboard state."""
        state = InputState(
            left=bool(keys_pressed[self.key_map["left"]]),
            right=bool(keys_pressed[self.key_map["right"]]),
            up=bool(keys_pressed[self.key_map["up"]]),
            down=bool(keys_pressed[self.key_map["down"]]),
            punch=bool(keys_pressed[self.key_map["punch"]]),
            kick=bool(keys_pressed[self.key_map["kick"]]),
            special=bool(keys_pressed[self.key_map["special"]]),
            heavy=bool(keys_pressed[self.key_map["heavy"]]),
        )
        self._process_new_state(state)
        return state

    def push_ai_input(self, ai_state: InputState) -> InputState:
        """Inject an AI-generated InputState."""
        self._process_new_state(ai_state)
        return ai_state

    def _process_new_state(self, state: InputState):
        """Internal: process a new input state, detect edges, buffer attacks."""
        prev = self._last_input

        # Detect rising edges for attack buttons
        attack_buttons = []
        if state.punch and not prev.punch:
            attack_buttons.append("punch")
        if state.kick and not prev.kick:
            attack_buttons.append("kick")
        if state.special and not prev.special:
            attack_buttons.append("special")

        if attack_buttons:
            self.buffered_attacks.append(
                BufferedInput(input_state=state, frame_pressed=self.current_frame)
            )

        # Update motion detector with direction
        direction = state.get_direction()
        # We don't have facing here — it will be set from outside
        # Store the raw direction for later resolution
        self.motion_detector.buffer.append(direction)
        self._last_input = state
        self.buffer.append(state)
        self.current_frame += 1

        # Expire old buffered attacks
        self.buffered_attacks = [
            bi for bi in self.buffered_attacks
            if self.current_frame - bi.frame_pressed < INPUT_BUFFER_ON_WAKEUP
        ]

    def update_motion_direction(self, direction: str, facing: int = 1):
        """
        Update motion detector with the current direction, resolved for facing.
        Called externally by the Fighter which knows its facing direction.
        """
        # Replace the last entry in the motion buffer with the resolved one
        if self.motion_detector.buffer:
            self.motion_detector.buffer[-1] = (
                self.motion_detector._resolve_direction(direction, facing)
            )
        else:
            self.motion_detector.push_direction(direction, facing)

    def get_current(self) -> InputState:
        return self.buffer[-1] if self.buffer else InputState()

    def get_previous(self, frames_back: int = 1) -> InputState:
        if len(self.buffer) > frames_back:
            return self.buffer[-(frames_back + 1)]
        return InputState()

    def consume_buffered_attack(self) -> Optional[InputState]:
        """Consume and return the oldest un-consumed buffered attack."""
        for buffered in self.buffered_attacks:
            if not buffered.consumed:
                buffered.consumed = True
                return buffered.input_state
        return None

    def has_buffered_attack(self) -> bool:
        return any(not bi.consumed for bi in self.buffered_attacks)

    def has_rising_edge(self, button: str) -> bool:
        """Check if a specific button was just pressed this frame."""
        current = self.get_current()
        prev = self.get_previous()
        if button == "punch":
            return current.punch and not prev.punch
        elif button == "kick":
            return current.kick and not prev.kick
        elif button == "special":
            return current.special and not prev.special
        elif button == "heavy":
            return current.heavy and not prev.heavy
        return False

    def reset_charges(self):
        """Reset motion charge timers (called when starting an attack)."""
        self.motion_detector.reset_charges()

    def clear(self):
        """Reset all buffers."""
        self.buffer.clear()
        self.buffered_attacks.clear()
        self.current_frame = 0
        self.motion_detector.clear()
        self._last_input = InputState()
