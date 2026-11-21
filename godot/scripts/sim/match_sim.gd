## A whole match: two fighters, projectiles, pushboxes, round timer, best-of-3.
## Deterministic: same inputs + same AI seed -> same match. One step() == one frame.
class_name MatchSim
extends RefCounted

enum Phase { INTRO, FIGHT, OUTRO, MATCH_OVER }

const P1_START_X := 300.0
const P2_START_X := 900.0

var f1: FighterSim
var f2: FighterSim
var ai1: AIController = null          # set to let the CPU drive a side
var ai2: AIController = null
var projectiles: Array[ProjectileSim] = []

var phase: int = Phase.INTRO
var phase_timer := FT.ROUND_INTRO_FRAMES
var frame := 0
var round_frames_left := FT.ROUND_TIME_SECONDS * FT.FPS
var current_round := 1
var p1_score := 0
var p2_score := 0
var round_winner := 0                 # 0 none/draw, 1 or 2
var match_winner := 0
var round_end_reason := ""            # "ko" / "time" / "draw"
var timer_enabled := true

var _ai_last_combo := [0, 0]
var _ai_was_blocked := [false, false]


func _init(c1: CharacterData, c2: CharacterData) -> void:
	f1 = FighterSim.new(c1, P1_START_X, 1)
	f2 = FighterSim.new(c2, P2_START_X, 2)
	f2.facing = -1


func fighters() -> Array[FighterSim]:
	return [f1, f2]


func opponent_of(f: FighterSim) -> FighterSim:
	return f2 if f == f1 else f1


## Seconds left on the round clock (for the HUD).
func time_left() -> int:
	return ceili(round_frames_left / float(FT.FPS))


## Advance one frame. i1/i2 are ignored for sides driven by an AIController.
func step(i1: InputFrame = null, i2: InputFrame = null) -> void:
	i1 = i1 if i1 else InputFrame.new()
	i2 = i2 if i2 else InputFrame.new()
	match phase:
		Phase.INTRO:
			# fighters idle in place; inputs are ignored but still advance buffers
			f1.update(f2, frame, InputFrame.new())
			f2.update(f1, frame, InputFrame.new())
			phase_timer -= 1
			if phase_timer <= 0:
				phase = Phase.FIGHT
		Phase.FIGHT:
			_step_fight(i1, i2)
		Phase.OUTRO:
			# let knockback / animations settle
			f1.update(f2, frame, InputFrame.new())
			f2.update(f1, frame, InputFrame.new())
			_step_projectiles()
			_resolve_pushboxes()
			phase_timer -= 1
			if phase_timer <= 0:
				if match_winner:
					phase = Phase.MATCH_OVER
				else:
					next_round()
		Phase.MATCH_OVER:
			pass
	frame += 1


func _step_fight(i1: InputFrame, i2: InputFrame) -> void:
	for f in fighters():
		f.projectile_active = projectiles.any(func(p): return p.owner == f and p.alive)

	if ai1: i1 = ai1.think(f1, f2, frame)
	f1.update(f2, frame, i1)
	if ai2: i2 = ai2.think(f2, f1, frame)
	f2.update(f1, frame, i2)

	for f in fighters():
		if f.pending_projectile:
			projectiles.append(ProjectileSim.spawn(f, f.pending_projectile))
			f.pending_projectile = null

	_notify_ai(ai1, f1, 0)
	_notify_ai(ai2, f2, 1)
	_step_projectiles()
	_resolve_pushboxes()

	if timer_enabled:
		round_frames_left -= 1
	_check_round_end()


func _notify_ai(ai: AIController, f: FighterSim, idx: int) -> void:
	if ai == null:
		return
	if f.combo_count > _ai_last_combo[idx]:
		ai.on_hit_landed(f.combo_count)
	_ai_last_combo[idx] = f.combo_count
	if f.attack_was_blocked and not _ai_was_blocked[idx]:
		ai.on_blocked()
	_ai_was_blocked[idx] = f.attack_was_blocked


func _step_projectiles() -> void:
	# opposing projectiles cancel each other
	for a in projectiles:
		for b in projectiles:
			if a != b and a.alive and b.alive and a.owner != b.owner and a.box().intersects(b.box()):
				a.alive = false
				b.alive = false
	for p in projectiles:
		p.step(opponent_of(p.owner))
	projectiles = projectiles.filter(func(p): return p.alive)


func _resolve_pushboxes() -> void:
	if f1.pushbox == null or f2.pushbox == null or not f1.pushbox.intersects(f2.pushbox):
		return
	var w1 := f1.character.width / 2
	var w2 := f2.character.width / 2
	var overlap: int
	if f1.x < f2.x:
		overlap = (f1.x + w1) - (f2.x - w2)
	else:
		overlap = (f2.x + w2) - (f1.x - w1)
	if overlap <= 0:
		return
	var push := overlap / 2 + 1
	if f1.x < f2.x:
		f1.pos_x -= push
		f2.pos_x += push
	else:
		f1.pos_x += push
		f2.pos_x -= push
	# keep both inside the stage; the one pinned on a wall pushes the other
	for f in fighters():
		var hw := f.character.width / 2.0
		f.pos_x = clampf(f.pos_x, hw, FT.SCREEN_W - hw)


func _check_round_end() -> void:
	var ko1 := f1.health <= 0
	var ko2 := f2.health <= 0
	if ko1 or ko2:
		round_end_reason = "ko"
		if ko1 and ko2:
			_end_round(0)
		else:
			_end_round(2 if ko1 else 1)
	elif timer_enabled and round_frames_left <= 0:
		round_end_reason = "time"
		var r1 := f1.health / float(f1.max_health)
		var r2 := f2.health / float(f2.max_health)
		_end_round(0 if is_equal_approx(r1, r2) else (1 if r1 > r2 else 2))


func _end_round(winner: int) -> void:
	round_winner = winner
	if winner == 1: p1_score += 1
	elif winner == 2: p2_score += 1
	else: round_end_reason = "draw" if round_end_reason == "time" else round_end_reason
	if p1_score >= FT.ROUNDS_TO_WIN or p2_score >= FT.ROUNDS_TO_WIN:
		match_winner = 1 if p1_score > p2_score else 2
	phase = Phase.OUTRO
	phase_timer = FT.ROUND_OUTRO_FRAMES


func next_round() -> void:
	current_round += 1
	f1.reset(P1_START_X)
	f2.reset(P2_START_X)
	f2.facing = -1
	projectiles.clear()
	if ai1: ai1.reset()
	if ai2: ai2.reset()
	_ai_last_combo = [0, 0]
	_ai_was_blocked = [false, false]
	round_winner = 0
	round_end_reason = ""
	round_frames_left = FT.ROUND_TIME_SECONDS * FT.FPS
	phase = Phase.INTRO
	phase_timer = FT.ROUND_INTRO_FRAMES
