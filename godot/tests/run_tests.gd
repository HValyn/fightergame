## Headless test runner:  godot --headless --path godot -s res://tests/run_tests.gd [-- filter]
## Runs every test_*() method of every res://tests/test_*.gd. Exit code 1 on failure.
extends SceneTree

func _init() -> void:
	var filter := ""
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		filter = args[0]
	var files := Array(DirAccess.get_files_at("res://tests"))
	files.sort()
	var passed := 0
	var failed: Array[String] = []
	for f in files:
		if not (f.begins_with("test_") and f.ends_with(".gd")) or f == "test_case.gd":
			continue
		var script: GDScript = load("res://tests/" + f)
		if script == null or not script.can_instantiate():
			failed.append("%s: failed to load (parse error?)" % f)
			continue
		for m in script.get_script_method_list():
			var name: String = m["name"]
			if not name.begins_with("test_") or (filter != "" and not (f + "::" + name).contains(filter)):
				continue
			var t: TestCase = script.new()
			t._current = f + "::" + name
			t.call(name)
			if t.failures.is_empty():
				passed += 1
			else:
				failed.append_array(t.failures)
				printerr("FAIL ", t._current)
	for msg in failed:
		printerr("  ", msg)
	print("%d passed, %d failed" % [passed, failed.size()])
	quit(1 if failed.size() > 0 else 0)
