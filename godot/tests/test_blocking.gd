## Port of prototype/tests/test_blocking.py: guard direction, blockstun, block height.
extends TestCase

func _attack_into_guard(attack_id: String, guard: InputFrame, x1 := 1100.0, x2 := 1165.0) -> Array:
	# default: defender pinned to the right wall so walking back can't leave range
	var s := sim("ryokan", "ryokan", x1, x2)
	s.step(null, guard, 3)
	s.f1.start_attack(ch("ryokan").find_attack(attack_id))
	var states := []
	for k in 30:
		s.step(null, guard)
		states.append(s.f2.state)
	return [s, states]

func test_standing_block_takes_only_chip() -> void:
	var s: DuelSim = _attack_into_guard("ryokan_lk_straight", I("right"))[0]
	eq(s.f2.health, s.f2.max_health - ch("ryokan").find_attack("ryokan_lk_straight").chip)

func test_block_works_on_both_sides_and_in_corners() -> void:
	for c in [[1100.0, 1170.0, "right"], [100.0, 30.0, "left"]]:
		var s: DuelSim = _attack_into_guard("ryokan_lk_straight", I(c[2]), c[0], c[1])[0]
		eq(s.f2.health, s.f2.max_health - 1, str(c))

func test_holding_toward_attacker_does_not_block() -> void:
	var s: DuelSim = _attack_into_guard("ryokan_lk_straight", I("left"))[0]
	eq(s.f2.health, s.f2.max_health - 8)

func test_blocked_hit_puts_defender_in_blockstun() -> void:
	var states: Array = _attack_into_guard("ryokan_lk_straight", I("right"))[1]
	check(FT.State.BLOCKSTUN in states, "no blockstun")
	check(not (FT.State.HITSTUN in states), "took hitstun")

func test_blockstun_length_matches_frame_data() -> void:
	var states: Array = _attack_into_guard("ryokan_lk_straight", I("right"))[1]
	var a := ch("ryokan").find_attack("ryokan_lk_straight")
	var stun := states.count(FT.State.BLOCKSTUN)
	check(stun >= a.blockstun and stun <= a.blockstun + a.hitstop / 2, "stun=%d" % stun)

func test_plain_down_does_not_block() -> void:
	var s: DuelSim = _attack_into_guard("ryokan_lp_low", I("down"))[0]
	eq(s.f2.health, s.f2.max_health - ch("ryokan").find_attack("ryokan_lp_low").damage)

func test_low_needs_crouch_block() -> void:
	var s: DuelSim = _attack_into_guard("ryokan_lp_low", I("right"))[0]
	check(s.f2.health < s.f2.max_health - 1, "standing guard blocked a low")
	s = _attack_into_guard("ryokan_lp_low", I("down+right"))[0]
	eq(s.f2.health, s.f2.max_health - 1)

func test_overhead_beats_crouch_block_but_not_standing_block() -> void:
	var oh := ch("ryokan").find_attack("ryokan_hp_high")
	var s: DuelSim = _attack_into_guard("ryokan_hp_high", I("down+right"))[0]
	eq(s.f2.health, s.f2.max_health - oh.damage)
	s = _attack_into_guard("ryokan_hp_high", I("right"))[0]
	eq(s.f2.health, s.f2.max_health - oh.chip)

func test_blocking_attacker_frame_advantage_is_reported() -> void:
	var s: DuelSim = _attack_into_guard("ryokan_lk_straight", I("right"))[0]
	var a := ch("ryokan").find_attack("ryokan_lk_straight")
	eq(s.f1.last_frame_advantage, a.advantage_on_block())
	check(s.f1.attack_was_blocked)
