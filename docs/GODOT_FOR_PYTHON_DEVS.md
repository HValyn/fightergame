# Godot for Python developers: a starter guide for this project

You know Python and the pygame prototype. This guide maps what you know onto Godot and this codebase,
so you can read, run and change the game without learning all of Godot first.

## 1. The 5-minute mental model

| pygame prototype | Godot version |
|---|---|
| `python main.py` | `godot --path godot`, or open the editor and press **F5** |
| `while running:` loop + `clock.tick(60)` | Godot runs the loop. It calls your `_physics_process()` 60 times a second |
| `pygame.draw.rect(screen, ...)` | `draw_rect(...)` inside a `_draw()` function (call `queue_redraw()` to repaint) |
| `pygame.key.get_pressed()` | `Input.is_action_pressed("p1_left")` (actions are named key bindings) |
| a `.py` module | a `.gd` script (GDScript) |
| `class Fighter:` | one class per file: `class_name FighterSim` at the top |
| `import fighter` | nothing to import: any `class_name` is usable everywhere in the project |
| `pytest` | `scripts/run_godot_tests.sh` (our own small runner, same idea) |
| `print()` | `print()` (output shows in the editor's *Output* panel or the terminal) |

**Node** and **scene**: Godot programs are trees of *nodes* (things in the game). A *scene* (`.tscn` file) is a
saved tree. This project keeps that part tiny on purpose: `scenes/main.tscn` is one node with the script
`scripts/view/main.gd`, and everything else is plain code. You hardly need the visual editor.

## 2. GDScript in 2 minutes (it's Python-shaped)

```gdscript
class_name Box            # this file defines the class "Box"
extends RefCounted        # base class (RefCounted = plain object, freed automatically)

const SPEED := 5.0        # constant; ":=" means "infer the type"
var x: float = 0.0        # typed variable (types are optional but this project uses them)
var hits := []            # Array (= Python list)
var stats := {"hp": 100}  # Dictionary (= dict)

func _init(px: float = 0) -> void:   # constructor (= __init__)
	x = px                           # no "self." needed (self.x also works)

func move(dx: float) -> float:
	if dx > 0 and x < 100:           # and / or / not, like Python
		x += dx
	elif dx == 0:
		pass
	for i in range(3):               # for i in 3:  also works
		hits.append(i)
	return x
```

Differences that will catch you out:
- **Tabs** for indentation (the editor handles this).
- `null` instead of `None`, `true/false` lowercase.
- Integer division: `7 / 2 == 3` when both are ints (use `7 / 2.0` for 3.5).
- `:=` needs a value whose type is known. `var a := some_dict["key"]` is an **error**; write `var a: int = some_dict["key"]`.
- String formatting: `"%s has %d hp" % [name, hp]` (like old-style Python `%`).
- Lambdas: `arr.filter(func(p): return p.alive)`.
- Docstrings are `##` comments above a thing.

The official docs are excellent: https://docs.godotengine.org/en/stable/ (search "GDScript basics").

## 3. How this project is organised

```
godot/
  project.godot            project settings (window size, main scene, 60 ticks/s). Edit via editor or text
  scenes/main.tscn         the only scene: a Node2D running scripts/view/main.gd
  data/characters/*.json   ALL move data / stats. Change balance here, no code needed
  scripts/sim/             the game rules: pure logic, like the prototype's fighter.py but cleaner
  scripts/view/            what you see and touch: menus, HUD, drawing, input
  tests/                   tests (test_*.gd, methods named test_*)
  assets/                  generated sprites and stages (from the art pipeline)
```

The important rule: **`sim/` never draws, and `view/` never changes game rules.** Same as keeping game logic
out of `renderer.py` in the prototype.

| Prototype file | Godot file |
|---|---|
| `fighter.py` | `scripts/sim/fighter_sim.gd` |
| `main.py` (round logic) | `scripts/sim/match_sim.gd` |
| `main.py` (menus, loop) | `scripts/view/main.gd` |
| `ai_controller.py` | `scripts/sim/ai_controller.gd` |
| `motion_input.py` | `scripts/sim/motion_detector.gd` |
| `move_system.py` | `scripts/sim/move_resolver.gd` |
| `input_handler.py` | `scripts/sim/input_buffer.gd` + `scripts/view/game_input.gd` |
| `character_defs.py` | `data/characters/*.json` + `scripts/sim/character_data.gd` |
| `animator.py` / `renderer.py` | `scripts/view/fighter_drawer.gd` / `sprite_set.gd` / `main.gd` |

## 4. Your first session

1. **Open the project**: run `godot`, click *Import*, choose `fightergame/godot/project.godot`. The first
   open takes a few seconds while Godot imports everything (it creates a hidden `.godot/` cache folder;
   that's normal and it's git-ignored).
2. **Run it**: press **F5** (or the ▶ button top-right). Pick a fighter and press **A** or click FIGHT.
3. **Read a script**: bottom panel *FileSystem* → `scripts/sim/fighter_sim.gd` opens in the *Script* tab.
4. **Make a balance change** (no code): edit `data/characters/ryokan.json`, e.g. the Fireball's
   `"damage"`, save, press F5 again.
5. **Make a code change**: in `scripts/view/main.gd`, find `"FIGHTERGAME"` in `_draw_select()` and change
   the title text. Press F5.
6. **Run the tests** from a terminal in the repo root: `scripts/run_godot_tests.sh`.
   Expected: `49 passed, 0 failed`.
7. **See hitboxes**: during a fight press **F1**: blue = hurtboxes, red = active hitbox, green = pushbox,
   with state names and frame advantage.

You can edit `.gd` files in VS Code as well. Install the *godot-tools* extension for highlighting.

## 5. Common tasks

**Add a new move to a character**: add an entry to `normals` (or `specials`) in the character's JSON.
`button`, `height` (`high/mid/low/overhead`), `heavy`, frame data (`startup/active/recovery`, `hitstun`,
`blockstun`), `hitbox`, `properties` (e.g. `chain_cancel`, `launcher`, `armor`, `projectile`). Then
re-run `pipeline.py prompts` so the art checklist includes it.

**Add a new character**: copy a JSON file in `data/characters/`, change `id`, `name`, stats, colours and moves.
It shows up on the select screen automatically. Add a `[characters.<id>]` look description to
`tools/sprite_pipeline/art_spec.toml` for its art.

**Write a test**: add a method `func test_something() -> void:` in any `godot/tests/test_*.gd` file.
Use `check(condition, "message")` and `eq(a, b)`. `sim()` gives you two fighters to step with inputs,
e.g. `s.feed(1, [I("down"), I("down+right"), I("right+punch")])`.

**Change controls**: `scripts/view/game_input.gd`, at the `KEYS` and `PAD_BUTTONS` tables at the top.

**Change the touch layout**: `scripts/view/touch_controls.gd`, at the `buttons` positions (screen is 1200×700).

## 6. When something goes wrong

| Symptom | Fix |
|---|---|
| `Could not find type "Something"` | You added a new `class_name` file. Run `godot --headless --path godot --import` (or open the editor once) |
| `Cannot infer the type of "x"` | Replace `var x := ...` with `var x: TypeName = ...` |
| New sprites don't show up | Run `pipeline.py process` (it re-imports), or open the editor once so it imports the PNGs |
| Red error in the *Debugger* panel while playing | Click it to jump to the line. The game keeps running so you can inspect |
| Export fails with "No export template found" | Editor → *Manage Export Templates* → *Download and Install* (one-time) |

## 7. Exporting (making the actual game files)

1. One-time: *Editor → Manage Export Templates → Download and Install*.
2. *Project → Export…* shows the presets already set up: **Android**, **Linux**, **Windows**.
3. Desktop (Steam builds): select Linux or Windows → *Export Project*. Output goes to `build/` (git-ignored).
4. Android: also install Android Studio (for the SDK) and point *Editor → Editor Settings → Export → Android*
   at the SDK. The editor's yellow warnings tell you exactly what's missing. Enable *Remote Debug →
   Deploy to Android device* to run straight on a phone connected via USB.

Steam itself (store page, Steamworks SDK, achievements) is a later step; the usual Godot route is the
**GodotSteam** add-on.
