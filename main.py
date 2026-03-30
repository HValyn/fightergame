"""
Main Game Loop and Initialization
"""

import pygame
import sys

# Explicitly initialize Pygame and its font module BEFORE anything else
pygame.init()
pygame.font.init()

from constants import *
from fighter import Fighter
from ai_controller import AIController, AIDifficulty

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("2D Fighter V2 - CPU AI Integration")
        self.clock = pygame.time.Clock()
        self.running = True
        
        self.fighter1 = Fighter(300, GROUND_Y, BLUE, 1)
        self.fighter2 = Fighter(900, GROUND_Y, RED, 2)
        
        self.difficulty_level = 1
        self.difficulties = [AIDifficulty.EASY, AIDifficulty.MEDIUM, AIDifficulty.HARD, AIDifficulty.BRUTAL]
        self.difficulty_names = ["EASY", "MEDIUM", "HARD", "BRUTAL"]
        self.ai_controller = AIController(self.fighter2, self.difficulties[self.difficulty_level])
        
        self.round_over = False
        self.winner = None
        self.current_frame = 0
        
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_r:
                    self._reset_game()
                elif event.key == pygame.K_TAB:
                    self.difficulty_level = (self.difficulty_level + 1) % 4
                    self.ai_controller = AIController(self.fighter2, self.difficulties[self.difficulty_level])
    
    def _reset_game(self):
        self.fighter1 = Fighter(300, GROUND_Y, BLUE, 1)
        self.fighter2 = Fighter(900, GROUND_Y, RED, 2)
        self.ai_controller = AIController(self.fighter2, self.difficulties[self.difficulty_level])
        self.round_over = False
        self.winner = None
    
    def update(self):
        keys = pygame.key.get_pressed()
        
        # Update Player 1 with keyboard
        self.fighter1.update(keys_pressed=keys, opponent=self.fighter2, current_frame=self.current_frame)
        
        # Update Player 2 with AI
        ai_input = self.ai_controller.update(self.fighter1, self.current_frame)
        
        # Notify AI of success (for combo extensions)
        if self.fighter2.has_hit_opponent and self.fighter2.combo_count > 0:
            self.ai_controller.on_hit_landed(self.fighter2.combo_count)
            
        self.fighter2.update(ai_input=ai_input, opponent=self.fighter1, current_frame=self.current_frame)
        
        self._handle_pushbox_collision()
        
        if self.fighter1.health <= 0:
            self.round_over = True
            self.winner = "CPU Wins!"
        elif self.fighter2.health <= 0:
            self.round_over = True
            self.winner = "Player 1 Wins!"
            
        self.current_frame += 1
    
    def _handle_pushbox_collision(self):
        if self.fighter1.pushbox and self.fighter2.pushbox:
            if self.fighter1.pushbox.intersects(self.fighter2.pushbox):
                if self.fighter1.x < self.fighter2.x:
                    overlap = (self.fighter1.x + self.fighter1.width // 2) - (self.fighter2.x - self.fighter2.width // 2)
                    if overlap > 0:
                        push = overlap // 2 + 1
                        self.fighter1.pos_x -= push
                        self.fighter2.pos_x += push
    
    def draw(self):
        self.screen.fill((40, 40, 50))
        self._draw_arena()
        self.fighter1.draw(self.screen)
        self.fighter2.draw(self.screen)
        self._draw_ui()
        if self.round_over:
            self._draw_round_over()
        pygame.display.flip()
    
    def _draw_arena(self):
        pygame.draw.rect(self.screen, BROWN, (0, GROUND_Y, SCREEN_WIDTH, SCREEN_HEIGHT - GROUND_Y))
        pygame.draw.line(self.screen, WHITE, (0, GROUND_Y), (SCREEN_WIDTH, GROUND_Y), 3)
        for x in range(0, SCREEN_WIDTH, 100):
            pygame.draw.line(self.screen, (50, 50, 60), (x, 0), (x, GROUND_Y), 1)
        for y in range(0, GROUND_Y, 100):
            pygame.draw.line(self.screen, (50, 50, 60), (0, y), (SCREEN_WIDTH, y), 1)
    
    def _draw_ui(self):
        font = pygame.font.Font(None, 32)
        small_font = pygame.font.Font(None, 22)
        
        title = font.render("2D Fighter V2 - CPU Opponent", True, WHITE)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 10))
        
        diff_text = font.render(f"CPU: {self.difficulty_names[self.difficulty_level]} (TAB to change)", True, ORANGE)
        self.screen.blit(diff_text, (SCREEN_WIDTH // 2 - diff_text.get_width() // 2, 35))
        
        controls = [
            "Player 1 Controls:",
            "Arrow Keys - Move/Jump/Crouch",
            "A - Punch | S - Kick",
            "Shift - Full Power",
            "Up/Down + Attack - High/Low",
            "R - Reset | ESC - Quit"
        ]
        for i, text in enumerate(controls):
            c = YELLOW if i == 0 else WHITE
            self.screen.blit(small_font.render(text, True, c), (10, 70 + i * 20))
        
        features = ["Engine Features:", "Input Buffer (12 frames)", "Hitbox/Hurtbox/Pushbox", "Attack Sub-states", "Hitstop on hit", "Frame Advantage", "Coyote Time", "Combo System"]
        for i, text in enumerate(features):
            c = CYAN if i == 0 else WHITE
            self.screen.blit(small_font.render(text, True, c), (SCREEN_WIDTH - 200, 70 + i * 20))
            
        box_legend = [("Hurtbox", GREEN), ("Pushbox", BLUE), ("Hitbox", RED)]
        for i, (text, color) in enumerate(box_legend):
            pygame.draw.rect(self.screen, color, (SCREEN_WIDTH - 190, 240 + i*20, 15, 15))
            self.screen.blit(small_font.render(text, True, color), (SCREEN_WIDTH - 170, 240 + i*20))
    
    def _draw_round_over(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))
        
        font = pygame.font.Font(None, 80)
        text = font.render(self.winner, True, YELLOW)
        self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - 60))
        
        small_font = pygame.font.Font(None, 36)
        restart_text = small_font.render("Press R to Restart", True, WHITE)
        self.screen.blit(restart_text, (SCREEN_WIDTH // 2 - restart_text.get_width() // 2, SCREEN_HEIGHT // 2 + 30))
    
    def run(self):
        while self.running:
            self.handle_events()
            if not self.round_over:
                self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = Game()
    game.run()