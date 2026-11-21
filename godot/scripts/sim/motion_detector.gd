## Recognises motion inputs (QCF, DP, HCB, charge...).
## Directions are stored NORMALISED so that "right" always means forward;
## templates are written once for a right-facing fighter.
class_name MotionDetector
extends RefCounted

const BUFFER_SIZE := 60
const DEFAULT_WINDOW := 20              # whole motion must fit in this many frames
const COMPLETION_WINDOW := 8            # last direction must be this recent
const MIN_CHARGE_FRAMES := 40
const CHARGE_RELEASE_GRACE := 10

const TEMPLATES := {
	FT.Motion.QCF: [["down", "downright", "right"]],
	FT.Motion.QCB: [["down", "downleft", "left"]],
	FT.Motion.DPF: [["right", "down", "downright"], ["right", "downright", "down", "downright"]],
	FT.Motion.DPB: [["left", "down", "downleft"], ["left", "downleft", "down", "downleft"]],
	FT.Motion.HCF: [["left", "downleft", "down", "downright", "right"]],
	FT.Motion.HCB: [["right", "downright", "down", "downleft", "left"]],
	FT.Motion.DOUBLE_QCF: [["down", "downright", "right", "down", "downright", "right"]],
	FT.Motion.ZIGZAG: [["down", "up"]],
}
const MIRROR := {
	"left": "right", "right": "left", "downleft": "downright", "downright": "downleft",
	"upleft": "upright", "upright": "upleft",
}
const BACK_DIRS := ["left", "downleft", "upleft"]
const FORWARD_DIRS := ["right", "downright", "upright"]
const DOWN_DIRS := ["down", "downleft", "downright"]
const UP_DIRS := ["up", "upleft", "upright"]

var buffer: Array[String] = []
var charge_back := 0
var charge_down := 0
var grace_back := 0
var grace_down := 0

static func normalise(dir: String, facing: int) -> String:
	return MIRROR.get(dir, dir) if facing == -1 else dir

func push(raw_dir: String, facing: int) -> void:
	var d := normalise(raw_dir, facing)
	buffer.append(d)
	if buffer.size() > BUFFER_SIZE:
		buffer.pop_front()
	var r := _tick(d in BACK_DIRS, charge_back, grace_back)
	charge_back = r[0]; grace_back = r[1]
	r = _tick(d in DOWN_DIRS, charge_down, grace_down)
	charge_down = r[0]; grace_down = r[1]

func _tick(holding: bool, timer: int, grace: int) -> Array:
	if holding:
		return [timer + 1, 0]
	if timer >= MIN_CHARGE_FRAMES:
		return [0, CHARGE_RELEASE_GRACE]
	return [0, maxi(0, grace - 1)]

func _charged(timer: int, grace: int) -> bool:
	return timer >= MIN_CHARGE_FRAMES or grace > 0

func detect(motion: int, window: int = DEFAULT_WINDOW) -> bool:
	if buffer.is_empty():
		return false
	var recent3 := buffer.slice(maxi(0, buffer.size() - 3))
	match motion:
		FT.Motion.NONE:
			return true
		FT.Motion.CHARGE_BACK:
			return _charged(charge_back, grace_back) and recent3.any(func(d): return d in FORWARD_DIRS)
		FT.Motion.CHARGE_DOWN:
			return _charged(charge_down, grace_down) and recent3.any(func(d): return d in UP_DIRS)
	var history := buffer.slice(maxi(0, buffer.size() - window))
	for t in TEMPLATES.get(motion, []):
		if _matches(history, t):
			return true
	return false

## Backward greedy subsequence match; neutral frames are ignored.
func _matches(history: Array, template: Array) -> bool:
	if template.is_empty() or history.size() < template.size():
		return false
	var t := template.size() - 1
	var n := history.size()
	for i in range(n - 1, -1, -1):
		var d: String = history[i]
		if d == "neutral":
			continue
		if d == template[t]:
			if t == template.size() - 1 and n - 1 - i >= COMPLETION_WINDOW:
				return false
			t -= 1
			if t < 0:
				return true
	return false

## Called after a special fires: it can't be reused.
func consume() -> void:
	buffer.clear()
	reset_charges()

func reset_charges() -> void:
	charge_back = 0; charge_down = 0; grace_back = 0; grace_down = 0

func clear() -> void:
	buffer.clear()
	reset_charges()
