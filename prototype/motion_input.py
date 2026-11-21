"""
Motion Input Detector — reads directional input history and recognizes
fighting game motion inputs (QCF, DP, HCF, charges, etc.).

All directions stored in the buffer are NORMALISED to "facing right":
when the fighter faces left, left/right are mirrored before storing. That way
every template below is written once ("right" == forward, "left" == back) and
works on both sides of the screen.

Usage:
    detector = MotionDetector()
    detector.push_direction("down", facing=1)
    detector.push_direction("downright", facing=1)
    detector.push_direction("right", facing=1)
    detector.detect(MotionType.QUARTER_CIRCLE_FORWARD)  # -> True
"""

from collections import deque
from typing import List

from constants import MotionType

# Templates are written for a fighter facing RIGHT ("right" = forward).
# Deliberately strict: shortcut templates such as ["down", "right"] made
# "crouch, then walk forward, then jab" come out as a fireball.
MOTION_TEMPLATES = {
    MotionType.QUARTER_CIRCLE_FORWARD: [["down", "downright", "right"]],
    MotionType.QUARTER_CIRCLE_BACK: [["down", "downleft", "left"]],
    MotionType.DRAGON_PUNCH_FORWARD: [
        ["right", "down", "downright"],
        ["right", "downright", "down", "downright"],
    ],
    MotionType.DRAGON_PUNCH_BACK: [
        ["left", "down", "downleft"],
        ["left", "downleft", "down", "downleft"],
    ],
    MotionType.HALF_CIRCLE_FORWARD: [["left", "downleft", "down", "downright", "right"]],
    MotionType.HALF_CIRCLE_BACK: [["right", "downright", "down", "downleft", "left"]],
    MotionType.CHARGE_BACK: [],   # handled by charge timers
    MotionType.CHARGE_DOWN: [],   # handled by charge timers
    MotionType.SUPER_CHARGE: [["down", "downright", "right", "down", "downright", "right"]],
    MotionType.ZIGZAG: [["down", "up"]],
}

DOWN_DIRECTIONS = {"down", "downleft", "downright"}
UP_DIRECTIONS = {"up", "upleft", "upright"}
BACK_DIRECTIONS = {"left", "downleft", "upleft"}         # normalised
FORWARD_DIRECTIONS = {"right", "downright", "upright"}   # normalised

_MIRROR = {
    "left": "right", "right": "left",
    "downleft": "downright", "downright": "downleft",
    "upleft": "upright", "upright": "upleft",
}

# The last direction of a motion must have been entered at most this many
# frames before the button press — stops stale motions from firing later.
MOTION_COMPLETION_WINDOW = 8
# After a charge is released, the special can still be performed this long.
CHARGE_RELEASE_GRACE = 10


class MotionDetector:
    """Detects motion inputs by tracking (normalised) directional input history."""

    def __init__(self, buffer_size: int = 60):
        self.buffer: deque = deque(maxlen=buffer_size)
        self.min_charge_frames: int = 40
        self.charge_timer_back: int = 0
        self.charge_timer_down: int = 0
        self.charge_grace_back: int = 0
        self.charge_grace_down: int = 0

    # ------------------------------------------------------------------ input
    @staticmethod
    def normalise(direction: str, facing: int) -> str:
        """Mirror a raw screen direction so that 'right' always means forward."""
        if facing == -1:
            return _MIRROR.get(direction, direction)
        return direction

    # Kept for backwards compatibility with older call sites.
    _resolve_direction = normalise

    def push_direction(self, direction: str, facing: int = 1):
        """Push this frame's raw direction (from InputState.get_direction())."""
        resolved = self.normalise(direction, facing)
        self.buffer.append(resolved)
        self._update_charges(resolved)

    def _update_charges(self, direction: str):
        self.charge_timer_back, self.charge_grace_back = self._tick_charge(
            direction in BACK_DIRECTIONS, self.charge_timer_back, self.charge_grace_back)
        self.charge_timer_down, self.charge_grace_down = self._tick_charge(
            direction in DOWN_DIRECTIONS, self.charge_timer_down, self.charge_grace_down)

    def _tick_charge(self, holding: bool, timer: int, grace: int):
        if holding:
            return timer + 1, 0
        if timer >= self.min_charge_frames:
            return 0, CHARGE_RELEASE_GRACE       # just released a full charge
        return 0, max(0, grace - 1)

    def _charged(self, timer: int, grace: int) -> bool:
        return timer >= self.min_charge_frames or grace > 0

    # -------------------------------------------------------------- detection
    def detect(self, motion: MotionType, within: int = 20, facing: int = 1) -> bool:
        """
        True if `motion` was completed recently. `facing` is accepted for API
        compatibility; the buffer is already normalised.
        """
        if len(self.buffer) < 1:
            return False

        recent3 = list(self.buffer)[-3:]
        if motion == MotionType.CHARGE_BACK:
            return (self._charged(self.charge_timer_back, self.charge_grace_back)
                    and any(d in FORWARD_DIRECTIONS for d in recent3))
        if motion == MotionType.CHARGE_DOWN:
            return (self._charged(self.charge_timer_down, self.charge_grace_down)
                    and any(d in UP_DIRECTIONS for d in recent3))

        history = list(self.buffer)[-within:]
        return any(self._matches_template(history, t) for t in MOTION_TEMPLATES.get(motion, []))

    def _matches_template(self, history: List[str], template: List[str]) -> bool:
        """
        Backward greedy subsequence match. The template's final direction must
        appear within the last MOTION_COMPLETION_WINDOW frames; earlier steps
        may have other inputs between them (neutral is ignored).
        """
        if not template or len(history) < len(template):
            return False
        t_idx = len(template) - 1
        n = len(history)
        for i in range(n - 1, -1, -1):
            d = history[i]
            if d == "neutral":
                continue
            if d == template[t_idx]:
                if t_idx == len(template) - 1 and n - 1 - i >= MOTION_COMPLETION_WINDOW:
                    return False
                t_idx -= 1
                if t_idx < 0:
                    return True
        return False

    # ---------------------------------------------------------------- utility
    def get_recent_directions(self, count: int = 10) -> List[str]:
        return list(self.buffer)[-count:]

    def consume(self):
        """Clear motion history after a special fires so it can't fire twice."""
        self.buffer.clear()

    def reset_charges(self):
        self.charge_timer_back = self.charge_timer_down = 0
        self.charge_grace_back = self.charge_grace_down = 0

    def clear(self):
        self.buffer.clear()
        self.reset_charges()
