"""
AI Controller — updated to work with the new character system.
Uses the InputState interface (no direct Fighter mutation) and is
aware of character-specific special moves.
"""

import random
from collections import deque
from typing import Optional, List, Tuple

from constants import (
    FighterState, AttackType, AttackHeight, AttackProperty, MotionType,
    InputState, AttackData, SpecialMoveDef,
)

# Stick motions written for a fighter facing RIGHT ("right" = forward).
# The AI mirrors them when facing left. The last entry is pressed with the button.
CHARGE_HOLD_FRAMES = 42
AI_MOTION_SEQUENCES = {
    MotionType.NONE: [[]],
    MotionType.QUARTER_CIRCLE_FORWARD: [["down"], ["down", "right"], ["right"]],
    MotionType.QUARTER_CIRCLE_BACK: [["down"], ["down", "left"], ["left"]],
    MotionType.DRAGON_PUNCH_FORWARD: [["right"], ["down"], ["down", "right"]],
    MotionType.DRAGON_PUNCH_BACK: [["left"], ["down"], ["down", "left"]],
    MotionType.HALF_CIRCLE_FORWARD: [["left"], ["down", "left"], ["down"], ["down", "right"], ["right"]],
    MotionType.HALF_CIRCLE_BACK: [["right"], ["down", "right"], ["down"], ["down", "left"], ["left"]],
    MotionType.CHARGE_BACK: [["left"]] * CHARGE_HOLD_FRAMES + [["right"]],
    MotionType.CHARGE_DOWN: [["down"]] * CHARGE_HOLD_FRAMES + [["up"]],
    MotionType.SUPER_CHARGE: [["down"], ["down", "right"], ["right"]] * 2,
    MotionType.ZIGZAG: [["down"], ["up"]],
}
_MIRROR = {"left": "right", "right": "left"}
from character_defs import CharacterDef


class AIBehavior:
    IDLE = "idle"
    APPROACH = "approach"
    RETREAT = "retreat"
    ATTACK = "attack"
    BLOCK = "block"
    PUNISH = "punish"
    PRESSURE = "pressure"
    WAIT = "wait"
    JUMP_IN = "jump_in"
    ANTI_AIR = "anti_air"
    MIXUP = "mixup"
    USE_SPECIAL = "use_special"


class AIDifficulty:
    EASY = {
        'reaction_frames': 20, 'decision_interval': 30,
        'block_chance': 0.3, 'punish_chance': 0.2, 'combo_chance': 0.1,
        'aggression': 0.3, 'whiff_punish_chance': 0.1, 'special_chance': 0.05,
    }
    MEDIUM = {
        'reaction_frames': 12, 'decision_interval': 15,
        'block_chance': 0.6, 'punish_chance': 0.5, 'combo_chance': 0.4,
        'aggression': 0.5, 'whiff_punish_chance': 0.4, 'special_chance': 0.15,
    }
    HARD = {
        'reaction_frames': 5, 'decision_interval': 6,
        'block_chance': 0.85, 'punish_chance': 0.8, 'combo_chance': 0.7,
        'aggression': 0.65, 'whiff_punish_chance': 0.75, 'special_chance': 0.3,
    }
    BRUTAL = {
        'reaction_frames': 2, 'decision_interval': 3,
        'block_chance': 0.95, 'punish_chance': 0.95, 'combo_chance': 0.9,
        'aggression': 0.7, 'whiff_punish_chance': 0.9, 'special_chance': 0.4,
    }


