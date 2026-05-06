"""
Motion Input Detector — reads directional input history and recognizes
fighting game motion inputs (QCF, DP, HCF, charges, etc.).

Usage:
    detector = MotionDetector()
    # Each frame, push the current direction:
    detector.push_direction("right")
    detector.push_direction("downright")
    # Then check for motions:
    if detector.detect(MotionType.QUARTER_CIRCLE_FORWARD, within=20):
        print("QCF detected!")
"""

from collections import deque
from typing import Optional, List, Tuple

from constants import MotionType

# Canonical motion sequences for detection.
# Each sequence is a list of direction tokens. The detector uses fuzzy matching
# to allow slight variations (extra neutral frames, skip diagonals, etc.)
MOTION_TEMPLATES = {
    # QCF: ↓ ↘ →
    MotionType.QUARTER_CIRCLE_FORWARD: [
        ["down", "downright", "right"],
        ["down", "downright"],          # abbreviated
        ["down", "right"],              # shortcut (lenient)
    ],
    # QCB: ↓ ↙ ←
    MotionType.QUARTER_CIRCLE_BACK: [
        ["down", "downleft", "left"],
        ["down", "downleft"],
        ["down", "left"],
    ],
    # DP forward: → ↓ ↘
    MotionType.DRAGON_PUNCH_FORWARD: [
        ["right", "down", "downright"],
        ["right", "downright", "down"],
        ["forward", "down", "forward"],
    ],
    # DP back: ← ↓ ↙
    MotionType.DRAGON_PUNCH_BACK: [
        ["left", "down", "downleft"],
        ["left", "downleft", "down"],
        ["back", "down", "back"],
    ],
    # HCF: ← ↙ ↓ ↘ →
    MotionType.HALF_CIRCLE_FORWARD: [
        ["left", "downleft", "down", "downright", "right"],
        ["left", "downleft", "down", "downright"],
        ["left", "down", "right"],
    ],
    # HCB: → ↘ ↓ ↙ ←
    MotionType.HALF_CIRCLE_BACK: [
        ["right", "downright", "down", "downleft", "left"],
        ["right", "downright", "down", "downleft"],
        ["right", "down", "left"],
    ],
    # Charge back →: hold ← for N frames, then →
    MotionType.CHARGE_BACK: [],  # Handled separately with charge tracking
    # Charge down ↑: hold ↓ for N frames, then ↑
    MotionType.CHARGE_DOWN: [],  # Handled separately with charge tracking
    # Super charge (double QCF): ↓↘→↓↘→
    MotionType.SUPER_CHARGE: [
        ["down", "downright", "right", "down", "downright", "right"],
        ["down", "right", "down", "right"],
    ],
    # Zigzag: ↓ then ↑
    MotionType.ZIGZAG: [
        ["down", "up"],
        ["down", "downleft", "up"],
        ["down", "downright", "up"],
    ],
}

# Map ambiguous direction tokens to their canonical forms for matching.
DIRECTION_EQUIVALENTS = {
    "forward": None,  # Resolved at runtime based on facing
    "back": None,
}

# All directional tokens that count as "down"
DOWN_DIRECTIONS = {"down", "downleft", "downright"}
UP_DIRECTIONS = {"up", "upleft", "upright"}
LEFT_DIRECTIONS = {"left", "downleft", "upleft"}
RIGHT_DIRECTIONS = {"right", "downright", "upright"}


