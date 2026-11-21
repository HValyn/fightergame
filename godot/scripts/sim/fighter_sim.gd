## One fighter: state machine, physics, boxes, hit/block resolution.
## Pure logic port of prototype/fighter.py (plus projectiles, armor,
## invincibility and teleport, which the prototype declared but never ran).
## Call update() exactly once per 60 FPS frame.
class_name FighterSim
extends RefCounted

const COYOTE_TIME_FRAMES := 3
const TELEPORT_BEHIND_GAP := 70.0
const AIRBORNE_HOP_VY := -7.0
const AIRBORNE_HOP_VX := 4.0

var character: CharacterData
var player_id := 1

# position / physics
var pos_x := 0.0
var pos_y := FT.GROUND_Y
var vel_x := 0.0
var vel_y := 0.0
var shake_x := 0.0

# state
var state: int = FT.State.IDLE
var facing := 1                       # +1 right, -1 left
var state_timer := 0

var max_health := 100
var health := 100
var super_meter := 0

# attack
var current_attack: AttackData = null
var attack_frame := 0
var has_hit_opponent := false
var can_cancel_attack := false
var attack_was_blocked := false
var attack_started_airborne := false
var armor_hits_remaining := 0
var projectile_spawned := false
var projectile_active := false        # set by MatchSim: do I own a live projectile?
var pending_projectile: AttackData = null   # MatchSim collects this after update()

# stun
var hitstop_frames := 0
var hitstun_frames := 0
var blockstun_frames := 0
var hitstun_direction := 0
var knockdown_timer := 0

# guard. block_direction = SCREEN direction held away (-1 left, +1 right, 0 none)
var is_blocking := false
var block_direction := 0
var block_crouching := false

# combo / feedback
var combo_count := 0
var combo_damage := 0
var last_hit_frame := -999
var last_frame_advantage := 0
var frame_adv_timer := 0
var hit_flash := 0
var block_flash := 0
var events: Array[Dictionary] = []   # per-frame events for the view (hit, block, armor...)

# movement
var coyote_time_remaining := 0
var was_grounded_last_frame := true
var dash_timer := 0
var dash_speed := 0.0
var jumps_remaining := 1
var air_dash_used := false

# boxes
var hurtboxes: Array[Box] = []
var active_hitbox: Box = null
var pushbox: Box = null

var input := InputBuffer.new()
var resolver: MoveResolver


func _init(c: CharacterData, x: float, pid: int = 1) -> void:
	character = c
	player_id = pid
	max_health = c.max_health
	resolver = MoveResolver.new(c)
	reset(x)


# ---------------------------------------------------------------------------
# derived properties
# ---------------------------------------------------------------------------
var x: int:
	get: return int(pos_x)

var facing_right: bool:
	get: return facing == 1

var is_grounded: bool:
	get: return pos_y >= FT.GROUND_Y

var is_crouching: bool:
	get: return state == FT.State.CROUCH or (state == FT.State.BLOCKSTUN and block_crouching)

var current_height: int:
	get:
		if is_crouching:
			return character.crouch_height
		if current_attack and current_attack.height == FT.Height.LOW:
			return character.crouch_height
		return character.height

var can_act: bool:
	get: return FT.actionable(state)

var in_attack: bool:
	get: return FT.attacking(state)


# ---------------------------------------------------------------------------
# main update
# ---------------------------------------------------------------------------
func update(opponent: FighterSim, frame: int, inp: InputFrame) -> void:
	events.clear()
	pending_projectile = null
	if hit_flash > 0: hit_flash -= 1
	if block_flash > 0: block_flash -= 1

	# The attacker's combo ends once the opponent is no longer stunned.
	if combo_count and not FT.stunned(opponent.state):
		combo_count = 0
		combo_damage = 0

	input.push(inp, facing)

	# Hitstop freeze: no state, no physics (knockback applies after the freeze)
	if hitstop_frames > 0:
		hitstop_frames -= 1
		shake_x *= 0.88
		return

	_update_state(inp, opponent, frame)
	_apply_physics()
	_update_boxes()
	state_timer += 1
	if frame_adv_timer > 0:
		frame_adv_timer -= 1
	shake_x *= 0.88