class AIController:
    """
    CPU AI that generates InputState commands.
    Does NOT directly mutate the Fighter — goes through the input system.
    """

    FAR_RANGE = 250
    MID_RANGE = 150
    CLOSE_RANGE = 90
    THROW_RANGE = 50

    def __init__(self, character: CharacterDef, difficulty: dict = None):
        self.character = character
        self.difficulty = difficulty or AIDifficulty.MEDIUM

        self.block_chance = self.difficulty['block_chance']
        self.punish_chance = self.difficulty['punish_chance']
        self.combo_chance = self.difficulty['combo_chance']
        self.aggression = self.difficulty['aggression']
        self.special_chance = self.difficulty['special_chance']

        self.current_behavior = AIBehavior.IDLE
        self.think_timer = 0
        self.behavior_timer = 0

        self.opponent_attack_history: deque = deque(maxlen=20)
        self.opponent_height_pref = {AttackHeight.HIGH: 0, AttackHeight.STRAIGHT: 0, AttackHeight.LOW: 0}

        self.combo_queue: List[InputState] = []
        self.pending_special: Optional[str] = None  # "qcf", "dp", etc.

        self.rng = random.Random()

        # Reaction model: the AI only "sees" an attack after reaction_frames
        self.reaction_frames = self.difficulty.get('reaction_frames', 0)
        self._opp_attack_frames = 0
        self._block_decision: Optional[bool] = None

    def update(self, opponent_state: FighterState, opponent_x: int,
               opponent_y: float, self_x: int, self_y: float,
               opponent_current_attack: Optional[AttackData],
               opponent_has_hit: bool,
               self_facing_right: bool,
               current_frame: int) -> InputState:
        """Generate an AI input based on the game state."""

        self.think_timer -= 1
        self.behavior_timer -= 1

        # Read opponent
        distance = abs(self_x - opponent_x)
        is_opponent_jumping = opponent_y < 545  # approx ground - 5
        is_opponent_crouching = opponent_state in (FighterState.CROUCH, FighterState.BLOCK_CROUCHING)

        is_startup = opponent_state == FighterState.ATTACK_STARTUP
        is_active = opponent_state == FighterState.ATTACK_ACTIVE
        is_recovery = opponent_state == FighterState.ATTACK_RECOVERY

        # Priority 1: React to opponent's attack (after a human-like delay)
        if is_startup or is_active:
            self._opp_attack_frames += 1
            if self._opp_attack_frames >= self.reaction_frames:
                return self._handle_opponent_attack(
                    opponent_current_attack, distance, self_x, self_facing_right
                )
        else:
            self._opp_attack_frames = 0
            self._block_decision = None

        # Priority 2: Punish recovery
        if is_recovery:
            return self._handle_punish(distance, self_facing_right)

        # Priority 3: Execute queued combo
        if self.combo_queue:
            return self.combo_queue.pop(0)

        # Priority 4: Anti-air
        if is_opponent_jumping and distance < self.MID_RANGE:
            if self.rng.random() < 0.6:
                return self._make_anti_air(self_facing_right)

        # Priority 5: Make a decision
        if self.think_timer <= 0:
            self._make_decision(distance, is_opponent_jumping, is_opponent_crouching)
            self.think_timer = self.difficulty['decision_interval'] + self.rng.randint(0, 5)

        # Priority 6: Execute behavior
        return self._execute_behavior(distance, self_facing_right)

    # =========================================================================
    # REACTION HANDLERS
    # =========================================================================
    def _handle_opponent_attack(self, opp_attack, distance, self_x, facing_right) -> InputState:
        inp = InputState()
        if not opp_attack:
            return inp
        # Decide ONCE per opponent attack (re-rolling every frame made the guard flicker)
        if self._block_decision is None:
            self._block_decision = self.rng.random() < self.block_chance
        if not self._block_decision:
            return inp

        # Hold away from the opponent
        back_dir = "left" if facing_right else "right"
        setattr(inp, back_dir, True)

        # Lows must be blocked crouching; overheads/mids/highs standing
        if opp_attack.height == AttackHeight.LOW:
            inp.down = True

        self.current_behavior = AIBehavior.BLOCK
        return inp

    def _handle_punish(self, distance, facing_right) -> InputState:
        if distance > self.CLOSE_RANGE or self.rng.random() > self.punish_chance:
            return InputState()

        # Try a special move for punish
        if self.rng.random() < self.special_chance and self.character.special_moves:
            sp = self.rng.choice(self.character.special_moves)
            if sp.meter_cost <= 0:  # Don't waste meter on random punishes
                return self._make_special_input(sp, facing_right)

        # Normal punish
        inp = InputState()
        inp.punch = True
        return inp

    def _make_anti_air(self, facing_right) -> InputState:
        # Try DP if available
        for sp in self.character.special_moves:
            if sp.attack_data.has_property(AttackProperty.INVINCIBLE_STARTUP) or \
               sp.attack_data.has_property(AttackProperty.LAUNCHER):
                return self._make_special_input(sp, facing_right)

        inp = InputState()
        inp.up = True
        inp.punch = True
        return inp

    # =========================================================================
    # DECISION MAKING
    # =========================================================================
    def _make_decision(self, distance, opp_jumping, opp_crouching):
        if distance > self.FAR_RANGE:
            self.current_behavior = (
                AIBehavior.APPROACH if self.rng.random() < self.aggression
                else AIBehavior.WAIT
            )
        elif distance > self.MID_RANGE:
            r = self.rng.random()
            if r < self.aggression * 0.3:
                self.current_behavior = AIBehavior.USE_SPECIAL
            elif r < self.aggression * 0.5:
                self.current_behavior = AIBehavior.JUMP_IN
            elif r < self.aggression * 0.8:
                self.current_behavior = AIBehavior.APPROACH
            elif r < 0.9:
                self.current_behavior = AIBehavior.WAIT
            else:
                self.current_behavior = AIBehavior.RETREAT
        elif distance > self.CLOSE_RANGE:
            r = self.rng.random()
            if r < self.aggression * 0.4:
                self.current_behavior = AIBehavior.ATTACK
            elif r < self.aggression * 0.6:
                self.current_behavior = AIBehavior.USE_SPECIAL
            elif r < self.aggression * 0.8:
                self.current_behavior = AIBehavior.MIXUP
            else:
                self.current_behavior = AIBehavior.WAIT
        else:
            r = self.rng.random()
            if r < self.aggression * 0.5:
                self.current_behavior = AIBehavior.ATTACK
            elif r < 0.65:
                self.current_behavior = AIBehavior.RETREAT
            elif r < 0.8:
                self.current_behavior = AIBehavior.MIXUP
            else:
                self.current_behavior = AIBehavior.USE_SPECIAL

        self.behavior_timer = 15 + self.rng.randint(0, 15)

    # =========================================================================
    # BEHAVIOR EXECUTION
    # =========================================================================
    def _execute_behavior(self, distance, facing_right) -> InputState:
        if self.behavior_timer <= 0:
            self.current_behavior = AIBehavior.IDLE

        if self.current_behavior == AIBehavior.APPROACH:
            inp = InputState()
            direction = "right" if facing_right else "left"
            setattr(inp, direction, True)
            return inp

        elif self.current_behavior == AIBehavior.RETREAT:
            inp = InputState()
            direction = "left" if facing_right else "right"
            setattr(inp, direction, True)
            return inp

        elif self.current_behavior == AIBehavior.WAIT:
            return InputState()

        elif self.current_behavior == AIBehavior.JUMP_IN:
            inp = InputState()
            inp.up = True
            direction = "right" if facing_right else "left"
            setattr(inp, direction, True)
            # Queue an air attack
            if self.combo_chance > 0.3:
                next_in = InputState()
                next_in.punch = self.rng.random() < 0.5
                next_in.kick = not next_in.punch
                self.combo_queue.append(next_in)
            return inp

        elif self.current_behavior == AIBehavior.ATTACK:
            return self._make_attack_input(distance, facing_right)

        elif self.current_behavior == AIBehavior.MIXUP:
            inp = self._make_attack_input(distance, facing_right)
            if self.rng.random() < self.combo_chance:
                next_in = InputState()
                next_in.kick = True
                self.combo_queue.append(next_in)
            return inp

        elif self.current_behavior == AIBehavior.USE_SPECIAL:
            return self._try_use_special(distance, facing_right)

        return InputState()

    def _make_attack_input(self, distance, facing_right) -> InputState:
        inp = InputState()
        if distance <= self.CLOSE_RANGE:
            # Close range — jab or low
            if self.rng.random() < 0.4:
                inp.down = True
                inp.punch = True
            else:
                inp.punch = True
        elif distance <= self.MID_RANGE:
            # Mid range — kick or heavy
            if self.rng.random() < 0.3:
                inp.kick = True
                inp.heavy = True
            else:
                inp.kick = True
        else:
            inp.kick = True
        self.current_behavior = AIBehavior.IDLE
        return inp

    def _try_use_special(self, distance, facing_right) -> InputState:
        """Try to use a character-specific special move."""
        specials = self.character.special_moves
        if not specials or self.rng.random() > self.special_chance:
            return self._make_attack_input(distance, facing_right)

        # Pick a random special (prefer projectile at range, grab up close)
        if distance > self.MID_RANGE:
            # Prefer projectiles
            projectile_specials = [s for s in specials
                                   if s.attack_data.has_property(AttackProperty.PROJECTILE)]
            if projectile_specials:
                sp = self.rng.choice(projectile_specials)
                return self._make_special_input(sp, facing_right)
        elif distance < self.CLOSE_RANGE:
            # Prefer grabs / close specials
            grab_specials = [s for s in specials
                            if s.attack_data.has_property(AttackProperty.THROW)]
            if grab_specials:
                sp = self.rng.choice(grab_specials)
                return self._make_special_input(sp, facing_right)

        sp = self.rng.choice(specials)
        return self._make_special_input(sp, facing_right)

    def _make_special_input(self, sp: SpecialMoveDef, facing_right: bool) -> InputState:
        """
        Perform a special the same way a human would: queue the stick motion
        frame by frame and press the button on the final frame. Returns the
        first frame; the rest goes into combo_queue.
        """
        frames = self.build_motion_inputs(sp.motion, sp.attack_button, facing_right)
        self.combo_queue = frames[1:] + self.combo_queue
        return frames[0]

    @staticmethod
    def build_motion_inputs(motion: MotionType, button: str, facing_right: bool) -> List[InputState]:
        seq = AI_MOTION_SEQUENCES.get(motion, [[]])
        frames: List[InputState] = []
        for i, dirs in enumerate(seq):
            inp = InputState()
            for d in dirs:
                setattr(inp, d if facing_right else _MIRROR.get(d, d), True)
            if i == len(seq) - 1:
                setattr(inp, button, True)
            frames.append(inp)
        return frames

    def on_hit_landed(self, combo_count: int):
        """Called when the AI's fighter lands a hit — queue follow-up."""
        if combo_count > 0 and self.rng.random() < self.combo_chance:
            follow_up = InputState()
            if self.rng.random() < 0.5:
                follow_up.punch = True
            else:
                follow_up.kick = True
            self.combo_queue.append(follow_up)

    def on_blocked(self):
        """Called when the AI's attack is blocked."""
        self.combo_queue.clear()
        self.current_behavior = AIBehavior.RETREAT
        self.behavior_timer = 15

    def reset(self):
        """Reset AI state for new round."""
        self.current_behavior = AIBehavior.IDLE
        self.think_timer = 0
        self.behavior_timer = 0
        self.combo_queue.clear()
        self._opp_attack_frames = 0
        self._block_decision = None
        self.opponent_attack_history.clear()
        self.opponent_height_pref = {AttackHeight.HIGH: 0, AttackHeight.STRAIGHT: 0, AttackHeight.LOW: 0}
