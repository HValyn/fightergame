## Minimal xUnit-style base class. Every method named test_* is run by tests/run_tests.gd.
class_name TestCase
extends RefCounted

var failures: Array[String] = []
var _current := ""

func check(cond: bool, msg := "") -> void:
	if not cond:
		failures.append("%s: %s" % [_current, msg if msg != "" else "check failed"])

func eq(a: Variant, b: Variant, msg := "") -> void:
	if a != b:
		failures.append("%s: expected %s == %s %s" % [_current, str(a), str(b), msg])

# --- helpers shared by the fighting tests -----------------------------------
func I(spec := "") -> InputFrame:
	return InputFrame.parse(spec)

func ch(id: String) -> CharacterData:
	return CharacterDB.get_character(id)

func sim(p1 := "ryokan", p2 := "ryokan", x1 := 500.0, x2 := 560.0) -> DuelSim:
	return DuelSim.new(ch(p1), ch(p2), x1, x2)


## Two fighters stepped in lock-step with scripted inputs (mirrors prototype/tests/conftest.py).
## No pushboxes, timer or rounds: use MatchSim for those.
class DuelSim:
	var f1: FighterSim
	var f2: FighterSim
	var frame := 0

	func _init(c1: CharacterData, c2: CharacterData, x1: float, x2: float) -> void:
		f1 = FighterSim.new(c1, x1, 1)
		f2 = FighterSim.new(c2, x2, 2)

	func step(i1: InputFrame = null, i2: InputFrame = null, n := 1) -> DuelSim:
		for k in n:
			f1.update(f2, frame, i1 if i1 else InputFrame.new())
			f2.update(f1, frame, i2 if i2 else InputFrame.new())
			frame += 1
		return self

	func feed(who: int, inputs: Array, other: InputFrame = null) -> DuelSim:
		for inp in inputs:
			if who == 1: step(inp, other)
			else: step(other, inp)
		return self
