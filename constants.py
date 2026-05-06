"""
Core constants, enumerations, and base data classes for the fighting game engine.
This file contains ONLY shared definitions — character-specific data lives in character_defs.py.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

# =============================================================================
# DISPLAY
# =============================================================================
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 700
FPS = 60
GROUND_Y = 550

# =============================================================================
# COLORS
# =============================================================================
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (220, 60, 60)
DARK_RED = (150, 40, 40)
BLUE = (60, 100, 220)
DARK_BLUE = (40, 70, 150)
GREEN = (60, 180, 60)
DARK_GREEN = (40, 120, 40)
YELLOW = (240, 200, 60)
ORANGE = (240, 140, 40)
PURPLE = (150, 60, 200)
CYAN = (60, 200, 220)
GRAY = (100, 100, 100)
LIGHT_GRAY = (180, 180, 180)
BROWN = (139, 90, 43)
DARK_BROWN = (90, 60, 30)
TEAL = (0, 128, 128)
MAGENTA = (200, 50, 150)

# =============================================================================
# PHYSICS (defaults — characters can override)
# =============================================================================
GRAVITY = 0.8
DEFAULT_JUMP_FORCE = -18
DEFAULT_WALK_SPEED = 5
DEFAULT_CROUCH_SPEED = 2
DEFAULT_HEALTH = 100

# =============================================================================
# INPUT BUFFER
# =============================================================================
INPUT_BUFFER_SIZE = 15
INPUT_BUFFER_ON_WAKEUP = 10
MOTION_BUFFER_SIZE = 60  # Track 1 second of directional input for motion detection

# =============================================================================
# GAME FEEL
# =============================================================================
DEFAULT_HITSTOP_FRAMES = 6
COYOTE_TIME_FRAMES = 3

# =============================================================================
# COMBO
# =============================================================================
COMBO_DECAY_WINDOW = 40  # frames before combo counter resets
MAX_COMBO_DAMAGE_SCALING = 0.3  # minimum damage multiplier at high combo counts

# =============================================================================
# ENUMS
# =============================================================================
class FighterState(Enum):
    """Core fighter states — extensible."""
    IDLE = auto()
    WALK_FORWARD = auto()
    WALK_BACKWARD = auto()
    JUMP = auto()
    CROUCH = auto()
    ATTACK_STARTUP = auto()
    ATTACK_ACTIVE = auto()
    ATTACK_RECOVERY = auto()
    BLOCK_STANDING = auto()
    BLOCK_CROUCHING = auto()
    HITSTUN = auto()
    KNOCKDOWN = auto()
    DASH_FORWARD = auto()
    DASH_BACKWARD = auto()
    STUN = auto()

class AttackType(Enum):
    """Basic attack categories."""
    PUNCH = "Punch"
    KICK = "Kick"
    SPECIAL = "Special"
    SUPER = "Super"
    THROW = "Throw"

class AttackHeight(Enum):
    """Attack height for high/low mixup game."""
    HIGH = "High"
    STRAIGHT = "Mid"
    LOW = "Low"
    OVERHEAD = "Overhead"  # Hits crouching opponents

class MoveType(Enum):
    """Classification of a move for system routing."""
    NORMAL = auto()       # Standard A/B button moves
    COMMAND_NORMAL = auto()  # f+P, b+K etc.
    SPECIAL = auto()      # Motion-input moves (fireballs, DPs)
    SUPER = auto()        # Meter-requiring moves
    THROW = auto()        # Command grabs
    UNIVERSAL = auto()    # Moves every character has

class FacingDirection(Enum):
    LEFT = -1
    RIGHT = 1

class BoxType(Enum):
    HITBOX = auto()
    HURTBOX = auto()
    PUSHBOX = auto()

class AttackProperty(Enum):
    """Flags that modify how a move behaves."""
    NONE = 0
    LAUNCHER = auto()        # Sends opponent airborne
    WALL_BOUNCE = auto()     # Bounces opponent off wall
    GROUND_BOUNCE = auto()   # Bounces opponent off ground
    CHAIN_CANCEL = auto()    # Can cancel into normals on hit
    SPECIAL_CANCEL = auto()  # Can cancel into specials on hit
    SUPER_CANCEL = auto()    # Can cancel into supers
    AIRBORNE = auto()        # Move launches the user airborne
    INVINCIBLE_STARTUP = auto()  # Strike invincible during startup
    INVINCIBLE_ALL = auto()      # Fully invincible during startup
    PROJECTILE = auto()      # Creates a projectile
    CHIP_KILLS = auto()      # Chip damage from block can kill
    LOW_PROFILE = auto()     # Avoids high attacks during startup
    ARMOR = auto()           # Absorbs one hit
    THROW = auto()           # Unblockable grab (requires proximity)
    GRANT_ARMOR = auto()     # Gives armor to the user during startup

class MotionType(Enum):
    """Input motion types for special moves."""
    NONE = auto()            # Just a button press
    QUARTER_CIRCLE_FORWARD = auto()   # ↓↘→ (QCF)
    QUARTER_CIRCLE_BACK = auto()      # ↓↙← (QCB)
    DRAGON_PUNCH_FORWARD = auto()     # →↓↘ (DP/F)
    DRAGON_PUNCH_BACK = auto()        # ←↓↙ (DP/B)
    HALF_CIRCLE_FORWARD = auto()      # ←↙↓↘→ (HCF)
    HALF_CIRCLE_BACK = auto()         # →↘↓↙← (HCB)
    CHARGE_BACK = auto()     # Hold ← 40+ frames then →
    CHARGE_DOWN = auto()     # Hold ↓ 40+ frames then ↑
    SUPER_CHARGE = auto()    # ↓↘→↓↘→ (double QCF)
    ZIGZAG = auto()          # ↓↑ (flash kick style)

# =============================================================================
# DATA CLASSES
# =============================================================================
@dataclass
class InputState:
    """Raw button/direction state for a single frame."""
    left: bool = False
    right: bool = False
    up: bool = False
    down: bool = False
    punch: bool = False
    kick: bool = False
    special: bool = False     # New: dedicated special move button
    heavy: bool = False       # Replaces "power" — more intuitive

    def has_attack(self) -> bool:
        return self.punch or self.kick or self.special

    def get_attack_buttons(self) -> List[str]:
        buttons = []
        if self.punch: buttons.append("punch")
        if self.kick: buttons.append("kick")
        if self.special: buttons.append("special")
        return buttons

    def get_direction(self) -> Optional[str]:
        """Returns primary direction or None if neutral/ambiguous."""
        if self.up and self.left: return "upleft"
        if self.up and self.right: return "upright"
        if self.down and self.left: return "downleft"
        if self.down and self.right: return "downright"
        if self.left: return "left"
        if self.right: return "right"
        if self.up: return "up"
        if self.down: return "down"
        return "neutral"

@dataclass
class BufferedInput:
    input_state: InputState
    frame_pressed: int
    consumed: bool = False

@dataclass
class AttackData:
    """Defines the properties of a single attack move."""
    name: str
    move_id: str               # Unique ID like "warrior_jab_high"
    attack_type: AttackType
    height: AttackHeight
    move_type: MoveType = MoveType.NORMAL
    base_damage: int = 10
    chip_damage: int = 1       # Damage on block
    startup_frames: int = 5
    active_frames: int = 3
    recovery_frames: int = 8
    hitstun_frames: int = 15
    blockstun_frames: int = 8
    knockback_x: float = 3.0
    knockback_y: float = 0.0   # Positive = launch upward
    range_x: int = 60          # Horizontal reach in pixels
    range_y: int = 30          # Vertical reach in pixels
    hitbox_offset_x: int = 0   # Relative to fighter edge
    hitbox_offset_y: int = 0
    hitbox_width: int = 45
    hitbox_height: int = 25
    hitstop: int = DEFAULT_HITSTOP_FRAMES
    cancel_window: int = 0     # Frames after hit where you can cancel
    properties: List[AttackProperty] = field(default_factory=list)

    @property
    def total_frames(self) -> int:
        return self.startup_frames + self.active_frames + self.recovery_frames

    @property
    def frame_advantage_on_hit(self) -> int:
        return self.hitstun_frames - self.recovery_frames

    @property
    def frame_advantage_on_block(self) -> int:
        return self.blockstun_frames - self.recovery_frames

    def has_property(self, prop: AttackProperty) -> bool:
        return prop in self.properties

@dataclass
class SpecialMoveDef:
    """Definition for a special/super move that requires motion input."""
    name: str
    move_id: str
    motion: MotionType
    attack_button: str          # "punch", "kick", or "special"
    attack_data: AttackData
    meter_cost: int = 0         # Super meter required (0 = no cost)
    is_super: bool = False
    is_ex: bool = False         # Enhanced version requiring meter

@dataclass
class Box:
    """Axis-aligned collision box."""
    x: int
    y: int
    width: int
    height: int
    box_type: BoxType

    def to_rect(self):
        """Lazy import to avoid circular dependency with pygame."""
        try:
            import pygame
            return pygame.Rect(self.x, self.y, self.width, self.height)
        except ImportError:
            return (self.x, self.y, self.width, self.height)

    def intersects(self, other: 'Box') -> bool:
        try:
            return self.to_rect().colliderect(other.to_rect())
        except (TypeError, AttributeError):
            # Fallback AABB intersection
            return not (self.x + self.width < other.x or
                       other.x + other.width < self.x or
                       self.y + self.height < other.y or
                       other.y + other.height < self.y)

@dataclass
class CharacterStats:
    """Physical stats that define a character's base properties."""
    max_health: int = DEFAULT_HEALTH
    walk_speed: float = DEFAULT_WALK_SPEED
    crouch_speed: float = DEFAULT_CROUCH_SPEED
    jump_force: float = DEFAULT_JUMP_FORCE
    forward_dash_speed: float = 12.0
    back_dash_speed: float = 8.0
    dash_duration: int = 12
    back_dash_duration: int = 15
    back_dash_invincible_frames: int = 5
    width: int = 60
    height: int = 120
    crouch_height: int = 80
    head_radius: int = 20
    gravity: float = GRAVITY

@dataclass
class CharacterColors:
    """Visual color palette for a character."""
    body: Tuple[int, int, int] = BLUE
    body_dark: Tuple[int, int, int] = DARK_BLUE
    limb: Tuple[int, int, int] = BLUE
    accent: Tuple[int, int, int] = CYAN
    eye: Tuple[int, int, int] = WHITE
    outline: Tuple[int, int, int] = BLACK
