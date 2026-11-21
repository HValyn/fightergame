## Port of prototype/tests/test_movement_and_moves.py.
extends TestCase

func _neutral(n: int) -> Array:
	var a := []
	for k in n: a.append(I())
	return a

func test_air_attack_is_possible() -> void:
	var s := sim("ryokan", "ryokan", 300, 800).step(null, null, 2)
	s.feed(1, [I("up")] + _neutral(6) + [I("kick")])
	check(not s.f1.is_grounded)
	check(s.f1.in_attack)

func test_landing_ends_air_attack() -> void:
	var s := sim("ryokan", "ryokan", 300, 800).step(null, null, 2)
	s.feed(1, [I("up")] + _neutral(30) + [I("kick")])
	s.step(null, null, 40)
	check(s.f1.is_grounded and s.f1.state == FT.State.IDLE)

func test_double_jump_for_shadow_only() -> void:
	for c in [["shadow", true], ["ryokan", false]]:
		var s := sim(c[0], "ryokan", 300, 800).step(null, null, 2)
		s.feed(1, [I("up")] + _neutral(8))
		var vy := s.f1.vel_y
		s.feed(1, [I("up")])
		eq(s.f1.vel_y < vy, c[1], c[0])

func test_every_normal_is_reachable() -> void:
	for id in ["ryokan", "shadow", "titan"]:
		var c := ch(id)
		var r := MoveResolver.new(c)
		var reach := {}
		for btn in ["punch", "kick"]:
			for dir in ["", "down", "up", "right"]:
				for heavy in ["", "+heavy"]:
					var inp := I(btn + ("+" + dir if dir != "" else "") + heavy)
					var a := r.resolve(inp, MotionDetector.new(), {"facing_right": true, "grounded": true})
					if a: reach[a.id] = true
		for a in c.normals:
			check(reach.has(a.id), "%s unreachable" % a.id)

func test_forward_heavy_punch_is_overhead_in_game() -> void:
	var s := sim("ryokan", "ryokan", 300, 800).step(null, null, 2)
	s.feed(1, [I("right+heavy+punch")])
	eq(s.f1.current_attack.name, "Overhead Smash")

func test_hitstop_freezes_movement() -> void:
	var s := sim().step(null, null, 2)
	s.f1.start_attack(ch("ryokan").find_attack("ryokan_hk_straight"))
	var guard := 0
	while s.f2.hitstop_frames == 0 and guard < 60:
		s.step(); guard += 1
	var x := s.f2.pos_x
	s.step(null, null, s.f2.hitstop_frames - 1)
	eq(s.f2.pos_x, x)

func test_holding_button_does_not_auto_cancel() -> void:
	var s := sim().step(null, null, 2)
	var seq := []
	for k in 14: seq.append(I("punch"))
	s.feed(1, seq)
	check(s.f1.combo_count <= 1)

func test_chain_cancel_on_fresh_press() -> void:
	var s := sim().step(null, null, 2)
	s.feed(1, [I("punch")] + _neutral(5) + [I("kick")] + _neutral(20))
	eq(s.f1.combo_count, 2)

func test_attacker_combo_resets_after_opponent_recovers() -> void:
	var s := sim().step(null, null, 2)
	s.feed(1, [I("punch")])
	s.step(null, null, 60)
	eq(s.f1.combo_count, 0)

func test_lows_and_overheads_connect() -> void:
	for id in ["ryokan", "shadow", "titan"]:
		for a in ch(id).normals:
			if a.height != FT.Height.LOW and a.height != FT.Height.OVERHEAD:
				continue
			for crouch in [false, true]:
				var s := sim(id, "ryokan", 1100, 1165)
				var guard := I("down") if crouch else I()
				s.step(null, guard, 3)
				s.f1.start_attack(a)
				s.step(null, guard, a.startup + a.active + 2)
				check(s.f2.health < s.f2.max_health, "%s vs %s" % [a.name, "crouch" if crouch else "stand"])
