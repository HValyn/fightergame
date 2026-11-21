## Builds an InputFrame per player from keyboard, gamepad and touch.
## Actions are registered in code (not project.godot) so the bindings live in
## one readable place. Rebinding UI can later edit InputMap at runtime.
class_name GameInput
extends RefCounted

const BUTTONS := ["left", "right", "up", "down", "punch", "kick", "special", "heavy"]

# Player 1: arrows + A/S/D + Shift (same as the pygame prototype), first gamepad.
# Player 2: numpad 4/6/8/5 + 1/2/3 + RShift... and second gamepad.
const KEYS := {
	1: {"left": [KEY_LEFT], "right": [KEY_RIGHT], "up": [KEY_UP], "down": [KEY_DOWN],
		"punch": [KEY_A], "kick": [KEY_S], "special": [KEY_D], "heavy": [KEY_SHIFT]},
	2: {"left": [KEY_KP_4], "right": [KEY_KP_6], "up": [KEY_KP_8], "down": [KEY_KP_5],
		"punch": [KEY_KP_1], "kick": [KEY_KP_2], "special": [KEY_KP_3], "heavy": [KEY_KP_0]},
}
const PAD_BUTTONS := {
	"left": [JOY_BUTTON_DPAD_LEFT], "right": [JOY_BUTTON_DPAD_RIGHT],
	"up": [JOY_BUTTON_DPAD_UP], "down": [JOY_BUTTON_DPAD_DOWN],
	"punch": [JOY_BUTTON_X], "kick": [JOY_BUTTON_A], "special": [JOY_BUTTON_B],
	"heavy": [JOY_BUTTON_Y, JOY_BUTTON_RIGHT_SHOULDER],
}
const STICK_DEADZONE := 0.5

static var _ready := false


static func action(player: int, button: String) -> String:
	return "p%d_%s" % [player, button]


static func ensure_actions() -> void:
	if _ready:
		return
	_ready = true
	for p: int in [1, 2]:
		var device := p - 1
		for b: String in BUTTONS:
			var act := action(p, b)
			if InputMap.has_action(act):
				continue
			InputMap.add_action(act, STICK_DEADZONE)
			for k in KEYS[p][b]:
				var e := InputEventKey.new()
				e.physical_keycode = k
				InputMap.action_add_event(act, e)
			for jb in PAD_BUTTONS[b]:
				var e := InputEventJoypadButton.new()
				e.button_index = jb
				e.device = device
				InputMap.action_add_event(act, e)
			var axis := {"left": [JOY_AXIS_LEFT_X, -1.0], "right": [JOY_AXIS_LEFT_X, 1.0],
				"up": [JOY_AXIS_LEFT_Y, -1.0], "down": [JOY_AXIS_LEFT_Y, 1.0]}
			if axis.has(b):
				var e := InputEventJoypadMotion.new()
				e.axis = axis[b][0]
				e.axis_value = axis[b][1]
				e.device = device
				InputMap.action_add_event(act, e)
	# extra menu keys
	_add_key("ui_accept", KEY_A)
	_add_key("ui_cancel", KEY_BACKSPACE)
	if not InputMap.has_action("pause"):
		InputMap.add_action("pause")
		_add_key("pause", KEY_ESCAPE)
		var e := InputEventJoypadButton.new()
		e.button_index = JOY_BUTTON_START
		e.device = -1
		InputMap.action_add_event("pause", e)
	if not InputMap.has_action("debug_overlay"):
		InputMap.add_action("debug_overlay")
		_add_key("debug_overlay", KEY_F1)


static func _add_key(act: String, key: int) -> void:
	var e := InputEventKey.new()
	e.physical_keycode = key
	InputMap.action_add_event(act, e)


## Current held state for `player`; `touch` (may be null) is OR-ed in.
static func read(player: int, touch: TouchControls = null) -> InputFrame:
	ensure_actions()
	var f := InputFrame.new()
	for b in BUTTONS:
		f.set(b, Input.is_action_pressed(action(player, b)))
	if touch and player == 1:
		touch.apply_to(f)
	# opposite directions cancel (SOCD: neutral)
	if f.left and f.right:
		f.left = false; f.right = false
	if f.up and f.down:
		f.up = false
	return f
