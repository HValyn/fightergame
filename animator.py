"""
Animation System — controls sprite/animation state and provides per-character
procedural drawing. Each character has a unique visual silhouette through
custom draw functions.

To add visuals for a new character, add a draw function to CHAR_DRAWERS
and register it in the Animator class.
"""

import math
from typing import Optional, Tuple

import pygame

from constants import (
    FighterState, AttackType, AttackHeight, AttackData,
    FacingDirection,
    WHITE, BLACK, CYAN, ORANGE, YELLOW, RED, GREEN, BLUE,
)
from character_defs import CharacterDef, BodyStyle


class AnimationController:
    """
    Manages animation state for a fighter.
    Tracks current animation, frame progression, and provides the
    correct draw function for the character's style.
    """

    def __init__(self, character: CharacterDef):
        self.character = character
        self.anim_frame = 0
        self.state_timer = 0
        self.current_state = FighterState.IDLE

        # Hit flash effect
        self.hit_flash_frames = 0
        self.block_flash_frames = 0

    def update(self, state: FighterState, attack: Optional[AttackData] = None):
        """Advance animation by one frame."""
        if state != self.current_state:
            self.current_state = state
            self.state_timer = 0
        else:
            self.state_timer += 1

        self.anim_frame = (self.anim_frame + 1) % 120

        if self.hit_flash_frames > 0:
            self.hit_flash_frames -= 1
        if self.block_flash_frames > 0:
            self.block_flash_frames -= 1

    def trigger_hit_flash(self):
        self.hit_flash_frames = 6

    def trigger_block_flash(self):
        self.block_flash_frames = 4

    def get_body_color(self) -> Tuple[int, int, int]:
        """Get the current body color, accounting for hit/block flash."""
        if self.hit_flash_frames > 0:
            return WHITE
        if self.block_flash_frames > 0:
            return CYAN
        if self.current_state == FighterState.ATTACK_ACTIVE:
            return ORANGE
        if self.current_state == FighterState.ATTACK_STARTUP:
            return YELLOW
        return self.character.colors.body

    def get_limb_color(self) -> Tuple[int, int, int]:
        if self.hit_flash_frames > 0:
            return WHITE
        return self.character.colors.limb


