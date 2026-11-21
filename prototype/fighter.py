"""
Fighter — the core character controller, refactored to be lean and modular.
Delegates input to InputHandler, moves to MoveResolver, and rendering to FighterRenderer.
"""

import math
from typing import Optional, List, Tuple

import pygame

from constants import (
    GROUND_Y, SCREEN_WIDTH, COYOTE_TIME_FRAMES, COMBO_DECAY_WINDOW, MAX_COMBO_DAMAGE_SCALING,
    FighterState, AttackType, AttackHeight, AttackProperty, FacingDirection, MoveType,
    InputState, AttackData, Box, BoxType, CharacterStats,
)
from character_defs import CharacterDef
from input_handler import InputHandler
from move_system import MoveResolver
from animator import FighterRenderer


class Fighter:
    """
    A playable fighter character. Wraps a CharacterDef and provides:
    - State machine (idle, walk, jump, crouch, attack, hitstun, knockdown, etc.)
    - Physics (gravity, knockback, screen shake)
    - Collision boxes (hurtbox, pushbox, hitbox)
    - Combo tracking with damage scaling

    Does NOT handle rendering directly — that's the FighterRenderer's job.
    Does NOT handle AI — that's the AIController's job.
    """

    def __init__(self, character: CharacterDef, x: int, player_id: int = 1):
        self.character = character
        self.player_id = player_id
        self.stats = character.stats

        # Position
        self.pos_x = float(x)
        self.pos_y = float(GROUND_Y)
        self.render_x = float(x)
        self.render_y = float(GROUND_Y)
        self.vel_x = 0.0
        self.vel_y = 0.0

        # Screen shake
        self.screen_shake_x = 0.0
        self.screen_shake_y = 0.0

        # State
        self.state = FighterState.IDLE
        self.facing = FacingDirection.RIGHT
        self.state_timer = 0

        # Health
        self.max_health = self.stats.max_health
        self.health = self.max_health

        # Super meter
        self.super_meter = 0
        self.max_super_meter = 100

        # Attack state
        self.current_attack: Optional[AttackData] = None
        self.attack_frame = 0
        self.has_hit_opponent = False
        self.can_cancel_attack = False

        # Hitstun / blockstun
        self.hitstop_frames = 0
        self.hitstun_frames = 0
        self.blockstun_frames = 0
        self.hitstun_direction = 0

        # Blocking. block_direction is the SCREEN direction being held away
        # (-1 = holding left, +1 = holding right, 0 = not blocking).
        self.is_blocking = False
        self.block_direction = 0
        self.block_crouching = False
        self.attack_was_blocked = False
        self.attack_started_airborne = False

        # Combo
        self.combo_count = 0
        self.combo_damage = 0
        self.last_hit_frame = -999

        # Frame advantage display
        self.last_frame_advantage = 0
        self.frame_adv_timer = 0

        # Coyote time
        self.coyote_time_remaining = 0
        self.was_grounded_last_frame = True

        # Dash
        self.dash_timer = 0
        self.dash_speed = 0.0

        # Knockdown
        self.knockdown_timer = 0

        # Air movement
        self.jumps_remaining = 2 if character.has_double_jump else 1
        self.air_dash_used = False

        # Armor
        self.armor_hits_remaining = character.armor_hits

        # Collision boxes
        self.hurtboxes: List[Box] = []
        self.active_hitbox: Optional[Box] = None
        self.pushbox: Optional[Box] = None

        # Subsystems
        self.input_handler = InputHandler(player_id)
        self.move_resolver = MoveResolver(character)
        self.renderer = FighterRenderer(character)

        self._update_boxes()

    # =========================================================================
    # PROPERTIES
    # =========================================================================
    @property
    def x(self) -> int:
        return int(self.pos_x)

    @property
    def y(self) -> int:
        return int(self.pos_y)

    @property
    def is_crouching(self) -> bool:
        if self.state in (FighterState.CROUCH, FighterState.BLOCK_CROUCHING):
            return True
        return self.state == FighterState.BLOCKSTUN and self.block_crouching

    @property
    def current_height(self) -> int:
        if self.is_crouching:
            return self.stats.crouch_height
        if self.current_attack and self.current_attack.height == AttackHeight.LOW:
            return self.stats.crouch_height
        return self.stats.height

    @property
    def is_grounded(self) -> bool:
        return self.pos_y >= GROUND_Y

    @property
    def can_act(self) -> bool:
        return self.state in (
            FighterState.IDLE, FighterState.WALK_FORWARD, FighterState.WALK_BACKWARD,
            FighterState.JUMP, FighterState.CROUCH,
        )

    @property
    def can_attack(self) -> bool:
        # Air attacks are allowed: JUMP is an actionable state.
        return self.can_act

    @property
    def is_in_attack_state(self) -> bool:
        return self.state in (
            FighterState.ATTACK_STARTUP, FighterState.ATTACK_ACTIVE, FighterState.ATTACK_RECOVERY,
        )

    @property
    def facing_right(self) -> bool:
        return self.facing == FacingDirection.RIGHT

    # =========================================================================
    # MAIN UPDATE
    # =========================================================================
    def update(self, opponent: 'Fighter', current_frame: int, keys_pressed=None, ai_input=None):
        """Main update — called every frame by the game loop."""
        # The attacker's combo ends once the opponent is no longer stunned.
        if self.combo_count and opponent.state not in (FighterState.HITSTUN, FighterState.KNOCKDOWN):
            self.combo_count = 0
            self.combo_damage = 0

        # Process input
        if ai_input is not None:
            current_input = self.input_handler.push_ai_input(ai_input)
        else:
            current_input = self.input_handler.read_keyboard(keys_pressed)

        # Update motion detector with facing
        facing_int = 1 if self.facing_right else -1
        self.input_handler.update_motion_direction(current_input.get_direction(), facing_int)

        # Hitstop freeze: no state, no physics (knockback is applied after the freeze)
        if self.hitstop_frames > 0:
            self.hitstop_frames -= 1
            self._update_render_position()
            self.renderer.update(self.state, self.current_attack)
            return

        # State machine
        self._update_state(current_input, opponent, current_frame)

        # Physics
        self._apply_physics()

        # Update collision boxes
        self._update_boxes()

        # Update timers
        self.state_timer += 1
        if self.frame_adv_timer > 0:
            self.frame_adv_timer -= 1

        # Update render position
        self._update_render_position()

        # Update animator
        self.renderer.update(self.state, self.current_attack)

    def _update_state(self, current_input: InputState, opponent: 'Fighter', frame: int):
        """Route to the appropriate state handler."""
        if self.state == FighterState.HITSTUN:
            self._update_hitstun()
        elif self.state == FighterState.BLOCKSTUN:
            self._update_blockstun(current_input)
        elif self.state == FighterState.KNOCKDOWN:
            self._update_knockdown()
        elif self.is_in_attack_state:
            self._update_attack(opponent, frame)
        elif self.state in (FighterState.DASH_FORWARD, FighterState.DASH_BACKWARD):
            self._update_dash()
        else:
            # Can act — face opponent, attacks take priority over movement
            # (so up+button on the frame of a charge release doesn't jump).
            self.face_target(opponent.x)
            if self._check_attack_input(current_input, frame):
                return
            self._update_movement(current_input)

    # =========================================================================
    # MOVEMENT
    # =========================================================================
    def _update_movement(self, inp: InputState):
        """Handle movement states: idle, walk, crouch, jump, block, dash."""
        self.block_direction = 0
        self.is_blocking = False
        self.block_crouching = False
        prev = self.input_handler.get_previous()

        is_back = ((inp.left and self.facing_right) or
                   (inp.right and not self.facing_right))
        is_forward = ((inp.right and self.facing_right) or
                      (inp.left and not self.facing_right))
        back_sign = -1 if self.facing_right else 1   # screen direction of "back"

        if self.is_grounded:
            self.vel_x = 0

            # Jump (direction chosen at take-off)
            if inp.up and not inp.down and self.jumps_remaining > 0:
                self.vel_y = self.stats.jump_force
                self.vel_x = self.stats.walk_speed * (1 if inp.right else -1 if inp.left else 0)
                self.state = FighterState.JUMP
                self.jumps_remaining -= 1
                self.coyote_time_remaining = 0
                self.air_dash_used = False
                return

            if inp.down:
                # Crouching. Only down+back blocks (plain down does not).
                self.state = FighterState.CROUCH
                if is_back:
                    self.is_blocking = True
                    self.block_crouching = True
                    self.block_direction = back_sign
            elif is_back:
                # Walking backward also guards (standing block)
                self.vel_x = back_sign * self.stats.walk_speed
                self.is_blocking = True
                self.block_direction = back_sign
                self.state = FighterState.WALK_BACKWARD
            elif is_forward:
                self.vel_x = -back_sign * self.stats.walk_speed
                self.state = FighterState.WALK_FORWARD
            else:
                self.state = FighterState.IDLE

            # Dash: heavy + direction (no attack button)
            heavy_pressed = inp.heavy and not prev.heavy
            if heavy_pressed and not inp.punch and not inp.kick and not inp.down:
                if is_forward:
                    self._start_dash(forward=True)
                elif is_back:
                    self._start_dash(forward=False)
        else:
            # Air control
            if inp.left:
                self.vel_x = -self.stats.walk_speed * 0.6
            elif inp.right:
                self.vel_x = self.stats.walk_speed * 0.6

            # Double jump needs a fresh press of up
            if inp.up and not prev.up and self.jumps_remaining > 0:
                self.vel_y = self.stats.jump_force * 0.85
                self.jumps_remaining -= 1

            # Air dash
            if (self.character.has_air_dash and not self.air_dash_used
                    and inp.heavy and not prev.heavy):
                self._start_dash(forward=True, is_air=True)
                self.air_dash_used = True

        # Coyote time
        if self.was_grounded_last_frame and not self.is_grounded:
            self.coyote_time_remaining = COYOTE_TIME_FRAMES
        elif self.is_grounded:
            self.coyote_time_remaining = 0
        self.was_grounded_last_frame = self.is_grounded
        if self.coyote_time_remaining > 0:
            self.coyote_time_remaining -= 1

    def _start_dash(self, forward: bool, is_air: bool = False):
        """Start a forward or backward dash."""
        if forward:
            self.state = FighterState.DASH_FORWARD
            self.dash_timer = self.stats.dash_duration
            self.dash_speed = self.stats.forward_dash_speed * (1 if self.facing_right else -1)
        else:
            self.state = FighterState.DASH_BACKWARD
            self.dash_timer = self.stats.back_dash_duration
            self.dash_speed = -self.stats.back_dash_speed * (1 if self.facing_right else -1)

    def _update_dash(self):
        """Update dash state."""
        self.dash_timer -= 1
        self.vel_x = self.dash_speed
        if self.dash_timer <= 0:
            self.state = FighterState.IDLE if self.is_grounded else FighterState.JUMP
            self.vel_x = 0

    # =========================================================================
    # ATTACK SYSTEM
    # =========================================================================
    def _check_attack_input(self, current_input: InputState, frame: int) -> bool:
        """Check for attack inputs and resolve them via MoveResolver. Returns True if one started."""
        if not self.can_attack:
            return False

        # Buffered attacks first (pressed during recovery/stun, replayed now)
        if self.input_handler.has_buffered_attack():
            buffered = self.input_handler.consume_buffered_attack()
            if buffered and self._resolve_and_start_attack(buffered, frame):
                return True

        # Fresh press this frame
        if current_input.has_attack() and self._has_fresh_press(current_input):
            return self._resolve_and_start_attack(current_input, frame)
        return False

    def _has_fresh_press(self, inp: InputState) -> bool:
        prev = self.input_handler.get_previous()
        return ((inp.punch and not prev.punch) or (inp.kick and not prev.kick)
                or (inp.special and not prev.special))

    def _resolve_attack(self, inp: InputState) -> Optional[AttackData]:
        return self.move_resolver.resolve_input(
            inp, self.state, self.is_grounded, self.facing_right,
            self.input_handler.motion_detector, self.super_meter,
        )

    def _resolve_and_start_attack(self, inp: InputState, frame: int) -> bool:
        """Use MoveResolver to find the right attack and start it."""
        attack = self._resolve_attack(inp)
        if attack:
            self.start_attack(attack)
            return True
        return False

    def start_attack(self, attack: AttackData):
        """Begin executing an attack."""
        self.current_attack = attack
        self.attack_frame = 0
        self.state = FighterState.ATTACK_STARTUP
        self.has_hit_opponent = False
        self.attack_was_blocked = False
        self.can_cancel_attack = False
        self.attack_started_airborne = not self.is_grounded
        if self.is_grounded:
            self.vel_x = 0          # keep air momentum for jump-ins
        self.active_hitbox = None
        self.is_blocking = False
        self.block_direction = 0
        if attack.move_type in (MoveType.SPECIAL, MoveType.SUPER):
            # Specials consume the motion (and any stored charge)
            self.input_handler.motion_detector.consume()
            self.input_handler.reset_charges()

    def _cancel_allowed(self, current: AttackData, nxt: AttackData) -> bool:
        if nxt.move_type == MoveType.SUPER:
            return current.has_property(AttackProperty.SUPER_CANCEL)
        if nxt.move_type == MoveType.SPECIAL:
            return current.has_property(AttackProperty.SPECIAL_CANCEL)
        return current.has_property(AttackProperty.CHAIN_CANCEL) and nxt is not current

    def _update_attack(self, opponent: 'Fighter', frame: int):
        """Process the attack through startup -> active -> recovery."""
        self.attack_frame += 1
        if not self.current_attack:
            self.state = FighterState.IDLE
            return

        atk = self.current_attack
        startup_end = atk.startup_frames
        active_end = startup_end + atk.active_frames
        recovery_end = active_end + atk.recovery_frames

        if self.attack_frame < startup_end:
            self.state = FighterState.ATTACK_STARTUP
            self.active_hitbox = None
        elif self.attack_frame < active_end:
            self.state = FighterState.ATTACK_ACTIVE
            self.active_hitbox = self.calculate_attack_hitbox()
            if not self.has_hit_opponent and self.active_hitbox:
                self._check_hit(opponent)
        else:
            self.state = FighterState.ATTACK_RECOVERY
            self.active_hitbox = None

        # Cancel window check
        self.can_cancel_attack = (
            self.has_hit_opponent and
            atk.cancel_window > 0 and
            self.attack_frame >= startup_end + atk.active_frames and
            self.attack_frame < recovery_end and
            self.attack_frame < startup_end + atk.active_frames + atk.cancel_window
        )

        # Cancel (fresh press only) into an allowed follow-up
        if self.can_cancel_attack:
            # Presses made during hitstop are in the buffer, so check it too
            current_input = self.input_handler.get_current()
            candidate = None
            if current_input.has_attack() and self._has_fresh_press(current_input):
                candidate = current_input
            elif self.input_handler.has_buffered_attack():
                candidate = self.input_handler.consume_buffered_attack()
            if candidate is not None:
                nxt = self._resolve_attack(candidate)
                if nxt and self._cancel_allowed(atk, nxt):
                    self.start_attack(nxt)
                    return

        # Attack finished
        if self.attack_frame >= recovery_end:
            self.state = FighterState.IDLE
            self.current_attack = None
            self.attack_frame = 0
            self.active_hitbox = None
            self.can_cancel_attack = False

    def _check_hit(self, opponent: 'Fighter'):
        """Check if active hitbox connects with opponent's hurtboxes."""
        if not self.active_hitbox:
            return
        for hurtbox in opponent.hurtboxes:
            if self.active_hitbox.intersects(hurtbox) and self._check_height_interaction(opponent):
                self._apply_hit(opponent)
                break

    def _check_height_interaction(self, opponent: 'Fighter') -> bool:
        """Does the attack's height allow it to touch the opponent at all?"""
        atk = self.current_attack
        if not atk:
            return False
        # High attacks whiff over crouching opponents
        if atk.height == AttackHeight.HIGH and opponent.is_crouching:
            return False
        return True

    def _is_block_correct(self, opponent: 'Fighter') -> bool:
        """
        Is the opponent guarding correctly against the current attack?
        - must hold AWAY from the attacker (by position, so cross-ups work)
        - lows must be blocked crouching, overheads standing
        """
        atk = self.current_attack
        if not opponent.is_blocking or atk is None:
            return False
        if opponent.x != self.x:
            away = 1 if opponent.x > self.x else -1
        else:
            away = 1 if self.facing_right else -1
        if opponent.block_direction != away:
            return False
        if atk.height == AttackHeight.LOW and not opponent.block_crouching:
            return False
        if atk.height == AttackHeight.OVERHEAD and opponent.block_crouching:
            return False
        return True

    def _apply_hit(self, opponent: 'Fighter'):
        """Apply damage, knockback, hitstun to the opponent."""
        atk = self.current_attack
        self.hitstun_direction = 1 if self.x > opponent.x else -1
        is_throw = atk.has_property(AttackProperty.THROW)

        # Throws are unblockable; everything else checks direction + height
        if not is_throw and self._is_block_correct(opponent):
            self._apply_block(opponent, atk)
            return

        # Wrong guard (direction or height) — they take the hit
        opponent.is_blocking = False
        opponent.block_direction = 0

        # --- Apply clean hit ---
        # Damage scaling based on combo count
        scaling = max(MAX_COMBO_DAMAGE_SCALING, 1.0 - (self.combo_count * 0.08))
        damage = max(1, int(atk.base_damage * scaling))

        opponent.health = max(0, opponent.health - damage)
        opponent.hitstun_frames = atk.hitstun_frames
        opponent.hitstun_direction = self.hitstun_direction * -1
        opponent.hitstop_frames = atk.hitstop

        # Knockback
        if is_throw:
            opponent.vel_x = atk.knockback_x * (1 if self.facing_right else -1)
            opponent.vel_y = atk.knockback_y if atk.knockback_y < 0 else -10
        else:
            opponent.vel_x = atk.knockback_x * opponent.hitstun_direction
            opponent.vel_y = atk.knockback_y

        opponent.state = FighterState.KNOCKDOWN if atk.has_property(AttackProperty.LAUNCHER) else FighterState.HITSTUN
        opponent.current_attack = None
        opponent.active_hitbox = None

        # Self hitstop
        self.hitstop_frames = atk.hitstop

        # Frame advantage
        self.last_frame_advantage = atk.frame_advantage_on_hit
        self.frame_adv_timer = 60

        # Screen shake on opponent
        opponent.screen_shake_x = atk.knockback_x * 0.5

        # Combo tracking
        current_frame = self.input_handler.current_frame
        if current_frame - self.last_hit_frame > COMBO_DECAY_WINDOW:
            self.combo_count = 0
            self.combo_damage = 0
        self.combo_count += 1
        self.combo_damage += damage
        self.last_hit_frame = current_frame

        # Super meter gain
        self.super_meter = min(self.max_super_meter, self.super_meter + 5 + damage // 4)
        opponent.super_meter = min(opponent.max_super_meter, opponent.super_meter + 2)

        # VFX triggers
        self.has_hit_opponent = True
        self.renderer.anim.trigger_hit_flash()

    def _apply_block(self, opponent: 'Fighter', atk: AttackData):
        """Apply blocked hit — reduced damage, reduced hitstun. Only called when block is correct."""
        chip = atk.chip_damage
        if chip > 0 and not atk.has_property(AttackProperty.CHIP_KILLS):
            opponent.health = max(1, opponent.health - chip)
        elif chip > 0:
            opponent.health = max(0, opponent.health - chip)

        opponent.state = FighterState.BLOCKSTUN
        opponent.blockstun_frames = atk.blockstun_frames
        opponent.hitstop_frames = atk.hitstop // 2
        opponent.hitstun_direction = self.hitstun_direction * -1
        opponent.vel_x = atk.knockback_x * 0.4 * opponent.hitstun_direction
        self.attack_was_blocked = True

        self.hitstop_frames = atk.hitstop // 2
        self.last_frame_advantage = atk.frame_advantage_on_block
        self.frame_adv_timer = 60
        self.has_hit_opponent = True

        opponent.renderer.anim.trigger_block_flash()

        # Small meter gain on block
        self.super_meter = min(self.max_super_meter, self.super_meter + 2)
        opponent.super_meter = min(opponent.max_super_meter, opponent.super_meter + 3)

    # =========================================================================
    # HITSTUN / KNOCKDOWN
    # =========================================================================
    def _update_hitstun(self):
        """Update hitstun state."""
        self.hitstun_frames -= 1
        self.vel_x *= 0.95

        if self.hitstun_frames <= 0 and self.is_grounded:
            self.state = FighterState.IDLE
            self.vel_x = 0

    def _update_blockstun(self, inp: InputState):
        """Blockstun: can't act, but guard is held and its height may be changed."""
        self.blockstun_frames -= 1
        self.vel_x *= 0.9
        self.is_blocking = True
        self.block_crouching = inp.down
        if self.blockstun_frames <= 0:
            self.state = FighterState.CROUCH if inp.down else FighterState.IDLE
            self.vel_x = 0

    def _update_knockdown(self):
        """Update knockdown state."""
        self.knockdown_timer += 1
        self.hitstun_frames -= 1
        self.vel_x *= 0.92

        if self.is_grounded and self.vel_y >= 0 and self.hitstun_frames <= 0:
            self.knockdown_timer = 0
            self.state = FighterState.IDLE
            self.vel_x = 0

    # =========================================================================
    # PHYSICS
    # =========================================================================
    def _apply_physics(self):
        """Apply gravity, velocity, and boundaries."""
        if not self.is_grounded:
            self.vel_y += self.stats.gravity
        self.pos_x += self.vel_x
        self.pos_y += self.vel_y

        if self.pos_y > GROUND_Y:
            self.pos_y = GROUND_Y
            self.vel_y = 0
            self.jumps_remaining = 2 if self.character.has_double_jump else 1
            if self.state == FighterState.JUMP:
                self.state = FighterState.IDLE
            elif self.is_in_attack_state and self.attack_started_airborne:
                # Landing cancels an air attack
                self.state = FighterState.IDLE
                self.current_attack = None
                self.active_hitbox = None
                self.attack_frame = 0
                self.vel_x = 0

        # Screen boundaries
        hw = self.stats.width // 2
        self.pos_x = max(hw, min(SCREEN_WIDTH - hw, self.pos_x))

    def _update_render_position(self):
        """Apply screen shake to render position."""
        self.render_x = self.pos_x + self.screen_shake_x
        self.render_y = self.pos_y + self.screen_shake_y
        self.screen_shake_x *= 0.88
        self.screen_shake_y *= 0.88

    # =========================================================================
    # COLLISION BOXES
    # =========================================================================
    def _update_boxes(self):
        """Recalculate hurtboxes and pushbox based on current state/position."""
        self.hurtboxes.clear()
        h = self.current_height
        w = self.stats.width

        # Main body hurtbox
        self.hurtboxes.append(Box(
            self.x - w // 2 + 5, self.y - h + 5,
            w - 10, h - 5, BoxType.HURTBOX
        ))
        # Head hurtbox
        hr = self.stats.head_radius
        self.hurtboxes.append(Box(
            self.x - hr, self.y - h - hr * 2,
            hr * 2, hr * 2, BoxType.HURTBOX
        ))

        # Pushbox
        self.pushbox = Box(
            self.x - w // 2, self.y - h,
            w, h, BoxType.PUSHBOX
        )

    def calculate_attack_hitbox(self) -> Optional[Box]:
        """Calculate the hitbox for the current attack."""
        if not self.current_attack:
            return None
        atk = self.current_attack
        hw = self.stats.width // 2

        # Base hitbox position
        if self.facing_right:
            hx = self.x + hw - 5 + atk.hitbox_offset_x
        else:
            hx = self.x - hw - atk.hitbox_width + 5 - atk.hitbox_offset_x

        # Vertical positioning based on attack height
        # LOW and OVERHEAD are anchored to the body (hitbox_offset_y is ignored):
        # the old formula put lows under the floor and overheads above a
        # crouching opponent, so neither could ever connect.
        h = self.current_height
        if atk.height == AttackHeight.HIGH:
            hy = self.y - h - 5 + atk.hitbox_offset_y
        elif atk.height == AttackHeight.OVERHEAD:
            # chest-to-waist height: tall enough to hit standing AND crouching bodies
            hy = self.y - self.stats.height // 2 - atk.hitbox_height
        elif atk.height == AttackHeight.LOW:
            hy = self.y - atk.hitbox_height - 2   # at the feet
        else:  # STRAIGHT / MID
            hy = self.y - h // 2 - atk.hitbox_height // 2 + atk.hitbox_offset_y

        return Box(hx, hy, atk.hitbox_width, atk.hitbox_height, BoxType.HITBOX)

    # =========================================================================
    # UTILITY
    # =========================================================================
    def face_target(self, target_x: int):
        """Auto-face the opponent."""
        if self.state in (FighterState.HITSTUN, FighterState.KNOCKDOWN):
            return
        if self.is_in_attack_state:
            return
        if target_x < self.x:
            self.facing = FacingDirection.LEFT
        else:
            self.facing = FacingDirection.RIGHT

    def reset(self, x: int):
        """Reset fighter to starting position."""
        self.pos_x = float(x)
        self.pos_y = float(GROUND_Y)
        self.render_x = float(x)
        self.render_y = float(GROUND_Y)
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.state = FighterState.IDLE
        self.health = self.max_health
        self.super_meter = 0
        self.current_attack = None
        self.attack_frame = 0
        self.hitstop_frames = 0
        self.hitstun_frames = 0
        self.combo_count = 0
        self.combo_damage = 0
        self.dash_timer = 0
        self.knockdown_timer = 0
        self.blockstun_frames = 0
        self.is_blocking = False
        self.block_direction = 0
        self.block_crouching = False
        self.has_hit_opponent = False
        self.attack_was_blocked = False
        self.jumps_remaining = 2 if self.character.has_double_jump else 1
        self.input_handler.clear()
        self.renderer.anim.hit_flash_frames = 0
        self.renderer.anim.block_flash_frames = 0
        self._update_boxes()

    def get_combo_damage_scaling(self) -> float:
        """Return current damage scaling multiplier based on combo count."""
        return max(MAX_COMBO_DAMAGE_SCALING, 1.0 - (self.combo_count * 0.08))
