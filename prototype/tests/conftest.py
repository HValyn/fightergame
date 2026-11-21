import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402
import pytest  # noqa: E402

pygame.init()

from character_defs import get_character  # noqa: E402
from constants import InputState  # noqa: E402
from fighter import Fighter  # noqa: E402

N = InputState  # shorthand: N() == neutral


class Sim:
    """Two fighters stepped in lock-step with scripted inputs (no keyboard)."""

    def __init__(self, p1="ryokan", p2="ryokan", x1=500, x2=560):
        self.f1 = Fighter(get_character(p1), x1, 1)
        self.f2 = Fighter(get_character(p2), x2, 2)
        self.frame = 0

    def step(self, i1=None, i2=None, n=1):
        for _ in range(n):
            self.f1.update(self.f2, self.frame, ai_input=i1 or N())
            self.f2.update(self.f1, self.frame, ai_input=i2 or N())
            self.frame += 1
        return self

    def feed(self, who, inputs, other=None):
        """Feed a list of InputStates to fighter `who` (1 or 2)."""
        for inp in inputs:
            if who == 1:
                self.step(inp, other)
            else:
                self.step(other, inp)
        return self


@pytest.fixture
def sim():
    return Sim
