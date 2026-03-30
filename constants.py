
"""
Contains all game constants, enumerations, data classes, and the Attack Database.
"""

import pygame
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Dict, Tuple

# =============================================================================
# CONSTANTS
# =============================================================================
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 700
FPS = 60
GROUND_Y = 550

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (220, 60, 60)
DARK_RED = (150, 40, 40)
BLUE = (60, 100, 220)
DARK_BLUE = (40, 70, 150)
GREEN = (60, 180, 60)
YELLOW = (240, 200, 60)
ORANGE = (240, 140, 40)
PURPLE = (150, 60, 200)
CYAN = (60, 200, 220)
GRAY = (100, 100, 100)
LIGHT_GRAY = (180, 180, 180)
BROWN = (139, 90, 43)

# Physics Constants
GRAVITY = 0.8
JUMP_FORCE = -18
WALK_SPEED = 5
CROUCH_SPEED = 2

# Input Buffer
INPUT_BUFFER_SIZE = 12
INPUT_BUFFER_ON_WAKEUP = 8

# Game Feel
HITSTOP_FRAMES = 6
COYOTE_TIME_FRAMES = 3

# =============================================================================
# ENUMS
# =============================================================================
class State(Enum):
    IDLE = auto()
    WALK = auto()
    JUMP = auto()
    CROUCH = auto()
    ATTACK_STARTUP = auto()
    ATTACK_ACTIVE = auto()
    ATTACK_RECOVERY = auto()
    BLOCK = auto()
    HITSTUN = auto()

class AttackType(Enum):
    PUNCH = "Punch"
    KICK = "Kick"

class AttackHeight(Enum):
    HIGH = "High"
    STRAIGHT = "Straight"
    LOW = "Low"

class FacingDirection(Enum):
    LEFT = -1
    RIGHT = 1

class BoxType(Enum):
    HITBOX = auto()
    HURTBOX = auto()
    PUSHBOX = auto()

# =============================================================================
# DATA CLASSES
# =============================================================================
@dataclass
class InputState:
    left: bool = False
    right: bool = False
    up: bool = False
    down: bool = False
    punch: bool = False
    kick: bool = False
    power: bool = False
    
    def has_attack(self) -> bool:
        return self.punch or self.kick

@dataclass
class BufferedInput:
    input_state: InputState
    frame_pressed: int
    consumed: bool = False

@dataclass
class AttackData:
    name: str
    attack_type: AttackType
    height: AttackHeight
    base_damage: int
    startup_frames: int
    active_frames: int
    recovery_frames: int
    hitstun_frames: int
    knockback: float
    range_bonus: int
    cancel_window: int = 0
    hitstop: int = HITSTOP_FRAMES
    
    @property
    def total_frames(self) -> int:
        return self.startup_frames + self.active_frames + self.recovery_frames
    
    @property
    def frame_advantage_on_hit(self) -> int:
        return self.hitstun_frames - self.recovery_frames
    
    @property
    def frame_advantage_on_block(self) -> int:
        return (self.hitstun_frames // 2) - self.recovery_frames

@dataclass
class Box:
    x: int
    y: int
    width: int
    height: int
    box_type: BoxType
    
    def to_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.width, self.height)
    
    def intersects(self, other: 'Box') -> bool:
        return self.to_rect().colliderect(other.to_rect())

# =============================================================================
# ATTACK DATABASE
# =============================================================================
class AttackDatabase:
    ATTACKS: Dict[Tuple[AttackType, AttackHeight, bool], AttackData] = {
        (AttackType.PUNCH, AttackHeight.HIGH, False): AttackData("Jab High", AttackType.PUNCH, AttackHeight.HIGH, base_damage=6, startup_frames=3, active_frames=3, recovery_frames=6, hitstun_frames=12, knockback=2.0, range_bonus=0, cancel_window=4),
        (AttackType.PUNCH, AttackHeight.STRAIGHT, False): AttackData("Jab Straight", AttackType.PUNCH, AttackHeight.STRAIGHT, base_damage=8, startup_frames=4, active_frames=3, recovery_frames=7, hitstun_frames=13, knockback=3.0, range_bonus=10, cancel_window=5),
        (AttackType.PUNCH, AttackHeight.LOW, False): AttackData("Jab Low", AttackType.PUNCH, AttackHeight.LOW, base_damage=5, startup_frames=3, active_frames=3, recovery_frames=5, hitstun_frames=10, knockback=1.5, range_bonus=-5, cancel_window=4),
        (AttackType.KICK, AttackHeight.HIGH, False): AttackData("Med High Kick", AttackType.KICK, AttackHeight.HIGH, base_damage=10, startup_frames=7, active_frames=4, recovery_frames=12, hitstun_frames=16, knockback=4.0, range_bonus=5, cancel_window=10),
        (AttackType.KICK, AttackHeight.STRAIGHT, False): AttackData("Med Straight Kick", AttackType.KICK, AttackHeight.STRAIGHT, base_damage=12, startup_frames=8, active_frames=5, recovery_frames=14, hitstun_frames=18, knockback=5.0, range_bonus=15, cancel_window=12),
        (AttackType.KICK, AttackHeight.LOW, False): AttackData("Med Low Kick", AttackType.KICK, AttackHeight.LOW, base_damage=8, startup_frames=6, active_frames=4, recovery_frames=10, hitstun_frames=13, knockback=2.5, range_bonus=0, cancel_window=8),
        (AttackType.PUNCH, AttackHeight.HIGH, True): AttackData("Heavy High Punch", AttackType.PUNCH, AttackHeight.HIGH, base_damage=16, startup_frames=12, active_frames=5, recovery_frames=18, hitstun_frames=22, knockback=8.0, range_bonus=5, cancel_window=16, hitstop=8),
        (AttackType.PUNCH, AttackHeight.STRAIGHT, True): AttackData("Heavy Straight", AttackType.PUNCH, AttackHeight.STRAIGHT, base_damage=20, startup_frames=14, active_frames=6, recovery_frames=22, hitstun_frames=28, knockback=10.0, range_bonus=15, cancel_window=18, hitstop=10),
        (AttackType.PUNCH, AttackHeight.LOW, True): AttackData("Heavy Low Punch", AttackType.PUNCH, AttackHeight.LOW, base_damage=14, startup_frames=10, active_frames=4, recovery_frames=16, hitstun_frames=18, knockback=5.0, range_bonus=0, cancel_window=14, hitstop=8),
        (AttackType.KICK, AttackHeight.HIGH, True): AttackData("Heavy High Kick", AttackType.KICK, AttackHeight.HIGH, base_damage=22, startup_frames=16, active_frames=6, recovery_frames=24, hitstun_frames=30, knockback=12.0, range_bonus=10, cancel_window=20, hitstop=10),
        (AttackType.KICK, AttackHeight.STRAIGHT, True): AttackData("Heavy Straight Kick", AttackType.KICK, AttackHeight.STRAIGHT, base_damage=28, startup_frames=18, active_frames=8, recovery_frames=28, hitstun_frames=36, knockback=15.0, range_bonus=20, cancel_window=24, hitstop=12),
        (AttackType.KICK, AttackHeight.LOW, True): AttackData("Heavy Low Kick", AttackType.KICK, AttackHeight.LOW, base_damage=18, startup_frames=14, active_frames=5, recovery_frames=20, hitstun_frames=24, knockback=6.0, range_bonus=5, cancel_window=18, hitstop=8),
    }
    
    @classmethod
    def get_attack(cls, attack_type: AttackType, height: AttackHeight, full_power: bool) -> Optional[AttackData]:
        return cls.ATTACKS.get((attack_type, height, full_power))