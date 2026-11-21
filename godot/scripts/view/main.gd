## Game shell: menus, fight loop, HUD, effects. All drawing is immediate-mode
## (_draw) so the whole presentation lives in a few readable files.
## The simulation (scripts/sim) is stepped from _physics_process at 60 Hz.
##
## Command-line (after `--`):
##   --touch               show touch controls on desktop (mouse emulates touch)
##   --autoplay            skip the menu and start a match (CPU vs CPU unless --mode=0|1)
##   --seed=N              fixed AI seed
##   --screenshot=PATH     save a PNG at frame --shot-frame=N (default 240) and quit
##   --quit-after=N        quit after N physics frames
extends Node2D

enum Screen { SELECT, FIGHT, PAUSED, RESULTS }
const MODES := ["VS CPU", "2 PLAYERS", "CPU VS CPU"]
const ROWS := ["fighter", "opponent", "mode", "cpu", "stage"]
const ROW_LABELS := {"fighter": "FIGHTER", "opponent": "OPPONENT", "mode": "MODE", "cpu": "CPU LEVEL", "stage": "STAGE"}

var screen: int = Screen.SELECT
var font: Font
var tick := 0

# menu state
var char_ids: Array = []
var row := 0
var sel := {"fighter": 0, "opponent": 0, "mode": 0, "cpu": 1, "stage": 0}
var pause_idx := 0
var results_idx := 0
var _zones: Array = []          # [Rect2, Callable] rebuilt every frame for mouse/touch

# match state
var sim: MatchSim
var stages: Array[StageArt] = []
var stage: StageArt = null
var sparks: Array[Dictionary] = []
var shake := 0.0
var debug_overlay := false
var touch: TouchControls
var preview: Dictionary = {}     # char id -> FighterSim used for menu previews

# command line
var args := {}


func _ready() -> void:
	GameInput.ensure_actions()
	font = ThemeDB.fallback_font
	char_ids = CharacterDB.ids()
	stages = StageArt.list()
	for id in char_ids:
		var f := FighterSim.new(CharacterDB.get_character(id), 0, 1)
		preview[id] = f
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"

	var layer := CanvasLayer.new()
	add_child(layer)
	touch = TouchControls.new()
	layer.add_child(touch)
	var want_touch := OS.has_feature("mobile") or DisplayServer.is_touchscreen_available() or args.has("touch")
	if args.has("touch"):
		Input.emulate_touch_from_mouse = true
	touch.set_meta("enabled", want_touch)
	touch.visible = false

	if args.has("autoplay"):
		sel["mode"] = int(args.get("mode", "2"))
		sel["cpu"] = 2
		start_match()


# ---------------------------------------------------------------------------
# flow
# ---------------------------------------------------------------------------
func start_match() -> void:
	var p1_id: String = char_ids[sel["fighter"]]
	var p2_id: String
	if sel["opponent"] == 0:
		var others := char_ids.filter(func(i): return i != p1_id)
		p2_id = others.pick_random() if not others.is_empty() else p1_id
	else:
		p2_id = char_ids[sel["opponent"] - 1]
	sim = MatchSim.new(CharacterDB.get_character(p1_id), CharacterDB.get_character(p2_id))
	var diff: String = AIController.DIFFICULTY_ORDER[sel["cpu"]]
	var seed_value := int(args.get("seed", "-1"))
	match MODES[sel["mode"]]:
		"VS CPU":
			sim.ai2 = AIController.new(sim.f2.character, diff, seed_value)
		"CPU VS CPU":
			sim.ai1 = AIController.new(sim.f1.character, diff, seed_value)
			sim.ai2 = AIController.new(sim.f2.character, diff, seed_value + 1 if seed_value >= 0 else -1)
	stage = null
	if sel["stage"] > 0 and sel["stage"] - 1 < stages.size():
		stage = stages[sel["stage"] - 1]
	elif sel["stage"] == 0 and not stages.is_empty() and args.has("autoplay"):
		stage = stages[0]
	sparks.clear()
	screen = Screen.FIGHT
	touch.visible = touch.get_meta("enabled") and sim.ai1 == null


func rematch() -> void:
	start_match()


func to_select() -> void:
	sim = null
	screen = Screen.SELECT
	touch.visible = false
	touch.release_all()


