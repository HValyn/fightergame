## CPU opponent. Produces InputFrames exactly like a human would (including
## stick motions for specials) and never touches the fighter directly.
## Port of prototype/ai_controller.py with a seedable RNG.
class_name AIController
extends RefCounted

enum Behavior { IDLE, APPROACH, RETREAT, ATTACK, BLOCK, WAIT, JUMP_IN, MIXUP, USE_SPECIAL }

const DIFFICULTIES := {
	"EASY": {"reaction_frames": 20, "decision_interval": 30, "block_chance": 0.3, "punish_chance": 0.2,
		"combo_chance": 0.1, "aggression": 0.3, "special_chance": 0.05},
	"MEDIUM": {"reaction_frames": 12, "decision_interval": 15, "block_chance": 0.6, "punish_chance": 0.5,
		"combo_chance": 0.4, "aggression": 0.5, "special_chance": 0.15},
	"HARD": {"reaction_frames": 5, "decision_interval": 6, "block_chance": 0.85, "punish_chance": 0.8,
		"combo_chance": 0.7, "aggression": 0.65, "special_chance": 0.3},
	"BRUTAL": {"reaction_frames": 2, "decision_interval": 3, "block_chance": 0.95, "punish_chance": 0.95,
		"combo_chance": 0.9, "aggression": 0.7, "special_chance": 0.4},
}
const DIFFICULTY_ORDER := ["EASY", "MEDIUM", "HARD", "BRUTAL"]

const FAR_RANGE := 250
const MID_RANGE := 150
const CLOSE_RANGE := 90
const CHARGE_HOLD_FRAMES := 42

## Stick motions for a RIGHT-facing fighter; mirrored when facing left.
## The button is pressed on the last entry.
static var MOTION_SEQUENCES := {
	FT.Motion.NONE: [[]],
	FT.Motion.QCF: [["down"], ["down", "right"], ["right"]],
	FT.Motion.QCB: [["down"], ["down", "left"], ["left"]],
	FT.Motion.DPF: [["right"], ["down"], ["down", "right"]],
	FT.Motion.DPB: [["left"], ["down"], ["down", "left"]],
	FT.Motion.HCF: [["left"], ["down", "left"], ["down"], ["down", "right"], ["right"]],
	FT.Motion.HCB: [["right"], ["down", "right"], ["down"], ["down", "left"], ["left"]],
	FT.Motion.CHARGE_BACK: _repeat([["left"]], CHARGE_HOLD_FRAMES) + [["right"]],
	FT.Motion.CHARGE_DOWN: _repeat([["down"]], CHARGE_HOLD_FRAMES) + [["up"]],
	FT.Motion.DOUBLE_QCF: [["down"], ["down", "right"], ["right"], ["down"], ["down", "right"], ["right"]],
	FT.Motion.ZIGZAG: [["down"], ["up"]],
}

var character: CharacterData
var difficulty_name := "MEDIUM"
var cfg: Dictionary
var rng := RandomNumberGenerator.new()

var behavior: int = Behavior.IDLE
var think_timer := 0
var behavior_timer := 0
var queue: Array[InputFrame] = []
var _opp_attack_frames := 0
var block_decision: Variant = null    # null = undecided for this opponent attack


func _init(c: CharacterData, diff: Variant = "MEDIUM", seed_value: int = -1) -> void:
	character = c
	if diff is Dictionary:
		cfg = DIFFICULTIES["MEDIUM"].duplicate()
		cfg.merge(diff, true)
		difficulty_name = "CUSTOM"
	else:
		difficulty_name = str(diff)
		cfg = DIFFICULTIES.get(difficulty_name, DIFFICULTIES["MEDIUM"]).duplicate()
	if seed_value >= 0:
		rng.seed = seed_value
	else:
		rng.randomize()


static func _repeat(item: Array, n: int) -> Array:
	var out := []
	for i in n:
		out.append(item[0])
	return out


