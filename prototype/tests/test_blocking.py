"""Bugs 1-3: blocking direction, blockstun, block height."""
import pytest

from character_defs import get_character
from constants import FighterState, InputState as I
from conftest import Sim

RY = get_character("ryokan")


def _attack_into_guard(attack_id, guard, x1=1100, x2=1165):
    # default: defender pinned to the right wall so walking back can't leave range
    s = Sim(x1=x1, x2=x2)
    s.step(i2=guard, n=3)
    s.f1.start_attack(RY.get_attack_by_id(attack_id))
    states = []
    for _ in range(30):
        s.step(i2=guard)
        states.append(s.f2.state)
    return s, states


# f1 on the left attacks f2 on the right -> f2 must hold RIGHT (away) to block
BACK = I(right=True)
DOWN_BACK = I(right=True, down=True)


def test_standing_block_takes_only_chip():
    s, _ = _attack_into_guard("ryokan_lk_straight", BACK)
    atk = RY.get_attack_by_id("ryokan_lk_straight")
    assert s.f2.health == s.f2.max_health - atk.chip_damage


@pytest.mark.parametrize("x1,x2,guard", [(1100, 1170, I(right=True)), (100, 30, I(left=True))])
def test_block_works_on_both_sides_and_in_corners(x1, x2, guard):
    s, _ = _attack_into_guard("ryokan_lk_straight", guard, x1, x2)
    assert s.f2.health == s.f2.max_health - 1


def test_holding_toward_attacker_does_not_block():
    s, _ = _attack_into_guard("ryokan_lk_straight", I(left=True))
    assert s.f2.health == s.f2.max_health - 8


def test_blocked_hit_puts_defender_in_blockstun():
    _, states = _attack_into_guard("ryokan_lk_straight", BACK)
    assert FighterState.BLOCKSTUN in states
    assert FighterState.HITSTUN not in states


def test_blockstun_length_matches_frame_data():
    _, states = _attack_into_guard("ryokan_lk_straight", BACK)
    atk = RY.get_attack_by_id("ryokan_lk_straight")
    # hitstop freezes the defender for hitstop//2 frames on top of blockstun
    stun = states.count(FighterState.BLOCKSTUN)
    assert atk.blockstun_frames <= stun <= atk.blockstun_frames + atk.hitstop // 2


def test_plain_down_does_not_block():
    s, _ = _attack_into_guard("ryokan_lp_low", I(down=True))
    assert s.f2.health == s.f2.max_health - RY.get_attack_by_id("ryokan_lp_low").base_damage


def test_low_needs_crouch_block():
    s, _ = _attack_into_guard("ryokan_lp_low", BACK)          # standing guard
    assert s.f2.health < s.f2.max_health - 1
    s, _ = _attack_into_guard("ryokan_lp_low", DOWN_BACK)     # crouching guard
    assert s.f2.health == s.f2.max_health - 1


def test_overhead_beats_crouch_block_but_not_standing_block():
    oh = RY.get_attack_by_id("ryokan_hp_high")
    s, _ = _attack_into_guard("ryokan_hp_high", DOWN_BACK)
    assert s.f2.health == s.f2.max_health - oh.base_damage
    s, _ = _attack_into_guard("ryokan_hp_high", BACK)
    assert s.f2.health == s.f2.max_health - oh.chip_damage


def test_blocking_attacker_frame_advantage_is_reported():
    s, _ = _attack_into_guard("ryokan_lk_straight", BACK)
    atk = RY.get_attack_by_id("ryokan_lk_straight")
    assert s.f1.last_frame_advantage == atk.frame_advantage_on_block
    assert s.f1.attack_was_blocked
