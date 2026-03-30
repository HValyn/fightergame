"""
Contains the Input Buffer and Fighter logic.
"""

import math
from collections import deque
from typing import Optional, List, Tuple

from constants import *

class InputBuffer:
    def __init__(self, size: int = INPUT_BUFFER_SIZE):
        self.size = size
        self.buffer: deque[InputState] = deque(maxlen=size)
        self.buffered_attacks: List[BufferedInput] = []
        self.current_frame = 0
        
    def update(self, keys_pressed) -> InputState:
        state = InputState(
            left=keys_pressed[pygame.K_LEFT],
            right=keys_pressed[pygame.K_RIGHT],
            up=keys_pressed[pygame.K_UP],
            down=keys_pressed[pygame.K_DOWN],
            punch=keys_pressed[pygame.K_a],
            kick=keys_pressed[pygame.K_s],
            power=keys_pressed[pygame.K_LSHIFT]
        )
        self._process_new_state(state)
        return state

    def push_ai_input(self, ai_state: InputState) -> InputState:
        """Used by the AI to inject inputs without reading pygame keys."""
        self._process_new_state(ai_state)
        return ai_state

    def _process_new_state(self, state: InputState):
        prev_punch = self.buffer[-1].punch if self.buffer else False
        prev_kick = self.buffer[-1].kick if self.buffer else False
        
        if (state.punch and not prev_punch) or (state.kick and not prev_kick):
            self.buffered_attacks.append(BufferedInput(input_state=state, frame_pressed=self.current_frame))
        
        self.buffer.append(state)
        self.current_frame += 1
        
        self.buffered_attacks = [bi for bi in self.buffered_attacks if self.current_frame - bi.frame_pressed < INPUT_BUFFER_ON_WAKEUP]
        
    def get_current(self) -> InputState:
        return self.buffer[-1] if self.buffer else InputState()
    
    def get_previous(self, frames_back: int = 1) -> InputState:
        if len(self.buffer) > frames_back:
            return self.buffer[-(frames_back + 1)]
        return InputState()
    
    def consume_buffered_attack(self) -> Optional[InputState]:
        for buffered in self.buffered_attacks:
            if not buffered.consumed:
                buffered.consumed = True
                return buffered.input_state
        return None
    
    def has_buffered_attack(self) -> bool:
        return any(not bi.consumed for bi in self.buffered_attacks)


