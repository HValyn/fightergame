"""
Google Flow -> Godot art pipeline.

Google Flow (labs.google/flow) has no public API, so generation is a manual
step in the browser; everything around it is automated:

  1. prompts   write prompts/PROMPTS.md: one copy-paste prompt per image, with
               the exact file name to save it as.
  2. (you)     generate each image in Flow, download, save into flow_raw/.
  3. process   key out the green background, crop, scale every frame to the
               character's in-game size, align the feet, and write
               godot/assets/sprites/<char>/ + manifest.json and
               godot/assets/stages/<stage>/ + manifest.json.
               Then re-imports the Godot project so exports include the art.
  4. status    what's generated / still missing (tier 1 first).

    conda run -n pygame python tools/sprite_pipeline/pipeline.py prompts
    conda run -n pygame python tools/sprite_pipeline/pipeline.py status
    conda run -n pygame python tools/sprite_pipeline/pipeline.py process [--char ryokan] [--no-import]

Raw file naming (inside tools/sprite_pipeline/flow_raw/):
    <char>/reference.png                 character sheet used as a Flow "ingredient" (not processed)
    <char>/portrait.png
    <char>/<anim>.png                    single frame
    <char>/<anim>_<n>.png                frames 1..n of a loop (idle_1.png, idle_2.png ...)
    <char>/<anim>_strip.png              all frames side by side in one image (split automatically)
    <char>/<attack>_<phase>.png          phase = startup | active | recovery  (punch_active.png,
                                         attack-ryokan_lp_high_startup.png ...)
    <char>/projectile-<move_id>[_n].png  the projectile itself
    stages/<stage_id>.png
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GODOT = ROOT / "godot"
CHAR_DATA = GODOT / "data" / "characters"
SPRITES_OUT = GODOT / "assets" / "sprites"
STAGES_OUT = GODOT / "assets" / "stages"
RAW = HERE / "flow_raw"
PROMPTS_DIR = HERE / "prompts"

SCREEN_W, SCREEN_H, GROUND_Y = 1200, 700, 550
PHASES = ("startup", "active", "recovery")
PHASE_TEXT = {
    "startup": "wind-up / anticipation frame just before the strike",
    "active": "moment of impact, limb at full extension",
    "recovery": "pulling back into guard after the strike",
}


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


# ---------------------------------------------------------------------------
# spec
# ---------------------------------------------------------------------------
@dataclass
class Anim:
    key: str                  # manifest key, e.g. "idle", "attack:ryokan_lp_high"
    file_stem: str            # raw file stem, e.g. "idle", "attack-ryokan_lp_high"
    pose: str
    tier: int = 2
    frames: int = 1
    fps: float = 10
    loop: bool = True
    height: float = 1.0       # silhouette height relative to standing
    phases: bool = False
    kind: str = "body"        # body | projectile


@dataclass
class Character:
    id: str
    name: str
    look: str
    standing_px: int          # world px from feet to top of head
    width_px: int
    anims: list[Anim] = field(default_factory=list)


def load_spec(spec_path: Path = HERE / "art_spec.toml", char_dir: Path = CHAR_DATA) -> dict:
    spec = tomllib.loads(spec_path.read_text())
    chars: list[Character] = []
    for jf in sorted(char_dir.glob("*.json")):
        d = json.loads(jf.read_text())
        look = spec.get("characters", {}).get(d["id"], {}).get("look", d.get("name", d["id"]))
        st = d.get("stats", {})
        c = Character(d["id"], d.get("name", d["id"]), look,
                      standing_px=int(st.get("height", 120)) + 2 * int(st.get("head_radius", 20)),
                      width_px=int(st.get("width", 60)))
        for key, p in spec.get("poses", {}).items():
            c.anims.append(Anim(key, key, p["pose"], p.get("tier", 2), p.get("frames", 1), p.get("fps", 10),
                                p.get("loop", True), p.get("height", 1.0), p.get("phases", False)))
        for mv in d.get("normals", []):
            c.anims.append(_move_anim(mv))
        for sp in d.get("specials", []):
            a = sp["attack"]
            c.anims.append(_move_anim(a, special=sp))
            if "projectile" in a.get("properties", []):
                c.anims.append(Anim(f"projectile:{a['id']}", f"projectile-{a['id']}",
                                    f"the {sp['name']} projectile on its own, flying toward the right, "
                                    "glowing energy, no character", 2, 3, 12, True, 1.0, False, "projectile"))
        chars.append(c)
    return {"raw": spec, "characters": chars, "stages": spec.get("stages", [])}


def _move_anim(mv: dict, special: dict | None = None) -> Anim:
    name = mv.get("name", mv["id"])
    btn = mv.get("button", "punch")
    h = mv.get("height", "mid")
    heavy = mv.get("heavy", False) or special is not None
    words = {"punch": "punch", "kick": "kick", "special": "technique"}[btn]
    if h == "low":
        desc = f"crouching low {words} aimed at the opponent's shins"
        height = 0.72
    elif h == "overhead":
        desc = f"leaping overhead downward smash with a {words}"
        height = 1.0
    elif h == "high":
        desc = f"rising upward {words}, body stretching up"
        height = 1.1
    else:
        desc = f"straight {words} to the chest"
        height = 1.0
    props = mv.get("properties", [])
    if special:
        desc = f"special move '{special['name']}': " + desc
        if "projectile" in props:
            desc = f"special move '{special['name']}': thrusting both palms forward releasing a glowing projectile"
        if "throw" in props:
            desc = f"special move '{special['name']}': grabbing and throwing the opponent"
        if mv.get("teleport_behind"):
            desc = f"special move '{special['name']}': vanishing in a burst of smoke, then striking"
        if "airborne" in props:
            desc = f"special move '{special['name']}': spinning airborne kick"
    pose = f"{name} — {'powerful ' if heavy else 'quick '}{desc}, toward the right"
    return Anim(f"attack:{mv['id']}", f"attack-{mv['id']}", pose, 2, 1, 10, False, height, True)


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------
def build_prompt(spec: dict, c: Character, a: Anim, phase: str | None = None, frame: int | None = None) -> str:
    st = spec["raw"]["style"]
    parts = [st["preamble"]]
    if a.kind == "projectile":
        parts += [a.pose, "isolated effect, centered", "flat solid pure green #00FF00 background, no text"]
        return ". ".join(parts) + "."
    parts.append(c.look)
    pose = a.pose
    if phase:
        pose += f", {PHASE_TEXT[phase]}"
    if frame is not None and a.frames > 1:
        pose += f", animation frame {frame} of {a.frames}"
    parts += [f"Pose: {pose}", st["framing"]]
    return ". ".join(parts) + "."


def expected_files(c: Character, a: Anim) -> list[tuple[str, str | None, int | None]]:
    """(file_name, phase, frame_number) for every raw image this anim wants."""
    if a.phases:
        return [(f"{a.file_stem}_{ph}.png", ph, None) for ph in PHASES]
    if a.frames == 1:
        return [(f"{a.file_stem}.png", None, None)]
    return [(f"{a.file_stem}_{i}.png", None, i) for i in range(1, a.frames + 1)]


def cmd_prompts(spec: dict, _args) -> None:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    st = spec["raw"]["style"]
    out = ["# Google Flow prompt checklist", "",
           "Generated by `tools/sprite_pipeline/pipeline.py prompts`. Do not edit; edit `art_spec.toml`.", "",
           "## How to use", "",
           "1. Open Google Flow (labs.google/flow), create an image project, pick the best image model on offer.",
           "2. **Make the character reference first** (prompt below each character). Pick the best one, save it as "
           "`flow_raw/<char>/reference.png`, and attach it as an *ingredient* / reference image for every other "
           "prompt of that character so the design stays consistent.",
           "3. Generate each pose. Choose the variant whose proportions best match the reference, download it, and "
           "save it under `tools/sprite_pipeline/flow_raw/` with the exact file name shown.",
           "4. Do tier 1 first. The game falls back gracefully: missing attacks use the generic `punch`/`kick` art, "
           "missing poses use `idle`, and a character with no art uses the procedural placeholder.",
           "5. Run `pipeline.py process`, then run the game.", "",
           "Tips: keep the green background flat (re-roll if the model adds a floor or shadow). Loops (idle, walk) "
           "can also be one image with all frames side by side, saved as `<anim>_strip.png`.", ""]
    for c in spec["characters"]:
        out += [f"## {c.name} (`{c.id}`)", "", "### Reference sheet → `flow_raw/%s/reference.png`" % c.id, "",
                "```", f"{st['preamble']}. Character design reference sheet: {c.look}. Front view and side view "
                f"facing right, full body, neutral standing pose, flat solid pure green #00FF00 background, no text.",
                "```", ""]
        por = spec["raw"].get("portrait", {}).get("pose", "head and shoulders portrait")
        out += [f"### Portrait → `flow_raw/{c.id}/portrait.png`", "", "```",
                f"{st['preamble']}. {c.look}. {por}, flat solid pure green #00FF00 background, no text.", "```", ""]
        for tier in (1, 2):
            anims = [a for a in c.anims if a.tier == tier]
            if not anims:
                continue
            out += [f"### Tier {tier}", ""]
            for a in anims:
                for fname, phase, fr in expected_files(c, a):
                    out += [f"- [ ] `flow_raw/{c.id}/{fname}`", "", "  ```",
                            "  " + build_prompt(spec, c, a, phase, fr), "  ```", ""]
    out += ["## Stages", ""]
    for s in spec["stages"]:
        out += [f"- [ ] `flow_raw/stages/{s['id']}.png` — {s['name']}", "", "  ```",
                f"  {s['look']}. {st['stage_framing']}.", "  ```", ""]
    path = PROMPTS_DIR / "PROMPTS.md"
    path.write_text("\n".join(out))
    n = sum(len(expected_files(c, a)) for c in spec["characters"] for a in c.anims)
    print(f"wrote {path.relative_to(ROOT)}  ({n} character images + {len(spec['stages'])} stages)")


# ---------------------------------------------------------------------------
# image processing
# ---------------------------------------------------------------------------
def _np():
    import numpy as np  # noqa: WPS433 (lazy: `prompts` / `status` work without numpy)
    return np


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def remove_background(img, key_hex: str = "#00FF00"):
    """RGBA with the flat background keyed out. Keeps existing transparency."""
    from PIL import Image
    np = _np()
    img = img.convert("RGBA")
    a = np.asarray(img).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3]
    if alpha.min() < 250:            # already has transparency (e.g. exported with alpha)
        return img
    # The real background colour: median of the border pixels
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    key = np.median(border, axis=0)
    if np.linalg.norm(key - np.array(_hex_rgb(key_hex))) > 160:
        print(f"    warning: border colour {key.astype(int)} is far from the requested key; keying it anyway")
    dist = np.linalg.norm(rgb - key, axis=-1)
    lo, hi = 40.0, 110.0             # <lo: background, >hi: subject, between: soft edge
    new_alpha = np.clip((dist - lo) / (hi - lo), 0, 1) * 255
    # despill: pull the key's dominant channel down where it exceeds the others
    out = rgb.copy()
    ch = int(np.argmax(key))
    others = [i for i in range(3) if i != ch]
    cap = np.max(out[..., others], axis=-1)
    edge = new_alpha < 255           # only the soft edge picks up spill; keep real greens inside
    out[..., ch] = np.where(edge, np.minimum(out[..., ch], cap), out[..., ch])
    res = np.dstack([out, new_alpha]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(res, "RGBA")


def opaque_bbox(img, threshold: int = 128, min_count: int = 2):
    """Bounding box of the subject, ignoring stray specks."""
    np = _np()
    m = np.asarray(img)[..., 3] >= threshold
    rows = np.where(m.sum(axis=1) >= min_count)[0]
    cols = np.where(m.sum(axis=0) >= min_count)[0]
    if rows.size == 0 or cols.size == 0:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def body_center_x(img) -> float:
    """Median x of opaque pixels: robust to an outstretched arm or leg."""
    np = _np()
    m = np.asarray(img)[..., 3] >= 128
    xs = np.nonzero(m)[1]
    return float(np.median(xs)) if xs.size else img.width / 2


def split_strip(img, n: int):
    """Split a horizontal strip into n frames, cutting at transparent gaps when possible."""
    np = _np()
    if n <= 1:
        return [img]
    cols = (np.asarray(img)[..., 3] >= 128).sum(axis=0)
    w = img.width
    cuts = [0]
    for k in range(1, n):
        ideal = int(w * k / n)
        lo, hi = max(cuts[-1] + 1, ideal - w // (3 * n)), min(w - 1, ideal + w // (3 * n))
        window = cols[lo:hi]
        cuts.append(lo + int(np.argmin(window)) if window.size else ideal)
    cuts.append(w)
    return [img.crop((cuts[i], 0, cuts[i + 1], img.height)) for i in range(n)]


@dataclass
class Canvas:
    """Fixed frame size for one character, feet at a fixed anchor."""
    w: int
    h: int
    feet_y: int
    target_h: int             # texture px of a standing silhouette

    @classmethod
    def for_character(cls, c: Character, ss: int) -> "Canvas":
        th = c.standing_px * ss
        h = int(th * 1.35)
        return cls(w=int(th * 1.9), h=h, feet_y=h - int(th * 0.04), target_h=th)

    @property
    def anchor(self) -> list[float]:
        return [0.5, round(self.feet_y / self.h, 4)]


def normalise_frame(img, canvas: Canvas, height_ratio: float):
    """Crop to the subject, scale so it's height_ratio * standing tall, put feet on the anchor."""
    from PIL import Image
    box = opaque_bbox(img)
    if box is None:
        raise ValueError("image is empty after background removal")
    cx = body_center_x(img) - box[0]
    sub = img.crop(box)
    scale = canvas.target_h * height_ratio / sub.height
    sub = sub.resize((max(1, round(sub.width * scale)), max(1, round(sub.height * scale))), Image.LANCZOS)
    cx *= scale
    out = Image.new("RGBA", (canvas.w, canvas.h), (0, 0, 0, 0))
    x = round(canvas.w / 2 - cx)
    y = canvas.feet_y - sub.height
    out.alpha_composite(sub, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))
    return out