# ---------------------------------------------------------------------------
# loop
# ---------------------------------------------------------------------------
func _physics_process(_delta: float) -> void:
	tick += 1
	if screen == Screen.FIGHT:
		_step_fight()
	if args.has("screenshot") and tick == int(args.get("shot-frame", "240")):
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(args["screenshot"])
		get_tree().quit()
	if args.has("quit-after") and tick >= int(args["quit-after"]):
		get_tree().quit()
	queue_redraw()


func _step_fight() -> void:
	if touch.pause_pressed:
		touch.pause_pressed = false
		_pause()
		return
	var i1 := GameInput.read(1, touch)
	var i2 := GameInput.read(2)
	sim.step(i1, i2)
	for f in sim.fighters():
		for e in f.events:
			_spawn_effect(e, f)
	if sim.phase == MatchSim.Phase.MATCH_OVER:
		screen = Screen.RESULTS
		results_idx = 0
		touch.visible = false
		touch.release_all()
	for s in sparks:
		s["t"] += 1
	sparks = sparks.filter(func(s): return s["t"] < s["life"])
	shake *= 0.85


func _spawn_effect(e: Dictionary, victim: FighterSim) -> void:
	var pos := Vector2(e["x"], e["y"])
	match e["type"]:
		"hit":
			var heavy: bool = e.get("heavy", false)
			sparks.append({"pos": pos, "t": 0, "life": 14 if heavy else 10, "color": Color("#ffd23f"),
				"size": 46.0 if heavy else 30.0, "kind": "burst"})
			sparks.append({"pos": pos + Vector2(0, -40), "t": 0, "life": 40, "color": Color.WHITE,
				"text": str(e["damage"]), "kind": "text"})
			shake = maxf(shake, 9.0 if heavy else 4.0)
		"block":
			sparks.append({"pos": pos, "t": 0, "life": 10, "color": Color("#7fc8ff"), "size": 26.0, "kind": "ring"})
		"armor":
			sparks.append({"pos": pos, "t": 0, "life": 12, "color": victim.character.color("accent"),
				"size": 40.0, "kind": "ring"})
			shake = maxf(shake, 3.0)


func _notification(what: int) -> void:
	# Android back button / desktop close request
	if what == NOTIFICATION_WM_GO_BACK_REQUEST:
		match screen:
			Screen.FIGHT: _pause()
			Screen.PAUSED: _resume()
			Screen.RESULTS: to_select()
			Screen.SELECT: get_tree().quit()


func _pause() -> void:
	screen = Screen.PAUSED
	pause_idx = 0
	touch.release_all()


func _resume() -> void:
	screen = Screen.FIGHT


# ---------------------------------------------------------------------------
# menu input
# ---------------------------------------------------------------------------
func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("debug_overlay"):
		debug_overlay = not debug_overlay
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var p := get_global_mouse_position()
		for z in _zones:
			if (z[0] as Rect2).has_point(p):
				(z[1] as Callable).call()
				return
		return
	var up := _pressed(event, "up")
	var down := _pressed(event, "down")
	var left := _pressed(event, "left")
	var right := _pressed(event, "right")
	var ok := event.is_action_pressed("ui_accept") or _pressed(event, "punch")
	var back := event.is_action_pressed("ui_cancel") or event.is_action_pressed("pause")
	match screen:
		Screen.SELECT:
			if up: row = wrapi(row - 1, 0, ROWS.size() + 1)
			elif down: row = wrapi(row + 1, 0, ROWS.size() + 1)
			elif left and row < ROWS.size(): _change(ROWS[row], -1)
			elif right and row < ROWS.size(): _change(ROWS[row], 1)
			elif ok: start_match()
			elif back and event.is_action_pressed("pause"): get_tree().quit()
		Screen.FIGHT:
			if back: _pause()
		Screen.PAUSED:
			if up or down: pause_idx = 1 - pause_idx
			elif ok: _resume() if pause_idx == 0 else to_select()
			elif back: _resume()
		Screen.RESULTS:
			if left or right or up or down: results_idx = 1 - results_idx
			elif ok: rematch() if results_idx == 0 else to_select()
			elif back: to_select()


func _pressed(event: InputEvent, b: String) -> bool:
	return event.is_action_pressed(GameInput.action(1, b)) or event.is_action_pressed(GameInput.action(2, b))


func _option_count(r: String) -> int:
	match r:
		"fighter": return char_ids.size()
		"opponent": return char_ids.size() + 1
		"mode": return MODES.size()
		"cpu": return AIController.DIFFICULTY_ORDER.size()
		"stage": return stages.size() + 1
	return 1


