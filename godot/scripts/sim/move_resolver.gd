## Turns an input frame into the move a character performs.
## Priority: supers > specials > normals.
##   forward + heavy + button -> overhead
##   down + button            -> low
##   up + button              -> high (if the character has one; otherwise jump)
class_name MoveResolver
extends RefCounted

var character: CharacterData
var _normals := {}    # "button|height|heavy" -> AttackData

func _init(c: CharacterData) -> void:
	character = c
	for a in c.normals:
		var key := _key(a.button, a.height, a.heavy)
		if not _normals.has(key):
			_normals[key] = a

static func _key(button: String, height: int, heavy: bool) -> String:
	return "%s|%d|%s" % [button, height, heavy]

## ctx: {facing_right, grounded, meter, projectile_active}
func resolve(inp: InputFrame, motion: MotionDetector, ctx: Dictionary) -> AttackData:
	if not inp.has_attack():
		return null
	var meter: int = ctx.get("meter", 0)
	var projectile_active: bool = ctx.get("projectile_active", false)
	var grounded: bool = ctx.get("grounded", true)

	# Supers first, then specials (both on the ground only)
	if grounded:
		for pass_supers in [true, false]:
			for sp in character.specials:
				if sp.is_super != pass_supers:
					continue
				if sp.meter_cost > meter:
					continue
				if sp.attack.is_projectile() and projectile_active:
					continue
				if inp.button(sp.button) and motion.detect(sp.motion):
					return sp.attack

	var facing_right: bool = ctx.get("facing_right", true)
	var forward := (inp.right and facing_right) or (inp.left and not facing_right)
	for btn in inp.attack_buttons():
		if btn == "special":
			continue
		if not grounded:
			var air := _lookup(btn, FT.Height.MID, inp.heavy)
			if air: return air
			continue
		if forward and inp.heavy and not inp.down:
			var oh: AttackData = _normals.get(_key(btn, FT.Height.OVERHEAD, true))
			if oh: return oh
		var h := FT.Height.MID
		if inp.down: h = FT.Height.LOW
		elif inp.up: h = FT.Height.HIGH
		var a := _lookup(btn, h, inp.heavy)
		if a: return a
	return null

func _lookup(btn: String, h: int, heavy: bool) -> AttackData:
	var a: AttackData = _normals.get(_key(btn, h, heavy))
	if a == null and heavy:
		a = _normals.get(_key(btn, h, false))
	return a
