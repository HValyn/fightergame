## Port of prototype/tests/test_match.py + Godot-only match flow.
extends TestCase

func _match(c1 := "ryokan", c2 := "shadow") -> MatchSim:
	return MatchSim.new(ch(c1), ch(c2))

func _run_until(m: MatchSim, pred: Callable, limit := 20000) -> void:
	var n := 0
	while not pred.call() and n < limit:
		m.step(); n += 1

func test_best_of_three_ends_after_two_wins() -> void:
	var m := _match()
	var rounds := 0
	while m.phase != MatchSim.Phase.MATCH_OVER and rounds < 5:
		_run_until(m, func(): return m.phase == MatchSim.Phase.FIGHT)
		m.f2.health = 0
		m.step()
		rounds += 1
		_run_until(m, func(): return m.phase != MatchSim.Phase.OUTRO)
	eq(rounds, 2)
	eq(m.match_winner, 1)
	eq(m.p1_score, 2)

func test_new_round_resets_fighters() -> void:
	var m := _match()
	_run_until(m, func(): return m.phase == MatchSim.Phase.FIGHT)
	m.f1.health = 0
	m.step()
	_run_until(m, func(): return m.phase == MatchSim.Phase.INTRO)
	eq(m.current_round, 2)
	eq(m.f1.health, m.f1.max_health)
	eq(m.p2_score, 1)

func test_timeout_awards_round_to_healthier_fighter() -> void:
	var m := _match()
	_run_until(m, func(): return m.phase == MatchSim.Phase.FIGHT)
	m.f1.health -= 10
	m.round_frames_left = 1
	m.step()
	eq(m.round_end_reason, "time")
	eq(m.round_winner, 2)

func test_inputs_ignored_during_intro() -> void:
	var m := _match()
	var x := m.f1.pos_x
	for k in 10: m.step(I("right"))
	eq(m.f1.pos_x, x)

func test_ai_can_perform_a_fireball() -> void:
	var s := sim("ryokan", "ryokan", 300, 900).step(null, null, 2)
	var sp := ch("ryokan").find_special("Fireball")
	s.feed(1, AIController.build_motion_inputs(sp.motion, sp.button, s.f1.facing_right))
	check(s.f1.current_attack and s.f1.current_attack.name == "Fireball")

func test_ai_can_perform_charge_move_facing_left() -> void:
	var s := sim("titan", "ryokan", 900, 300).step(null, null, 2)
	var sp: CharacterData.SpecialMove = null
	for x in s.f1.character.specials:
		if x.motion == FT.Motion.CHARGE_BACK: sp = x
	s.feed(1, AIController.build_motion_inputs(sp.motion, sp.button, s.f1.facing_right))
	check(s.f1.current_attack and s.f1.current_attack.name == sp.attack.name)

func test_ai_block_decision_is_stable_during_one_attack() -> void:
	var ai := AIController.new(ch("ryokan"), {"reaction_frames": 0}, 3)
	var a := ch("ryokan").find_attack("ryokan_lk_straight")
	var seen := {}
	for k in 5:
		var o := ai.update_from(FT.State.ATTACK_STARTUP, 500, 550, 560, a, false)
		seen[[o.left, o.right]] = true
	eq(seen.size(), 1)

func test_ai_reaction_delay() -> void:
	var ai := AIController.new(ch("ryokan"), {"block_chance": 1.0, "reaction_frames": 5}, 3)
	var a := ch("ryokan").find_attack("ryokan_lk_straight")
	var decided := []
	for k in 6:
		ai.update_from(FT.State.ATTACK_STARTUP, 500, 550, 560, a, false)
		decided.append(ai.block_decision != null)
	eq(decided, [false, false, false, false, true, true])

func test_ai_blocks_overhead_standing_and_low_crouching() -> void:
	for c in [["ryokan_hp_high", false], ["ryokan_lp_low", true]]:
		var ai := AIController.new(ch("ryokan"), {"block_chance": 1.0, "reaction_frames": 0}, 3)
		var o := ai.update_from(FT.State.ATTACK_STARTUP, 500, 550, 560, ch("ryokan").find_attack(c[0]), false)
		eq(o.down, c[1], c[0])

func test_cpu_vs_cpu_matches_finish_and_are_deterministic() -> void:
	var ids := CharacterDB.ids()
	for a in ids:
		for b in ids:
			var results := []
			for rep in 2:
				var m := _match(a, b)
				m.ai1 = AIController.new(ch(a), "HARD", 11)
				m.ai2 = AIController.new(ch(b), "HARD", 22)
				_run_until(m, func(): return m.phase == MatchSim.Phase.MATCH_OVER, 60 * 60 * 15)
				check(m.phase == MatchSim.Phase.MATCH_OVER, "%s vs %s never finished" % [a, b])
				check(m.f1.health >= 0 and m.f2.health >= 0)
				results.append([m.p1_score, m.p2_score, m.frame, m.f1.health, m.f2.health])
			eq(results[0], results[1], "%s vs %s not deterministic" % [a, b])
