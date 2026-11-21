## Loads every character JSON under res://data/characters/.
class_name CharacterDB
extends RefCounted

const DATA_DIR := "res://data/characters"

static var _cache: Dictionary = {}

static func load_all(force := false) -> Dictionary:
	if not _cache.is_empty() and not force:
		return _cache
	_cache = {}
	var dir := DirAccess.open(DATA_DIR)
	if dir == null:
		push_error("CharacterDB: cannot open %s" % DATA_DIR)
		return _cache
	var files := Array(dir.get_files())
	files.sort()
	for f in files:
		if not f.ends_with(".json"):
			continue
		var text := FileAccess.get_file_as_string(DATA_DIR + "/" + f)
		var parsed = JSON.parse_string(text)
		if typeof(parsed) != TYPE_DICTIONARY:
			push_error("CharacterDB: bad JSON in %s" % f)
			continue
		var c := CharacterData.from_dict(parsed)
		_cache[c.id] = c
	return _cache

static func get_character(id: String) -> CharacterData:
	return load_all().get(id)

static func ids() -> Array:
	var k := load_all().keys()
	k.sort()
	return k
