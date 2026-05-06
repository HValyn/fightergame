"""
Move System — resolves character inputs into the correct AttackData.
Handles normal attacks, command normals, special moves, and move priority.
"""

from typing import Optional, Tuple, List

from constants import (
    AttackType, AttackHeight, MoveType, AttackProperty, MotionType,
    InputState, AttackData, SpecialMoveDef, FighterState,
)
from character_defs import CharacterDef
from motion_input import MotionDetector


class MoveResolver:
    """
    Resolves player inputs into attack data using the character's movelist.
    Priority order:
        1. Super moves (if meter available)
        2. Special moves (motion + button)
        3. Heavy normals (button + heavy modifier)
        4. Command normals (direction + button)
        5. Light normals (button alone)
    """

    def __init__(self, character: CharacterDef):
        self.character = character
        self._build_attack_lookup()

    def _build_attack_lookup(self):
        """Build quick-lookup dictionaries for the character's attacks."""
        self.normal_lookup = {}    # (attack_type, height, heavy) -> AttackData
        self.move_id_lookup = {}   # move_id -> AttackData

        for attack in self.character.attacks:
            self.move_id_lookup[attack.move_id] = attack

            # Index normals for quick lookup
            if attack.move_type in (MoveType.NORMAL, MoveType.COMMAND_NORMAL):
                # Determine if heavy based on damage heuristic or properties
                is_heavy = attack.base_damage >= 12 or any(
                    p in (AttackProperty.LAUNCHER, AttackProperty.WALL_BOUNCE,
                          AttackProperty.GROUND_BOUNCE)
                    for p in attack.properties
                )
                # Map to a simple key for quick lookup
                key = (attack.attack_type, attack.height, is_heavy)
                # Don't overwrite — first match wins (or we could prefer command normals)
                if key not in self.normal_lookup:
                    self.normal_lookup[key] = attack

    def resolve_input(
        self,
        input_state: InputState,
        current_state: FighterState,
        is_grounded: bool,
        facing_right: bool,
        motion_detector: MotionDetector,
        super_meter: int = 0,
    ) -> Optional[AttackData]:
        """
        Given current input state and fighter conditions, return the
        appropriate AttackData or None if no attack is triggered.
        """
        if not input_state.has_attack():
            return None

        # Determine what buttons are pressed
        is_heavy = input_state.heavy
        buttons = input_state.get_attack_buttons()

        # Determine direction modifiers
        direction = input_state.get_direction()
        is_up = input_state.up
        is_down = input_state.down
        is_forward = (input_state.right and facing_right) or (input_state.left and not facing_right)
        is_back = (input_state.left and facing_right) or (input_state.right and not facing_right)

        facing_int = 1 if facing_right else -1

        # --- Priority 1: Super Moves ---
        for sp_move in self.character.special_moves:
            if sp_move.is_super and sp_move.meter_cost > super_meter:
                continue
            if self._check_special_input(sp_move, input_state, motion_detector, facing_int):
                return sp_move.attack_data

        # --- Priority 2: Special Moves ---
        for sp_move in self.character.special_moves:
            if sp_move.is_super:
                continue  # Already checked above
            if self._check_special_input(sp_move, input_state, motion_detector, facing_int):
                return sp_move.attack_data

        # --- Priority 3: Normal Attacks ---
        if not is_grounded:
            return self._resolve_air_normal(buttons, is_heavy)
        return self._resolve_ground_normal(buttons, is_heavy, is_down, is_up, is_forward)

    def _check_special_input(
        self, sp_move: SpecialMoveDef,
        input_state: InputState,
        motion_detector: MotionDetector,
        facing: int,
    ) -> bool:
        """Check if the input matches a special move's requirements."""
        # Check if the right button was pressed (rising edge)
        required_button = sp_move.attack_button
        if not input_state.__getattribute__(required_button):
            return False

        # Check motion (skip for NONE motion type — just button press)
        if sp_move.motion == MotionType.NONE:
            return True

        return motion_detector.detect(sp_move.motion, within=20, facing=facing)

    def _resolve_ground_normal(
        self, buttons: List[str], is_heavy: bool,
        is_down: bool, is_up: bool, is_forward: bool,
    ) -> Optional[AttackData]:
        """Resolve a ground-based normal attack."""
        for btn in buttons:
            attack_type = AttackType.PUNCH if btn == "punch" else AttackType.KICK

            # Determine height
            if is_down:
                height = AttackHeight.LOW
            elif is_up:
                height = AttackHeight.HIGH
            else:
                height = AttackHeight.STRAIGHT

            key = (attack_type, height, is_heavy)
            attack = self.normal_lookup.get(key)
            if attack:
                return attack

            # Fallback: try without heavy modifier
            key_light = (attack_type, height, False)
            attack = self.normal_lookup.get(key_light)
            if attack:
                return attack

        return None

    def _resolve_air_normal(
        self, buttons: List[str], is_heavy: bool,
    ) -> Optional[AttackData]:
        """Resolve an air normal attack (simplified — uses STRAIGHT height)."""
        for btn in buttons:
            attack_type = AttackType.PUNCH if btn == "punch" else AttackType.KICK
            key = (attack_type, AttackHeight.STRAIGHT, is_heavy)
            attack = self.normal_lookup.get(key)
            if attack:
                return attack
            key_light = (attack_type, AttackHeight.STRAIGHT, False)
            attack = self.normal_lookup.get(key_light)
            if attack:
                return attack
        return None

    def get_attack_by_id(self, move_id: str) -> Optional[AttackData]:
        """Get an attack by its move ID."""
        return self.move_id_lookup.get(move_id)

    def get_light_attacks(self) -> List[AttackData]:
        """Get all light (non-heavy) normal attacks."""
        return [a for a in self.character.attacks
                if a.move_type == MoveType.NORMAL and a.base_damage < 12]

    def get_heavy_attacks(self) -> List[AttackData]:
        """Get all heavy normal attacks."""
        return [a for a in self.character.attacks
                if a.move_type == MoveType.NORMAL and a.base_damage >= 12]

    def get_special_moves(self) -> List[SpecialMoveDef]:
        """Get all special move definitions."""
        return self.character.special_moves
