## Godot-only mechanics the prototype declared but never ran:
## projectiles, armor, invincibility, teleport, supers/meter.
extends TestCase

func _fight(c1 := "ryokan", c2 := "ryokan", x1 := 300.0, x2 := 700.0) -> MatchSim:
	var m := MatchSim.new(ch(c1), ch(c2))
	m.f1.reset(x1); m.f2.reset(x2)
	m.phase = MatchSim.Phase.FIGHT
	m.step(); m.step()
	return m

func _qcf() -> Array:
	return [I("down"), I("down+right"), I("right"), I("right+punch")]

func test_fireball_spawns_travels_and_hits() -> void:
	var m := _fight()
	for inp in _qcf(): m.step(inp)
	for k in 20: m.step()
	eq(m.projectiles.size(), 1)
	var before := m.f2.health
	for k in 80: m.step()
	check(m.f2.health < before, "fireball never hit")
	eq(m.projectiles.size(), 0)

func test_fireball_can_be_blocked() -> void:
	var m := _fight()
	for inp in _qcf(): m.step(inp, I("right"))
	for k in 170: m.step(null, I("right"))
	eq(m.f2.health, m.f2.max_health - ch("ryokan").find_special("Fireball").attack.chip)

func test_only_one_fireball_at_a_time() -> void:
	var m := _fight("ryokan", "ryokan", 100, 1100)
	for inp in _qcf(): m.step(inp)
	for k in 40: m.step()
	for inp in _qcf(): m.step(inp)
	check(m.f1.current_attack == null or m.f1.current_attack.name != "Fireball", "second fireball came out")
	eq(m.projectiles.size(), 1)

func test_opposing_fireballs_cancel() -> void:
	var m := _fight("ryokan", "ryokan", 200, 1000)
	var mirrored := [I("down"), I("down+left"), I("left"), I("left+punch")]
	for k in 4: m.step(_qcf()[k], mirrored[k])
	for k in 120: m.step()
	eq(m.f1.health, m.f1.max_health)
	eq(m.f2.health, m.f2.max_health)

func test_uppercut_is_invincible_on_startup() -> void:
	var s := sim().step(null, null, 2)
	s.f2.start_attack(ch("ryokan").find_attack("ryokan_uppercut"))
	s.f1.start_attack(ch("ryokan").find_attack("ryokan_lp_high"))
	s.step(null, null, 4)
	eq(s.f2.health, s.f2.max_health)

func test_titan_armor_absorbs_one_hit() -> void:
	var s := sim("ryokan", "titan", 500, 560).step(null, null, 2)
	s.f2.start_attack(ch("titan").find_attack("titan_hp_straight"))
	s.f1.start_attack(ch("ryokan").find_attack("ryokan_lp_high"))
	s.step(null, null, 6)
	check(s.f2.health < s.f2.max_health, "armor should still take damage")
	check(s.f2.in_attack, "armored move was interrupted")

func test_throw_beats_armor_and_block() -> void:
	var s := sim("shadow", "titan", 500, 560).step(null, I("right"), 2)
	s.f1.start_attack(ch("shadow").find_attack("shadow_grab"))
	s.step(null, I("right"), 20)
	check(s.f2.health < s.f2.max_health - 2, "throw was blocked")

func test_shadow_port_teleports_behind() -> void:
	var s := sim("shadow", "ryokan", 300, 700).step(null, null, 2)
	s.f1.start_attack(ch("shadow").find_attack("shadow_teleport"))
	s.step(null, null, 30)
	check(s.f1.pos_x > s.f2.pos_x, "did not end up behind")

func test_back_dash_has_invincible_frames() -> void:
	var s := sim().step(null, null, 2)
	s.f2.facing = -1
	s.f2._start_dash(false)
	check(s.f2.evades(ch("ryokan").find_attack("ryokan_lp_high")))