func _change(r: String, d: int) -> void:
	sel[r] = wrapi(sel[r] + d, 0, _option_count(r))


func _option_text(r: String) -> String:
	var v: int = sel[r]
	match r:
		"fighter": return CharacterDB.get_character(char_ids[v]).display_name.to_upper()
		"opponent": return "RANDOM" if v == 0 else CharacterDB.get_character(char_ids[v - 1]).display_name.to_upper()
		"mode": return MODES[v]
		"cpu": return AIController.DIFFICULTY_ORDER[v]
		"stage": return "BASIC ARENA" if v == 0 else stages[v - 1].display_name.to_upper()
	return ""


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------
func _draw() -> void:
	_zones.clear()
	match screen:
		Screen.SELECT:
			_draw_select()
		Screen.FIGHT, Screen.PAUSED, Screen.RESULTS:
			_draw_fight()
			if screen == Screen.PAUSED:
				_draw_menu_overlay("PAUSED", ["RESUME", "CHARACTER SELECT"], pause_idx,
					[_resume, to_select])
			elif screen == Screen.RESULTS:
				var w := sim.match_winner
				var title := "DRAW"
				if w > 0:
					var wf := sim.f1 if w == 1 else sim.f2
					title = "%s WINS" % wf.character.display_name.to_upper()
				_draw_menu_overlay(title, ["REMATCH", "CHARACTER SELECT"], results_idx, [rematch, to_select],
					"%d - %d" % [sim.p1_score, sim.p2_score])


func _text(s: String, pos: Vector2, size: int, color := Color.WHITE, align := HORIZONTAL_ALIGNMENT_LEFT,
		width := -1.0, outline := 0) -> void:
	if align == HORIZONTAL_ALIGNMENT_CENTER and width < 0:
		width = float(FT.SCREEN_W)   # centre on the screen
		pos.x = 0.0
	if outline > 0:
		draw_string_outline(font, pos, s, align, width, size, outline, Color(0, 0, 0, 0.85))
	draw_string(font, pos, s, align, width, size, color)


func _draw_background() -> void:
	if stage and not stage.layers.is_empty():
		for t in stage.layers:
			draw_texture_rect(t, Rect2(0, 0, FT.SCREEN_W, FT.SCREEN_H), false)
		return
	# procedural "basic arena" (used when no generated stage is selected)
	var top := Color("#1b1d2e")
	var bot := Color("#3a2f4f")
	for i in 14:
		var y := i * FT.GROUND_Y / 14.0
		draw_rect(Rect2(0, y, FT.SCREEN_W, FT.GROUND_Y / 14.0 + 1), top.lerp(bot, i / 13.0))
	for x in range(0, FT.SCREEN_W, 80):
		draw_line(Vector2(x, 0), Vector2(x, FT.GROUND_Y), Color(1, 1, 1, 0.04), 1.0)
	draw_rect(Rect2(0, FT.GROUND_Y, FT.SCREEN_W, FT.SCREEN_H - FT.GROUND_Y), Color("#5b4636"))
	for i in 8:
		draw_line(Vector2(600, FT.GROUND_Y), Vector2(-600 + i * 343, FT.SCREEN_H), Color(0, 0, 0, 0.15), 2.0)
	draw_line(Vector2(0, FT.GROUND_Y), Vector2(FT.SCREEN_W, FT.GROUND_Y), Color("#c8b48c"), 3.0)


func _draw_fighter(f: FighterSim, rx: float) -> void:
	var sprites := SpriteSet.for_character(f.character.id)
	var tex: Texture2D = sprites.pick(f, tick) if sprites else null
	if tex == null:
		FighterDrawer.draw(self, f, tick, rx)
		return
	# shadow
	draw_set_transform(Vector2(rx, FT.GROUND_Y + 2), 0, Vector2(1, 0.25))
	draw_circle(Vector2.ZERO, f.character.width * 0.7, Color(0, 0, 0, 0.35))
	var tint := FighterDrawer.body_tint(f, Color.WHITE)
	draw_set_transform(Vector2(rx, f.pos_y), 0, Vector2(sprites.scale * f.facing, sprites.scale))
	draw_texture(tex, -sprites.anchor * tex.get_size(), tint)
	draw_set_transform(Vector2.ZERO)


