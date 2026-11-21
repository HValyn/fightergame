## Sprite frames for one character, produced by tools/sprite_pipeline.
##
## res://assets/sprites/<char_id>/manifest.json
## {
##   "character": "ryokan",
##   "scale": 0.5,                 # texture px -> world px
##   "anchor": [0.5, 1.0],         # feet point, as a fraction of the frame size
##   "animations": {
##     "idle":   {"frames": ["idle/0.png", "idle/1.png"], "fps": 8, "loop": true},
##     "attack:ryokan_lp_high": {"startup": [..], "active": [..], "recovery": [..]},
##     "projectile": {"frames": [..], "fps": 12, "loop": true}
##   },
##   "portrait": "portrait.png"
## }
## Frames face RIGHT; the view mirrors them for left-facing fighters.
## Any animation may be missing: pick() falls back down a chain and finally
## returns null, in which case the view draws the procedural placeholder.
class_name SpriteSet
extends RefCounted

const ROOT := "res://assets/sprites"

static var _cache: Dictionary = {}

var char_id := ""
var scale := 1.0
var anchor := Vector2(0.5, 1.0)
var anims: Dictionary = {}           # key -> {frames|startup|active|recovery: [Texture2D], fps, loop}
var portrait: Texture2D = null


static func for_character(id: String) -> SpriteSet:
	if _cache.has(id):
		return _cache[id]
	var s: SpriteSet = null
	var path := "%s/%s/manifest.json" % [ROOT, id]
	if FileAccess.file_exists(path):
		var d = JSON.parse_string(FileAccess.get_file_as_string(path))
		if d is Dictionary:
			s = SpriteSet.new()
			s._load(id, d)
			if s.anims.is_empty() and s.portrait == null:
				s = null
	_cache[id] = s
	return s


static func clear_cache() -> void:
	_cache.clear()


func _load(id: String, d: Dictionary) -> void:
	char_id = id
	scale = float(d.get("scale", 1.0))
	var a: Array = d.get("anchor", [0.5, 1.0])
	anchor = Vector2(a[0], a[1])
	var base := "%s/%s/" % [ROOT, id]
	for key in d.get("animations", {}):
		var spec: Dictionary = d["animations"][key]
		var anim := {"fps": float(spec.get("fps", 10)), "loop": bool(spec.get("loop", true))}
		var ok := false
		for part in ["frames", "startup", "active", "recovery"]:
			if spec.has(part):
				var texs: Array[Texture2D] = []
				for f in spec[part]:
					var t := _tex(base + str(f))
					if t: texs.append(t)
				if not texs.is_empty():
					anim[part] = texs
					ok = true
		if ok:
			anims[key] = anim
	if d.has("portrait"):
		portrait = _tex(base + str(d["portrait"]))


static func _tex(path: String) -> Texture2D:
	if ResourceLoader.exists(path):
		return load(path) as Texture2D
	# Not imported yet (e.g. pipeline just ran and the editor wasn't opened):
	# fall back to loading the PNG directly. Only works for un-exported runs.
	if FileAccess.file_exists(path):
		var img := Image.load_from_file(ProjectSettings.globalize_path(path))
		if img:
			return ImageTexture.create_from_image(img)
	return null


func _first(keys: Array) -> Dictionary:
	for k in keys:
		if anims.has(k):
			return anims[k]
	return {}


## Texture to draw for this fighter right now, or null.
func pick(f: FighterSim, tick: int) -> Texture2D:
	var S := FT.State
	if f.in_attack and f.current_attack:
		var a := f.current_attack
		var h: String = ["high", "mid", "low", "overhead"][a.height]
		var anim := _first(["attack:" + a.id, "%s_%s" % [a.button, h], a.button, "punch"])
		if not anim.is_empty():
			return _attack_frame(anim, f)
	var keys: Array
	match f.state:
		S.WALK_FORWARD: keys = ["walk_forward", "walk"]
		S.WALK_BACKWARD: keys = ["walk_backward", "walk"]
		S.JUMP: keys = ["jump"]
		S.CROUCH: keys = ["block_crouch", "crouch"] if f.is_blocking else ["crouch"]
		S.BLOCKSTUN: keys = ["block_crouch", "crouch"] if f.block_crouching else ["block_stand", "idle"]
		S.HITSTUN: keys = ["hit", "idle"]
		S.KNOCKDOWN: keys = ["knockdown", "hit", "idle"]
		S.DASH_FORWARD: keys = ["dash_forward", "walk_forward", "walk"]
		S.DASH_BACKWARD: keys = ["dash_backward", "walk_backward", "walk"]
		_: keys = []
	keys.append("idle")
	return _loop_frame(_first(keys), f.state_timer if f.state != S.IDLE else tick)


func pick_named(key: String, tick: int) -> Texture2D:
	return _loop_frame(_first([key, "idle"]), tick)


func _loop_frame(anim: Dictionary, t: int) -> Texture2D:
	if anim.is_empty() or not anim.has("frames"):
		return null
	var frames: Array = anim["frames"]
	var i := int(t * anim["fps"] / FT.FPS)
	i = i % frames.size() if anim["loop"] else mini(i, frames.size() - 1)
	return frames[i]


## Attacks are timed by frame data, not fps: startup frames play during
## startup, active during active, recovery during recovery.
func _attack_frame(anim: Dictionary, f: FighterSim) -> Texture2D:
	var a := f.current_attack
	var phase := "startup"
	var into := f.attack_frame
	var length := a.startup
	if f.state == FT.State.ATTACK_ACTIVE:
		phase = "active"; into -= a.startup; length = a.active
	elif f.state == FT.State.ATTACK_RECOVERY:
		phase = "recovery"; into -= a.startup + a.active; length = a.recovery
	if anim.has(phase):
		var fr: Array = anim[phase]
		return fr[clampi(int(float(into) / maxi(1, length) * fr.size()), 0, fr.size() - 1)]
	if anim.has("frames"):
		var fr: Array = anim["frames"]
		var t := float(f.attack_frame) / maxi(1, a.total_frames())
		return fr[clampi(int(t * fr.size()), 0, fr.size() - 1)]
	return null