class Fighter:
    def __init__(self, x: int, y: int, color: Tuple[int, int, int], player_id: int = 1):
        self.pos_x = float(x)
        self.pos_y = float(y)
        self.render_x = float(x)
        self.render_y = float(y)
        self.screen_shake_offset_x = 0.0
        self.screen_shake_offset_y = 0.0
        
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.width = 60
        self.height = 120
        self.crouch_height = 80
        self.color = color
        self.player_id = player_id
        
        self.input_buffer = InputBuffer()
        self.state = State.IDLE
        self.facing = FacingDirection.RIGHT
        
        self.max_health = 100
        self.health = self.max_health
        
        self.current_attack: Optional[AttackData] = None
        self.attack_frame = 0
        self.has_hit_opponent = False
        
        self.hitstop_frames = 0
        self.hitstun_frames = 0
        self.hitstun_direction = 0
        
        self.last_frame_advantage = 0
        self.frame_advantage_display_timer = 0
        
        self.is_blocking = False
        self.block_direction = 0
        
        self.coyote_time_remaining = 0
        self.was_grounded_last_frame = True
        self.animation_frame = 0
        
        self.combo_count = 0
        self.combo_damage = 0
        self.last_hit_frame = -999
        
        self.hurtboxes: List[Box] = []
        self.active_hitbox: Optional[Box] = None
        self.pushbox: Optional[Box] = None
        self._update_hurtboxes()
        self._update_pushbox()
    
    @property
    def x(self) -> int: return int(self.pos_x)
    @property
    def y(self) -> int: return int(self.pos_y)
    
    @property
    def current_height(self) -> int:
        if self.state == State.CROUCH or self.is_in_attack_crouch():
            return self.crouch_height
        return self.height
    
    @property
    def is_grounded(self) -> bool: return self.pos_y >= GROUND_Y
    
    @property
    def can_act(self) -> bool:
        return self.state in (State.IDLE, State.WALK, State.JUMP, State.CROUCH)
    
    @property
    def can_attack(self) -> bool:
        return self.can_act and (self.is_grounded or self.coyote_time_remaining > 0)
    
    @property
    def is_in_attack_state(self) -> bool:
        return self.state in (State.ATTACK_STARTUP, State.ATTACK_ACTIVE, State.ATTACK_RECOVERY)
    
    def is_in_attack_crouch(self) -> bool:
        return self.current_attack and self.current_attack.height == AttackHeight.LOW
    
    def _update_hurtboxes(self):
        self.hurtboxes.clear()
        height = self.current_height
        self.hurtboxes.append(Box(self.x - self.width // 2 + 5, self.y - height + 5, self.width - 10, height - 5, BoxType.HURTBOX))
        head_r = 20
        self.hurtboxes.append(Box(self.x - head_r, self.y - height - head_r * 2, head_r * 2, head_r * 2, BoxType.HURTBOX))
        
    def _update_pushbox(self):
        height = self.current_height
        self.pushbox = Box(self.x - self.width // 2, self.y - height, self.width, height, BoxType.PUSHBOX)
    
    def face_target(self, target_x: int):
        self.facing = FacingDirection.LEFT if target_x < self.x else FacingDirection.RIGHT
    
    def calculate_attack_hitbox(self) -> Optional[Box]:
        if not self.current_attack: return None
        attack = self.current_attack
        base_w, base_h = (45, 25) if attack.attack_type == AttackType.PUNCH else (60, 35)
        hitbox_w = base_w + attack.range_bonus // 2
        
        hitbox_x = (self.x + self.width // 2 - 5) if self.facing == FacingDirection.RIGHT else (self.x - self.width // 2 - hitbox_w + 5)
        
        if attack.height == AttackHeight.HIGH: hitbox_y = self.y - self.current_height - 10
        elif attack.height == AttackHeight.STRAIGHT: hitbox_y = self.y - self.current_height // 2 - base_h // 2
        else: hitbox_y = self.y - 40
        
        return Box(hitbox_x, hitbox_y, hitbox_w, base_h, BoxType.HITBOX)
    
    def start_attack(self, attack_type: AttackType, height: AttackHeight, full_power: bool):
        attack = AttackDatabase.get_attack(attack_type, height, full_power)
        if attack:
            self.current_attack = attack
            self.attack_frame = 0
            self.state = State.ATTACK_STARTUP
            self.has_hit_opponent = False
            self.vel_x = 0
            self.active_hitbox = None
    
    def take_hit(self, attack: AttackData, attacker_x: int) -> Tuple[bool, int]:
        self.hitstun_direction = 1 if self.x > attacker_x else -1
        
        if self.is_blocking and self.block_direction == -self.hitstun_direction:
            self.health = max(0, self.health - attack.base_damage // 10)
            self.hitstun_frames = attack.hitstun_frames // 3
            self.hitstop_frames = attack.hitstop // 2
            self.vel_x = (attack.knockback * 0.5) * self.hitstun_direction
            return False, 0
            
        self.health = max(0, self.health - attack.base_damage)
        self.hitstun_frames = attack.hitstun_frames
        self.hitstop_frames = attack.hitstop
        self.state = State.HITSTUN
        self.current_attack = None
        self.attack_frame = 0
        self.active_hitbox = None
        self.vel_x = attack.knockback * self.hitstun_direction
        self.vel_y = -5
        
        current_frame = self.input_buffer.current_frame
        if current_frame - self.last_hit_frame > 30:
            self.combo_count = 0
            self.combo_damage = 0
        self.combo_count += 1
        self.combo_damage += attack.base_damage
        self.last_hit_frame = current_frame
        return True, self.combo_count
    
    def update(self, keys_pressed=None, ai_input: InputState = None, opponent: 'Fighter' = None, current_frame: int = 0):
        # Accept either keyboard input or AI input
        if ai_input is not None:
            current_input = self.input_buffer.push_ai_input(ai_input)
        else:
            current_input = self.input_buffer.update(keys_pressed)
            
        if self.was_grounded_last_frame and not self.is_grounded:
            self.coyote_time_remaining = COYOTE_TIME_FRAMES
        elif self.is_grounded:
            self.coyote_time_remaining = 0
        self.was_grounded_last_frame = self.is_grounded
        
        if self.hitstop_frames > 0:
            self.hitstop_frames -= 1
            return
            
        if self.state not in (State.HITSTUN, State.ATTACK_STARTUP, State.ATTACK_ACTIVE, State.ATTACK_RECOVERY):
            self.face_target(opponent.x)
            
        if self.state == State.HITSTUN:
            self._update_hitstun()
        elif self.is_in_attack_state:
            self._update_attack(opponent, current_frame)
        else:
            self._update_movement(current_input)
            self._check_combat_input(current_input)
            
        self._apply_physics()
        self._update_hurtboxes()
        self._update_pushbox()
        self.animation_frame = (self.animation_frame + 1) % 60
        
        self.render_x = self.pos_x + self.screen_shake_offset_x
        self.render_y = self.pos_y + self.screen_shake_offset_y
        self.screen_shake_offset_x *= 0.9
        self.screen_shake_offset_y *= 0.9
        if self.frame_advantage_display_timer > 0:
            self.frame_advantage_display_timer -= 1
    
    def _update_hitstun(self):
        self.hitstun_frames -= 1
        self.vel_x *= 0.95
        if self.hitstun_frames <= 0 and self.is_grounded:
            self.state = State.IDLE
            self.vel_x = 0
            if self.combo_count > 0:
                self.combo_count = 0
                self.combo_damage = 0
    
    def _update_attack(self, opponent: 'Fighter', current_frame: int):
        self.attack_frame += 1
        if not self.current_attack:
            self.state = State.IDLE
            return
        attack = self.current_attack
        startup_end = attack.startup_frames
        active_end = startup_end + attack.active_frames
        recovery_end = active_end + attack.recovery_frames
        
        if self.attack_frame < startup_end:
            self.state = State.ATTACK_STARTUP
            self.active_hitbox = None
        elif self.attack_frame < active_end:
            self.state = State.ATTACK_ACTIVE
            self.active_hitbox = self.calculate_attack_hitbox()
            if not self.has_hit_opponent and self.active_hitbox:
                for hurtbox in opponent.hurtboxes:
                    if self.active_hitbox.intersects(hurtbox) and self._check_height_interaction(opponent):
                        damaged, combo = opponent.take_hit(attack, self.x)
                        self.has_hit_opponent = True
                        self.hitstop_frames = attack.hitstop
                        self.last_frame_advantage = attack.frame_advantage_on_hit if damaged else attack.frame_advantage_on_block
                        self.frame_advantage_display_timer = 60
                        opponent.screen_shake_offset_x = attack.knockback * 0.5
                        break
        else:
            self.state = State.ATTACK_RECOVERY
            self.active_hitbox = None
            
        if self.attack_frame >= recovery_end:
            self.state = State.IDLE
            self.current_attack = None
            self.attack_frame = 0
            self.active_hitbox = None
            
    def _check_height_interaction(self, opponent: 'Fighter') -> bool:
        if not self.current_attack: return False
        if self.current_attack.height == AttackHeight.HIGH and (opponent.state == State.CROUCH or opponent.is_in_attack_crouch()):
            return False
        return True
    
    def _update_movement(self, current_input: InputState):
        self.block_direction = 0
        self.is_blocking = False
        if self.is_grounded:
            self.vel_x = 0
            moving = False
            if current_input.left:
                self.vel_x = -WALK_SPEED
                moving = True
                if self.facing == FacingDirection.RIGHT:
                    self.is_blocking = True
                    self.block_direction = -1
                    self.state = State.BLOCK
                else:
                    self.state = State.WALK
            elif current_input.right:
                self.vel_x = WALK_SPEED
                moving = True
                if self.facing == FacingDirection.LEFT:
                    self.is_blocking = True
                    self.block_direction = 1
                    self.state = State.BLOCK
                else:
                    self.state = State.WALK
            if current_input.down:
                self.state = State.CROUCH
                self.vel_x *= 0.5
            if current_input.up and (self.is_grounded or self.coyote_time_remaining > 0):
                self.vel_y = JUMP_FORCE
                self.state = State.JUMP
                self.coyote_time_remaining = 0
            if not moving and not current_input.down and not current_input.up and self.state != State.BLOCK:
                self.state = State.IDLE
            if self.state == State.BLOCK and not self.is_blocking:
                self.state = State.IDLE
        else:
            if current_input.left: self.vel_x = -WALK_SPEED * 0.5
            elif current_input.right: self.vel_x = WALK_SPEED * 0.5
        if self.coyote_time_remaining > 0: self.coyote_time_remaining -= 1
    
    def _check_combat_input(self, current_input: InputState):
        if self.can_attack and self.input_buffer.has_buffered_attack():
            buffered = self.input_buffer.consume_buffered_attack()
            if buffered: self._process_attack_input(buffered); return
        if self.can_attack and current_input.has_attack():
            prev = self.input_buffer.get_previous()
            if (current_input.punch and not prev.punch) or (current_input.kick and not prev.kick):
                self._process_attack_input(current_input)
    
    def _process_attack_input(self, input_state: InputState):
        height = AttackHeight.HIGH if input_state.up else AttackHeight.LOW if input_state.down else AttackHeight.STRAIGHT
        if input_state.punch: self.start_attack(AttackType.PUNCH, height, input_state.power)
        elif input_state.kick: self.start_attack(AttackType.KICK, height, input_state.power)
    
    def _apply_physics(self):
        if not self.is_grounded: self.vel_y += GRAVITY
        self.pos_x += self.vel_x
        self.pos_y += self.vel_y
        if self.pos_y > GROUND_Y:
            self.pos_y = GROUND_Y
            self.vel_y = 0
            if self.state == State.JUMP: self.state = State.IDLE
        self.pos_x = max(self.width // 2, min(SCREEN_WIDTH - self.width // 2, self.pos_x))
    
    def draw(self, surface: pygame.Surface):
        if self.state == State.HITSTUN: body_color = WHITE
        elif self.state == State.BLOCK: body_color = CYAN
        elif self.state == State.ATTACK_ACTIVE: body_color = ORANGE
        elif self.state == State.ATTACK_STARTUP: body_color = YELLOW
        else: body_color = self.color
        
        rx, ry = int(self.render_x), int(self.render_y)
        
        for hurtbox in self.hurtboxes:
            s = pygame.Surface((hurtbox.width, hurtbox.height), pygame.SRCALPHA)
            s.fill((0, 255, 0, 40))
            surface.blit(s, (hurtbox.x, hurtbox.y))
            pygame.draw.rect(surface, GREEN, hurtbox.to_rect(), 1)
        if self.pushbox: pygame.draw.rect(surface, BLUE, self.pushbox.to_rect(), 1)
        
        body_rect = pygame.Rect(rx - self.width // 2, ry - self.current_height, self.width, self.current_height)
        pygame.draw.rect(surface, body_color, body_rect)
        pygame.draw.rect(surface, BLACK, body_rect, 2)
        
        head_r = 20
        head_y = ry - self.current_height - head_r
        pygame.draw.circle(surface, body_color, (rx, int(head_y)), head_r)
        pygame.draw.circle(surface, BLACK, (rx, int(head_y)), head_r, 2)
        
        eye_off = 8 * self.facing.value
        pygame.draw.circle(surface, WHITE, (rx + eye_off, int(head_y - 3)), 5)
        pygame.draw.circle(surface, BLACK, (rx + int(eye_off * 1.3), int(head_y - 3)), 2)
        
        if self.active_hitbox:
            s = pygame.Surface((self.active_hitbox.width, self.active_hitbox.height), pygame.SRCALPHA)
            s.fill((255, 0, 0, 100))
            surface.blit(s, (self.active_hitbox.x, self.active_hitbox.y))
            pygame.draw.rect(surface, RED, self.active_hitbox.to_rect(), 2)
        
        self._draw_limbs(surface, rx, ry)
        self._draw_state_indicator(surface, rx, ry)
        self._draw_health_bar(surface, rx, ry)
        
        if self.frame_advantage_display_timer > 0: self._draw_frame_advantage(surface, rx, ry)
        if self.combo_count > 1: self._draw_combo_counter(surface, rx, ry)
    
    def _draw_limbs(self, surface, rx, ry):
        lc = DARK_BLUE if self.player_id == 1 else DARK_RED
        arm_l = 35
        arm_y = ry - self.current_height + 30
        if self.is_in_attack_state and self.current_attack:
            if self.current_attack.attack_type == AttackType.PUNCH:
                if self.state == State.ATTACK_ACTIVE:
                    ax = rx + arm_l * self.facing.value
                    pygame.draw.line(surface, lc, (rx, arm_y), (ax, arm_y - 10), 8)
                    pygame.draw.circle(surface, lc, (int(ax), int(arm_y - 10)), 12)
                else:
                    pygame.draw.line(surface, lc, (rx, arm_y), (rx - 15 * self.facing.value, arm_y + 15), 6)
            else:
                pygame.draw.line(surface, lc, (rx, arm_y), (rx - 15 * self.facing.value, arm_y + 15), 6)
                
            if self.current_attack.attack_type == AttackType.KICK:
                leg_y = ry - 20
                if self.state == State.ATTACK_ACTIVE:
                    kx = rx + 50 * self.facing.value
                    ky = leg_y - 20 if self.current_attack.height == AttackHeight.HIGH else leg_y + 10
                    pygame.draw.line(surface, lc, (rx, leg_y), (kx, ky), 8)
                    pygame.draw.rect(surface, lc, (kx - 10, ky - 8, 20, 16))
                else:
                    pygame.draw.line(surface, lc, (rx - 10, leg_y), (rx - 15, ry), 8)
            else:
                pygame.draw.line(surface, lc, (rx - 10, ry - 20), (rx - 15, ry), 8)
                pygame.draw.line(surface, lc, (rx + 10, ry - 20), (rx + 15, ry), 8)
        elif self.state == State.CROUCH:
            pygame.draw.line(surface, lc, (rx - 10, ry - 20), (rx - 25, ry - 30), 8)
            pygame.draw.line(surface, lc, (rx + 10, ry - 20), (rx + 25, ry - 30), 8)
            pygame.draw.line(surface, lc, (rx, ry - 50), (rx - 20 * self.facing.value, ry - 40), 6)
        else:
            pygame.draw.line(surface, lc, (rx, arm_y), (rx - 20 * self.facing.value, arm_y + 25), 6)
            off = math.sin(self.animation_frame * 0.2) * 3 if self.state == State.WALK else 0
            pygame.draw.line(surface, lc, (rx - 10, ry - 20), (rx - 15 + off, ry), 8)
            pygame.draw.line(surface, lc, (rx + 10, ry - 20), (rx + 15 - off, ry), 8)
            
    def _draw_state_indicator(self, surface, rx, ry):
        font = pygame.font.Font(None, 22)
        txt = f"{self.current_attack.name}" if self.current_attack else self.state.name.replace("ATTACK_", "")
        ts = font.render(txt, True, WHITE)
        tr = ts.get_rect(centerx=rx, bottom=ry - self.current_height - 55)
        bg = tr.inflate(8, 4)
        pygame.draw.rect(surface, BLACK, bg); pygame.draw.rect(surface, WHITE, bg, 1)
        surface.blit(ts, tr)
        
    def _draw_frame_advantage(self, surface, rx, ry):
        font = pygame.font.Font(None, 24)
        a = self.last_frame_advantage
        c = GREEN if a > 0 else RED if a < 0 else WHITE
        ts = font.render(f"{'+' if a >= 0 else ''}{a}f", True, c)
        tr = ts.get_rect(centerx=rx, bottom=ry - self.current_height - 75)
        pygame.draw.rect(surface, BLACK, tr.inflate(6, 4))
        surface.blit(ts, tr)
        
    def _draw_combo_counter(self, surface, rx, ry):
        font = pygame.font.Font(None, 36)
        ts = font.render(f"{self.combo_count} HITS! {self.combo_damage} dmg", True, ORANGE)
        tr = ts.get_rect(centerx=rx, top=ry - self.current_height - 100)
        bg = tr.inflate(10, 6)
        pygame.draw.rect(surface, BLACK, bg); pygame.draw.rect(surface, ORANGE, bg, 2)
        surface.blit(ts, tr)
        
    def _draw_health_bar(self, surface, rx, ry):
        bw, bh = 80, 10
        bx = rx - bw // 2
        by = ry - self.current_height - 70
        pygame.draw.rect(surface, GRAY, (bx, by, bw, bh))
        hw = int(bw * (self.health / self.max_health))
        hc = GREEN if self.health > 50 else YELLOW if self.health > 25 else RED
        pygame.draw.rect(surface, hc, (bx, by, hw, bh))
        pygame.draw.rect(surface, WHITE, (bx, by, bw, bh), 2)