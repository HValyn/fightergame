## Axis-aligned box (hitbox / hurtbox / pushbox) in world pixels.
class_name Box
extends RefCounted

var x: float
var y: float
var w: float
var h: float

func _init(px: float = 0, py: float = 0, pw: float = 0, ph: float = 0) -> void:
	x = px; y = py; w = pw; h = ph

func intersects(o: Box) -> bool:
	return x < o.x + o.w and o.x < x + w and y < o.y + o.h and o.y < y + h

func to_rect() -> Rect2:
	return Rect2(x, y, w, h)