func _update_state(inp: InputFrame, opponent: FighterSim, frame: int) -> void:
	match state:
		FT.State.HITSTUN:
			_update_hitstun()
		FT.State.BLOCKSTUN:
			_update_blockstun(inp)
		FT.State.KNOCKDOWN:
			_update_knockdown()
		FT.State.DASH_FORWARD, FT.State.DASH_BACKWARD:
			_update_dash()
		_:
			if in_attack:
				_update_attack(opponent, frame)
			else:
				# Attacks take priority over movement (so up+button on a charge
				# release doesn't jump).
				face_target(opponent.x)
				if _check_attack_input(inp):
					return
				_update_movement(inp)


# ---------------------------------------------------------------------------
# movement
# ---------------------------------------------------------------------------
func _update_movement(inp: InputFrame) -> void:
	block_direction = 0
	is_blocking = false
	block_crouching = false
	var prev := input.previous()
	var is_back := (inp.left and facing_right) or (inp.right and not facing_right)
	var is_forward := (inp.right and facing_right) or (inp.left and not facing_right)
	var back_sign := -facing

	if is_grounded:
		vel_x = 0.0
		if inp.up and not inp.down and jumps_remaining > 0:
			vel_y = character.jump_force
			vel_x = character.walk_speed * (1 if inp.right else (-1 if inp.left else 0))
			_set_state(FT.State.JUMP)
			jumps_remaining -= 1
			coyote_time_remaining = 0
			air_dash_used = false
			return
		if inp.down:
			# Only down+back blocks (plain down does not).
			_set_state(FT.State.CROUCH)
			if is_back:
				is_blocking = true
				block_crouching = true
				block_direction = back_sign
		elif is_back:
			vel_x = back_sign * character.walk_speed
			is_blocking = true
			block_direction = back_sign
			_set_state(FT.State.WALK_BACKWARD)
		elif is_forward:
			vel_x = -back_sign * character.walk_speed
			_set_state(FT.State.WALK_FORWARD)
		else:
			_set_state(FT.State.IDLE)

		# Dash: heavy + direction (no attack button)
		var heavy_pressed := inp.heavy and not prev.heavy
		if heavy_pressed and not inp.punch and not inp.kick and not inp.down:
			if is_forward:
				_start_dash(true)
			elif is_back:
				_start_dash(false)
	else:
		if inp.left:
			vel_x = -character.walk_speed * 0.6
		elif inp.right:
			vel_x = character.walk_speed * 0.6
		if inp.up and not prev.up and jumps_remaining > 0:
			vel_y = character.jump_force * 0.85
			jumps_remaining -= 1
		if character.has_air_dash and not air_dash_used and inp.heavy and not prev.heavy:
			_start_dash(true)
			air_dash_used = true

	if was_grounded_last_frame and not is_grounded:
		coyote_time_remaining = COYOTE_TIME_FRAMES
	elif is_grounded:
		coyote_time_remaining = 0
	was_grounded_last_frame = is_grounded
	if coyote_time_remaining > 0:
		coyote_time_remaining -= 1


func _start_dash(forward: bool) -> void:
	if forward:
		_set_state(FT.State.DASH_FORWARD)
		dash_timer = character.dash_duration
		dash_speed = character.forward_dash_speed * facing
	else:
		_set_state(FT.State.DASH_BACKWARD)
		dash_timer = character.back_dash_duration
		dash_speed = -character.back_dash_speed * facing


func _update_dash() -> void:
	dash_timer -= 1
	vel_x = dash_speed
	if dash_timer <= 0:
		_set_state(FT.State.IDLE if is_grounded else FT.State.JUMP)
		vel_x = 0.0


# ---------------------------------------------------------------------------
# attacks
# ---------------------------------------------------------------------------
func _check_attack_input(inp: InputFrame) -> bool:
	if not can_act:
		return false
	# Buffered presses first (pressed during recovery/stun, replayed now)
	if input.has_buffered():
		var b := input.consume_buffered()
		if b and _resolve_and_start(b):
			return true
	if inp.has_attack() and input.fresh_press(inp):
		return _resolve_and_start(inp)
	return false


func resolve_attack(inp: InputFrame) -> AttackData:
	return resolver.resolve(inp, input.motion, {
		"facing_right": facing_right, "grounded": is_grounded,
		"meter": super_meter, "projectile_active": projectile_active,
	})


func _resolve_and_start(inp: InputFrame) -> bool:
	var a := resolve_attack(inp)
	if a:
		start_attack(a)
		return true
	return false


