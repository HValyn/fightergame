"""Roster + prompt generator tests."""
import sys
from itertools import product
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rig_prompts as R  # noqa: E402


@pytest.fixture
def roster():
    return R.load_roster()


def test_one_fighter_per_province_setting_gender(roster):
    combos = [(f.province, f.setting, f.gender) for f in roster["fighters"]]
    assert sorted(combos) == sorted(product(R.PROVINCES, ("urban", "rural"), ("male", "female")))


def test_ids_unique_and_safe(roster):
    ids = [f.id for f in roster["fighters"]]
    assert len(ids) == len(set(ids))
    assert all(i.isascii() and i.isidentifier() and i.islower() for i in ids)


def test_movesets_exist_and_are_not_shared(roster):
    used = [f.moveset for f in roster["fighters"] if f.moveset]
    assert len(used) == len(set(used))
    for m in used:
        assert (R.ROOT / "godot" / "data" / "characters" / f"{m}.json").exists()


def test_prompts_carry_look_key_and_every_part(roster):
    near, far = R.part_names(roster["raw"]["skeleton"])
    for f in roster["fighters"]:
        p = R.build_prompts(roster, f)
        assert set(p) == set(R.IMAGES)
        assert f.look in p["reference"]
        assert all(f.key.upper() in text for text in p.values())
        assert "facing to the RIGHT" in p["reference"]
        assert all(part in p["parts"] for part in near + f.cloth + f.props)
        assert all(part in p["far_parts"] for part in far)


def test_markdown_lists_every_image(roster, tmp_path):
    md = R.render_markdown(roster, raw_root=tmp_path)
    for f in roster["fighters"]:
        for img in R.IMAGES:
            assert f"- [ ] `rig_raw/{f.id}/{img}.png`" in md
    (tmp_path / "bashir").mkdir()
    (tmp_path / "bashir" / "reference.png").write_bytes(b"")
    assert "- [x] `rig_raw/bashir/reference.png`" in R.render_markdown(roster, raw_root=tmp_path)
