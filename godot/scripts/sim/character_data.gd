## A complete character: stats, palette, normals and specials.
class_name CharacterData
extends RefCounted

class SpecialMove:
	var name := ""
	var motion: int = FT.Motion.NONE
	var button := "punch"
	var meter_cost := 0
	var is_super := false
	var attack: AttackData

var id := ""
var display_name := ""
var subtitle := ""
var body_style := "rectangle"

# stats
var max_health := 100
var walk_speed := 5.0
var jump_force := -18.0
var gravity := 0.8
var forward_dash_speed := 12.0
var back_dash_speed := 8.0
var dash_duration := 12
var back_dash_duration := 15
var back_dash_invincible_frames := 5
var width := 60
var height := 120
var crouch_height := 80
var head_radius := 20

var colors := {}                      # name -> Color
var has_air_dash := false
var has_double_jump := false
var armor_hits := 0

var normals: Array[AttackData] = []
var specials: Array[SpecialMove] = []

static func from_dict(d: Dictionary) -> CharacterData:
	var c := CharacterData.new()
	c.id = d["id"]
	c.display_name = d.get("name", c.id)
	c.subtitle = d.get("subtitle", "")
	c.body_style = d.get("body_style", "rectangle")
	var s: Dictionary = d.get("stats", {})
	for k in ["max_health", "dash_duration", "back_dash_duration", "back_dash_invincible_frames",
			"width", "height", "crouch_height", "head_radius"]:
		if s.has(k): c.set(k, int(s[k]))
	for k in ["walk_speed", "jump_force", "gravity", "forward_dash_speed", "back_dash_speed"]:
		if s.has(k): c.set(k, float(s[k]))
	var cols: Dictionary = d.get("colors", {})
	for k in cols:
		c.colors[k] = Color.html(cols[k])
	c.has_air_dash = d.get("has_air_dash", false)
	c.has_double_jump = d.get("has_double_jump", false)
	c.armor_hits = int(d.get("armor_hits", 0))
	for n in d.get("normals", []):
		c.normals.append(AttackData.from_dict(n))
	for sd in d.get("specials", []):
		var sp := SpecialMove.new()
		sp.name = sd.get("name", "")
		sp.motion = FT.MOTION_NAMES.get(sd.get("motion", "none"), FT.Motion.NONE)
		sp.button = sd.get("button", "punch")
		sp.meter_cost = int(sd.get("meter_cost", 0))
		sp.is_super = sd.get("is_super", false)
		sp.attack = AttackData.from_dict(sd["attack"])
		sp.attack.meter_cost = sp.meter_cost
		if sp.attack.move_type == FT.MoveType.NORMAL:
			sp.attack.move_type = FT.MoveType.SUPER if sp.is_super else FT.MoveType.SPECIAL
		c.specials.append(sp)
	return c

func color(key: String, fallback := Color.WHITE) -> Color:
	return colors.get(key, fallback)

func find_attack(move_id: String) -> AttackData:
	for a in normals:
		if a.id == move_id: return a
	for sp in specials:
		if sp.attack.id == move_id: return sp.attack
	return null

func find_special(special_name: String) -> SpecialMove:
	for sp in specials:
		if sp.name == special_name: return sp
	return null