func start_attack(a: AttackData) -> void:
	current_attack = a
	attack_frame = 0
	_set_state(FT.State.ATTACK_STARTUP)
	has_hit_opponent = false
	attack_was_blocked = false
	can_cancel_attack = false
	projectile_spawned = false
	armor_hits_remaining = character.armor_hits if a.has("armor") else 0
	attack_started_airborne = not is_grounded
	if is_grounded:
		vel_x = 0.0          # keep air momentum for jump-ins
		if a.has("airborne"):
			vel_y = AIRBORNE_HOP_VY
			vel_x = AIRBORNE_HOP_VX * facing
	active_hitbox = null
	is_blocking = false
	block_direction = 0
	if a.is_special():
		# Specials consume the motion (and any stored charge); supers spend meter
		input.motion.consume()
		super_meter = maxi(0, super_meter - a.meter_cost)


func _cancel_allowed(cur: AttackData, nxt: AttackData) -> bool:
	if nxt.move_type == FT.MoveType.SUPER:
		return cur.has("super_cancel")
	if nxt.move_type == FT.MoveType.SPECIAL:
		return cur.has("special_cancel")
	return cur.has("chain_cancel") and nxt != cur


func _update_attack(opponent: FighterSim, _frame: int) -> void:
	attack_frame += 1
	if current_attack == null:
		_set_state(FT.State.IDLE)
		return
	var a := current_attack
	var startup_end := a.startup
	var active_end := startup_end + a.active
	var recovery_end := active_end + a.recovery

	if attack_frame < startup_end:
		state = FT.State.ATTACK_STARTUP
		active_hitbox = null
	elif attack_frame < active_end:
		if state != FT.State.ATTACK_ACTIVE:
			_on_first_active_frame(opponent)
		state = FT.State.ATTACK_ACTIVE
		if a.is_projectile():
			active_hitbox = null          # the projectile carries the hit
		else:
			active_hitbox = calculate_attack_hitbox()
			if not has_hit_opponent and active_hitbox:
				_check_hit(opponent)
	else:
		state = FT.State.ATTACK_RECOVERY
		active_hitbox = null

	can_cancel_attack = (has_hit_opponent and a.cancel_window > 0
		and attack_frame >= active_end and attack_frame < recovery_end
		and attack_frame < active_end + a.cancel_window)

	if can_cancel_attack:
		# Presses made during hitstop are in the buffer, so check it too
		var cur := input.current()
		var candidate: InputFrame = null
		if cur.has_attack() and input.fresh_press(cur):
			candidate = cur
		elif input.has_buffered():
			candidate = input.consume_buffered()
		if candidate:
			var nxt := resolve_attack(candidate)
			if nxt and _cancel_allowed(a, nxt):
				start_attack(nxt)
				return

	if attack_frame >= recovery_end:
		_end_attack()


func _end_attack() -> void:
	_set_state(FT.State.IDLE)
	current_attack = null
	attack_frame = 0
	active_hitbox = null
	can_cancel_attack = false


func _on_first_active_frame(opponent: FighterSim) -> void:
	var a := current_attack
	if a.is_projectile() and not projectile_spawned:
		projectile_spawned = true
		pending_projectile = a
	if a.teleport_behind:
		var side := 1 if opponent.pos_x >= pos_x else -1
		var hw := character.width / 2.0
		pos_x = clampf(opponent.pos_x + side * TELEPORT_BEHIND_GAP, hw, FT.SCREEN_W - hw)
		facing = 1 if opponent.pos_x >= pos_x else -1
		_update_boxes()


func _check_hit(opponent: FighterSim) -> void:
	if active_hitbox == null:
		return
	for hb in opponent.hurtboxes:
		if active_hitbox.intersects(hb):
			var r := opponent.receive_attack(current_attack, pos_x, facing, combo_scaling())
			_after_contact(opponent, current_attack, r)
			return


## Attacker-side bookkeeping after one of my attacks (melee or projectile) met the defender.
func _after_contact(opponent: FighterSim, a: AttackData, r: Dictionary) -> void:
	var result: int = r["result"]
	if result == FT.HitResult.WHIFF:
		return
	has_hit_opponent = true
	match result:
		FT.HitResult.HIT:
			hitstop_frames = a.hitstop
			last_frame_advantage = a.advantage_on_hit()
			if input.frame - last_hit_frame > FT.COMBO_DECAY_WINDOW:
				combo_count = 0
				combo_damage = 0
			combo_count += 1
			combo_damage += int(r["damage"])
			last_hit_frame = input.frame
			add_meter(5 + int(r["damage"]) / 4)
			opponent.add_meter(2)
		FT.HitResult.BLOCK:
			hitstop_frames = a.hitstop / 2
			last_frame_advantage = a.advantage_on_block()
			attack_was_blocked = true
			add_meter(2)
			opponent.add_meter(3)
		FT.HitResult.ARMOR:
			hitstop_frames = a.hitstop / 2
			last_frame_advantage = 0
			add_meter(2)
	frame_adv_timer = 60


