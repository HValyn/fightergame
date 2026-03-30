"""
The CPU AI Controller System.
Analyzes opponent state, manages distance zones, and generates human-like InputStates.
"""

import random
from collections import deque
from typing import Optional, List, Tuple

from constants import *

class AIBehavior(Enum):
    IDLE = auto()
    APPROACH = auto()
    RETREAT = auto()
    ATTACK = auto()
    BLOCK_HIGH = auto()
    BLOCK_LOW = auto()
    PUNISH = auto()
    PRESSURE = auto()
    WAIT = auto()
    JUMP_IN = auto()
    ANTI_AIR = auto()
    MIXUP = auto()

class AIDifficulty:
    EASY = {'reaction_frames': 20, 'decision_interval': 30, 'block_chance': 0.3, 'punish_chance': 0.2, 'combo_chance': 0.1, 'aggression': 0.3, 'whiff_punish_chance': 0.1}
    MEDIUM = {'reaction_frames': 12, 'decision_interval': 15, 'block_chance': 0.6, 'punish_chance': 0.5, 'combo_chance': 0.4, 'aggression': 0.5, 'whiff_punish_chance': 0.4}
    HARD = {'reaction_frames': 5, 'decision_interval': 6, 'block_chance': 0.85, 'punish_chance': 0.8, 'combo_chance': 0.7, 'aggression': 0.65, 'whiff_punish_chance': 0.75}
    BRUTAL = {'reaction_frames': 2, 'decision_interval': 3, 'block_chance': 0.95, 'punish_chance': 0.95, 'combo_chance': 0.9, 'aggression': 0.7, 'whiff_punish_chance': 0.9}

@dataclass
class OpponentReading:
    state: State = State.IDLE
    attack_type: Optional[AttackType] = None
    attack_height: Optional[AttackHeight] = None
    distance: int = 0
    in_startup: bool = False
    in_active: bool = False
    in_recovery: bool = False
    is_jumping: bool = False
    is_crouching: bool = False
    health_percent: float = 1.0