func _draw_projectiles() -> void:
	for p in sim.projectiles:
		var sprites := SpriteSet.for_character(p.owner.character.id)
		var tex: Texture2D = null
		if sprites:
			tex = sprites.pick_named("projectile:" + p.attack.id, p.age)
			if tex == sprites.pick_named("idle", p.age):
				tex = sprites.pick_named("projectile", p.age)
				if tex == sprites.pick_named("idle", p.age):
					tex = null
		if tex:
			var dir := signf(p.vel_x)
			draw_set_transform(Vector2(p.pos_x, p.pos_y), 0, Vector2(sprites.scale * dir, sprites.scale))
			draw_texture(tex, -tex.get_size() / 2)
			draw_set_transform(Vector2.ZERO)
		else:
			var c := p.owner.character.color("accent", Color.CYAN)
			var pulse := 1.0 + sin(p.age * 0.5) * 0.15
			draw_circle(Vector2(p.pos_x, p.pos_y), 24 * pulse, Color(c, 0.35))
			draw_circle(Vector2(p.pos_x, p.pos_y), 15 * pulse, c)
			draw_circle(Vector2(p.pos_x, p.pos_y), 7, Color.WHITE)


func _draw_fight() -> void:
	var off := Vector2(randf_range(-shake, shake), randf_range(-shake, shake)) if shake > 0.5 else Vector2.ZERO
	draw_set_transform(off)
	_draw_background()
	# draw the attacker on top
	var order: Array[FighterSim] = [sim.f1, sim.f2]
	if sim.f1.in_attack and not sim.f2.in_attack:
		order = [sim.f2, sim.f1]
	for f in order:
		_draw_fighter(f, f.pos_x + f.shake_x)
		draw_set_transform(off)
	_draw_projectiles()
	for s in sparks:
		var k: float = s["t"] / float(s["life"])
		match s["kind"]:
			"burst":
				for i in 8:
					var ang: float = i * TAU / 8 + s["t"] * 0.1
					var r1: float = s["size"] * k * 0.3
					var r2: float = s["size"] * (0.4 + k)
					draw_line(s["pos"] + Vector2.from_angle(ang) * r1, s["pos"] + Vector2.from_angle(ang) * r2,
						Color(s["color"], 1.0 - k), 4.0)
				draw_circle(s["pos"], s["size"] * 0.4 * (1.0 - k), Color(1, 1, 1, 1.0 - k))
			"ring":
				draw_arc(s["pos"], s["size"] * (0.4 + k), 0, TAU, 24, Color(s["color"], 1.0 - k), 5.0)
			"text":
				_text(s["text"], s["pos"] + Vector2(-30, -k * 40), 26, Color(s["color"], 1.0 - k),
					HORIZONTAL_ALIGNMENT_CENTER, 60, 4)
	if debug_overlay:
		_draw_debug()
	draw_set_transform(Vector2.ZERO)
	_draw_hud()


func _draw_debug() -> void:
	for f in sim.fighters():
		for hb in f.hurtboxes:
			draw_rect(hb.to_rect(), Color(0.2, 0.5, 1, 0.8), false, 1.5)
		if f.pushbox:
			draw_rect(f.pushbox.to_rect(), Color(0.2, 1, 0.3, 0.5), false, 1.0)
		if f.active_hitbox:
			draw_rect(f.active_hitbox.to_rect(), Color(1, 0.2, 0.2, 0.45))
		var label := FT.state_name(f.state)
		if f.current_attack:
			label += " %s f%d" % [f.current_attack.id, f.attack_frame]
		_text(label, Vector2(f.pos_x - 100, f.pos_y + 40), 14, Color.YELLOW, HORIZONTAL_ALIGNMENT_CENTER, 200, 3)
		if f.frame_adv_timer > 0:
			_text("%+d" % f.last_frame_advantage, Vector2(f.pos_x - 50, f.pos_y - f.current_height - 70), 20,
				Color.GREEN if f.last_frame_advantage >= 0 else Color.RED, HORIZONTAL_ALIGNMENT_CENTER, 100, 3)
	for p in sim.projectiles:
		draw_rect(p.box().to_rect(), Color(1, 0.2, 0.2, 0.45))


