"""
One-shot exporter: prototype/character_defs.py  ->  godot/data/characters/<id>.json

After the Godot port the JSON files are the SOURCE OF TRUTH. Re-running this
overwrites them, so only do it if you intentionally changed the prototype.

    conda run -n pygame python tools/export_characters.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "prototype"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from character_defs import get_all_characters  # noqa: E402
from constants import AttackHeight, MotionType, MoveType  # noqa: E402

HEIGHT = {AttackHeight.HIGH: "high", AttackHeight.STRAIGHT: "mid",
          AttackHeight.LOW: "low", AttackHeight.OVERHEAD: "overhead"}
MOTION = {
    MotionType.NONE: "none", MotionType.QUARTER_CIRCLE_FORWARD: "qcf",
    MotionType.QUARTER_CIRCLE_BACK: "qcb", MotionType.DRAGON_PUNCH_FORWARD: "dpf",
    MotionType.DRAGON_PUNCH_BACK: "dpb", MotionType.HALF_CIRCLE_FORWARD: "hcf",
    MotionType.HALF_CIRCLE_BACK: "hcb", MotionType.CHARGE_BACK: "charge_back",
    MotionType.CHARGE_DOWN: "charge_down", MotionType.SUPER_CHARGE: "double_qcf",
    MotionType.ZIGZAG: "zigzag",
}
MOVE_TYPE = {MoveType.NORMAL: "normal", MoveType.COMMAND_NORMAL: "command_normal",
             MoveType.SPECIAL: "special", MoveType.SUPER: "super", MoveType.THROW: "throw",
             MoveType.UNIVERSAL: "normal"}

# Extra data the prototype never modelled (projectiles, teleport).
EXTRA = {
    "ryokan_fireball": {"projectile": {"speed": 7.0, "lifetime": 150, "y_offset": -70}},
    "shadow_kunai": {"projectile": {"speed": 11.0, "lifetime": 90, "y_offset": -80}},
    "shadow_teleport": {"teleport_behind": True},
}


def is_heavy(a):
    return a.base_damage >= 12 or any(p.name in ("LAUNCHER", "WALL_BOUNCE", "GROUND_BOUNCE")
                                      for p in a.properties)


def attack(a, normal=True):
    d = {
        "id": a.move_id, "name": a.name, "button": a.attack_type.value.lower(),
        "height": HEIGHT[a.height], "move_type": MOVE_TYPE[a.move_type],
        "damage": a.base_damage, "chip": a.chip_damage,
        "startup": a.startup_frames, "active": a.active_frames, "recovery": a.recovery_frames,
        "hitstun": a.hitstun_frames, "blockstun": a.blockstun_frames,
        "knockback_x": a.knockback_x, "knockback_y": a.knockback_y,
        "hitbox": {"w": a.hitbox_width, "h": a.hitbox_height,
                   "x": a.hitbox_offset_x, "y": a.hitbox_offset_y},
        "hitstop": a.hitstop, "cancel_window": a.cancel_window,
        "properties": [p.name.lower() for p in a.properties if p.name != "NONE"],
    }
    if normal:
        d["heavy"] = is_heavy(a)
    d.update(EXTRA.get(a.move_id, {}))
    return d


def rgb(c):
    return "#%02x%02x%02x" % c


def main():
    out_dir = os.path.join(ROOT, "godot", "data", "characters")
    os.makedirs(out_dir, exist_ok=True)
    for c in get_all_characters():
        s = c.stats
        data = {
            "id": c.char_id, "name": c.name, "subtitle": c.subtitle,
            "body_style": c.body_style,
            "stats": {
                "max_health": s.max_health, "walk_speed": s.walk_speed,
                "jump_force": s.jump_force, "gravity": s.gravity,
                "forward_dash_speed": s.forward_dash_speed, "back_dash_speed": s.back_dash_speed,
                "dash_duration": s.dash_duration, "back_dash_duration": s.back_dash_duration,
                "back_dash_invincible_frames": s.back_dash_invincible_frames,
                "width": s.width, "height": s.height, "crouch_height": s.crouch_height,
                "head_radius": s.head_radius,
            },
            "colors": {k: rgb(getattr(c.colors, k)) for k in
                       ("body", "body_dark", "limb", "accent", "eye", "outline")},
            "has_air_dash": c.has_air_dash, "has_double_jump": c.has_double_jump,
            "armor_hits": c.armor_hits,
            "normals": [attack(a) for a in c.attacks],
            "specials": [{
                "name": sp.name, "motion": MOTION[sp.motion], "button": sp.attack_button,
                "meter_cost": sp.meter_cost, "is_super": sp.is_super,
                "attack": attack(sp.attack_data, normal=False),
            } for sp in c.special_moves],
        }
        path = os.path.join(out_dir, f"{c.char_id}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print("wrote", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
