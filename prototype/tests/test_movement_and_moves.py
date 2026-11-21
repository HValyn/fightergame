"""Bugs 7-8 and 12: air attacks, double jump, overhead input, hitstop, cancels, combos."""
import pytest

from character_defs import get_character
from constants import FighterState, InputState as I
from conftest import Sim


def test_air_attack_is_possible():
    s = Sim(x1=300, x2=800).step(n=2)
    s.feed(1, [I(up=True)] + [I()] * 6 + [I(kick=True)])
    assert not s.f1.is_grounded
    assert s.f1.is_in_attack_state


def test_landing_ends_air_attack():
    s = Sim(x1=300, x2=800).step(n=2)
    s.feed(1, [I(up=True)] + [I()] * 30 + [I(kick=True)])
    s.step(n=40)
    assert s.f1.is_grounded and s.f1.state == FighterState.IDLE


def test_double_jump_for_shadow_only():
    for char, expected in [("shadow", True), ("ryokan", False)]:
        s = Sim(char, "ryokan", 300, 800).step(n=2)
        s.feed(1, [I(up=True)] + [I()] * 8)
        vy_before = s.f1.vel_y
        s.feed(1, [I(up=True)])
        jumped = s.f1.vel_y < vy_before   # gravity alone would make it larger
        assert jumped == expected, char


@pytest.mark.parametrize("char", ["ryokan", "shadow", "titan"])
def test_every_normal_is_reachable(char):
    from move_system import MoveResolver
    c = get_character(char)
    r = MoveResolver(c)
    reach = set()
    for btn in ["punch", "kick"]:
        for down, up, fwd in [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]:
            for heavy in (False, True):
                a = r._resolve_ground_normal([btn], heavy, bool(down), bool(up), bool(fwd))
                if a:
                    reach.add(a.move_id)
    assert {a.move_id for a in c.attacks} - reach == set()


def test_forward_heavy_punch_is_overhead_in_game():
    s = Sim(x1=300, x2=800).step(n=2)
    s.feed(1, [I(right=True, heavy=True, punch=True)])
    assert s.f1.current_attack.name == "Overhead Smash"


def test_hitstop_freezes_movement():
    s = Sim(x1=500, x2=560).step(n=2)
    s.f1.start_attack(get_character("ryokan").get_attack_by_id("ryokan_hk_straight"))
    while not s.f2.hitstop_frames:
        s.step()
    x = s.f2.pos_x
    frozen = s.f2.hitstop_frames
    s.step(n=frozen - 1)
    assert s.f2.pos_x == x


def test_holding_button_does_not_auto_cancel():
    s = Sim(x1=500, x2=560).step(n=2)
    s.feed(1, [I(punch=True)] * 14)  # hold punch through the jab's hit + cancel window
    assert s.f1.combo_count <= 1


def test_chain_cancel_on_fresh_press():
    s = Sim(x1=500, x2=560).step(n=2)
    # kick pressed during the jab's hitstop -> buffered -> cancels in recovery
    s.feed(1, [I(punch=True)] + [I()] * 5 + [I(kick=True)] + [I()] * 20)
    assert s.f1.combo_count == 2


def test_attacker_combo_resets_after_opponent_recovers():
    s = Sim(x1=500, x2=560).step(n=2)
    s.feed(1, [I(punch=True)])
    s.step(n=60)
    assert s.f1.combo_count == 0


@pytest.mark.parametrize("char", ["ryokan", "shadow", "titan"])
def test_lows_and_overheads_connect(char):
    """Regression: old hitbox maths put lows under the floor and overheads over crouchers."""
    from constants import AttackHeight, MoveType
    c = get_character(char)
    for atk in c.attacks:
        if atk.height not in (AttackHeight.LOW, AttackHeight.OVERHEAD):
            continue
        for crouch in (False, True):
            s = Sim(char, "ryokan", 1100, 1165)
            guard = I(down=True) if crouch else I()
            s.step(i2=guard, n=3)
            s.f1.start_attack(atk)
            s.step(i2=guard, n=atk.startup_frames + atk.active_frames + 2)
            assert s.f2.health < s.f2.max_health, (atk.name, "crouching" if crouch else "standing")