class FighterRenderer:
    """
    Renders a fighter character using procedural drawing.
    Dispatches to per-character draw functions based on body style.
    """

    def __init__(self, character: CharacterDef):
        self.character = character
        self.stats = character.stats
        self.colors = character.colors
        self.body_style = character.body_style
        self.anim = AnimationController(character)

    def update(self, state: FighterState, attack: Optional[AttackData] = None):
        """Advance animation by one frame (called by Fighter every tick)."""
        self.anim.update(state, attack)

    def draw(
        self,
        surface: pygame.Surface,
        rx: int,
        ry: int,
        facing: FacingDirection,
        current_height: int,
        current_state: FighterState,
        attack: Optional[AttackData] = None,
        attack_frame: int = 0,
        hurtboxes: list = None,
        active_hitbox=None,
        pushbox=None,
    ):
        """Main draw call — renders the complete fighter."""
        self.anim.current_state = current_state

        # Draw collision boxes (debug)
        self._draw_collision_boxes(surface, hurtboxes, active_hitbox, pushbox)

        body_color = self.anim.get_body_color()
        limb_color = self.anim.get_limb_color()
        accent = self.colors.accent
        outline = self.colors.outline
        f = facing.value  # 1 or -1

        # Dispatch to body-style-specific renderer
        if self.body_style == BodyStyle.RECTANGLE:
            self._draw_rectangle_style(
                surface, rx, ry, f, current_height, current_state,
                attack, attack_frame, body_color, limb_color, accent, outline,
            )
        elif self.body_style == BodyStyle.SLIM:
            self._draw_slim_style(
                surface, rx, ry, f, current_height, current_state,
                attack, attack_frame, body_color, limb_color, accent, outline,
            )
        elif self.body_style == BodyStyle.TRAPEZOID:
            self._draw_trapezoid_style(
                surface, rx, ry, f, current_height, current_state,
                attack, attack_frame, body_color, limb_color, accent, outline,
            )
        else:
            self._draw_rectangle_style(
                surface, rx, ry, f, current_height, current_state,
                attack, attack_frame, body_color, limb_color, accent, outline,
            )

    # =========================================================================
    # RECTANGLE STYLE (Ryokan — balanced, upright)
    # =========================================================================
    def _draw_rectangle_style(
        self, surface, rx, ry, f, h, state, attack, atk_frame,
        body_col, limb_col, accent, outline,
    ):
        w = self.stats.width
        hr = self.stats.head_radius

        # Body
        body_rect = pygame.Rect(rx - w // 2, ry - h, w, h)
        pygame.draw.rect(surface, body_col, body_rect, border_radius=6)
        pygame.draw.rect(surface, outline, body_rect, 2, border_radius=6)

        # Accent stripe
        stripe_rect = pygame.Rect(rx - w // 2 + 4, ry - h + 8, w - 8, 6)
        pygame.draw.rect(surface, accent, stripe_rect, border_radius=2)

        # Head
        head_y = ry - h - hr
        pygame.draw.circle(surface, body_col, (rx, int(head_y)), hr)
        pygame.draw.circle(surface, outline, (rx, int(head_y)), hr, 2)

        # Face
        eye_off = 8 * f
        pygame.draw.circle(surface, WHITE, (rx + eye_off, int(head_y - 3)), 5)
        pygame.draw.circle(surface, BLACK, (rx + int(eye_off * 1.3), int(head_y - 3)), 2)

        # Mouth guard (accent)
        pygame.draw.line(surface, accent,
                        (rx - 6 * f, int(head_y + 6)),
                        (rx + 8 * f, int(head_y + 6)), 3)

        # Arms and legs
        self._draw_rectangle_limbs(surface, rx, ry, f, h, state, attack, atk_frame, limb_col, accent)

    def _draw_rectangle_limbs(self, surface, rx, ry, f, h, state, attack, atk_frame, lc, ac):
        arm_y = ry - h + 30
        is_attacking = state in (FighterState.ATTACK_STARTUP, FighterState.ATTACK_ACTIVE, FighterState.ATTACK_RECOVERY)

        if is_attacking and attack:
            at = attack.attack_type
            # Arms
            if at == AttackType.PUNCH:
                if state == FighterState.ATTACK_ACTIVE:
                    # Extended punch
                    punch_reach = 35 + (10 if attack.base_damage >= 12 else 0)
                    ax = rx + punch_reach * f
                    ay = arm_y - 5
                    pygame.draw.line(surface, lc, (rx, arm_y), (ax, ay), 8)
                    pygame.draw.circle(surface, lc, (int(ax), int(ay)), 11)
                    pygame.draw.circle(surface, ac, (int(ax), int(ay)), 7)
                elif state == FighterState.ATTACK_STARTUP:
                    # Wind-up (pull back)
                    pygame.draw.line(surface, lc, (rx, arm_y), (rx - 18 * f, arm_y + 20), 7)
                    pygame.draw.circle(surface, lc, (rx - int(18 * f), arm_y + 20), 10)
                else:
                    pygame.draw.line(surface, lc, (rx, arm_y), (rx - 10 * f, arm_y + 10), 6)
            else:
                pygame.draw.line(surface, lc, (rx, arm_y), (rx - 12 * f, arm_y + 15), 6)

            # Legs
            leg_y = ry - 20
            if at == AttackType.KICK:
                if state == FighterState.ATTACK_ACTIVE:
                    kick_reach = 50 + (15 if attack.base_damage >= 12 else 0)
                    ky_offset = -20 if attack.height == AttackHeight.HIGH else 10
                    kx = rx + kick_reach * f
                    ky = leg_y + ky_offset
                    pygame.draw.line(surface, lc, (rx, leg_y), (kx, ky), 8)
                    # Foot
                    foot_w = 18 if attack.base_damage >= 12 else 14
                    pygame.draw.rect(surface, lc,
                                   (kx - foot_w // 2, ky - 8, foot_w, 16),
                                   border_radius=3)
                    pygame.draw.rect(surface, ac,
                                   (kx - foot_w // 2 + 2, ky - 6, foot_w - 4, 12),
                                   border_radius=2)
                elif state == FighterState.ATTACK_STARTUP:
                    # Chamber leg
                    pygame.draw.line(surface, lc, (rx, leg_y), (rx, leg_y - 25), 8)
                    pygame.draw.circle(surface, lc, (rx, leg_y - 25), 10)
                else:
                    pygame.draw.line(surface, lc, (rx, leg_y), (rx - 10, ry), 7)
            else:
                pygame.draw.line(surface, lc, (rx - 8, ry - 20), (rx - 12, ry), 7)
                pygame.draw.line(surface, lc, (rx + 8, ry - 20), (rx + 12, ry), 7)
        elif state == FighterState.CROUCH or state == FighterState.BLOCK_CROUCHING:
            # Crouching pose
            pygame.draw.line(surface, lc, (rx, arm_y - 10), (rx - 20 * f, arm_y), 6)
            pygame.draw.line(surface, lc, (rx - 8, ry - 15), (rx - 22, ry - 25), 7)
            pygame.draw.line(surface, lc, (rx + 8, ry - 15), (rx + 22, ry - 25), 7)
        elif state == FighterState.KNOCKDOWN:
            # Falling pose
            pygame.draw.line(surface, lc, (rx, arm_y), (rx + 20 * f, arm_y + 15), 6)
            pygame.draw.line(surface, lc, (rx - 15, ry - 10), (rx + 15 * f, ry - 5), 7)
        else:
            # Idle / Walk
            arm_swing = math.sin(self.anim.anim_frame * 0.15) * 4
            pygame.draw.line(surface, lc, (rx, arm_y), (rx - 18 * f, arm_y + 20 + arm_swing), 6)
            walk_off = math.sin(self.anim.anim_frame * 0.2) * 4 if state == FighterState.WALK_FORWARD else 0
            pygame.draw.line(surface, lc, (rx - 8, ry - 20), (rx - 12 + walk_off, ry), 7)
            pygame.draw.line(surface, lc, (rx + 8, ry - 20), (rx + 12 - walk_off, ry), 7)

    # =========================================================================
    # SLIM STYLE (Shadow — ninja, agile, compact)
    # =========================================================================
    def _draw_slim_style(
        self, surface, rx, ry, f, h, state, attack, atk_frame,
        body_col, limb_col, accent, outline,
    ):
        w = self.stats.width
        hr = self.stats.head_radius

        # Slimmer body (slightly narrower than width)
        bw = int(w * 0.75)
        body_rect = pygame.Rect(rx - bw // 2, ry - h, bw, h)
        pygame.draw.rect(surface, body_col, body_rect, border_radius=4)
        pygame.draw.rect(surface, outline, body_rect, 2, border_radius=4)

        # Headband / accent
        band_y = ry - h - hr + 2
        pygame.draw.line(surface, accent, (rx - hr, band_y), (rx + hr, band_y), 4)
        # Headband tails (flowing)
        tail_wave = math.sin(self.anim.anim_frame * 0.12) * 8
        pygame.draw.line(surface, accent,
                        (rx - hr, band_y),
                        (rx - hr - 18, band_y + 4 + tail_wave), 3)
        pygame.draw.line(surface, accent,
                        (rx - hr, band_y),
                        (rx - hr - 14, band_y + 10 + tail_wave * 0.7), 2)

        # Head
        head_y = ry - h - hr
        pygame.draw.circle(surface, body_col, (rx, int(head_y)), hr)
        pygame.draw.circle(surface, outline, (rx, int(head_y)), hr, 2)

        # Glowing eyes
        eye_x = rx + 6 * f
        pygame.draw.circle(surface, self.colors.eye, (eye_x, int(head_y - 2)), 4)
        pygame.draw.circle(surface, accent, (eye_x, int(head_y - 2)), 2)

        # Scar across face
        pygame.draw.line(surface, outline,
                        (rx + 2 * f, int(head_y + 2)),
                        (rx + 10 * f, int(head_y + 6)), 1)

        # Limbs
        self._draw_slim_limbs(surface, rx, ry, f, h, state, attack, atk_frame, limb_col, accent)

    def _draw_slim_limbs(self, surface, rx, ry, f, h, state, attack, atk_frame, lc, ac):
        arm_y = ry - h + 25
        is_attacking = state in (FighterState.ATTACK_STARTUP, FighterState.ATTACK_ACTIVE, FighterState.ATTACK_RECOVERY)

        if is_attacking and attack:
            at = attack.attack_type
            if at == AttackType.PUNCH:
                if state == FighterState.ATTACK_ACTIVE:
                    ax = rx + 38 * f
                    pygame.draw.line(surface, lc, (rx, arm_y), (ax, arm_y - 8), 6)
                    # Open palm / blade hand
                    pygame.draw.polygon(surface, ac, [
                        (int(ax), int(arm_y - 14)),
                        (int(ax + 8 * f), int(arm_y - 6)),
                        (int(ax), int(arm_y + 2)),
                    ])
                else:
                    pygame.draw.line(surface, lc, (rx, arm_y), (rx - 12 * f, arm_y + 12), 5)
            else:
                pygame.draw.line(surface, lc, (rx, arm_y), (rx - 10 * f, arm_y + 12), 5)

            leg_y = ry - 18
            if at == AttackType.KICK:
                if state == FighterState.ATTACK_ACTIVE:
                    reach = 55 + (10 if attack.base_damage >= 12 else 0)
                    ky_off = -22 if attack.height == AttackHeight.HIGH else 8
                    kx = rx + reach * f
                    ky = leg_y + ky_off
                    pygame.draw.line(surface, lc, (rx, leg_y), (kx, ky), 7)
                    # Slim foot blade
                    pygame.draw.polygon(surface, ac, [
                        (int(kx - 4), int(ky - 6)),
                        (int(kx + 10 * f), int(ky)),
                        (int(kx - 4), int(ky + 6)),
                    ])
                else:
                    pygame.draw.line(surface, lc, (rx, leg_y), (rx, leg_y - 20), 7)
            else:
                pygame.draw.line(surface, lc, (rx - 6, ry - 16), (rx - 10, ry), 6)
                pygame.draw.line(surface, lc, (rx + 6, ry - 16), (rx + 10, ry), 6)
        elif state == FighterState.CROUCH:
            # Ninja crouch — compact
            pygame.draw.line(surface, lc, (rx, arm_y - 8), (rx - 16 * f, arm_y - 2), 5)
            pygame.draw.line(surface, lc, (rx - 6, ry - 12), (rx - 18, ry - 20), 6)
            pygame.draw.line(surface, lc, (rx + 6, ry - 12), (rx + 18, ry - 20), 6)
        else:
            arm_wave = math.sin(self.anim.anim_frame * 0.18) * 3
            pygame.draw.line(surface, lc, (rx, arm_y), (rx - 15 * f, arm_y + 18 + arm_wave), 5)
            walk_off = math.sin(self.anim.anim_frame * 0.25) * 5 if state in (FighterState.WALK_FORWARD, FighterState.WALK_BACKWARD) else 0
            # Ninja running stance — one leg forward
            pygame.draw.line(surface, lc, (rx - 5, ry - 16), (rx - 8 + walk_off, ry), 6)
            pygame.draw.line(surface, lc, (rx + 5, ry - 16), (rx + 8 - walk_off, ry), 6)

    # =========================================================================
    # TRAPEZOID STYLE (Titan — broad shoulders, heavy build)
    # =========================================================================
    def _draw_trapezoid_style(
        self, surface, rx, ry, f, h, state, attack, atk_frame,
        body_col, limb_col, accent, outline,
    ):
        w = self.stats.width
        hr = self.stats.head_radius

        # Trapezoid body — broad shoulders, narrower waist
        shoulder_w = int(w * 1.2)
        waist_w = int(w * 0.7)
        top_y = ry - h
        waist_y = ry - int(h * 0.3)

        body_points = [
            (rx - shoulder_w // 2, top_y),
            (rx + shoulder_w // 2, top_y),
            (rx + waist_w // 2, waist_y),
            (rx - waist_w // 2, waist_y),
        ]
        pygame.draw.polygon(surface, body_col, body_points)
        pygame.draw.polygon(surface, outline, body_points, 2)

        # Lower body (hips)
        hip_points = [
            (rx - waist_w // 2, waist_y),
            (rx + waist_w // 2, waist_y),
            (rx + waist_w // 2 + 4, ry),
            (rx - waist_w // 2 - 4, ry),
        ]
        pygame.draw.polygon(surface, self.character.colors.body_dark, hip_points)
        pygame.draw.polygon(surface, outline, hip_points, 2)

        # Belt / accent
        pygame.draw.rect(surface, accent,
                        (rx - waist_w // 2 - 2, waist_y - 3, waist_w + 4, 8),
                        border_radius=2)

        # Massive head
        head_y = ry - h - hr
        pygame.draw.circle(surface, body_col, (rx, int(head_y)), hr)
        pygame.draw.circle(surface, outline, (rx, int(head_y)), hr, 2)

        # Angry eyes + brow
        eye_off = 7 * f
        pygame.draw.line(surface, outline,
                        (rx + eye_off - 5 * f, int(head_y - 10)),
                        (rx + eye_off + 5 * f, int(head_y - 7)), 3)
        pygame.draw.circle(surface, WHITE, (rx + eye_off, int(head_y - 3)), 5)
        pygame.draw.circle(surface, RED, (rx + int(eye_off * 1.3), int(head_y - 3)), 3)

        # Jaw line
        pygame.draw.line(surface, outline,
                        (rx - hr + 4, int(head_y + 8)),
                        (rx + hr - 4, int(head_y + 8)), 2)

        # Limbs
        self._draw_trapezoid_limbs(surface, rx, ry, f, h, state, attack, atk_frame,
                                   limb_col, accent, shoulder_w, waist_w)

    def _draw_trapezoid_limbs(self, surface, rx, ry, f, h, state, attack, atk_frame,
                              lc, ac, shoulder_w, waist_w):
        arm_y = ry - h + 35
        is_attacking = state in (FighterState.ATTACK_STARTUP, FighterState.ATTACK_ACTIVE, FighterState.ATTACK_RECOVERY)

        if is_attacking and attack:
            at = attack.attack_type
            if at == AttackType.PUNCH:
                if state == FighterState.ATTACK_ACTIVE:
                    # Massive fist
                    reach = 40 + (15 if attack.base_damage >= 20 else 0)
                    ax = rx + reach * f
                    pygame.draw.line(surface, lc, (rx, arm_y), (ax, arm_y - 8), 10)
                    pygame.draw.circle(surface, lc, (int(ax), int(arm_y - 8)), 14)
                    pygame.draw.circle(surface, ac, (int(ax), int(arm_y - 8)), 9)
                    # Impact lines
                    for i in range(3):
                        y_off = (i - 1) * 8
                        pygame.draw.line(surface, ac,
                                        (int(ax + 12 * f), int(arm_y - 8 + y_off)),
                                        (int(ax + 22 * f), int(arm_y - 8 + y_off)), 2)
                elif state == FighterState.ATTACK_STARTUP:
                    # Big wind-up
                    pygame.draw.line(surface, lc, (rx, arm_y), (rx - 22 * f, arm_y + 20), 10)
                    pygame.draw.circle(surface, lc, (rx - int(22 * f), arm_y + 20), 13)
                else:
                    pygame.draw.line(surface, lc, (rx, arm_y), (rx - 14 * f, arm_y + 12), 8)
            else:
                pygame.draw.line(surface, lc, (rx, arm_y), (rx - 14 * f, arm_y + 16), 8)

            leg_y = ry - 20
            if at == AttackType.KICK:
                if state == FighterState.ATTACK_ACTIVE:
                    reach = 55 + (20 if attack.base_damage >= 20 else 0)
                    ky_off = -24 if attack.height == AttackHeight.HIGH else 12
                    kx = rx + reach * f
                    ky = leg_y + ky_off
                    pygame.draw.line(surface, lc, (rx, leg_y), (kx, ky), 10)
                    # Heavy boot
                    boot_w = 22
                    pygame.draw.rect(surface, lc,
                                   (kx - boot_w // 2, ky - 10, boot_w, 20),
                                   border_radius=4)
                    pygame.draw.rect(surface, ac,
                                   (kx - boot_w // 2 + 2, ky - 8, boot_w - 4, 16),
                                   border_radius=3)
                else:
                    pygame.draw.line(surface, lc, (rx, leg_y), (rx, leg_y - 28), 9)
                    pygame.draw.circle(surface, lc, (rx, leg_y - 28), 12)
            else:
                pygame.draw.line(surface, lc, (rx - 12, ry - 20), (rx - 16, ry), 9)
                pygame.draw.line(surface, lc, (rx + 12, ry - 20), (rx + 16, ry), 9)
        elif state == FighterState.CROUCH:
            pygame.draw.line(surface, lc, (rx, arm_y - 5), (rx - 25 * f, arm_y + 5), 8)
            pygame.draw.line(surface, lc, (rx - 10, ry - 18), (rx - 28, ry - 30), 9)
            pygame.draw.line(surface, lc, (rx + 10, ry - 18), (rx + 28, ry - 30), 9)
        else:
            arm_heave = math.sin(self.anim.anim_frame * 0.12) * 5
            pygame.draw.line(surface, lc, (rx, arm_y), (rx - 22 * f, arm_y + 22 + arm_heave), 9)
            walk_off = math.sin(self.anim.anim_frame * 0.15) * 3 if state in (FighterState.WALK_FORWARD, FighterState.WALK_BACKWARD) else 0
            pygame.draw.line(surface, lc, (rx - 12, ry - 20), (rx - 16 + walk_off, ry), 9)
            pygame.draw.line(surface, lc, (rx + 12, ry - 20), (rx + 16 - walk_off, ry), 9)

    # =========================================================================
    # COLLISION BOX DRAWING
    # =========================================================================
    def _draw_collision_boxes(self, surface, hurtboxes, active_hitbox, pushbox):
        if not hurtboxes:
            return
        for hurtbox in hurtboxes:
            s = pygame.Surface((hurtbox.width, hurtbox.height), pygame.SRCALPHA)
            s.fill((0, 255, 0, 35))
            surface.blit(s, (hurtbox.x, hurtbox.y))
            pygame.draw.rect(surface, GREEN, hurtbox.to_rect(), 1)
        if pushbox:
            pygame.draw.rect(surface, BLUE, pushbox.to_rect(), 1)
        if active_hitbox:
            s = pygame.Surface((active_hitbox.width, active_hitbox.height), pygame.SRCALPHA)
            s.fill((255, 0, 0, 90))
            surface.blit(s, (active_hitbox.x, active_hitbox.y))
            pygame.draw.rect(surface, RED, active_hitbox.to_rect(), 2)
