"""
Character definitions — each character's stats, colors, moveset, and visual style.
To add a new character: create a new CharacterDef entry and register it in CHARACTER_REGISTRY.

Characters:
  - RYOKAN (Warrior): Balanced brawler. Good normals, fireball, DP uppercut.
  - SHADOW (Ninja): Fast, low HP. Teleport dash, command grab, low profile.
  - TITAN (Bruiser): Slow, high HP. Armored normals, grab super, massive damage.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from constants import (
    AttackType, AttackHeight, MoveType, AttackProperty, MotionType,
    AttackData, SpecialMoveDef, CharacterStats, CharacterColors,
    DARK_BLUE, RED, DARK_RED, BLUE, GREEN, DARK_GREEN, YELLOW, ORANGE,
    PURPLE, CYAN, GRAY, BLACK, WHITE, TEAL, MAGENTA, BROWN,
)

# =============================================================================
# CHARACTER DEFINITION
# =============================================================================
class BodyStyle:
    """Visual style identifiers for the procedural sprite renderer."""
    RECTANGLE = "rectangle"     # Standard upright body (like original)
    TRAPEZOID = "trapezoid"     # Broad shoulders, narrow waist (heavy)
    SLIM = "slim"               # Narrow, agile build
    ROUNDED = "rounded"         # Barrel-chested


@dataclass
class CharacterDef:
    """Complete definition for a playable character."""
    # Identity
    char_id: str
    name: str
    subtitle: str = ""

    # Physics
    stats: CharacterStats = field(default_factory=CharacterStats)

    # Visuals
    colors: CharacterColors = field(default_factory=CharacterColors)
    body_style: str = BodyStyle.RECTANGLE

    # Moveset: list of AttackData (normals + command normals)
    attacks: List[AttackData] = field(default_factory=list)

    # Special moves requiring motion inputs
    special_moves: List[SpecialMoveDef] = field(default_factory=list)

    # Unique mechanics
    has_air_dash: bool = False
    has_double_jump: bool = False
    has_wall_jump: bool = False
    armor_hits: int = 0          # How many hits this character can absorb

    def get_attack_by_id(self, move_id: str) -> Optional[AttackData]:
        for atk in self.attacks:
            if atk.move_id == move_id:
                return atk
        for sp in self.special_moves:
            if sp.attack_data.move_id == move_id:
                return sp.attack_data
        return None

    def get_normal_attacks(self) -> List[AttackData]:
        return [a for a in self.attacks if a.move_type in (MoveType.NORMAL, MoveType.COMMAND_NORMAL)]

    def get_special_attacks(self) -> List[SpecialMoveDef]:
        return self.special_moves


# =============================================================================
# RYOKAN — THE BALANCED WARRIOR
# =============================================================================
def _build_ryokan() -> CharacterDef:
    stats = CharacterStats(
        max_health=100, walk_speed=5.0, crouch_speed=2.0,
        jump_force=-18.0, width=60, height=120, crouch_height=80,
        head_radius=20,
    )
    colors = CharacterColors(
        body=(50, 100, 200), body_dark=(30, 70, 150),
        limb=(40, 80, 180), accent=(100, 180, 255),
        eye=WHITE, outline=BLACK,
    )
    attacks = [
        # --- Light Punches ---
        AttackData("Light Jab", "ryokan_lp_high", AttackType.PUNCH, AttackHeight.STRAIGHT,
                   base_damage=6, startup_frames=3, active_frames=3, recovery_frames=6,
                   hitstun_frames=12, blockstun_frames=6, knockback_x=2.0,
                   range_x=55, hitbox_width=40, hitbox_height=22,
                   cancel_window=4, properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL]),
        AttackData("Low Jab", "ryokan_lp_low", AttackType.PUNCH, AttackHeight.LOW,
                   base_damage=5, startup_frames=3, active_frames=3, recovery_frames=5,
                   hitstun_frames=10, blockstun_frames=5, knockback_x=1.5,
                   range_x=50, hitbox_height=20, hitbox_offset_y=40,
                   cancel_window=4, properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL]),

        # --- Heavy Punches ---
        AttackData("Strong Straight", "ryokan_hp_straight", AttackType.PUNCH, AttackHeight.STRAIGHT,
                   base_damage=14, startup_frames=8, active_frames=4, recovery_frames=12,
                   hitstun_frames=18, blockstun_frames=10, knockback_x=5.0,
                   range_x=70, hitbox_width=50, hitbox_height=28,
                   cancel_window=10, hitstop=8,
                   properties=[AttackProperty.SPECIAL_CANCEL]),
        AttackData("Overhead Smash", "ryokan_hp_high", AttackType.PUNCH, AttackHeight.OVERHEAD,
                   base_damage=16, startup_frames=12, active_frames=4, recovery_frames=16,
                   hitstun_frames=20, blockstun_frames=12, knockback_x=6.0,
                   range_x=60, hitbox_height=25, hitbox_offset_y=-30,
                   cancel_window=12, hitstop=8,
                   properties=[AttackProperty.SPECIAL_CANCEL]),

        # --- Light Kicks ---
        AttackData("Quick Kick", "ryokan_lk_straight", AttackType.KICK, AttackHeight.STRAIGHT,
                   base_damage=8, startup_frames=5, active_frames=3, recovery_frames=8,
                   hitstun_frames=12, blockstun_frames=6, knockback_x=3.0,
                   range_x=65, hitbox_width=45, hitbox_height=28,
                   cancel_window=6, properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL]),
        AttackData("Low Sweep", "ryokan_lk_low", AttackType.KICK, AttackHeight.LOW,
                   base_damage=7, startup_frames=6, active_frames=4, recovery_frames=10,
                   hitstun_frames=13, blockstun_frames=7, knockback_x=2.5,
                   range_x=60, hitbox_offset_y=35,
                   cancel_window=6, properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL, AttackProperty.LOW_PROFILE]),

        # --- Heavy Kicks ---
        AttackData("Roundhouse", "ryokan_hk_straight", AttackType.KICK, AttackHeight.STRAIGHT,
                   base_damage=16, startup_frames=10, active_frames=5, recovery_frames=16,
                   hitstun_frames=22, blockstun_frames=14, knockback_x=8.0,
                   range_x=85, hitbox_width=55, hitbox_height=32,
                   cancel_window=14, hitstop=8,
                   properties=[AttackProperty.SPECIAL_CANCEL, AttackProperty.SUPER_CANCEL]),
        AttackData("Heavy Sweep", "ryokan_hk_low", AttackType.KICK, AttackHeight.LOW,
                   base_damage=14, startup_frames=10, active_frames=5, recovery_frames=18,
                   hitstun_frames=20, blockstun_frames=14, knockback_x=6.0, knockback_y=2.0,
                   range_x=70, hitbox_offset_y=35,
                   cancel_window=14, hitstop=8,
                   properties=[AttackProperty.SPECIAL_CANCEL, AttackProperty.LAUNCHER]),
    ]

    specials = [
        # Fireball: QCF + Punch
        SpecialMoveDef("Fireball", "ryokan_fireball", MotionType.QUARTER_CIRCLE_FORWARD,
                       "punch",
                       AttackData("Fireball", "ryokan_fireball", AttackType.SPECIAL, AttackHeight.STRAIGHT,
                                 move_type=MoveType.SPECIAL, base_damage=12,
                                 startup_frames=10, active_frames=1, recovery_frames=20,
                                 hitstun_frames=18, blockstun_frames=10,
                                 knockback_x=10.0, range_x=300, hitbox_width=30, hitbox_height=30,
                                 hitstop=4, properties=[AttackProperty.PROJECTILE])),
        # Shoryuken: DP + Punch
        SpecialMoveDef("Rising Uppercut", "ryokan_uppercut", MotionType.DRAGON_PUNCH_FORWARD,
                       "punch",
                       AttackData("Rising Uppercut", "ryokan_uppercut", AttackType.SPECIAL, AttackHeight.HIGH,
                                 move_type=MoveType.SPECIAL, base_damage=18,
                                 startup_frames=3, active_frames=6, recovery_frames=24,
                                 hitstun_frames=28, blockstun_frames=14,
                                 knockback_x=5.0, knockback_y=-12.0,
                                 range_x=50, hitbox_height=60, hitbox_offset_y=-40,
                                 hitstop=10, properties=[AttackProperty.LAUNCHER, AttackProperty.INVINCIBLE_STARTUP])),
        # Tatsumaki: QCB + Kick
        SpecialMoveDef("Hurricane Kick", "ryokan_tatsumaki", MotionType.QUARTER_CIRCLE_BACK,
                       "kick",
                       AttackData("Hurricane Kick", "ryokan_tatsumaki", AttackType.SPECIAL, AttackHeight.STRAIGHT,
                                 move_type=MoveType.SPECIAL, base_damage=14,
                                 startup_frames=8, active_frames=12, recovery_frames=18,
                                 hitstun_frames=16, blockstun_frames=8,
                                 knockback_x=4.0, knockback_y=-6.0,
                                 range_x=70, hitbox_height=40,
                                 hitstop=4, properties=[AttackProperty.AIRBORNE])),
    ]

    return CharacterDef(
        char_id="ryokan", name="Ryokan", subtitle="The Balanced Warrior",
        stats=stats, colors=colors, body_style=BodyStyle.RECTANGLE,
        attacks=attacks, special_moves=specials,
    )


# =============================================================================
# SHADOW — THE SPEED NINJA
# =============================================================================
def _build_shadow() -> CharacterDef:
    stats = CharacterStats(
        max_health=80, walk_speed=6.5, crouch_speed=3.0,
        jump_force=-19.5, width=50, height=110, crouch_height=72,
        head_radius=17, forward_dash_speed=14.0, dash_duration=14,
    )
    colors = CharacterColors(
        body=(100, 20, 120), body_dark=(60, 10, 80),
        limb=(80, 15, 100), accent=(200, 80, 255),
        eye=(255, 200, 100), outline=BLACK,
    )
    attacks = [
        # --- Light Punches ---
        AttackData("Fast Jab", "shadow_lp_high", AttackType.PUNCH, AttackHeight.STRAIGHT,
                   base_damage=5, startup_frames=2, active_frames=2, recovery_frames=4,
                   hitstun_frames=10, blockstun_frames=5, knockback_x=1.5,
                   range_x=45, hitbox_width=35, hitbox_height=18,
                   cancel_window=5, properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL]),
        AttackData("Crouch Jab", "shadow_lp_low", AttackType.PUNCH, AttackHeight.LOW,
                   base_damage=4, startup_frames=2, active_frames=2, recovery_frames=4,
                   hitstun_frames=9, blockstun_frames=4, knockback_x=1.0,
                   range_x=40, hitbox_height=16, hitbox_offset_y=30,
                   cancel_window=5, properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL]),

        # --- Heavy Punches ---
        AttackData("Palm Strike", "shadow_hp_straight", AttackType.PUNCH, AttackHeight.STRAIGHT,
                   base_damage=12, startup_frames=7, active_frames=3, recovery_frames=10,
                   hitstun_frames=16, blockstun_frames=8, knockback_x=4.0,
                   range_x=60, hitbox_width=42, hitbox_height=24,
                   cancel_window=8, hitstop=6,
                   properties=[AttackProperty.SPECIAL_CANCEL]),
        AttackData("Axe Kick", "shadow_hp_high", AttackType.PUNCH, AttackHeight.OVERHEAD,
                   base_damage=14, startup_frames=10, active_frames=4, recovery_frames=14,
                   hitstun_frames=18, blockstun_frames=10, knockback_x=5.0,
                   range_x=55, hitbox_offset_y=-20,
                   cancel_window=10, hitstop=6,
                   properties=[AttackProperty.SPECIAL_CANCEL, AttackProperty.LAUNCHER]),

        # --- Light Kicks ---
        AttackData("Snap Kick", "shadow_lk_straight", AttackType.KICK, AttackHeight.STRAIGHT,
                   base_damage=6, startup_frames=4, active_frames=3, recovery_frames=6,
                   hitstun_frames=11, blockstun_frames=5, knockback_x=2.5,
                   range_x=55, hitbox_width=40, hitbox_height=24,
                   cancel_window=5, properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL]),
        AttackData("Ankle Kick", "shadow_lk_low", AttackType.KICK, AttackHeight.LOW,
                   base_damage=5, startup_frames=4, active_frames=2, recovery_frames=6,
                   hitstun_frames=10, blockstun_frames=4, knockback_x=2.0,
                   range_x=45, hitbox_offset_y=30,
                   cancel_window=5, properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL, AttackProperty.LOW_PROFILE]),

        # --- Heavy Kicks ---
        AttackData("Spinning Back Kick", "shadow_hk_straight", AttackType.KICK, AttackHeight.STRAIGHT,
                   base_damage=15, startup_frames=9, active_frames=5, recovery_frames=14,
                   hitstun_frames=20, blockstun_frames=12, knockback_x=10.0,
                   range_x=75, hitbox_width=50, hitbox_height=30,
                   cancel_window=12, hitstop=8,
                   properties=[AttackProperty.SPECIAL_CANCEL, AttackProperty.SUPER_CANCEL]),
        AttackData("Slide Kick", "shadow_hk_low", AttackType.KICK, AttackHeight.LOW,
                   base_damage=12, startup_frames=8, active_frames=6, recovery_frames=16,
                   hitstun_frames=16, blockstun_frames=8, knockback_x=8.0,
                   range_x=80, hitbox_offset_y=30, hitbox_width=55,
                   cancel_window=0, hitstop=4,
                   properties=[AttackProperty.LOW_PROFILE]),
    ]

    specials = [
        # Shadow Port: QCF + Punch (teleport dash)
        SpecialMoveDef("Shadow Port", "shadow_teleport", MotionType.QUARTER_CIRCLE_FORWARD,
                       "punch",
                       AttackData("Shadow Port", "shadow_teleport", AttackType.SPECIAL, AttackHeight.STRAIGHT,
                                 move_type=MoveType.SPECIAL, base_damage=0,
                                 startup_frames=4, active_frames=2, recovery_frames=8,
                                 hitstun_frames=0, blockstun_frames=0,
                                 knockback_x=0, range_x=0,
                                 hitstop=0, properties=[AttackProperty.INVINCIBLE_ALL])),
        # Command Grab: HCB + Kick
        SpecialMoveDef("Shadow Grab", "shadow_grab", MotionType.HALF_CIRCLE_BACK,
                       "kick",
                       AttackData("Shadow Grab", "shadow_grab", AttackType.SPECIAL, AttackHeight.STRAIGHT,
                                 move_type=MoveType.SPECIAL, base_damage=16,
                                 startup_frames=5, active_frames=3, recovery_frames=22,
                                 hitstun_frames=30, blockstun_frames=0,
                                 knockback_x=6.0, knockback_y=-10.0,
                                 range_x=50, hitbox_width=40, hitbox_height=50,
                                 hitstop=8, properties=[AttackProperty.THROW, AttackProperty.LAUNCHER, AttackProperty.INVINCIBLE_STARTUP])),
        # Kunai Toss: QCB + Punch (projectile)
        SpecialMoveDef("Kunai Toss", "shadow_kunai", MotionType.QUARTER_CIRCLE_BACK,
                       "punch",
                       AttackData("Kunai Toss", "shadow_kunai", AttackType.SPECIAL, AttackHeight.STRAIGHT,
                                 move_type=MoveType.SPECIAL, base_damage=8,
                                 startup_frames=6, active_frames=2, recovery_frames=14,
                                 hitstun_frames=12, blockstun_frames=6,
                                 knockback_x=6.0, range_x=250, hitbox_width=20, hitbox_height=12,
                                 hitstop=3, properties=[AttackProperty.PROJECTILE])),
    ]

    return CharacterDef(
        char_id="shadow", name="Shadow", subtitle="The Silent Assassin",
        stats=stats, colors=colors, body_style=BodyStyle.SLIM,
        attacks=attacks, special_moves=specials,
        has_air_dash=True, has_double_jump=True,
    )


# =============================================================================
# TITAN — THE HEAVY BRUISER
# =============================================================================
def _build_titan() -> CharacterDef:
    stats = CharacterStats(
        max_health=130, walk_speed=3.5, crouch_speed=1.5,
        jump_force=-15.0, width=75, height=130, crouch_height=90,
        head_radius=24, forward_dash_speed=9.0, dash_duration=15,
    )
    colors = CharacterColors(
        body=(200, 60, 40), body_dark=(150, 40, 30),
        limb=(180, 50, 35), accent=(255, 140, 40),
        eye=WHITE, outline=BLACK,
    )
    attacks = [
        # --- Light Punches ---
        AttackData("Power Jab", "titan_lp_straight", AttackType.PUNCH, AttackHeight.STRAIGHT,
                   base_damage=8, startup_frames=5, active_frames=3, recovery_frames=8,
                   hitstun_frames=14, blockstun_frames=8, knockback_x=3.0,
                   range_x=65, hitbox_width=50, hitbox_height=28,
                   cancel_window=5, hitstop=6,
                   properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL, AttackProperty.ARMOR]),
        AttackData("Low Slam", "titan_lp_low", AttackType.PUNCH, AttackHeight.LOW,
                   base_damage=7, startup_frames=5, active_frames=3, recovery_frames=7,
                   hitstun_frames=12, blockstun_frames=6, knockback_x=2.5,
                   range_x=55, hitbox_offset_y=40, hitbox_width=45, hitbox_height=25,
                   cancel_window=5, hitstop=6,
                   properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL, AttackProperty.ARMOR]),

        # --- Heavy Punches ---
        AttackData("Hammer Fist", "titan_hp_straight", AttackType.PUNCH, AttackHeight.STRAIGHT,
                   base_damage=22, startup_frames=12, active_frames=5, recovery_frames=18,
                   hitstun_frames=24, blockstun_frames=16, knockback_x=10.0,
                   range_x=80, hitbox_width=60, hitbox_height=35,
                   cancel_window=14, hitstop=12,
                   properties=[AttackProperty.SPECIAL_CANCEL, AttackProperty.SUPER_CANCEL, AttackProperty.ARMOR]),
        AttackData("Titan Slam", "titan_hp_high", AttackType.PUNCH, AttackHeight.OVERHEAD,
                   base_damage=26, startup_frames=16, active_frames=5, recovery_frames=22,
                   hitstun_frames=28, blockstun_frames=18, knockback_x=12.0, knockback_y=-4.0,
                   range_x=70, hitbox_width=55, hitbox_height=40, hitbox_offset_y=-30,
                   cancel_window=16, hitstop=14,
                   properties=[AttackProperty.SPECIAL_CANCEL, AttackProperty.LAUNCHER, AttackProperty.ARMOR]),

        # --- Light Kicks ---
        AttackData("Thrust Kick", "titan_lk_straight", AttackType.KICK, AttackHeight.STRAIGHT,
                   base_damage=10, startup_frames=7, active_frames=4, recovery_frames=10,
                   hitstun_frames=15, blockstun_frames=8, knockback_x=4.0,
                   range_x=70, hitbox_width=50, hitbox_height=30,
                   cancel_window=7, hitstop=6,
                   properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL]),
        AttackData("Low Crush", "titan_lk_low", AttackType.KICK, AttackHeight.LOW,
                   base_damage=9, startup_frames=8, active_frames=4, recovery_frames=12,
                   hitstun_frames=14, blockstun_frames=8, knockback_x=3.5,
                   range_x=65, hitbox_offset_y=35,
                   cancel_window=7, hitstop=6,
                   properties=[AttackProperty.CHAIN_CANCEL, AttackProperty.SPECIAL_CANCEL, AttackProperty.LOW_PROFILE]),

        # --- Heavy Kicks ---
        AttackData("Earth Shaker", "titan_hk_straight", AttackType.KICK, AttackHeight.STRAIGHT,
                   base_damage=28, startup_frames=16, active_frames=6, recovery_frames=24,
                   hitstun_frames=32, blockstun_frames=20, knockback_x=16.0, knockback_y=-4.0,
                   range_x=95, hitbox_width=65, hitbox_height=38,
                   cancel_window=18, hitstop=14,
                   properties=[AttackProperty.SPECIAL_CANCEL, AttackProperty.SUPER_CANCEL, AttackProperty.ARMOR, AttackProperty.WALL_BOUNCE]),
        AttackData("Earthquake Stomp", "titan_hk_low", AttackType.KICK, AttackHeight.LOW,
                   base_damage=20, startup_frames=14, active_frames=6, recovery_frames=22,
                   hitstun_frames=26, blockstun_frames=16, knockback_x=8.0, knockback_y=-8.0,
                   range_x=85, hitbox_offset_y=30, hitbox_width=60, hitbox_height=35,
                   cancel_window=16, hitstop=12,
                   properties=[AttackProperty.SPECIAL_CANCEL, AttackProperty.LAUNCHER, AttackProperty.ARMOR]),
    ]

    specials = [
        # Ground Pound: Charge Down + Kick
        SpecialMoveDef("Ground Pound", "titan_groundpound", MotionType.CHARGE_DOWN,
                       "kick",
                       AttackData("Ground Pound", "titan_groundpound", AttackType.SPECIAL, AttackHeight.LOW,
                                 move_type=MoveType.SPECIAL, base_damage=20,
                                 startup_frames=6, active_frames=8, recovery_frames=24,
                                 hitstun_frames=24, blockstun_frames=16,
                                 knockback_x=12.0, knockback_y=-10.0,
                                 range_x=120, hitbox_width=80, hitbox_height=40,
                                 hitstop=10, properties=[AttackProperty.LAUNCHER, AttackProperty.ARMOR, AttackProperty.GROUND_BOUNCE])),
        # Armor Rush: Charge Back + Punch
        SpecialMoveDef("Armor Rush", "titan_armorrush", MotionType.CHARGE_BACK,
                       "punch",
                       AttackData("Armor Rush", "titan_armorrush", AttackType.SPECIAL, AttackHeight.STRAIGHT,
                                 move_type=MoveType.SPECIAL, base_damage=24,
                                 startup_frames=8, active_frames=6, recovery_frames=20,
                                 hitstun_frames=22, blockstun_frames=14,
                                 knockback_x=14.0,
                                 range_x=90, hitbox_width=60, hitbox_height=40,
                                 hitstop=10, properties=[AttackProperty.ARMOR, AttackProperty.INVINCIBLE_STARTUP])),
        # Mega Slam: 360 + Punch (grab)
        SpecialMoveDef("Mega Slam", "titan_megaslam", MotionType.HALF_CIRCLE_FORWARD,
                       "punch",
                       AttackData("Mega Slam", "titan_megaslam", AttackType.SPECIAL, AttackHeight.STRAIGHT,
                                 move_type=MoveType.SPECIAL, base_damage=30,
                                 startup_frames=6, active_frames=4, recovery_frames=26,
                                 hitstun_frames=36, blockstun_frames=0,
                                 knockback_x=8.0, knockback_y=-14.0,
                                 range_x=60, hitbox_width=50, hitbox_height=55,
                                 hitstop=12, properties=[AttackProperty.THROW, AttackProperty.LAUNCHER, AttackProperty.INVINCIBLE_STARTUP, AttackProperty.WALL_BOUNCE])),
    ]

    return CharacterDef(
        char_id="titan", name="Titan", subtitle="The Unstoppable Force",
        stats=stats, colors=colors, body_style=BodyStyle.TRAPEZOID,
        attacks=attacks, special_moves=specials,
        armor_hits=1,
    )


# =============================================================================
# CHARACTER REGISTRY
# =============================================================================
CHARACTER_REGISTRY: Dict[str, CharacterDef] = {}

def _register_all():
    for builder in [_build_ryokan, _build_shadow, _build_titan]:
        char = builder()
        CHARACTER_REGISTRY[char.char_id] = char

_register_all()


def get_character(char_id: str) -> Optional[CharacterDef]:
    """Look up a character definition by ID."""
    return CHARACTER_REGISTRY.get(char_id)


def get_all_characters() -> List[CharacterDef]:
    """Return all registered characters."""
    return list(CHARACTER_REGISTRY.values())


def get_character_choices() -> List[Tuple[str, str, str]]:
    """Return (char_id, name, subtitle) for character select."""
    return [(c.char_id, c.name, c.subtitle) for c in get_all_characters()]