## One frame of thinking. `me` is the fighter this AI drives.
func think(me: FighterSim, opp: FighterSim, _frame: int) -> InputFrame:
	return update_from(opp.state, opp.x, opp.pos_y, me.x, opp.current_attack, me.facing_right)


## Same as think() but from raw values (handy for tests).
func update_from(opp_state: int, opp_x: int, opp_y: float, self_x: int,
		opp_attack: AttackData, facing_right: bool) -> InputFrame:
	think_timer -= 1
	behavior_timer -= 1
	var distance := absi(self_x - opp_x)
	var opp_jumping := opp_y < FT.GROUND_Y - 5
	var opp_crouching := opp_state == FT.State.CROUCH

	# 1. React to the opponent's attack (after a human-like delay)
	if opp_state == FT.State.ATTACK_STARTUP or opp_state == FT.State.ATTACK_ACTIVE:
		_opp_attack_frames += 1
		if _opp_attack_frames >= int(cfg["reaction_frames"]):
			return _handle_opponent_attack(opp_attack, facing_right)
	else:
		_opp_attack_frames = 0
		block_decision = null

	# 2. Punish recovery
	if opp_state == FT.State.ATTACK_RECOVERY:
		return _handle_punish(distance, facing_right)

	# 3. Queued inputs (motions, combos)
	if not queue.is_empty():
		return queue.pop_front()

	# 4. Anti-air
	if opp_jumping and distance < MID_RANGE and rng.randf() < 0.6:
		return _make_anti_air(facing_right)

	# 5. Decide
	if think_timer <= 0:
		_decide(distance, opp_jumping, opp_crouching)
		think_timer = int(cfg["decision_interval"]) + rng.randi_range(0, 5)

	return _execute(distance, facing_right)


func _handle_opponent_attack(a: AttackData, facing_right: bool) -> InputFrame:
	var inp := InputFrame.new()
	if a == null:
		return inp
	# Decide ONCE per opponent attack (re-rolling every frame made the guard flicker)
	if block_decision == null:
		block_decision = rng.randf() < float(cfg["block_chance"])
	if not block_decision:
		return inp
	if facing_right: inp.left = true
	else: inp.right = true
	if a.height == FT.Height.LOW:
		inp.down = true
	behavior = Behavior.BLOCK
	return inp


func _handle_punish(distance: int, facing_right: bool) -> InputFrame:
	if distance > CLOSE_RANGE or rng.randf() > float(cfg["punish_chance"]):
		return InputFrame.new()
	if rng.randf() < float(cfg["special_chance"]) and not character.specials.is_empty():
		var sp: CharacterData.SpecialMove = character.specials[rng.randi_range(0, character.specials.size() - 1)]
		if sp.meter_cost <= 0:
			return _special_input(sp, facing_right)
	return InputFrame.parse("punch")


func _make_anti_air(facing_right: bool) -> InputFrame:
	for sp in character.specials:
		if sp.attack.has("invincible_startup") or sp.attack.has("launcher"):
			if sp.meter_cost <= 0:
				return _special_input(sp, facing_right)
	return InputFrame.parse("up+punch")


func _decide(distance: int, _opp_jumping: bool, _opp_crouching: bool) -> void:
	var agg := float(cfg["aggression"])
	var r := rng.randf()
	if distance > FAR_RANGE:
		behavior = Behavior.APPROACH if r < agg else Behavior.WAIT
	elif distance > MID_RANGE:
		if r < agg * 0.3: behavior = Behavior.USE_SPECIAL
		elif r < agg * 0.5: behavior = Behavior.JUMP_IN
		elif r < agg * 0.8: behavior = Behavior.APPROACH
		elif r < 0.9: behavior = Behavior.WAIT
		else: behavior = Behavior.RETREAT
	elif distance > CLOSE_RANGE:
		if r < agg * 0.4: behavior = Behavior.ATTACK
		elif r < agg * 0.6: behavior = Behavior.USE_SPECIAL
		elif r < agg * 0.8: behavior = Behavior.MIXUP
		else: behavior = Behavior.WAIT
	else:
		if r < agg * 0.5: behavior = Behavior.ATTACK
		elif r < 0.65: behavior = Behavior.RETREAT
		elif r < 0.8: behavior = Behavior.MIXUP
		else: behavior = Behavior.USE_SPECIAL
	behavior_timer = 15 + rng.randi_range(0, 15)


