"""Bugs 4-6: facing-relative motions, accidental specials, charge moves."""
from constants import FighterState, MotionType, InputState as I
from motion_input import MotionDetector
from conftest import Sim


def _qcf(forward):  # forward = "right" or "left"
    return [I(down=True), I(down=True, **{forward: True}), I(**{forward: True}),
            I(punch=True, **{forward: True})]


def test_fireball_facing_right():
    s = Sim(x1=300, x2=700).step(n=2)
    assert s.f1.facing_right
    s.feed(1, _qcf("right"))
    assert s.f1.current_attack and s.f1.current_attack.name == "Fireball"


def test_fireball_facing_left():
    s = Sim(x1=800, x2=300).step(n=2)
    assert not s.f1.facing_right
    s.feed(1, _qcf("left"))
    assert s.f1.current_attack and s.f1.current_attack.name == "Fireball"


def test_motion_away_from_opponent_is_not_a_fireball():
    s = Sim(x1=800, x2=300).step(n=2)
    s.feed(1, _qcf("right"))       # this is QCB for a left-facing fighter
    assert not (s.f1.current_attack and s.f1.current_attack.name == "Fireball")


def test_crouch_then_walk_then_jab_is_a_jab():
    s = Sim(x1=300, x2=700).step(n=2)
    s.feed(1, [I(down=True)] * 5 + [I(right=True)] * 5 + [I(punch=True)])
    assert s.f1.current_attack.name == "Light Jab"


def test_stale_motion_does_not_fire():
    s = Sim(x1=300, x2=700).step(n=2)
    s.feed(1, _qcf("right")[:3] + [I()] * 12 + [I(punch=True)])
    assert s.f1.current_attack.name == "Light Jab"


def test_motion_is_consumed_after_special():
    s = Sim(x1=200, x2=1000).step(n=2)
    s.feed(1, _qcf("right"))
    total = s.f1.current_attack.total_frames
    s.step(n=total + 2)
    s.feed(1, [I(punch=True)])
    assert s.f1.current_attack.name == "Light Jab"


def test_charge_down_up_ground_pound():
    s = Sim("titan", "ryokan", 300, 700).step(n=2)
    s.feed(1, [I(down=True)] * 45 + [I(up=True, kick=True)])   # Ground Pound = charge down, up + K
    assert s.f1.current_attack and s.f1.current_attack.name == "Ground Pound"
    assert s.f1.state != FighterState.JUMP


def test_charge_back_forward_armor_rush():
    s = Sim("titan", "ryokan", 300, 900).step(n=2)
    sp = next(x for x in s.f1.character.special_moves if x.motion == MotionType.CHARGE_BACK)
    btn = {sp.attack_button: True}
    s.feed(1, [I(left=True)] * 45 + [I(right=True, **btn)])
    assert s.f1.current_attack and s.f1.current_attack.name == sp.name


def test_short_charge_does_not_work():
    s = Sim("titan", "ryokan", 300, 700).step(n=2)
    s.feed(1, [I(down=True)] * 10 + [I(up=True, kick=True)])
    assert not (s.f1.current_attack and s.f1.current_attack.name == "Ground Pound")


def test_charge_grace_window_expires():
    d = MotionDetector()
    for _ in range(45):
        d.push_direction("down")
    for _ in range(15):
        d.push_direction("neutral")
    d.push_direction("up")
    assert not d.detect(MotionType.CHARGE_DOWN)


def test_detector_mirrors_for_left_facing():
    d = MotionDetector()
    for x in ["down", "downleft", "left"]:
        d.push_direction(x, facing=-1)
    assert d.detect(MotionType.QUARTER_CIRCLE_FORWARD)
    assert not d.detect(MotionType.QUARTER_CIRCLE_BACK)
