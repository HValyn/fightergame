# Rig plan (version 4: Skeleton2D cutout animation)

Working plan for the `version4-godot-animation` branch. A Claude Code session should be able to pick this up
and implement it step by step. Do the steps in order; each ends with something testable.

## Decisions so far

- **Cutout animation, not frame-by-frame sprites.** One painted character per fighter, cut into parts, posed by a
  skeleton in Godot. Roster and prompts: `tools/rig_art/roster.toml`, `tools/rig_art/rig_prompts.py`.
- **Three generated images per fighter:** `reference` (approved look, assembly guide, never cut), `parts`
  (what actually gets cut), `portrait` (select screen). All in `tools/rig_art/rig_raw/<id>/`, git-ignored,
  `.png` or `.jpg`.
- **The parts sheet is the source of the game art, not the reference.** All parts come from one generation, so they
  match each other in scale and colour. The reference often comes out three-quarter view and mid-stride, with
  limbs crossing, so it can't be cut cleanly.
- **Far-side limbs are darkened copies of the near ones.** No far-parts image. (A test generation put a faint
  ghost of the whole body behind the far parts, which welded them into one blob.)
- **Part order on the sheet is random, so labelling is a manual step**: the cutter numbers the pieces, the user
  writes which number is which part. ~30 seconds per fighter, no guessing.
- **Joint pivots are clicked by hand**, ~20 clicks per fighter. Pose estimators are unreliable on stylised art
  and there are only 16 fighters.
- **The sim is untouched.** The rig is a view: every frame it reads `FighterSim` and poses itself. Never let an
  `AnimationPlayer` run on its own clock. Hitstop freezes the rig for free because `state_timer` stops.

## Evidence: Hamza test images (2026-11-22)

Keying the magenta and labelling connected regions (> 2000 px) on Hamza's parts sheet gave exactly
**11 clean pieces**: head (with collar), chest (with shoulder cap), kameez hem, upper arm (with elbow cap),
forearm (red wrap), hand, pelvis (with hip caps), thigh, shin, shoe, charkhi. The model drew round joint caps
by itself. The far-parts sheet gave 5 blobs, one of them the ghost body fused with the far arm and thigh: unusable.
Detected key colour: about `(253, 10, 251)`; the sheets were 1438×2576 JPEGs.

## Data layout

```
tools/rig_art/rig_raw/<id>/{reference,parts,portrait}.(png|jpg)   generated, git-ignored
tools/rig_art/rigs/<id>/labels.toml       hand-written: piece number -> part name           (committed)
tools/rig_art/rigs/<id>/pivots.json       clicked joint points per part, part-local px      (committed)
tools/rig_art/rigs/<id>/_preview.png      numbered piece preview for labelling              (git-ignored)
godot/assets/rigs/<id>/parts/<part>.png   cut, keyed, trimmed parts at game scale           (committed)
godot/assets/rigs/<id>/portrait.png
godot/assets/rigs/<id>/rig.json           bones, rest offsets, lengths, draw order, moveset (committed)
godot/data/poses/*.json                   pose library (bone angles), shared across fighters (committed)
```

Part names come from `[skeleton]` in `roster.toml` (`head chest pelvis upper_arm forearm hand thigh shin foot`;
the limbs exist as `near_*` and `far_*` bones) plus each fighter's `cloth` and `props` lists.

## Steps

### 1. `tools/rig_art/cut.py <id>`
- Load `rig_raw/<id>/parts.*`. Key the background: median border colour as the key (like `remove_background`
  in `tools/sprite_pipeline/pipeline.py`, reuse it or move it to a shared module), soft alpha edge, despill edges only.
- Connected components on alpha ≥ 128 after a small morphological opening; drop pieces under ~0.2% of the image.
- Warn when one piece is far larger than the rest (the ghost-body failure) or when the piece count differs from
  the expected part count by more than 2.
- Save each piece trimmed to its bbox with padding to `rigs/<id>/_pieces/<n>.png`, plus `_preview.png` (sheet with
  big numbers on each piece).
- If `labels.toml` doesn't exist, write a template: every expected part name with an empty number, for example
  `head = 0`. Validate an existing one: every number exists, no number used twice, required parts present.
- Tests on synthetic sheets: N separated shapes → N pieces; a translucent full-body ghost → warning; JPEG noise
  on the key doesn't create extra pieces.