def normalise_projectile(img, target_w: int):
    from PIL import Image
    box = opaque_bbox(img)
    if box is None:
        raise ValueError("empty projectile image")
    sub = img.crop(box)
    s = target_w / sub.width
    sub = sub.resize((max(1, round(sub.width * s)), max(1, round(sub.height * s))), Image.LANCZOS)
    side = max(sub.width, sub.height) + 8
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.alpha_composite(sub, ((side - sub.width) // 2, (side - sub.height) // 2))
    return out


def make_portrait(img, size: int = 256):
    from PIL import Image
    box = opaque_bbox(img)
    if box is None:
        raise ValueError("empty portrait")
    sub = img.crop(box)
    side = max(sub.width, sub.height)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(sub, ((side - sub.width) // 2, side - sub.height))
    return sq.resize((size, size), Image.LANCZOS)


def make_stage(img, floor_y: float, ss: int):
    """Cover-fit to the screen with the image's floor line on the game's ground line."""
    from PIL import Image
    img = img.convert("RGB")
    W, H, G = SCREEN_W * ss, SCREEN_H * ss, GROUND_Y * ss
    s = max(W / img.width, H / img.height)
    # the parts above AND below the image's floor must cover the screen above/below the ground line
    s = max(s, G / max(1.0, floor_y * img.height), (H - G) / max(1.0, (1 - floor_y) * img.height))
    rw, rh = round(img.width * s), round(img.height * s)
    big = img.resize((rw, rh), Image.LANCZOS)
    top = round(floor_y * rh - G)
    top = min(max(0, top), rh - H)
    left = (rw - W) // 2
    return big.crop((left, top, left + W, top + H))


# ---------------------------------------------------------------------------
# process
# ---------------------------------------------------------------------------
def _frame_files(raw_dir: Path, stem: str) -> list[Path]:
    numbered = []
    for p in raw_dir.glob(f"{stem}_*.png"):
        m = re.fullmatch(re.escape(stem) + r"_(\d+)", p.stem)
        if m:
            numbered.append((int(m.group(1)), p))
    return [p for _, p in sorted(numbered)]


def collect_raw(raw_dir: Path, a: Anim):
    """Returns {"frames": [images]} or {"startup": [...], ...} from whatever raw files exist."""
    from PIL import Image
    found: dict[str, list] = {}
    if a.phases:
        for ph in PHASES:
            files = sorted(raw_dir.glob(f"{a.file_stem}_{ph}.png")) + _frame_files(raw_dir, f"{a.file_stem}_{ph}")
            if files:
                found[ph] = [(Image.open(f), f) for f in files]
        return found
    strip = raw_dir / f"{a.file_stem}_strip.png"
    if strip.exists():
        im = Image.open(strip)
        found["frames"] = [(fr, strip) for fr in split_strip(remove_background(im), a.frames)]
        return found
    files = _frame_files(raw_dir, a.file_stem)
    single = raw_dir / f"{a.file_stem}.png"
    if not files and single.exists():
        files = [single]
    if files:
        found["frames"] = [(Image.open(f), f) for f in files]
    return found


def process_character(spec: dict, c: Character, raw_root: Path = RAW, out_root: Path = SPRITES_OUT) -> dict | None:
    raw_dir = raw_root / c.id
    if not raw_dir.is_dir():
        return None
    ss = int(spec["raw"]["style"].get("supersample", 2))
    key = spec["raw"]["style"].get("key_color", "#00FF00")
    canvas = Canvas.for_character(c, ss)
    out_dir = out_root / c.id
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    manifest = {"character": c.id, "scale": round(1 / ss, 4), "anchor": canvas.anchor,
                "frame_size": [canvas.w, canvas.h], "animations": {},
                "_generated_by": "tools/sprite_pipeline/pipeline.py process"}
    for a in c.anims:
        found = collect_raw(raw_dir, a)
        if not found:
            continue
        entry: dict = {"fps": a.fps, "loop": a.loop}
        anim_dir = out_dir / a.file_stem
        anim_dir.mkdir(exist_ok=True)
        for part, imgs in found.items():
            names = []
            for i, (im, src) in enumerate(imgs):
                try:
                    keyed = remove_background(im, key)
                    if a.kind == "projectile":
                        fr = normalise_projectile(keyed, 64 * ss)
                    else:
                        fr = normalise_frame(keyed, canvas, a.height)
                except ValueError as e:
                    print(f"    skip {src.name}: {e}")
                    continue
                name = f"{part}_{i}.png"
                fr.save(anim_dir / name, optimize=True)
                names.append(f"{a.file_stem}/{name}")
            if names:
                entry[part] = names
        if any(p in entry for p in ("frames",) + PHASES):
            manifest["animations"][a.key] = entry
    por = raw_dir / "portrait.png"
    if por.exists():
        from PIL import Image
        make_portrait(remove_background(Image.open(por), key)).save(out_dir / "portrait.png", optimize=True)
        manifest["portrait"] = "portrait.png"
    if not manifest["animations"] and "portrait" not in manifest:
        shutil.rmtree(out_dir)
        return None
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"  {c.id}: {len(manifest['animations'])} animations -> {_rel(out_dir)}")
    return manifest


def process_stages(spec: dict, raw_root: Path = RAW, out_root: Path = STAGES_OUT) -> list[str]:
    from PIL import Image
    done = []
    ss = int(spec["raw"]["style"].get("supersample", 2))
    for s in spec["stages"]:
        src = raw_root / "stages" / f"{s['id']}.png"
        if not src.exists():
            src = raw_root / "stages" / f"{s['id']}.jpg"
        if not src.exists():
            continue
        out_dir = out_root / s["id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        make_stage(Image.open(src), float(s.get("floor_y", 0.82)), ss).save(out_dir / "background.png", optimize=True)
        (out_dir / "manifest.json").write_text(json.dumps(
            {"name": s.get("name", s["id"]), "layers": [{"image": "background.png", "parallax": 0.0}]}, indent=2))
        print(f"  stage {s['id']} -> {_rel(out_dir)}")
        done.append(s["id"])
    return done


def godot_import() -> None:
    godot = shutil.which("godot") or shutil.which("godot4")
    if not godot:
        print("godot not on PATH: open the project in the editor once so the new PNGs get imported")
        return
    print("re-importing Godot project ...")
    subprocess.run([godot, "--headless", "--path", str(GODOT), "--import"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600, check=False)


def cmd_process(spec: dict, args) -> None:
    if not RAW.exists():
        sys.exit(f"no raw images yet: put Flow downloads in {RAW.relative_to(ROOT)}/ (run `prompts` for the list)")
    for c in spec["characters"]:
        if args.char and c.id != args.char:
            continue
        process_character(spec, c)
    if not args.char:
        process_stages(spec)
    if not args.no_import:
        godot_import()


def cmd_status(spec: dict, _args) -> None:
    total = have = 0
    for c in spec["characters"]:
        print(f"{c.name} ({c.id})")
        raw_dir = RAW / c.id
        for tier in (1, 2):
            missing = []
            for a in [a for a in c.anims if a.tier == tier]:
                for fname, _, _ in expected_files(c, a):
                    total += 1
                    stem = fname[:-4]
                    ok = (raw_dir / fname).exists() or (
                        not a.phases and a.frames > 1 and (raw_dir / f"{a.file_stem}_strip.png").exists())
                    have += ok
                    if not ok:
                        missing.append(stem)
            print(f"  tier {tier}: {'complete' if not missing else str(len(missing)) + ' missing: ' + ', '.join(missing[:8]) + (' ...' if len(missing) > 8 else '')}")
        print(f"  portrait: {'yes' if (raw_dir / 'portrait.png').exists() else 'missing'}"
              f"   reference: {'yes' if (raw_dir / 'reference.png').exists() else 'missing'}")
    st = [s["id"] for s in spec["stages"] if (RAW / "stages" / f"{s['id']}.png").exists()]
    print(f"stages: {len(st)}/{len(spec['stages'])} {st}")
    print(f"character images: {have}/{total}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prompts", help="write prompts/PROMPTS.md")
    sub.add_parser("status", help="show which raw images exist")
    p = sub.add_parser("process", help="raw Flow images -> Godot assets")
    p.add_argument("--char", help="only this character id")
    p.add_argument("--no-import", action="store_true", help="skip the Godot re-import")
    args = ap.parse_args(argv)
    spec = load_spec()
    {"prompts": cmd_prompts, "status": cmd_status, "process": cmd_process}[args.cmd](spec, args)


if __name__ == "__main__":
    main()
