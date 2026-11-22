# Notes for Claude sessions

Read `README.md` first for layout, commands and controls. The user knows Python well but is new to Godot: explain Godot-specific steps, and keep `docs/GODOT_FOR_PYTHON_DEVS.md` current when workflows change. This file holds the things that aren't obvious from the code.

## Environment
- Python: conda env **`pygame`** (`conda run -n pygame ...`). It has pygame, pytest, Pillow, numpy.
  `conda run` does **not** forward stdin, so write scripts to files instead of piping heredocs to it.
- Godot **4.7.2** binary is `godot` (~/.local/bin). Export templates are **not** installed yet.
- A display is available (X/Wayland), so real screenshots work:
  `godot --path godot -- --autoplay --seed=4 --screenshot=/abs/path.png --shot-frame=300`
  (`--mode=0` = VS CPU with the touch UI if `--touch`; headless runs can't screenshot).
- After adding a new `class_name` script or new PNGs, run `godot --headless --path godot --import`
  or the test runner fails with "Could not find type".
- GDScript is strictly typed here: `:=` on an untyped value (Dictionary/Array element, untyped loop var) is a
  parse error. Use `var x: T = ...` or typed loops `for p: int in [...]`.

## Architecture rules
- `godot/scripts/sim/` is pure logic: no Nodes, no rendering, no wall clock, no global RNG.
  `MatchSim.step()` = one 60 Hz frame. AI uses its own seeded `RandomNumberGenerator`.
  Determinism is tested (CPU vs CPU twice → identical result). Keep it that way. It's what makes replays,
  rollback netcode and the tests possible.
- `godot/scripts/view/` only reads sim state; effects come from `FighterSim.events` (cleared every update).
- `godot/data/characters/*.json` is the **source of truth** for moves/frame data. `tools/export_characters.py`
  would overwrite them from the prototype, so only run it deliberately.
- Directions in `InputFrame` are screen-absolute; `MotionDetector` normalises them by facing (templates are
  written for a right-facing fighter).

## Gameplay decisions (made while fixing the prototype; tests encode them)
- Guard = hold away from the attacker **by position** (cross-ups work). Plain down does not guard.
  Lows need a crouch guard, overheads a standing guard. Throws are unblockable and beat armor.
- Specials need a fresh button press; the motion must finish within 8 frames of the press and is consumed after use.
- Cancels need a fresh/buffered press inside the cancel window, only after the attack connected.
- Hitstop freezes both fighters; knockback applies after it.
- Godot-only additions (the prototype declared these properties but ignored them): projectiles (one per player,
  opposing ones cancel), `invincible_startup`, `invincible_all`, `low_profile` (evades HIGH), `armor`
  (`armor_hits` per move, takes damage but no stun), `teleport_behind`, `airborne` hop, back-dash invincibility.
- Not simulated yet: `wall_bounce`, `ground_bounce`, `chip_kills` exists, supers exist in code but no move costs meter.

## Art pipeline
- `tools/sprite_pipeline/pipeline.py` + `art_spec.toml`. Manifest format is documented at the top of
  `godot/scripts/view/sprite_set.gd`; the pipeline and that file must agree.
- Raw Flow images go in `tools/sprite_pipeline/flow_raw/` (git-ignored). `prompts/PROMPTS.md` is generated, so edit the spec instead.
- Sprite frames face right, feet at `anchor`, drawn at `scale` (0.5 = 2x supersampled).

## Rig art (version 4)
- **Start with `docs/RIG_PLAN.md`**: decisions, data layout, and the ordered implementation steps.
- `tools/rig_art/roster.toml` is the source of truth for the 16-fighter roster (province × urban/rural × male/female)
  and for the shared skeleton's part names. `prompts/RIG_PROMPTS.md` is generated from it; edit the roster.
- Plan for the rig: one shared bone naming for all fighters; the view poses bones from sim state each frame
  (never let AnimationPlayer run on its own clock); attack poses are data keyed to startup/active/recovery so
  frame-data changes retime the animation. `scripts/sim/` stays untouched.
- The parts sheet is what gets cut; the reference image is never cut. Piece order on the sheet is random, so
  labelling (piece number → part) is a hand-written file per fighter. Far limbs = darkened near limbs.
- Loose garments (kameez hems, shalwar, ghagra, chadar, turban tails) need Polygon2D + bone weights or jiggle bones.

## History
- 2026-11-21: prototype bugs fixed (commit 60ac7f4). Same day, Godot port, view, tests, pipeline and docs
  written on branch `version3-godot`. The session froze once mid-port; `fighter_sim.gd` was empty afterwards and was rewritten.
