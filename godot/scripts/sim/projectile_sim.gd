## A fireball / kunai. Owned by a fighter; hits the other one once.
class_name ProjectileSim
extends RefCounted

const W := 40
const H := 30

var owner: FighterSim
var attack: AttackData
var pos_x := 0.0
var pos_y := 0.0
var vel_x := 0.0
var lifetime := 0
var age := 0
var alive := true

static func spawn(f: FighterSim, a: AttackData) -> ProjectileSim:
	var p := ProjectileSim.new()
	p.owner = f
	p.attack = a
	var spec: Dictionary = a.projectile
	p.vel_x = float(spec.get("speed", 7.0)) * f.facing
	p.lifetime = int(spec.get("lifetime", 120))
	p.pos_x = f.pos_x + f.facing * (f.character.width / 2.0 + W / 2.0)
	p.pos_y = f.pos_y + float(spec.get("y_offset", -70))
	return p

func box() -> Box:
	return Box.new(pos_x - W / 2.0, pos_y - H / 2.0, W, H)

## Move, then try to hit `target`. Returns the contact result dictionary or {}.
func step(target: FighterSim) -> Dictionary:
	if not alive:
		return {}
	age += 1
	pos_x += vel_x
	if age >= lifetime or pos_x < -W or pos_x > FT.SCREEN_W + W:
		alive = false
		return {}
	var b := box()
	for hb in target.hurtboxes:
		if b.intersects(hb):
			var r := target.receive_attack(attack, pos_x, owner.facing if vel_x == 0 else int(signf(vel_x)), 1.0)
			if r["result"] != FT.HitResult.WHIFF:
				alive = false
				owner.on_projectile_contact(target, attack, r)
			return r
	return {}
