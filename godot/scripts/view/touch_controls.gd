## On-screen controls for phones/tablets: a floating 8-way stick on the left
## half and four buttons (P K S H) on the right. Multi-touch aware.
class_name TouchControls
extends Control

const STICK_RADIUS := 90.0
const STICK_DEAD := 0.35
const BTN_RADIUS := 52.0

var _stick_finger := -1
var _stick_origin := Vector2(170, 540)
var _stick_pos := Vector2.ZERO          # offset from origin, clamped to radius
var _held := {}                          # button -> finger index
var pause_pressed := false               # read & cleared by main.gd

var buttons := {
	"punch": {"pos": Vector2(930, 560), "label": "P", "color": Color("#e8574a")},
	"kick": {"pos": Vector2(1060, 500), "label": "K", "color": Color("#4a9be8")},
	"special": {"pos": Vector2(1060, 630), "label": "S", "color": Color("#e8c84a")},
	"heavy": {"pos": Vector2(930, 440), "label": "H", "color": Color("#9b5de5")},
}
const PAUSE_RECT := Rect2(575, 104, 50, 36)


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)


func _input(event: InputEvent) -> void:
	if not visible:
		return
	if event is InputEventScreenTouch:
		var pos := _to_local(event.position)
		if event.pressed:
			if PAUSE_RECT.has_point(pos):
				pause_pressed = true
				return
			var b := _button_at(pos)
			if b != "":
				_held[b] = event.index
			elif pos.x < 600 and _stick_finger == -1:
				_stick_finger = event.index
				_stick_origin = pos
				_stick_pos = Vector2.ZERO
		else:
			_release(event.index)
		queue_redraw()
	elif event is InputEventScreenDrag:
		var pos := _to_local(event.position)
		if event.index == _stick_finger:
			_stick_pos = (pos - _stick_origin).limit_length(STICK_RADIUS)
		else:
			# sliding a finger across buttons (common on phones)
			var b := _button_at(pos)
			for k in _held.keys():
				if _held[k] == event.index and k != b:
					_held.erase(k)
			if b != "":
				_held[b] = event.index
		queue_redraw()


func _to_local(screen_pos: Vector2) -> Vector2:
	return get_global_transform_with_canvas().affine_inverse() * screen_pos


func _release(index: int) -> void:
	if index == _stick_finger:
		_stick_finger = -1
		_stick_pos = Vector2.ZERO
	for k in _held.keys():
		if _held[k] == index:
			_held.erase(k)


func _button_at(pos: Vector2) -> String:
	for b in buttons:
		if pos.distance_to(buttons[b]["pos"]) <= BTN_RADIUS * 1.15:
			return b
	return ""


func release_all() -> void:
	_held.clear()
	_stick_finger = -1
	_stick_pos = Vector2.ZERO


func apply_to(f: InputFrame) -> void:
	if not visible:
		return
	var v := _stick_pos / STICK_RADIUS
	if v.length() >= STICK_DEAD:
		var ang := v.angle()                  # 8-way: 45 degree sectors
		var sector := wrapi(int(round(ang / (PI / 4))), 0, 8)
		match sector:
			0: f.right = true
			1: f.right = true; f.down = true
			2: f.down = true
			3: f.left = true; f.down = true
			4: f.left = true
			5: f.left = true; f.up = true
			6: f.up = true
			7: f.right = true; f.up = true
	for b in _held:
		f.set(b, true)


func _draw() -> void:
	var font := ThemeDB.fallback_font
	# stick
	var base := Color(1, 1, 1, 0.12)
	draw_circle(_stick_origin, STICK_RADIUS, base)
	draw_arc(_stick_origin, STICK_RADIUS, 0, TAU, 48, Color(1, 1, 1, 0.3), 2.0)
	draw_circle(_stick_origin + _stick_pos, 38, Color(1, 1, 1, 0.35))
	# buttons
	for b in buttons:
		var spec: Dictionary = buttons[b]
		var c: Color = spec["color"]
		c.a = 0.75 if _held.has(b) else 0.35
		draw_circle(spec["pos"], BTN_RADIUS, c)
		draw_arc(spec["pos"], BTN_RADIUS, 0, TAU, 40, Color(1, 1, 1, 0.5), 2.0)
		draw_string(font, spec["pos"] + Vector2(-10, 11), spec["label"], HORIZONTAL_ALIGNMENT_LEFT, -1, 32)
	# pause
	draw_rect(PAUSE_RECT, Color(0, 0, 0, 0.35))
	draw_rect(Rect2(PAUSE_RECT.position + Vector2(16, 8), Vector2(6, 20)), Color.WHITE)
	draw_rect(Rect2(PAUSE_RECT.position + Vector2(28, 8), Vector2(6, 20)), Color.WHITE)