func _execute(distance: int, facing_right: bool) -> InputFrame:
	if behavior_timer <= 0:
		behavior = Behavior.IDLE
	var fwd := "right" if facing_right else "left"
	var back := "left" if facing_right else "right"
	match behavior:
		Behavior.APPROACH:
			return InputFrame.parse(fwd)
		Behavior.RETREAT:
			return InputFrame.parse(back)
		Behavior.JUMP_IN:
			if float(cfg["combo_chance"]) > 0.3:
				queue.append(InputFrame.parse("punch" if rng.randf() < 0.5 else "kick"))
			behavior = Behavior.IDLE
			return InputFrame.parse("up+" + fwd)
		Behavior.ATTACK:
			return _attack_input(distance)
		Behavior.MIXUP:
			var inp := _attack_input(distance)
			if rng.randf() < float(cfg["combo_chance"]):
				queue.append(InputFrame.parse("kick"))
			return inp
		Behavior.USE_SPECIAL:
			behavior = Behavior.IDLE
			return _try_special(distance, facing_right)
	return InputFrame.new()


func _attack_input(distance: int) -> InputFrame:
	behavior = Behavior.IDLE
	if distance <= CLOSE_RANGE:
		return InputFrame.parse("down+punch" if rng.randf() < 0.4 else "punch")
	if distance <= MID_RANGE:
		return InputFrame.parse("kick+heavy" if rng.randf() < 0.3 else "kick")
	return InputFrame.parse("kick")


func _try_special(distance: int, facing_right: bool) -> InputFrame:
	var specials := character.specials.filter(func(s): return s.meter_cost <= 0)
	if specials.is_empty() or rng.randf() > float(cfg["special_chance"]):
		return _attack_input(distance)
	var pool := specials
	if distance > MID_RANGE:
		var proj := specials.filter(func(s): return s.attack.is_projectile())
		if not proj.is_empty(): pool = proj
	elif distance < CLOSE_RANGE:
		var grabs := specials.filter(func(s): return s.attack.is_throw())
		if not grabs.is_empty(): pool = grabs
	return _special_input(pool[rng.randi_range(0, pool.size() - 1)], facing_right)


## Perform a special like a human: queue the motion, button on the last frame.
func _special_input(sp: CharacterData.SpecialMove, facing_right: bool) -> InputFrame:
	var frames := build_motion_inputs(sp.motion, sp.button, facing_right)
	var rest: Array[InputFrame] = []
	rest.assign(frames.slice(1))
	rest.append_array(queue)
	queue = rest
	return frames[0]


static func build_motion_inputs(motion: int, button: String, facing_right: bool) -> Array[InputFrame]:
	var seq: Array = MOTION_SEQUENCES.get(motion, [[]])
	var out: Array[InputFrame] = []
	for i in seq.size():
		var inp := InputFrame.new()
		for d in seq[i]:
			var dd: String = d
			if not facing_right:
				dd = {"left": "right", "right": "left"}.get(dd, dd)
			inp.set(dd, true)
		if i == seq.size() - 1:
			inp.set(button, true)
		out.append(inp)
	return out


func on_hit_landed(combo_count: int) -> void:
	if combo_count > 0 and rng.randf() < float(cfg["combo_chance"]):
		queue.append(InputFrame.parse("punch" if rng.randf() < 0.5 else "kick"))


func on_blocked() -> void:
	queue.clear()
	behavior = Behavior.RETREAT
	behavior_timer = 15


func reset() -> void:
	behavior = Behavior.IDLE
	think_timer = 0
	behavior_timer = 0
	queue.clear()
	_opp_attack_frames = 0
	block_decision = null
