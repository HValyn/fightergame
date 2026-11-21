## Stage backgrounds, produced by tools/sprite_pipeline.
##
## res://assets/stages/<stage_id>/manifest.json
## {"name": "Harbor Dusk", "layers": [{"image": "background.png", "parallax": 0.0}]}
## Images are 1200x700 with the floor line already aligned to FT.GROUND_Y.
## (parallax is stored for when a moving camera is added; it's unused today.)
class_name StageArt
extends RefCounted

const ROOT := "res://assets/stages"

var id := ""
var display_name := ""
var layers: Array[Texture2D] = []


static func list() -> Array[StageArt]:
	var out: Array[StageArt] = []
	if not DirAccess.dir_exists_absolute(ROOT):
		return out
	var dirs := Array(DirAccess.get_directories_at(ROOT))
	dirs.sort()
	for d in dirs:
		var path := "%s/%s/manifest.json" % [ROOT, d]
		if not FileAccess.file_exists(path):
			continue
		var m = JSON.parse_string(FileAccess.get_file_as_string(path))
		if not (m is Dictionary):
			continue
		var s := StageArt.new()
		s.id = d
		s.display_name = m.get("name", d)
		for layer in m.get("layers", []):
			var t := SpriteSet._tex("%s/%s/%s" % [ROOT, d, layer["image"]])
			if t: s.layers.append(t)
		if not s.layers.is_empty():
			out.append(s)
	return out
