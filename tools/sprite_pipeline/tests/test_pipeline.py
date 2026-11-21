"""Pipeline tests on synthetic "Flow" images (figure on a green screen)."""
import json
import random
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as P  # noqa: E402


def fake_flow_image(size=(1024, 1024), fig_h=600, offset=(0, 0), arm=False, green=(4, 250, 8), seed=0):
    """A blocky 'fighter' on an imperfect green background, like a generator would give."""
    rnd = random.Random(seed)
    im = Image.new("RGB", size, green)
    px = np.asarray(im).astype(int) + np.array([[[rnd.randint(-6, 6) for _ in range(3)]]])
    im = Image.fromarray(px.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    cx = size[0] // 2 + offset[0]
    feet = size[1] - 120 + offset[1]
    head = fig_h // 6
    d.ellipse([cx - head // 2, feet - fig_h, cx + head // 2, feet - fig_h + head], fill=(230, 190, 150))
    d.rectangle([cx - fig_h // 8, feet - fig_h + head, cx + fig_h // 8, feet], fill=(40, 80, 200))
    d.rectangle([cx - fig_h // 8, feet - fig_h // 2, cx + fig_h // 8, feet - fig_h // 2 + 20], fill=(30, 160, 60))  # a real green belt
    if arm:
        d.rectangle([cx, feet - fig_h * 2 // 3, cx + fig_h // 2, feet - fig_h * 2 // 3 + 30], fill=(40, 80, 200))
    return im


@pytest.fixture
def spec():
    return P.load_spec()


def test_spec_has_every_move_as_attack_anim(spec):
    for c in spec["characters"]:
        data = json.loads((P.CHAR_DATA / f"{c.id}.json").read_text())
        keys = {a.key for a in c.anims}
        for mv in data["normals"]:
            assert f"attack:{mv['id']}" in keys
        assert "idle" in keys and "punch" in keys


def test_prompts_mention_green_screen_and_character(spec):
    c = spec["characters"][0]
    a = next(a for a in c.anims if a.key == "idle")
    p = P.build_prompt(spec, c, a, frame=1)
    assert "#00FF00" in p and c.look.split(",")[0] in p and "frame 1 of" in p


def test_background_removed_and_real_green_kept():
    out = P.remove_background(fake_flow_image())
    a = np.asarray(out)
    assert a[5, 5, 3] == 0                      # corner is transparent
    assert a[1024 - 120 - 5, 512, 3] == 255     # body is opaque
    belt = a[1024 - 120 - 300 + 10, 512]
    assert belt[3] == 255 and belt[1] > belt[0] + 50   # the green belt survived


def test_frames_normalised_to_same_canvas_height_and_feet(spec):
    c = spec["characters"][0]
    canvas = P.Canvas.for_character(c, 2)
    results = []
    for fig_h, off, arm in [(600, (0, 0), False), (380, (-150, -60), False), (500, (90, 20), True)]:
        fr = P.normalise_frame(P.remove_background(fake_flow_image(fig_h=fig_h, offset=off, arm=arm)), canvas, 1.0)
        assert fr.size == (canvas.w, canvas.h)
        box = P.opaque_bbox(fr)
        results.append(box)
        assert abs(box[3] - canvas.feet_y) <= 1                     # feet on the anchor line
        assert abs((box[3] - box[1]) - canvas.target_h) <= 2        # same standing height
    # body stays centred even with an outstretched arm
    for fr_box in results:
        body_w = canvas.target_h // 4
        assert fr_box[0] >= canvas.w / 2 - body_w


def test_strip_split_finds_gaps():
    strip = Image.new("RGBA", (900, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    for i, x in enumerate([60, 380, 700]):
        d.rectangle([x, 50, x + 120 + i * 20, 280], fill=(200, 0, 0, 255))
    frames = P.split_strip(strip, 3)
    assert len(frames) == 3
    for f in frames:
        assert P.opaque_bbox(f) is not None


def test_stage_floor_lands_on_ground_line():
    im = Image.new("RGB", (1600, 900), (90, 120, 200))
    ImageDraw.Draw(im).rectangle([0, int(900 * 0.8), 1600, 900], fill=(120, 80, 40))
    out = P.make_stage(im, 0.8, 1)
    assert out.size == (1200, 700)
    a = np.asarray(out)
    assert a[P.GROUND_Y - 4, 600, 2] > 150      # sky just above the ground line
    assert a[P.GROUND_Y + 4, 600, 2] < 80       # floor just below it


def test_process_character_end_to_end(spec, tmp_path):
    c = next(c for c in spec["characters"] if c.id == "ryokan")
    raw = tmp_path / "raw" / "ryokan"
    raw.mkdir(parents=True)
    for i in (1, 2, 3, 4):
        fake_flow_image(fig_h=560 + i * 10, seed=i).save(raw / f"idle_{i}.png")
    for ph in P.PHASES:
        fake_flow_image(arm=ph == "active").save(raw / f"punch_{ph}.png")
    fake_flow_image(fig_h=400).save(raw / "crouch.png")
    fake_flow_image().save(raw / "portrait.png")
    m = P.process_character(spec, c, tmp_path / "raw", tmp_path / "out")
    assert set(m["animations"]) == {"idle", "punch", "crouch"}
    assert len(m["animations"]["idle"]["frames"]) == 4
    assert set(m["animations"]["punch"]) >= {"startup", "active", "recovery"}
    on_disk = json.loads((tmp_path / "out" / "ryokan" / "manifest.json").read_text())
    for f in on_disk["animations"]["idle"]["frames"]:
        assert (tmp_path / "out" / "ryokan" / f).exists()
    crouch = Image.open(tmp_path / "out" / "ryokan" / on_disk["animations"]["crouch"]["frames"][0])
    box = P.opaque_bbox(crouch)
    assert abs((box[3] - box[1]) - int(c.standing_px * 2 * 0.70)) <= 2