func _draw_bar(rect: Rect2, frac: float, color: Color, from_right: bool) -> void:
	draw_rect(rect.grow(2), Color(0, 0, 0, 0.7))
	draw_rect(rect, Color("#3a1010"))
	var w := rect.size.x * clampf(frac, 0, 1)
	var x := rect.position.x + (rect.size.x - w if from_right else 0.0)
	draw_rect(Rect2(x, rect.position.y, w, rect.size.y), color)


func _draw_hud() -> void:
	var bar_w := 440.0
	for side in [0, 1]:
		var f: FighterSim = sim.f1 if side == 0 else sim.f2
		var x := 30.0 if side == 0 else FT.SCREEN_W - 30.0 - bar_w
		var frac := f.health / float(f.max_health)
		var col := Color("#3ddc84") if frac > 0.5 else (Color("#ffc23d") if frac > 0.25 else Color("#ff4d4d"))
		_draw_bar(Rect2(x, 30, bar_w, 24), frac, col, side == 1)
		_draw_bar(Rect2(x + (0.0 if side == 0 else bar_w - 300), 62, 300, 9), f.super_meter / float(FT.MAX_SUPER_METER),
			f.character.color("accent", Color.CYAN), side == 1)
		var name := f.character.display_name.to_upper()
		var align := HORIZONTAL_ALIGNMENT_LEFT if side == 0 else HORIZONTAL_ALIGNMENT_RIGHT
		_text(name, Vector2(x, 24), 18, Color.WHITE, align, bar_w, 4)
		# round pips
		var score := sim.p1_score if side == 0 else sim.p2_score
		for i in FT.ROUNDS_TO_WIN:
			var px := x + bar_w - 20 - i * 22 if side == 0 else x + 20 + i * 22
			draw_circle(Vector2(px, 85), 7, Color("#ffd23f") if i < score else Color(1, 1, 1, 0.2))
		if f.combo_count >= 2:
			var cx := 40.0 if side == 0 else FT.SCREEN_W - 240.0
			_text("%d HITS" % f.combo_count, Vector2(cx, 200), 40, Color("#ffd23f"), align, 200, 6)
			_text("%d DMG" % f.combo_damage, Vector2(cx, 230), 20, Color.WHITE, align, 200, 4)
	# timer
	draw_rect(Rect2(565, 22, 70, 48), Color(0, 0, 0, 0.6))
	_text(str(sim.time_left()), Vector2(0, 60), 38, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	_text("ROUND %d" % sim.current_round, Vector2(0, 92), 14, Color("#ffd23f"), HORIZONTAL_ALIGNMENT_CENTER, -1, 3)

	match sim.phase:
		MatchSim.Phase.INTRO:
			var t := sim.phase_timer
			var msg := "ROUND %d" % sim.current_round if t > 20 else "FIGHT!"
			_text(msg, Vector2(0, 330), 72, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER, -1, 10)
		MatchSim.Phase.OUTRO:
			var msg := "K.O." if sim.round_end_reason == "ko" else ("DRAW" if sim.round_winner == 0 else "TIME")
			_text(msg, Vector2(0, 330), 96, Color("#ff4d4d"), HORIZONTAL_ALIGNMENT_CENTER, -1, 12)
			if sim.phase_timer < 80 and sim.round_winner > 0:
				var wf := sim.f1 if sim.round_winner == 1 else sim.f2
				_text("%s WINS THE ROUND" % wf.character.display_name.to_upper(), Vector2(0, 390), 28,
					Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER, -1, 6)

	if not touch.visible and screen == Screen.FIGHT:
		_text("Arrows move  ·  A punch  S kick  D special  Shift heavy  ·  Esc pause  F1 hitboxes",
			Vector2(0, FT.SCREEN_H - 12), 14, Color(1, 1, 1, 0.45), HORIZONTAL_ALIGNMENT_CENTER)


func _button(rect: Rect2, label: String, focused: bool, action: Callable, size := 26) -> void:
	draw_rect(rect, Color("#ffd23f") if focused else Color(1, 1, 1, 0.1))
	draw_rect(rect, Color(1, 1, 1, 0.6), false, 2.0)
	_text(label, Vector2(rect.position.x, rect.position.y + rect.size.y / 2 + size * 0.35), size,
		Color.BLACK if focused else Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER, rect.size.x)
	_zones.append([rect, action])


func _draw_menu_overlay(title: String, items: Array, idx: int, actions: Array, subtitle := "") -> void:
	draw_rect(Rect2(0, 0, FT.SCREEN_W, FT.SCREEN_H), Color(0, 0, 0, 0.6))
	_text(title, Vector2(0, 230), 64, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER, -1, 10)
	if subtitle != "":
		_text(subtitle, Vector2(0, 285), 32, Color("#ffd23f"), HORIZONTAL_ALIGNMENT_CENTER, -1, 6)
	for i in items.size():
		_button(Rect2(400, 330 + i * 80, 400, 60), items[i], i == idx, actions[i])


func _draw_select() -> void:
	var bg_top := Color("#14152a")
	draw_rect(Rect2(0, 0, FT.SCREEN_W, FT.SCREEN_H), bg_top)
	for i in 20:
		draw_line(Vector2(i * 80 - 400 + (tick % 80), 0), Vector2(i * 80 + (tick % 80), FT.SCREEN_H),
			Color(1, 1, 1, 0.03), 18.0)
	_text("FIGHTERGAME", Vector2(0, 62), 52, Color("#ffd23f"), HORIZONTAL_ALIGNMENT_CENTER, -1, 8)

	# character cards
	var n := char_ids.size()
	var card_w := 250.0
	var gap := 30.0
	var x0 := (FT.SCREEN_W - (n * card_w + (n - 1) * gap)) / 2.0
	for i in n:
		var id: String = char_ids[i]
		var c := CharacterDB.get_character(id)
		var r := Rect2(x0 + i * (card_w + gap), 90, card_w, 290)
		var chosen: bool = i == sel["fighter"]
		draw_rect(r, Color(1, 1, 1, 0.12) if chosen else Color(1, 1, 1, 0.04))
		draw_rect(r, c.color("accent") if chosen else Color(1, 1, 1, 0.2), false, 4.0 if chosen else 1.0)
		var sprites := SpriteSet.for_character(id)
		var f: FighterSim = preview[id]
		if sprites and sprites.portrait:
			draw_texture_rect(sprites.portrait, Rect2(r.position + Vector2(25, 10), Vector2(200, 200)), false)
		elif sprites and sprites.pick_named("idle", tick):
			var t := sprites.pick_named("idle", tick)
			var feet := Vector2(r.position.x + card_w / 2, r.position.y + 215)
			draw_set_transform(feet, 0, Vector2(sprites.scale, sprites.scale))
			draw_texture(t, -sprites.anchor * t.get_size())
			draw_set_transform(Vector2.ZERO)
		else:
			f.pos_y = r.position.y + 215
			f.facing = 1
			f.state = FT.State.IDLE
			FighterDrawer.draw(self, f, tick, r.position.x + card_w / 2, f.pos_y)
		_text(c.display_name.to_upper(), Vector2(r.position.x, r.position.y + 250), 26,
			c.color("accent"), HORIZONTAL_ALIGNMENT_CENTER, card_w, 5)
		_text(c.subtitle, Vector2(r.position.x, r.position.y + 276), 15, Color(1, 1, 1, 0.7),
			HORIZONTAL_ALIGNMENT_CENTER, card_w)
		var idx := i
		_zones.append([r, func(): sel["fighter"] = idx; row = 0])

	# option rows
	for i in ROWS.size():
		var key: String = ROWS[i]
		var y := 400.0 + i * 44
		var focused := row == i
		var dim: bool = key == "cpu" and MODES[sel["mode"]] == "2 PLAYERS"
		var col := Color("#ffd23f") if focused else (Color(1, 1, 1, 0.35) if dim else Color.WHITE)
		_text(ROW_LABELS[key], Vector2(300, y + 28), 20, col)
		var lr := Rect2(560, y + 4, 40, 34)
		var rr := Rect2(860, y + 4, 40, 34)
		_text("<", lr.position + Vector2(12, 26), 24, col)
		_text(">", rr.position + Vector2(12, 26), 24, col)
		_text(_option_text(key), Vector2(600, y + 28), 20, col, HORIZONTAL_ALIGNMENT_CENTER, 260)
		if focused:
			draw_rect(Rect2(290, y, 620, 42), Color(1, 1, 1, 0.06))
		var k := key
		var ii := i
		_zones.append([lr, func(): row = ii; _change(k, -1)])
		_zones.append([rr, func(): row = ii; _change(k, 1)])
		_zones.append([Rect2(290, y, 270, 42), func(): row = ii])
	_button(Rect2(450, 625, 300, 58), "FIGHT!", row == ROWS.size(), start_match, 30)
