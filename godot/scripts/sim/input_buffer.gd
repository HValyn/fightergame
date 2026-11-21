## Per-fighter input history: rising edges, buffered presses and motions.
class_name InputBuffer
extends RefCounted

var history: Array[InputFrame] = []
var buffered: Array[Dictionary] = []    # {input, frame, consumed}
var frame := 0
var motion := MotionDetector.new()

func push(inp: InputFrame, facing: int) -> void:
	var prev := previous_of(inp)
	if (inp.punch and not prev.punch) or (inp.kick and not prev.kick) or (inp.special and not prev.special):
		buffered.append({"input": inp, "frame": frame, "consumed": false})
	history.append(inp)
	if history.size() > FT.INPUT_HISTORY:
		history.pop_front()
	motion.push(inp.direction(), facing)
	frame += 1
	buffered = buffered.filter(func(b): return frame - int(b["frame"]) <= FT.INPUT_BUFFER_FRAMES)

## The frame before the most recent one (or neutral).
func previous() -> InputFrame:
	return history[history.size() - 2] if history.size() >= 2 else InputFrame.new()

func current() -> InputFrame:
	return history.back() if history.size() > 0 else InputFrame.new()

## Previous frame relative to an input that is ABOUT to be pushed.
func previous_of(_inp: InputFrame) -> InputFrame:
	return history.back() if history.size() > 0 else InputFrame.new()

func fresh_press(inp: InputFrame) -> bool:
	var p := previous()
	return (inp.punch and not p.punch) or (inp.kick and not p.kick) or (inp.special and not p.special)

func fresh(button: String) -> bool:
	return current().button(button) and not previous().button(button)

func has_buffered() -> bool:
	return buffered.any(func(b): return not b["consumed"])

func consume_buffered() -> InputFrame:
	for b in buffered:
		if not b["consumed"]:
			b["consumed"] = true
			return b["input"]
	return null

func clear() -> void:
	history.clear()
	buffered.clear()
	frame = 0
	motion.clear()