## Called by projectiles: same bookkeeping as a melee contact.
func on_projectile_contact(opponent: FighterSim, a: AttackData, r: Dictionary) -> void:
	var saved_hitstop := hitstop_frames
	_after_contact(opponent, a, r)
	hitstop_frames = saved_hitstop        # thrower isn't frozen by a distant hit


func combo_scaling() -> float:
	return maxf(FT.MIN_COMBO_SCALING, 1.0 - combo_count * FT.COMBO_SCALING_STEP)


func add_meter(n: int) -> void:
	super_meter = clampi(super_meter + n, 0, FT.MAX_SUPER_METER)


# ---------------------------------------------------------------------------
# defender side
# ---------------------------------------------------------------------------
## Is this fighter immune to `a` right now (invincibility / low profile / high over crouch)?
func evades(a: AttackData) -> bool:
	if a.height == FT.Height.HIGH and is_crouching:
		return true
	if state == FT.State.DASH_BACKWARD and \
			character.back_dash_duration - dash_timer < character.back_dash_invincible_frames:
		return true
	if in_attack and current_attack:
		var ca := current_attack
		if ca.has("invincible_all") and state != FT.State.ATTACK_RECOVERY:
			return true
		if ca.has("invincible_startup") and state == FT.State.ATTACK_STARTUP:
			return true
		if ca.has("low_profile") and a.height == FT.Height.HIGH and state != FT.State.ATTACK_RECOVERY:
			return true
	return false


## Guarding correctly? Hold AWAY from the source (by position, so cross-ups
## work); lows need a crouch block, overheads a standing block.
func is_block_correct(a: AttackData, source_x: float, source_facing: int) -> bool:
	if not is_blocking:
		return false
	var away: int
	if int(source_x) != x:
		away = 1 if pos_x > source_x else -1
	else:
		away = source_facing
	if block_direction != away:
		return false
	if a.height == FT.Height.LOW and not block_crouching:
		return false
	if a.height == FT.Height.OVERHEAD and block_crouching:
		return false
	return true


## Apply attack `a` coming from source_x. Returns {result, damage}.
func receive_attack(a: AttackData, source_x: float, source_facing: int, scaling: float) -> Dictionary:
	if evades(a):
		return {"result": FT.HitResult.WHIFF, "damage": 0}
	var dir_from_source := 1 if pos_x >= source_x else -1
	var is_throw := a.is_throw()

	if not is_throw and is_block_correct(a, source_x, source_facing):
		if a.chip > 0:
			health = maxi(0 if a.has("chip_kills") else 1, health - a.chip)
		_set_state(FT.State.BLOCKSTUN)
		blockstun_frames = a.blockstun
		hitstop_frames = a.hitstop / 2
		hitstun_direction = dir_from_source
		vel_x = a.knockback_x * 0.4 * dir_from_source
		block_flash = 8
		events.append({"type": "block", "x": pos_x, "y": pos_y - current_height * 0.6})
		return {"result": FT.HitResult.BLOCK, "damage": a.chip}

	var damage := maxi(1, int(a.damage * scaling))

	# Armor soaks the hit: damage but no stun
	if not is_throw and armor_hits_remaining > 0 and in_attack and state != FT.State.ATTACK_RECOVERY:
		armor_hits_remaining -= 1
		health = maxi(0, health - damage)
		hitstop_frames = a.hitstop / 2
		hit_flash = 4
		events.append({"type": "armor", "x": pos_x, "y": pos_y - current_height * 0.6, "damage": damage})
		return {"result": FT.HitResult.ARMOR, "damage": damage}

	is_blocking = false
	block_direction = 0
	health = maxi(0, health - damage)
	hitstun_frames = a.hitstun
	hitstun_direction = dir_from_source
	hitstop_frames = a.hitstop
	if is_throw:
		vel_x = a.knockback_x * source_facing
		vel_y = a.knockback_y if a.knockback_y < 0 else -10.0
	else:
		vel_x = a.knockback_x * dir_from_source
		vel_y = a.knockback_y
	_set_state(FT.State.KNOCKDOWN if a.has("launcher") else FT.State.HITSTUN)
	current_attack = null
	active_hitbox = null
	shake_x = a.knockback_x * 0.5
	hit_flash = 6
	events.append({"type": "hit", "x": pos_x, "y": pos_y - current_height * 0.6,
		"damage": damage, "heavy": a.heavy or a.is_special()})
	return {"result": FT.HitResult.HIT, "damage": damage}


