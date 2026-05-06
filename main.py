"""
Main Game Loop — character select, round system, match management, and the core loop.
This is the entry point: python main.py
"""

import pygame
import sys

pygame.init()
pygame.font.init()

from constants import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, GROUND_Y, FighterState
from character_defs import get_character, get_character_choices, CharacterDef
from fighter import Fighter
from ai_controller import AIController, AIDifficulty
from renderer import Renderer


class Game:
    """Main game controller — manages states, rounds, and the game loop."""

    # Game states
    STATE_CHARACTER_SELECT = "char_select"
    STATE_FIGHTING = "fighting"
    STATE_ROUND_OVER = "round_over"
    STATE_MATCH_OVER = "match_over"

    ROUNDS_TO_WIN = 2  # Best of 3

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("2D Fighter V3 — Refactored Engine")
        self.clock = pygame.time.Clock()
        self.running = True

        self.renderer = Renderer(self.screen)

        # Character selection
        self.character_choices = get_character_choices()
        self.selected_char_idx = 0
        self.cursor_blink = True
        self.cursor_blink_timer = 0

        # Players
        self.fighter1: Fighter = None
        self.fighter2: Fighter = None
        self.ai_controller: AIController = None

        # Round system
        self.current_round = 1
        self.p1_score = 0
        self.p2_score = 0
        self.round_over = False
        self.match_over = False
        self.winner_text = ""
        self.current_frame = 0

        # Difficulty
        self.difficulty_idx = 1
        self.difficulties = [AIDifficulty.EASY, AIDifficulty.MEDIUM, AIDifficulty.HARD, AIDifficulty.BRUTAL]
        self.difficulty_names = ["EASY", "MEDIUM", "HARD", "BRUTAL"]

        # Game state
        self.state = self.STATE_CHARACTER_SELECT

    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    def run(self):
        """Main game loop."""
        while self.running:
            self._handle_events()

            if self.state == self.STATE_CHARACTER_SELECT:
                self._update_character_select()
                self.renderer.draw_character_select(
                    self.character_choices, self.selected_char_idx, self.cursor_blink
                )
            elif self.state == self.STATE_FIGHTING:
                self._update_fight()
                self.renderer.draw_frame(
                    self.fighter1, self.fighter2, self.current_frame,
                    self.difficulty_names[self.difficulty_idx], self.current_round,
                )
            elif self.state == self.STATE_ROUND_OVER:
                self.renderer.draw_round_over(
                    self.winner_text, self.p1_score, self.p2_score, False
                )
            elif self.state == self.STATE_MATCH_OVER:
                self.renderer.draw_round_over(
                    self.winner_text, self.p1_score, self.p2_score, True
                )

            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()

    # =========================================================================
    # EVENT HANDLING
    # =========================================================================
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == self.STATE_FIGHTING:
                        self.state = self.STATE_CHARACTER_SELECT
                    else:
                        self.running = False

                elif self.state == self.STATE_CHARACTER_SELECT:
                    self._handle_char_select_key(event.key)

                elif self.state == self.STATE_FIGHTING:
                    self._handle_fight_key(event.key)

                elif self.state == self.STATE_ROUND_OVER:
                    if event.key == pygame.K_RETURN:
                        self._start_next_round()
                    elif event.key == pygame.K_r:
                        self._reset_match()

                elif self.state == self.STATE_MATCH_OVER:
                    if event.key == pygame.K_r:
                        self._reset_match()

    def _handle_char_select_key(self, key):
        if key == pygame.K_LEFT:
            self.selected_char_idx = (self.selected_char_idx - 1) % len(self.character_choices)
        elif key == pygame.K_RIGHT:
            self.selected_char_idx = (self.selected_char_idx + 1) % len(self.character_choices)
        elif key == pygame.K_RETURN:
            self._start_match()
        elif key == pygame.K_TAB:
            self.difficulty_idx = (self.difficulty_idx + 1) % len(self.difficulties)
        elif key == pygame.K_r:
            self._reset_match()

    def _handle_fight_key(self, key):
        if key == pygame.K_r:
            self._reset_match()
        elif key == pygame.K_TAB:
            self.difficulty_idx = (self.difficulty_idx + 1) % len(self.difficulties)
            self._recreate_ai()

    # =========================================================================
    # CHARACTER SELECT
    # =========================================================================
    def _update_character_select(self):
        self.cursor_blink_timer += 1
        if self.cursor_blink_timer >= 30:
            self.cursor_blink = not self.cursor_blink
            self.cursor_blink_timer = 0

    # =========================================================================
    # MATCH / ROUND MANAGEMENT
    # =========================================================================
    def _start_match(self):
        """Initialize a new match with the selected character."""
        char_id = self.character_choices[self.selected_char_idx][0]
        p1_char = get_character(char_id)

        # AI picks a random character (different from player)
        available = [c for c in self.character_choices if c[0] != char_id]
        ai_char_id = available[0][0] if available else self.character_choices[0][0]
        ai_char = get_character(ai_char_id)

        self._init_fighters(p1_char, ai_char)

        self.p1_score = 0
        self.p2_score = 0
        self.current_round = 1
        self.state = self.STATE_FIGHTING

    def _start_next_round(self):
        """Start the next round (keep characters, reset positions)."""
        if self.fighter1 and self.fighter2:
            self.fighter1.reset(300)
            self.fighter2.reset(900)
            self.ai_controller.reset()

        self.current_round += 1
        self.round_over = False
        self.match_over = False
        self.state = self.STATE_FIGHTING

    def _reset_match(self):
        """Go back to character select."""
        self.fighter1 = None
        self.fighter2 = None
        self.ai_controller = None
        self.current_frame = 0
        self.state = self.STATE_CHARACTER_SELECT

    def _init_fighters(self, p1_char: CharacterDef, p2_char: CharacterDef):
        """Create fighter instances for both players."""
        self.fighter1 = Fighter(p1_char, 300, player_id=1)
        self.fighter2 = Fighter(p2_char, 900, player_id=2)
        self.ai_controller = AIController(p2_char, self.difficulties[self.difficulty_idx])
        self.current_frame = 0

    def _recreate_ai(self):
        """Recreate the AI with the new difficulty (same character)."""
        if self.fighter2:
            self.ai_controller = AIController(
                self.fighter2.character, self.difficulties[self.difficulty_idx]
            )

    # =========================================================================
    # FIGHT UPDATE
    # =========================================================================
    def _update_fight(self):
        """Main fight update loop."""
        if self.round_over:
            return

        keys = pygame.key.get_pressed()

        # Update Player 1 (keyboard input)
        self.fighter1.update(
            opponent=self.fighter2,
            current_frame=self.current_frame,
            keys_pressed=keys,
        )

        # Generate AI input for Player 2
        ai_input = self.ai_controller.update(
            opponent_state=self.fighter1.state,
            opponent_x=self.fighter1.x,
            opponent_y=self.fighter1.pos_y,
            self_x=self.fighter2.x,
            self_y=self.fighter2.pos_y,
            opponent_current_attack=self.fighter1.current_attack,
            opponent_has_hit=self.fighter1.has_hit_opponent,
            self_facing_right=self.fighter2.facing_right,
            current_frame=self.current_frame,
        )

        # Notify AI of hit results
        if self.fighter2.has_hit_opponent and self.fighter2.combo_count > 1:
            self.ai_controller.on_hit_landed(self.fighter2.combo_count)

        # Update Player 2 (AI input)
        self.fighter2.update(
            opponent=self.fighter1,
            current_frame=self.current_frame,
            ai_input=ai_input,
        )

        # Pushbox collision
        self._handle_pushbox_collision()

        # Check round end
        self._check_round_end()

        self.current_frame += 1

    def _handle_pushbox_collision(self):
        """Prevent fighters from overlapping via pushbox collision."""
        if not self.fighter1.pushbox or not self.fighter2.pushbox:
            return

        if self.fighter1.pushbox.intersects(self.fighter2.pushbox):
            if self.fighter1.x < self.fighter2.x:
                overlap = ((self.fighter1.x + self.fighter1.stats.width // 2) -
                          (self.fighter2.x - self.fighter2.stats.width // 2))
            else:
                overlap = ((self.fighter2.x + self.fighter2.stats.width // 2) -
                          (self.fighter1.x - self.fighter1.stats.width // 2))

            if overlap > 0:
                push = overlap // 2 + 1
                if self.fighter1.x < self.fighter2.x:
                    self.fighter1.pos_x -= push
                    self.fighter2.pos_x += push
                else:
                    self.fighter1.pos_x += push
                    self.fighter2.pos_x -= push

    def _check_round_end(self):
        """Check if the round should end."""
        if self.fighter1.health <= 0:
            self._end_round("CPU Wins!")
            self.p2_score += 1
        elif self.fighter2.health <= 0:
            self._end_round("Player 1 Wins!")
            self.p1_score += 1

    def _end_round(self, winner_text: str):
        """Handle round end."""
        self.round_over = True
        self.winner_text = winner_text

        # Check match end
        if self.p1_score >= self.ROUNDS_TO_WIN or self.p2_score >= self.ROUNDS_TO_WIN:
            self.match_over = True
            self.state = self.STATE_MATCH_OVER
        else:
            self.state = self.STATE_ROUND_OVER


# =============================================================================
# ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    game = Game()
    game.run()
