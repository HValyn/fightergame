"""
Renderer — handles all drawing: arena, fighters, HUD, character select.
Extracted from Fighter to keep rendering separate from game logic.
"""

import math
from typing import Optional

import pygame

from constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, GROUND_Y,
    WHITE, BLACK, RED, DARK_RED, BLUE, DARK_BLUE, GREEN, YELLOW,
    ORANGE, PURPLE, CYAN, GRAY, LIGHT_GRAY, BROWN, TEAL, MAGENTA,
    FighterState, AttackHeight, FacingDirection,
)
from character_defs import CharacterDef
from fighter import Fighter


class Renderer:
    """Handles all game rendering."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_large = pygame.font.Font(None, 80)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)
        self.font_tiny = pygame.font.Font(None, 20)

        # Pre-render arena background (optimization)
        self.arena_surface = None

    def draw_frame(
        self,
        fighter1: Fighter,
        fighter2: Fighter,
        current_frame: int,
        difficulty_name: str = "",
        round_num: int = 1,
        show_debug: bool = True,
    ):
        """Draw a complete game frame."""
        self.screen.fill((35, 35, 45))

        self._draw_arena()
        fighter1.renderer.draw(
            self.screen,
            int(fighter1.render_x), int(fighter1.render_y),
            fighter1.facing, fighter1.current_height,
            fighter1.state, fighter1.current_attack, fighter1.attack_frame,
            fighter1.hurtboxes, fighter1.active_hitbox, fighter1.pushbox,
        )
        fighter2.renderer.draw(
            self.screen,
            int(fighter2.render_x), int(fighter2.render_y),
            fighter2.facing, fighter2.current_height,
            fighter2.state, fighter2.current_attack, fighter2.attack_frame,
            fighter2.hurtboxes, fighter2.active_hitbox, fighter2.pushbox,
        )
        self._draw_hud(fighter1, fighter2, difficulty_name, round_num)

        # Per-fighter overlays
        for fighter in [fighter1, fighter2]:
            self._draw_fighter_overlays(fighter)

        pygame.display.flip()

    # =========================================================================
    # ARENA
    # =========================================================================
    def _draw_arena(self):
        """Draw the fighting arena background."""
        # Ground
        pygame.draw.rect(self.screen, BROWN, (0, GROUND_Y, SCREEN_WIDTH, SCREEN_HEIGHT - GROUND_Y))
        # Ground line
        pygame.draw.line(self.screen, (200, 180, 140), (0, GROUND_Y), (SCREEN_WIDTH, GROUND_Y), 3)

        # Subtle grid
        for x in range(0, SCREEN_WIDTH, 80):
            pygame.draw.line(self.screen, (42, 42, 52), (x, 0), (x, GROUND_Y), 1)
        for y in range(0, GROUND_Y, 80):
            pygame.draw.line(self.screen, (42, 42, 52), (0, y), (SCREEN_WIDTH, y), 1)

        # Side borders
        pygame.draw.rect(self.screen, (50, 50, 60), (0, 0, 4, GROUND_Y))
        pygame.draw.rect(self.screen, (50, 50, 60), (SCREEN_WIDTH - 4, 0, 4, GROUND_Y))

    # =========================================================================
    # HUD
    # =========================================================================
    def _draw_hud(self, f1: Fighter, f2: Fighter, difficulty_name: str, round_num: int):
        """Draw the heads-up display: health bars, super meter, names, round info."""
        bar_w = 420
        bar_h = 22
        bar_y = 18
        p1_x = 30
        p2_x = SCREEN_WIDTH - 30 - bar_w

        # P1 health bar (left-aligned)
        self._draw_health_bar(p1_x, bar_y, bar_w, bar_h, f1.health, f1.max_health,
                             f1.character.colors.body, left_align=True)
        # P2 health bar (right-aligned, mirrored)
        self._draw_health_bar(p2_x, bar_y, bar_w, bar_h, f2.health, f2.max_health,
                             f2.character.colors.body, left_align=False)

        # Super meter bars
        meter_h = 8
        meter_y = bar_y + bar_h + 4
        self._draw_super_meter(p1_x, meter_y, bar_w, meter_h, f1.super_meter, f1.max_super_meter,
                              f1.character.colors.accent, left_align=True)
        self._draw_super_meter(p2_x, meter_y, bar_w, meter_h, f2.super_meter, f2.max_super_meter,
                              f2.character.colors.accent, left_align=False)

        # Names
        p1_name = self.font_small.render(f1.character.name, True, f1.character.colors.accent)
        self.screen.blit(p1_name, (p1_x, bar_y - 20))
        p2_name = self.font_small.render(f2.character.name, True, f2.character.colors.accent)
        self.screen.blit(p2_name, (p2_x + bar_w - p2_name.get_width(), bar_y - 20))

        # VS / Round indicator (center)
        vs_text = self.font_small.render(f"Round {round_num}", True, YELLOW)
        self.screen.blit(vs_text, (SCREEN_WIDTH // 2 - vs_text.get_width() // 2, 5))

        if difficulty_name:
            diff_text = self.font_tiny.render(f"CPU: {difficulty_name}", True, ORANGE)
            self.screen.blit(diff_text, (SCREEN_WIDTH // 2 - diff_text.get_width() // 2, 22))

        # Controls hint (bottom)
        controls = "Arrows:Move/Jump/Crouch | A:Punch S:Kick D:Special Shift:Heavy | Tab:Difficulty R:Reset ESC:Quit"
        ctrl_text = self.font_tiny.render(controls, True, (100, 100, 120))
        self.screen.blit(ctrl_text, (SCREEN_WIDTH // 2 - ctrl_text.get_width() // 2, SCREEN_HEIGHT - 20))

    def _draw_health_bar(self, x, y, w, h, health, max_health, color, left_align=True):
        """Draw a health bar with damage indication."""
        # Background
        pygame.draw.rect(self.screen, (40, 40, 40), (x, y, w, h), border_radius=3)

        # Health fill
        ratio = max(0, health / max_health)
        fill_w = int(w * ratio)
        if left_align:
            fill_rect = pygame.Rect(x, y, fill_w, h)
        else:
            fill_rect = pygame.Rect(x + w - fill_w, y, fill_w, h)

        # Color gradient based on health
        if ratio > 0.5:
            fill_color = GREEN
        elif ratio > 0.25:
            fill_color = YELLOW
        else:
            fill_color = RED

        if fill_w > 0:
            pygame.draw.rect(self.screen, fill_color, fill_rect, border_radius=3)

        # Border
        pygame.draw.rect(self.screen, WHITE, (x, y, w, h), 2, border_radius=3)

        # Health number
        health_text = self.font_tiny.render(f"{max(0, health)}/{max_health}", True, WHITE)
        self.screen.blit(health_text, (x + w // 2 - health_text.get_width() // 2, y + 3))

    def _draw_super_meter(self, x, y, w, h, meter, max_meter, color, left_align=True):
        """Draw the super meter bar."""
        pygame.draw.rect(self.screen, (30, 30, 30), (x, y, w, h), border_radius=2)
        ratio = min(1.0, meter / max_meter) if max_meter > 0 else 0
        fill_w = int(w * ratio)

        if fill_w > 0:
            if left_align:
                fill_rect = pygame.Rect(x, y, fill_w, h)
            else:
                fill_rect = pygame.Rect(x + w - fill_w, y, fill_w, h)

            # Glow effect when full
            if ratio >= 1.0:
                glow = abs(math.sin(pygame.time.get_ticks() * 0.005)) * 50
                glow_color = (
                    min(255, color[0] + int(glow)),
                    min(255, color[1] + int(glow)),
                    min(255, color[2] + int(glow)),
                )
                pygame.draw.rect(self.screen, glow_color, fill_rect, border_radius=2)
            else:
                pygame.draw.rect(self.screen, color, fill_rect, border_radius=2)

        pygame.draw.rect(self.screen, (80, 80, 80), (x, y, w, h), 1, border_radius=2)

    # =========================================================================
    # FIGHTER OVERLAYS
    # =========================================================================
    def _draw_fighter_overlays(self, fighter: Fighter):
        """Draw combo counter, frame advantage, state indicator above the fighter."""
        rx = int(fighter.render_x)
        ry = int(fighter.render_y)
        h = fighter.current_height

        # Combo counter
        if fighter.combo_count > 1:
            self._draw_combo_counter(rx, ry, h, fighter.combo_count, fighter.combo_damage)

        # Frame advantage
        if fighter.frame_adv_timer > 0:
            self._draw_frame_advantage(rx, ry, h, fighter.last_frame_advantage)

        # State indicator (subtle, below fighter)
        self._draw_state_label(rx, ry, h, fighter)

    def _draw_combo_counter(self, rx, ry, h, count, damage):
        pulse = 1.0 + abs(math.sin(pygame.time.get_ticks() * 0.01)) * 0.1
        font = pygame.font.Font(None, int(36 * pulse))
        text = font.render(f"{count} HITS! {damage} dmg", True, ORANGE)
        tr = text.get_rect(centerx=rx, top=ry - h - 120)
        bg = tr.inflate(12, 8)
        pygame.draw.rect(self.screen, (0, 0, 0, 180), bg, border_radius=4)
        pygame.draw.rect(self.screen, ORANGE, bg, 2, border_radius=4)
        self.screen.blit(text, tr)

    def _draw_frame_advantage(self, rx, ry, h, advantage):
        font = self.font_small
        color = GREEN if advantage > 0 else RED if advantage < 0 else WHITE
        sign = "+" if advantage >= 0 else ""
        text = font.render(f"{sign}{advantage}f", True, color)
        tr = text.get_rect(centerx=rx, top=ry - h - 90)
        bg = tr.inflate(8, 4)
        pygame.draw.rect(self.screen, BLACK, bg, border_radius=2)
        self.screen.blit(text, tr)

    def _draw_state_label(self, rx, ry, h, fighter):
        """Draw the current attack/state name."""
        font = self.font_tiny
        if fighter.current_attack:
            label = fighter.current_attack.name
        else:
            label = fighter.state.name.replace("ATTACK_", "").replace("_", " ")

        text = font.render(label, True, (180, 180, 180))
        tr = text.get_rect(centerx=rx, top=ry + 8)
        self.screen.blit(text, tr)

    # =========================================================================
    # CHARACTER SELECT SCREEN
    # =========================================================================
    def draw_character_select(self, characters, selected_idx, cursor_blink):
        """Draw the character selection screen."""
        self.screen.fill((25, 25, 35))

        # Title
        title = self.font_large.render("SELECT YOUR FIGHTER", True, YELLOW)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 40))

        # Subtitle
        sub = self.font_small.render("Left/Right to choose, Enter to confirm", True, LIGHT_GRAY)
        self.screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, 110))

        # Character cards
        card_w = 300
        card_h = 350
        total_w = len(characters) * card_w + (len(characters) - 1) * 30
        start_x = (SCREEN_WIDTH - total_w) // 2

        for i, (char_id, name, subtitle) in enumerate(characters):
            cx = start_x + i * (card_w + 30)
            cy = 160

            # Card background
            is_selected = i == selected_idx
            bg_color = (60, 60, 80) if is_selected else (40, 40, 55)
            border_color = YELLOW if is_selected else (70, 70, 80)
            border_w = 3 if is_selected else 1

            card_rect = pygame.Rect(cx, cy, card_w, card_h)
            pygame.draw.rect(self.screen, bg_color, card_rect, border_radius=8)
            pygame.draw.rect(self.screen, border_color, card_rect, border_w, border_radius=8)

            # Character preview (simple colored body)
            from character_defs import get_character
            char_def = get_character(char_id)
            if char_def:
                preview_x = cx + card_w // 2
                preview_y = cy + 180
                self._draw_character_preview(self.screen, char_def, preview_x, preview_y, is_selected)

            # Name
            name_text = self.font_medium.render(name, True,
                                                char_def.colors.accent if char_def else WHITE)
            self.screen.blit(name_text, (cx + card_w // 2 - name_text.get_width() // 2, cy + 15))

            # Subtitle
            if subtitle:
                sub_text = self.font_tiny.render(subtitle, True, LIGHT_GRAY)
                self.screen.blit(sub_text, (cx + card_w // 2 - sub_text.get_width() // 2, cy + 50))

            # Stats preview
            if char_def:
                self._draw_stats_preview(cx + 20, cy + card_h - 100, card_w - 40, char_def)

        # Blinking cursor indicator
        if cursor_blink:
            arrow_text = self.font_medium.render("v", True, YELLOW)
            ax = start_x + selected_idx * (card_w + 30) + card_w // 2
            self.screen.blit(arrow_text, (ax - arrow_text.get_width() // 2, 140))

        pygame.display.flip()

    def _draw_character_preview(self, surface, char_def, cx, cy, animated):
        """Draw a simplified character preview for the select screen."""
        s = char_def.stats
        c = char_def.colors
        f = 1  # Facing right

        # Body
        if char_def.body_style == "trapezoid":
            sw = int(s.width * 1.2)
            ww = int(s.width * 0.7)
            points = [
                (cx - sw // 2, cy - 80),
                (cx + sw // 2, cy - 80),
                (cx + ww // 2, cy - 20),
                (cx - ww // 2, cy - 20),
            ]
            pygame.draw.polygon(surface, c.body, points)
            pygame.draw.polygon(surface, c.outline, points, 2)
        elif char_def.body_style == "slim":
            bw = int(s.width * 0.75)
            pygame.draw.rect(surface, c.body,
                           (cx - bw // 2, cy - 80, bw, 60), border_radius=4)
            pygame.draw.rect(surface, c.outline,
                           (cx - bw // 2, cy - 80, bw, 60), 2, border_radius=4)
            # Headband
            pygame.draw.line(surface, c.accent, (cx - s.head_radius, cy - 80 - s.head_radius + 2),
                           (cx + s.head_radius, cy - 80 - s.head_radius + 2), 3)
        else:
            pygame.draw.rect(surface, c.body,
                           (cx - s.width // 2, cy - 80, s.width, 60), border_radius=6)
            pygame.draw.rect(surface, c.outline,
                           (cx - s.width // 2, cy - 80, s.width, 60), 2, border_radius=6)
            # Accent stripe
            pygame.draw.rect(surface, c.accent,
                           (cx - s.width // 2 + 4, cy - 72, s.width - 8, 5), border_radius=2)

        # Head
        head_y = cy - 80 - s.head_radius
        pygame.draw.circle(surface, c.body, (cx, head_y), s.head_radius)
        pygame.draw.circle(surface, c.outline, (cx, head_y), s.head_radius, 2)

        # Eyes
        eye_x = cx + 6 * f
        pygame.draw.circle(surface, c.eye, (eye_x, head_y - 3), 4)
        pygame.draw.circle(surface, BLACK, (eye_x + 2 * f, head_y - 3), 2)

        # Legs
        if animated:
            bob = math.sin(pygame.time.get_ticks() * 0.005) * 3
        else:
            bob = 0
        pygame.draw.line(surface, c.limb, (cx - 8, cy - 20), (cx - 12 + bob, cy), 6)
        pygame.draw.line(surface, c.limb, (cx + 8, cy - 20), (cx + 12 - bob, cy), 6)

    def _draw_stats_preview(self, x, y, w, char_def):
        """Draw a small stat bar preview for a character."""
        s = char_def.stats
        stats = [
            ("HP", s.max_health / 130),
            ("SPD", s.walk_speed / 6.5),
            ("ATK", 0.5),  # Could calculate from average damage
            ("DEF", s.max_health / 130),
        ]
        bar_h = 10
        for i, (label, ratio) in enumerate(stats):
            sy = y + i * 20
            text = self.font_tiny.render(label, True, LIGHT_GRAY)
            self.screen.blit(text, (x, sy))
            bx = x + 35
            bw = w - 35
            pygame.draw.rect(self.screen, (30, 30, 30), (bx, sy + 2, bw, bar_h), border_radius=2)
            fill_w = int(bw * min(1.0, ratio))
            color = GREEN if ratio > 0.7 else YELLOW if ratio > 0.4 else RED
            if fill_w > 0:
                pygame.draw.rect(self.screen, color, (bx, sy + 2, fill_w, bar_h), border_radius=2)

    # =========================================================================
    # ROUND OVER SCREEN
    # =========================================================================
    def draw_round_over(self, winner_text: str, p1_score: int, p2_score: int, match_over: bool):
        """Draw the round/match over overlay."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        # Winner announcement
        text = self.font_large.render(winner_text, True, YELLOW)
        self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - 80))

        # Score
        score_text = self.font_medium.render(f"Score: {p1_score} - {p2_score}", True, WHITE)
        self.screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, SCREEN_HEIGHT // 2 - 10))

        # Prompt
        if match_over:
            prompt = "Press R to rematch, ESC to quit"
        else:
            prompt = "Press ENTER for next round, R to restart"
        prompt_text = self.font_small.render(prompt, True, LIGHT_GRAY)
        self.screen.blit(prompt_text, (SCREEN_WIDTH // 2 - prompt_text.get_width() // 2, SCREEN_HEIGHT // 2 + 40))

        pygame.display.flip()
