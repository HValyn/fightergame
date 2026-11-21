"""Bugs 9-10 + AI fixes + a smoke test of the full loop."""
import random

import main as M
from ai_controller import AIController, AIDifficulty
from character_defs import get_character
from constants import FighterState, MotionType, InputState as I
from conftest import Sim


def test_best_of_three_ends_after_two_wins():
    g = M.Game()
    g._start_match()
    wins = 0
    while g.state != g.STATE_MATCH_OVER and wins < 5:
        g.fighter2.health = 0
        g._check_round_end()
        wins += 1
        if g.state == g.STATE_ROUND_OVER:
            g._start_next_round()
    assert wins == 2


def test_cpu_opponent_varies():
    random.seed(1)
    g = M.Game()
    seen = set()
    for _ in range(20):
        g._start_match()
        seen.add(g.fighter2.character.char_id)
        assert g.fighter2.character.char_id != g.fighter1.character.char_id
    assert len(seen) == 2


def test_ai_can_perform_a_fireball():
    s = Sim(x1=300, x2=900).step(n=2)
    ai = AIController(get_character("ryokan"), AIDifficulty.MEDIUM)
    sp = next(x for x in s.f1.character.special_moves if x.name == "Fireball")
    frames = AIController.build_motion_inputs(sp.motion, sp.attack_button, s.f1.facing_right)
    s.feed(1, frames)
    assert s.f1.current_attack and s.f1.current_attack.name == "Fireball"


def test_ai_can_perform_charge_move_facing_left():
    s = Sim("titan", "ryokan", 900, 300).step(n=2)
    sp = next(x for x in s.f1.character.special_moves if x.motion == MotionType.CHARGE_BACK)
    frames = AIController.build_motion_inputs(sp.motion, sp.attack_button, s.f1.facing_right)
    s.feed(1, frames)
    assert s.f1.current_attack and s.f1.current_attack.name == sp.name


def test_ai_block_decision_is_stable_during_one_attack():
    ai = AIController(get_character("ryokan"), dict(AIDifficulty.MEDIUM, reaction_frames=0))
    atk = get_character("ryokan").get_attack_by_id("ryokan_lk_straight")
    outs = [ai.update(FighterState.ATTACK_STARTUP, 500, 550, 560, 550, atk, False, False, i)
            for i in range(5)]
    assert len({(o.left, o.right) for o in outs}) == 1


def test_ai_reaction_delay():
    ai = AIController(get_character("ryokan"), dict(AIDifficulty.BRUTAL, block_chance=1.0, reaction_frames=5))
    atk = get_character("ryokan").get_attack_by_id("ryokan_lk_straight")
    decided = []
    for i in range(6):
        ai.update(FighterState.ATTACK_STARTUP, 500, 550, 560, 550, atk, False, False, i)
        decided.append(ai._block_decision is not None)
    assert decided == [False, False, False, False, True, True]


def test_ai_blocks_overhead_standing_and_low_crouching():
    c = get_character("ryokan")
    for move, want_down in [("ryokan_hp_high", False), ("ryokan_lp_low", True)]:
        ai = AIController(c, dict(AIDifficulty.BRUTAL, block_chance=1.0, reaction_frames=0))
        o = ai.update(FighterState.ATTACK_STARTUP, 500, 550, 560, 550, c.get_attack_by_id(move), False, False, 0)
        assert o.down == want_down


def test_full_match_loop_runs_and_renders():
    g = M.Game()
    g._start_match()
    for _ in range(1200):
        if g.state != g.STATE_FIGHTING:
            break
        g._update_fight()
        g.renderer.draw_frame(g.fighter1, g.fighter2, g.current_frame, "MEDIUM", 1)
    assert g.fighter1.health >= 0 and g.fighter2.health >= 0
