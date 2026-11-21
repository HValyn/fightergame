## Frame data + properties of a single move. Loaded from data/characters/*.json.
class_name AttackData
extends RefCounted

var id := ""
var name := ""
var button := "punch"           # punch / kick / special
var height: int = FT.Height.MID
var move_type: int = FT.MoveType.NORMAL
var heavy := false
var damage := 10
var chip := 1
var startup := 5
var active := 3
var recovery := 8
var hitstun := 15
var blockstun := 8
var knockback_x := 3.0
var knockback_y := 0.0           # negative = launch upward
var hitbox_w := 45
var hitbox_h := 25
var hitbox_x := 0
var hitbox_y := 0
var hitstop := 6
var cancel_window := 0
var properties: PackedStringArray = []
var projectile: Dictionary = {}  # {speed, lifetime, y_offset} when property "projectile"
var teleport_behind := false
var meter_cost := 0             # copied from the SpecialMove that owns this attack

static func from_dict(d: Dictionary) -> AttackData:
	var a := AttackData.new()
	a.id = d.get("id", "")
	a.name = d.get("name", a.id)
	a.button = d.get("button", "punch")
	a.height = FT.HEIGHT_NAMES.get(d.get("height", "mid"), FT.Height.MID)
	a.move_type = FT.MOVE_TYPE_NAMES.get(d.get("move_type", "normal"), FT.MoveType.NORMAL)
	a.heavy = d.get("heavy", false)
	a.damage = int(d.get("damage", 10))
	a.chip = int(d.get("chip", 1))
	a.startup = int(d.get("startup", 5))
	a.active = int(d.get("active", 3))
	a.recovery = int(d.get("recovery", 8))
	a.hitstun = int(d.get("hitstun", 15))
	a.blockstun = int(d.get("blockstun", 8))
	a.knockback_x = float(d.get("knockback_x", 3.0))
	a.knockback_y = float(d.get("knockback_y", 0.0))
	var hb: Dictionary = d.get("hitbox", {})
	a.hitbox_w = int(hb.get("w", 45))
	a.hitbox_h = int(hb.get("h", 25))
	a.hitbox_x = int(hb.get("x", 0))
	a.hitbox_y = int(hb.get("y", 0))
	a.hitstop = int(d.get("hitstop", 6))
	a.cancel_window = int(d.get("cancel_window", 0))
	a.properties = PackedStringArray(d.get("properties", []))
	a.projectile = d.get("projectile", {})
	a.teleport_behind = d.get("teleport_behind", false)
	return a

func has(prop: String) -> bool:
	return properties.has(prop)

func total_frames() -> int:
	return startup + active + recovery

func advantage_on_hit() -> int:
	return hitstun - recovery

func advantage_on_block() -> int:
	return blockstun - recovery

func is_special() -> bool:
	return move_type == FT.MoveType.SPECIAL or move_type == FT.MoveType.SUPER

func is_throw() -> bool:
	return has("throw")

func is_projectile() -> bool:
	return has("projectile")
