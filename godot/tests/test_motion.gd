## Port of prototype/tests/test_motion.py: facing-relative motions, stale motions, charge.
extends TestCase

func _qcf(fwd: String) -> Array:
	return [I("down"), I("down+" + fwd), I(fwd), I("punch+" + fwd)]

func _name(f: FighterSim) -> String:
	return f.current_attack.name if f.current_attack else ""

func test_fireball_facing_right() -> void:
	var s := sim("ryokan", "ryokan", 300, 700).step(null, null, 2)
	check(s.f1.facing_right)
	s.feed(1, _qcf("right"))
	eq(_name(s.f1), "Fireball")

func test_fireball_facing_left() -> void:
	var s := sim("ryokan", "ryokan", 800, 300).step(null, null, 2)
	check(not s.f1.facing_right)
	s.feed(1, _qcf("left"))
	eq(_name(s.f1), "Fireball")

func test_motion_away_from_opponent_is_not_a_fireball() -> void:
	var s := sim("ryokan", "ryokan", 800, 300).step(null, null, 2)
	s.feed(1, _qcf("right"))
	check(_name(s.f1) != "Fireball")

func test_crouch_then_walk_then_jab_is_a_jab() -> void:
	var s := sim("ryokan", "ryokan", 300, 700).step(null, null, 2)
	var seq := []
	for k in 5: seq.append(I("down"))
	for k in 5: seq.append(I("right"))
	seq.append(I("punch"))
	s.feed(1, seq)
	eq(_name(s.f1), "Light Jab")

func test_stale_motion_does_not_fire() -> void:
	var s := sim("ryokan", "ryokan", 300, 700).step(null, null, 2)
	var seq := _qcf("right").slice(0, 3)
	for k in 12: seq.append(I())
	seq.append(I("punch"))
	s.feed(1, seq)
	eq(_name(s.f1), "Light Jab")

func test_motion_is_consumed_after_special() -> void:
	var s := sim("ryokan", "ryokan", 200, 1000).step(null, null, 2)
	s.feed(1, _qcf("right"))
	s.step(null, null, s.f1.current_attack.total_frames() + 2)
	s.feed(1, [I("punch")])
	eq(_name(s.f1), "Light Jab")

func test_charge_down_up_ground_pound() -> void:
	var s := sim("titan", "ryokan", 300, 700).step(null, null, 2)
	var seq := []
	for k in 45: seq.append(I("down"))
	seq.append(I("up+kick"))
	s.feed(1, seq)
	eq(_name(s.f1), "Ground Pound")
	check(s.f1.state != FT.State.JUMP)

func test_charge_back_forward_armor_rush() -> void:
	var s := sim("titan", "ryokan", 300, 900).step(null, null, 2)
	var sp: CharacterData.SpecialMove = null
	for x in s.f1.character.specials:
		if x.motion == FT.Motion.CHARGE_BACK: sp = x
	var seq := []
	for k in 45: seq.append(I("left"))
	seq.append(I("right+" + sp.button))
	s.feed(1, seq)
	eq(_name(s.f1), sp.attack.name)

func test_short_charge_does_not_work() -> void:
	var s := sim("titan", "ryokan", 300, 700).step(null, null, 2)
	var seq := []
	for k in 10: seq.append(I("down"))
	seq.append(I("up+kick"))
	s.feed(1, seq)
	check(_name(s.f1) != "Ground Pound")

func test_charge_grace_window_expires() -> void:
	var d := MotionDetector.new()
	for k in 45: d.push("down", 1)
	for k in 15: d.push("neutral", 1)
	d.push("up", 1)
	check(not d.detect(FT.Motion.CHARGE_DOWN))

func test_detector_mirrors_for_left_facing() -> void:
	var d := MotionDetector.new()
	for x in ["down", "downleft", "left"]:
		d.push(x, -1)
	check(d.detect(FT.Motion.QCF))
	check(not d.detect(FT.Motion.QCB))