### 2. `tools/rig_art/pivots.py <id>`
- matplotlib window (`plt.ginput`), one labelled piece at a time, with instructions in the title:

  | part | points to click, in order |
  |---|---|
  | pelvis (root) | waist (where the chest sits), hip (where the thigh hangs) |
  | chest | waist, neck base, shoulder |
  | head | neck base |
  | upper_arm | shoulder, elbow |
  | forearm | elbow, wrist |
  | hand | wrist |
  | thigh | hip, knee |
  | shin | knee, ankle |
  | foot | ankle |
  | each cloth / prop | attach point, then type the parent part (default: pelvis for hems, chest for shawls) |

- Save `pivots.json` (part-local pixel coordinates). Re-running edits only the parts named with `--part`.
- Pure functions for the maths so they're testable without a window.

### 3. `tools/rig_art/build_rig.py <id>`
- From pieces + labels + pivots: bone lengths = distance between a part's first and last pivot; rest pose =
  standing upright, bones pointing down the body (head up).
- Scale all parts uniformly so the assembled standing height = `stats.height` of the moveset's character JSON
  × supersample (2, as in the sprite pipeline). One scale for the whole fighter; never per part.
- Write parts PNGs, `portrait.png` (cropped like `make_portrait`) and `rig.json` to `godot/assets/rigs/<id>/`:
  bone tree, each sprite's offset so its first pivot sits on the bone origin, z order
  (far limbs < pelvis < chest < near limbs < head; cloth and props per entry), `far_tint` (default 0.7 brightness),
  `moveset` (from roster).
- Also render `_assembled.png` of the rest pose next to the reference image, so the user can check proportions
  at a glance. Add a `rig_prompts.py status` column for cut / labelled / pivoted / built.
- Re-import Godot afterwards (`godot --headless --path godot --import`), like the sprite pipeline does.

### 4. Godot: `FighterRig` (`godot/scripts/view/fighter_rig.gd`)
- Built at runtime from `rig.json`: `Skeleton2D` → `Bone2D` chain → `Sprite2D` per part. No hand-made `.tscn`, so
  all 16 fighters work the same way. Use Skeleton2D/Bone2D (not plain Node2D) so cloth can later become
  `Polygon2D` meshes weighted to bones. Turn off Bone2D auto length/angle and set them from `rig.json`.
  Explain the Godot bits in `docs/GODOT_FOR_PYTHON_DEVS.md` (the user is new to Godot).
- `update(f: FighterSim)` each frame: choose a pose from `f.state`, `f.state_timer` and the current move, apply
  bone angles, flip with `scale.x` by facing. Read-only on sim state.
- Fallback order in the view: rig (if `godot/assets/rigs/<id>/rig.json` exists for the character's moveset)
  → sprites (`SpriteSet`) → procedural placeholder.
- Until real art exists, `build_rig.py --placeholder <moveset>` writes a rig made of flat coloured rectangles in
  the character JSON's `colors`, so the rig and poses can be built and tuned with no art at all.

### 5. Poses (`godot/data/poses/`)
- A pose = bone name → angle in degrees, plus optional root offset and per-part z swaps.
- Loops (idle, walk, walk back, crouch, jump, block, hit, knockdown, dash, victory) = list of key poses with frame
  counts, sampled by `state_timer`.
- Attacks = per move id `{startup, active, recovery}` poses. Timing comes from the move's frame data in
  `godot/data/characters/*.json`: ease from guard into `startup` over the startup frames, **snap** to `active`
  (impact frames should hold, not tween), ease back to guard over recovery. Changing frame data retimes the
  animation automatically.
- One shared library; a fighter may override single poses. Moves without a pose use the generic punch/kick pose
  for their button and height (same fallback idea as the sprite pipeline).
- Check alignment with **F1**: the active pose's limb should sit inside the hitbox.

### 6. First fighters
Hamza (moveset `shadow`), then Bashir (`titan`) and Ali (`ryokan`). Hamza's three images exist: put them in
`tools/rig_art/rig_raw/hamza/` as `reference.jpg`, `parts.jpg`, `portrait.jpg`.

### 7. Later
- Loose cloth: kameez hem first (Hamza has it as its own piece). Start as a rigid part on the pelvis with a small
  view-side spring on its angle; move to `Polygon2D` + bone weights for the `hard` fighters (ghagra, wide shalwar,
  chadar, turban tails). Keep any cloth physics view-only and outside `scripts/sim/`.
- Proper character JSONs for the roster ids (`hamza.json` etc.) instead of borrowing movesets.

## Backlog from the version 3 review (sprite pipeline; lower priority now)
- `pipeline.py` scales every frame separately, strip frames included, which erases motion like the idle bob. Use one
  scale per animation.
- The sprite pipeline's `#00FF00` key eats bright green clothing. The rig route already picks the key per fighter.