class AIController:
    FAR_RANGE = 250
    MID_RANGE = 150
    CLOSE_RANGE = 90
    THROW_RANGE = 50

    def __init__(self, fighter: 'Fighter', difficulty: dict = None):
        self.fighter = fighter
        self.difficulty = difficulty or AIDifficulty.MEDIUM
        self.block_chance = self.difficulty['block_chance']
        self.punish_chance = self.difficulty['punish_chance']
        self.combo_chance = self.difficulty['combo_chance']
        self.aggression = self.difficulty['aggression']
        
        self.current_behavior = AIBehavior.IDLE
        self.think_timer = 0
        self.behavior_timer = 0
        
        self.opponent_attack_history: deque[Tuple[AttackType, AttackHeight]] = deque(maxlen=20)
        self.opponent_height_preference = {AttackHeight.HIGH: 0, AttackHeight.STRAIGHT: 0, AttackHeight.LOW: 0}
        
        self.combo_queue: List[Tuple[AttackType, AttackHeight, bool]] = []
        self.rng = random.Random()

    def update(self, opponent: 'Fighter', current_frame: int) -> InputState:
        self.think_timer -= 1
        self.behavior_timer -= 1
        self._track_opponent(opponent)
        reading = self._read_opponent(opponent)
        ai_input = self._generate_input(reading, opponent, current_frame)
        return ai_input

    def _read_opponent(self, opponent: 'Fighter') -> OpponentReading:
        r = OpponentReading()
        r.state = opponent.state
        r.distance = abs(self.fighter.x - opponent.x)
        r.is_jumping = not opponent.is_grounded
        r.is_crouching = opponent.state == State.CROUCH
        r.health_percent = opponent.health / opponent.max_health
        if opponent.current_attack:
            r.attack_type = opponent.current_attack.attack_type
            r.attack_height = opponent.current_attack.height
            r.in_startup = opponent.state == State.ATTACK_STARTUP
            r.in_active = opponent.state == State.ATTACK_ACTIVE
            r.in_recovery = opponent.state == State.ATTACK_RECOVERY
        return r

    def _track_opponent(self, opponent: 'Fighter'):
        if opponent.current_attack and opponent.has_hit_opponent:
            a = (opponent.current_attack.attack_type, opponent.current_attack.height)
            self.opponent_attack_history.append(a)
            self.opponent_height_preference[a[1]] += 1

    def _generate_input(self, reading: OpponentReading, opponent: 'Fighter', current_frame: int) -> InputState:
        if reading.in_startup or reading.in_active:
            return self._handle_opponent_attack(reading, opponent)
        if reading.in_recovery:
            return self._handle_opponent_recovery(reading, opponent)
        if self.combo_queue:
            return self._execute_combo()
        if self.think_timer <= 0:
            self._make_decision(reading, opponent)
            self.think_timer = self.difficulty['decision_interval'] + self.rng.randint(0, 5)
        return self._execute_behavior(reading, opponent)

    def _handle_opponent_attack(self, reading: OpponentReading, opponent: 'Fighter') -> InputState:
        inp = InputState()
        if self.rng.random() < self.block_chance:
            block_away = 1 if self.fighter.x > opponent.x else -1
            if reading.attack_height == AttackHeight.LOW:
                inp.down = True
                self.current_behavior = AIBehavior.BLOCK_LOW
            elif reading.attack_height == AttackHeight.HIGH:
                if block_away == 1: inp.left = True
                else: inp.right = True
                self.current_behavior = AIBehavior.BLOCK_HIGH
            else:
                likely_low = self.opponent_height_preference[AttackHeight.LOW] > self.opponent_height_preference[AttackHeight.HIGH]
                if likely_low: inp.down = True
                else:
                    if block_away == 1: inp.left = True
                    else: inp.right = True
            self.fighter.is_blocking = True
            self.fighter.block_direction = block_away
        else:
            self.fighter.is_blocking = False
        return inp

    def _handle_opponent_recovery(self, reading: OpponentReading, opponent: 'Fighter') -> InputState:
        if reading.distance > self.CLOSE_RANGE or self.rng.random() > self.punish_chance:
            return InputState()
        if reading.distance < self.THROW_RANGE:
            return self._get_attack_input(AttackType.PUNCH, AttackHeight.LOW, False)
        return self._get_attack_input(AttackType.KICK, AttackHeight.STRAIGHT, False)

    def _make_decision(self, reading: OpponentReading, opponent: 'Fighter'):
        my_hp = self.fighter.health / self.fighter.max_health
        ag = self.aggression * (0.5 if my_hp < 0.3 else 1.3 if reading.health_percent < 0.3 else 1.0)
        
        if reading.distance > self.FAR_RANGE:
            self.current_behavior = AIBehavior.APPROACH if self.rng.random() < ag else AIBehavior.WAIT
        elif reading.distance > self.MID_RANGE:
            r = self.rng.random()
            if r < ag * 0.4: self.current_behavior = AIBehavior.JUMP_IN
            elif r < ag * 0.7: self.current_behavior = AIBehavior.APPROACH
            elif r < 0.85: self.current_behavior = AIBehavior.WAIT
            else: self.current_behavior = AIBehavior.RETREAT
        elif reading.distance > self.CLOSE_RANGE:
            r = self.rng.random()
            if r < ag * 0.6: self.current_behavior = AIBehavior.ATTACK
            elif r < ag * 0.8: self.current_behavior = AIBehavior.MIXUP
            else: self.current_behavior = AIBehavior.WAIT
        else:
            r = self.rng.random()
            if r < ag * 0.5: self.current_behavior = AIBehavior.ATTACK
            elif r < 0.7: self.current_behavior = AIBehavior.RETREAT
            else: self.current_behavior = AIBehavior.MIXUP
            
        if reading.is_jumping and reading.distance < self.MID_RANGE and self.rng.random() < 0.6:
            self.current_behavior = AIBehavior.ANTI_AIR
        self.behavior_timer = 15 + self.rng.randint(0, 15)

    def _execute_behavior(self, reading: OpponentReading, opponent: 'Fighter') -> InputState:
        inp = InputState()
        self.fighter.is_blocking = False
        self.fighter.block_direction = 0
        
        if self.behavior_timer <= 0: self.current_behavior = AIBehavior.IDLE
        
        if self.current_behavior == AIBehavior.APPROACH:
            if self.fighter.x < opponent.x: inp.right = True
            else: inp.left = True
        elif self.current_behavior == AIBehavior.RETREAT:
            if self.fighter.x < opponent.x: inp.left = True
            else: inp.right = True
        elif self.current_behavior == AIBehavior.ATTACK:
            if reading.distance <= self.CLOSE_RANGE:
                h = AttackHeight.LOW if self.rng.random() < 0.4 else AttackHeight.STRAIGHT
                inp = self._get_attack_input(AttackType.PUNCH, h, False)
            elif reading.distance <= self.MID_RANGE:
                if self.rng.random() < 0.3: inp = self._get_attack_input(AttackType.KICK, AttackHeight.LOW, False)
                else: inp = self._get_attack_input(AttackType.KICK, AttackHeight.STRAIGHT, self.rng.random() < 0.2)
            self.current_behavior = AIBehavior.IDLE
        elif self.current_behavior == AIBehavior.MIXUP:
            h = self.rng.choice([AttackHeight.LOW, AttackHeight.STRAIGHT, AttackHeight.HIGH])
            p = self.rng.random() < 0.2
            t = self.rng.choice([AttackType.PUNCH, AttackType.KICK])
            inp = self._get_attack_input(t, h, p)
            if self.rng.random() < self.combo_chance:
                self.combo_queue.append((AttackType.KICK, AttackHeight.STRAIGHT if h == AttackHeight.LOW else AttackHeight.LOW, False))
            self.current_behavior = AIBehavior.IDLE
        elif self.current_behavior == AIBehavior.JUMP_IN:
            inp.up = True
            if self.fighter.x < opponent.x: inp.right = True
            else: inp.left = True
            self.combo_queue.append((self.rng.choice([AttackType.PUNCH, AttackType.KICK]), self.rng.choice([AttackHeight.HIGH, AttackHeight.STRAIGHT]), False))
        elif self.current_behavior == AIBehavior.ANTI_AIR:
            inp = self._get_attack_input(AttackType.PUNCH if self.rng.random() < 0.6 else AttackType.KICK, AttackHeight.HIGH, False)
            self.current_behavior = AIBehavior.IDLE
        return inp

    def _execute_combo(self) -> InputState:
        if not self.combo_queue: return InputState()
        t, h, p = self.combo_queue.pop(0)
        return self._get_attack_input(t, h, p)

    def _get_attack_input(self, attack_type: AttackType, height: AttackHeight, power: bool) -> InputState:
        inp = InputState()
        if attack_type == AttackType.PUNCH: inp.punch = True
        else: inp.kick = True
        if height == AttackHeight.HIGH: inp.up = True
        elif height == AttackHeight.LOW: inp.down = True
        inp.power = power
        return inp

    def on_hit_landed(self, combo_count: int):
        if combo_count > 0 and self.rng.random() < self.combo_chance:
            self.combo_queue.append((self.rng.choice([AttackType.PUNCH, AttackType.KICK]), self.rng.choice([AttackHeight.STRAIGHT, AttackHeight.LOW]), False))
            if combo_count >= 3:
                self.combo_queue.append((AttackType.KICK, AttackHeight.STRAIGHT, True))

    def on_blocked(self):
        self.combo_queue.clear()
        self.current_behavior = AIBehavior.RETREAT
        self.behavior_timer = 15