# ---------------------------------------------------------------------------
# stun states
# ---------------------------------------------------------------------------
func _update_hitstun() -> void:
	hitstun_frames -= 1
	vel_x *= 0.95
	if hitstun_frames <= 0 and is_grounded:
		_set_state(FT.State.IDLE)
		vel_x = 0.0


func _update_blockstun(inp: InputFrame) -> void:
	blockstun_frames -= 1
	vel_x *= 0.9
	is_blocking = true
	block_crouching = inp.down
	if blockstun_frames <= 0:
		_set_state(FT.State.CROUCH if inp.down else FT.State.IDLE)
		vel_x = 0.0


func _update_knockdown() -> void:
	knockdown_timer += 1
	hitstun_frames -= 1
	vel_x *= 0.92
	if is_grounded and vel_y >= 0 and hitstun_frames <= 0:
		knockdown_timer = 0
		_set_state(FT.State.IDLE)
		vel_x = 0.0


# ---------------------------------------------------------------------------
# physics / boxes
# ---------------------------------------------------------------------------
func _apply_physics() -> void:
	if not is_grounded:
		vel_y += character.gravity
	pos_x += vel_x
	pos_y += vel_y
	if pos_y > FT.GROUND_Y:
		pos_y = FT.GROUND_Y
		vel_y = 0.0
		jumps_remaining = 2 if character.has_double_jump else 1
		if state == FT.State.JUMP:
			_set_state(FT.State.IDLE)
		elif in_attack and attack_started_airborne:
			# Landing cancels an air attack
			_end_attack()
			vel_x = 0.0
	var hw := character.width / 2
	pos_x = clampf(pos_x, hw, FT.SCREEN_W - hw)


func _update_boxes() -> void:
	hurtboxes.clear()
	var h := current_height
	var w := character.width
	hurtboxes.append(Box.new(x - w / 2 + 5, int(pos_y) - h + 5, w - 10, h - 5))
	var hr := character.head_radius
	hurtboxes.append(Box.new(x - hr, int(pos_y) - h - hr * 2, hr * 2, hr * 2))
	pushbox = Box.new(x - w / 2, int(pos_y) - h, w, h)


func calculate_attack_hitbox() -> Box:
	if current_attack == null:
		return null
	var a := current_attack
	var hw := character.width / 2
	var hx: int
	if facing_right:
		hx = x + hw - 5 + a.hitbox_x
	else:
		hx = x - hw - a.hitbox_w + 5 - a.hitbox_x
	var h := current_height
	var y := int(pos_y)
	var hy: int
	match a.height:
		FT.Height.HIGH:
			hy = y - h - 5 + a.hitbox_y
		FT.Height.OVERHEAD:
			hy = y - character.height / 2 - a.hitbox_h   # hits standing AND crouching
		FT.Height.LOW:
			hy = y - a.hitbox_h - 2                      # at the feet
		_:
			hy = y - h / 2 - a.hitbox_h / 2 + a.hitbox_y
	return Box.new(hx, hy, a.hitbox_w, a.hitbox_h)


# ---------------------------------------------------------------------------
# utility
# ---------------------------------------------------------------------------
func _set_state(s: int) -> void:
	if s != state:
		state = s
		state_timer = 0


func face_target(target_x: int) -> void:
	if FT.stunned(state) or in_attack:
		return
	facing = -1 if target_x < x else 1


func reset(px: float) -> void:
	pos_x = px
	pos_y = FT.GROUND_Y
	vel_x = 0.0
	vel_y = 0.0
	shake_x = 0.0
	state = FT.State.IDLE
	state_timer = 0
	health = max_health
	super_meter = 0
	current_attack = null
	attack_frame = 0
	hitstop_frames = 0
	hitstun_frames = 0
	blockstun_frames = 0
	combo_count = 0
	combo_damage = 0
	last_hit_frame = -999
	dash_timer = 0
	knockdown_timer = 0
	is_blocking = false
	block_direction = 0
	block_crouching = false
	has_hit_opponent = false
	attack_was_blocked = false
	projectile_active = false
	pending_projectile = null
	hit_flash = 0
	block_flash = 0
	jumps_remaining = 2 if character.has_double_jump else 1
	input.clear()
	events.clear()
	_update_boxes()
