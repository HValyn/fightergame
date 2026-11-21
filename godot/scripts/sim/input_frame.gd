## Buttons and directions held during ONE frame. Directions are screen-absolute.
class_name InputFrame
extends RefCounted

var left := false
var right := false
var up := false
var down := false
var punch := false
var kick := false
var special := false
var heavy := false

const FIELDS := ["left", "right", "up", "down", "punch", "kick", "special", "heavy"]

## Build from a string such as "down+right+punch" (handy in tests and the AI).
static func parse(spec: String) -> InputFrame:
	var f := InputFrame.new()
	for tok in spec.split("+", false):
		tok = tok.strip_edges()
		if tok in FIELDS:
			f.set(tok, true)
		elif tok != "" and tok != "neutral":
			push_error("InputFrame.parse: unknown token '%s'" % tok)
	return f

func copy() -> InputFrame:
	var f := InputFrame.new()
	for k in FIELDS:
		f.set(k, get(k))
	return f

func has_attack() -> bool:
	return punch or kick or special

func attack_buttons() -> Array[String]:
	var out: Array[String] = []
	if punch: out.append("punch")
	if kick: out.append("kick")
	if special: out.append("special")
	return out

func direction() -> String:
	if up and left: return "upleft"
	if up and right: return "upright"
	if down and left: return "downleft"
	if down and right: return "downright"
	if left: return "left"
	if right: return "right"
	if up: return "up"
	if down: return "down"
	return "neutral"

func button(name: String) -> bool:
	return bool(get(name))

func _to_string() -> String:
	var on: Array[String] = []
	for k in FIELDS:
		if get(k): on.append(k)
	return "+".join(on) if on.size() > 0 else "neutral"