class MotionDetector:
    """
    Detects motion inputs by tracking directional input history.
    Supports both relative ("forward", "back") and absolute ("left", "right") directions.
    """

    def __init__(self, buffer_size: int = 60):
        self.buffer: deque = deque(maxlen=buffer_size)
        self.charge_timer_back: int = 0
        self.charge_timer_down: int = 0
        self.min_charge_frames: int = 40  # Minimum frames to charge

    def reset_charges(self):
        """Reset charge timers (call on hit/block/character switch)."""
        self.charge_timer_back = 0
        self.charge_timer_down = 0

    def push_direction(self, direction: str, facing: int = 1):
        """
        Push a new direction onto the history buffer.
        direction: raw direction string from InputState.get_direction()
        facing: 1 for facing right, -1 for facing left
        """
        resolved = self._resolve_direction(direction, facing)
        self.buffer.append(resolved)
        self._update_charges(resolved, facing)

    def _resolve_direction(self, direction: str, facing: int) -> str:
        """Convert relative directions to absolute based on facing."""
        if direction == "neutral":
            return "neutral"
        # For non-diagonal relative directions
        if direction == "forward":
            return "right" if facing == 1 else "left"
        if direction == "back":
            return "left" if facing == 1 else "right"
        return direction

    def _update_charges(self, direction: str, facing: int):
        """Track charge inputs for CHARGE_BACK and CHARGE_DOWN."""
        back_dir = "left" if facing == 1 else "right"
        # Charge back: holding the back direction
        if direction == back_dir or direction == ("downleft" if facing == 1 else "downright"):
            self.charge_timer_back += 1
        else:
            if self.charge_timer_back >= self.min_charge_frames:
                self.charge_timer_back = self.min_charge_frames + 5  # Keep charged briefly
            else:
                self.charge_timer_back = 0

        # Charge down: holding down
        if direction in DOWN_DIRECTIONS:
            self.charge_timer_down += 1
        else:
            if self.charge_timer_down >= self.min_charge_frames:
                self.charge_timer_down = self.min_charge_frames + 5
            else:
                self.charge_timer_down = 0

    def detect(self, motion: MotionType, within: int = 20, facing: int = 1) -> bool:
        """
        Check if the given motion was completed within the last `within` frames.
        Returns True if the motion pattern is found in the buffer.
        """
        if len(self.buffer) < 2:
            return False

        # Handle charge motions separately
        if motion == MotionType.CHARGE_BACK:
            forward_dir = "right" if facing == 1 else "left"
            recent = [self.buffer[i] for i in range(max(0, len(self.buffer) - 5), len(self.buffer))]
            return (self.charge_timer_back >= self.min_charge_frames and
                    any(d == forward_dir for d in recent[-3:]))

        if motion == MotionType.CHARGE_DOWN:
            recent = [self.buffer[i] for i in range(max(0, len(self.buffer) - 5), len(self.buffer))]
            return (self.charge_timer_down >= self.min_charge_frames and
                    any(d in UP_DIRECTIONS for d in recent[-3:]))

        # Normal motion detection via template matching
        templates = MOTION_TEMPLATES.get(motion, [])
        if not templates:
            return False

        recent_history = list(self.buffer)[-within:]
        filtered = self._filter_redundant(recent_history)

        for template in templates:
            if self._matches_template(filtered, template):
                return True

        return False

    def _filter_redundant(self, directions: List[str]) -> List[str]:
        """Remove consecutive duplicate directions to simplify matching."""
        if not directions:
            return []
        result = [directions[0]]
        for d in directions[1:]:
            if d != result[-1]:
                result.append(d)
        return result

    def _matches_template(self, history: List[str], template: List[str]) -> bool:
        """
        Check if the template sequence exists as a subsequence in history.
        Uses fuzzy matching: allows extra entries between template entries,
        but template order must be preserved.
        """
        if len(template) > len(history):
            return False

        t_idx = 0
        for h_dir in history:
            if h_dir == "neutral":
                continue  # Skip neutral inputs
            if self._directions_match(h_dir, template[t_idx]):
                t_idx += 1
                if t_idx >= len(template):
                    return True

        return False

    def _directions_match(self, actual: str, expected: str) -> bool:
        """Check if two directions match, with some leniency."""
        if actual == expected:
            return True
        # Allow shortcut: down can substitute for diagonal in some cases
        if expected in ("downleft", "downright") and actual == "down":
            return True
        if expected in ("upleft", "upright") and actual == "up":
            return True
        return False

    def get_recent_directions(self, count: int = 10) -> List[str]:
        """Return the last N directions from the buffer."""
        return list(self.buffer)[-count:]

    def clear(self):
        """Clear all buffers and charge timers."""
        self.buffer.clear()
        self.charge_timer_back = 0
        self.charge_timer_down = 0
