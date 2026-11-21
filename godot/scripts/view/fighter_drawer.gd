## Procedural placeholder art (port of prototype/animator.py's three body
## styles). Used for any character without generated sprites.
class_name FighterDrawer
extends RefCounted


static func body_tint(f: FighterSim, base: Color) -> Color:
	if f.hit_flash > 0:
		return base.lerp(Color.WHITE, 0.7)
	if f.block_flash > 0:
		return base.lerp(Color("#80c0ff"), 0.6)
	if f.state == FT.State.HITSTUN or f.state == FT.State.KNOCKDOWN:
		return base.lerp(Color("#ff4040"), 0.25)
	return base


static func draw(ci: CanvasItem, f: FighterSim, tick: int, rx: float, ground_y: float = FT.GROUND_Y) -> void:
	var c := f.character
	var ry := f.pos_y
	var h := float(f.current_height)
	var dir := float(f.facing)
	var body := body_tint(f, c.color("body", Color.STEEL_BLUE))
	var limb := body_tint(f, c.color("limb", body.darkened(0.2)))
	var accent := c.color("accent", Color.SKY_BLUE)
	var outline := c.color("outline", Color.BLACK)
	var w := float(c.width)
	var hr := float(c.head_radius)

	if f.state == FT.State.KNOCKDOWN and f.is_grounded and f.knockdown_timer > 4:
		# lying on the floor
		var r := Rect2(rx - h * 0.5, ry - w * 0.45, h, w * 0.45)
		ci.draw_rect(r, body)
		ci.draw_rect(r, outline, false, 2.0)
		ci.draw_circle(Vector2(rx - h * 0.5 * dir - hr * dir, ry - hr), hr, body)
		return

	# shadow
	ci.draw_set_transform(Vector2(rx, ground_y + 2), 0, Vector2(1, 0.25))
	ci.draw_circle(Vector2.ZERO, w * 0.7, Color(0, 0, 0, 0.35))
	ci.draw_set_transform(Vector2.ZERO)

	match c.body_style:
		"slim":
			var bw := w * 0.75
			var r := Rect2(rx - bw / 2, ry - h, bw, h)
			ci.draw_rect(r, body)
			ci.draw_rect(r, outline, false, 2.0)
			# scarf trailing behind
			var sy := ry - h + 6
			var wave := sin(tick * 0.2) * 4
			ci.draw_colored_polygon(PackedVector2Array([
				Vector2(rx, sy), Vector2(rx - dir * 40, sy + 4 + wave),
				Vector2(rx - dir * 36, sy + 12 + wave), Vector2(rx, sy + 9)]), accent)
		"trapezoid":
			var top := w * 1.15
			var bottom := w * 0.8
			var poly := PackedVector2Array([
				Vector2(rx - top / 2, ry - h), Vector2(rx + top / 2, ry - h),
				Vector2(rx + bottom / 2, ry), Vector2(rx - bottom / 2, ry)])
			ci.draw_colored_polygon(poly, body)
			poly.append(poly[0])
			ci.draw_polyline(poly, outline, 2.0)
			ci.draw_rect(Rect2(rx - top / 2 + 6, ry - h + 10, top - 12, 8), accent)
		_:
			var r := Rect2(rx - w / 2, ry - h, w, h)
			ci.draw_rect(r, body)
			ci.draw_rect(r, outline, false, 2.0)
			ci.draw_rect(Rect2(rx - w / 2 + 4, ry - h + 8, w - 8, 6), accent)

	_draw_limbs(ci, f, rx, ry, h, dir, tick, limb, accent)

	# head + face
	var hy := ry - h - hr
	ci.draw_circle(Vector2(rx, hy), hr, body)
	ci.draw_arc(Vector2(rx, hy), hr, 0, TAU, 32, outline, 2.0)
	ci.draw_circle(Vector2(rx + 8 * dir, hy - 3), 5, c.color("eye", Color.WHITE))
	ci.draw_circle(Vector2(rx + 10.4 * dir, hy - 3), 2, Color.BLACK)
	ci.draw_line(Vector2(rx - 6 * dir, hy + 6), Vector2(rx + 8 * dir, hy + 6), accent, 3.0)


static func _draw_limbs(ci: CanvasItem, f: FighterSim, rx: float, ry: float, h: float,
		dir: float, tick: int, lc: Color, ac: Color) -> void:
	var arm := Vector2(rx, ry - h + 30)
	var hip_l := Vector2(rx - 8, ry - 20)
	var hip_r := Vector2(rx + 8, ry - 20)
	var S := FT.State
	if f.in_attack and f.current_attack:
		var a := f.current_attack
		var big := 1.0 if a.heavy or a.is_special() else 0.0
		var active := f.state == S.ATTACK_ACTIVE
		if a.button != "kick":
			if active:
				var reach := 35 + 10 * big
				var lift := -20.0 if a.height == FT.Height.HIGH or a.height == FT.Height.OVERHEAD else -5.0
				if a.height == FT.Height.LOW: lift = 25.0
				var fist := arm + Vector2(reach * dir, lift)
				ci.draw_line(arm, fist, lc, 8.0)
				ci.draw_circle(fist, 11, lc)
				ci.draw_circle(fist, 7, ac)
			elif f.state == S.ATTACK_STARTUP:
				ci.draw_line(arm, arm + Vector2(-18 * dir, 20), lc, 7.0)
				ci.draw_circle(arm + Vector2(-18 * dir, 20), 10, lc)
			else:
				ci.draw_line(arm, arm + Vector2(-10 * dir, 10), lc, 6.0)
			_legs(ci, hip_l, hip_r, ry, lc, 0.0)
		else:
			ci.draw_line(arm, arm + Vector2(-12 * dir, 15), lc, 6.0)
			var hip := Vector2(rx, ry - 20)
			if active:
				var reach := 50 + 15 * big
				var ky := -20.0 if a.height == FT.Height.HIGH else (15.0 if a.height == FT.Height.LOW else 5.0)
				var foot := hip + Vector2(reach * dir, ky)
				ci.draw_line(hip, foot, lc, 8.0)
				var fw := 18.0 if big > 0 else 14.0
				ci.draw_rect(Rect2(foot.x - fw / 2, foot.y - 8, fw, 16), lc)
				ci.draw_rect(Rect2(foot.x - fw / 2 + 2, foot.y - 6, fw - 4, 12), ac)
			elif f.state == S.ATTACK_STARTUP:
				ci.draw_line(hip, hip + Vector2(0, -25), lc, 8.0)
				ci.draw_circle(hip + Vector2(0, -25), 10, lc)
			else:
				ci.draw_line(hip, Vector2(rx - 10, ry), lc, 7.0)
			ci.draw_line(Vector2(rx + 6, ry - 20), Vector2(rx + 12, ry), lc, 7.0)
	elif f.is_crouching:
		ci.draw_line(arm + Vector2(0, -10), arm + Vector2(-20 * dir, 0), lc, 6.0)
		ci.draw_line(Vector2(rx - 8, ry - 15), Vector2(rx - 22, ry - 25), lc, 7.0)
		ci.draw_line(Vector2(rx + 8, ry - 15), Vector2(rx + 22, ry - 25), lc, 7.0)
	elif f.state == S.KNOCKDOWN or f.state == S.HITSTUN:
		ci.draw_line(arm, arm + Vector2(20 * dir * -1, -15), lc, 6.0)
		_legs(ci, hip_l, hip_r, ry, lc, 6.0)
	elif f.state == S.JUMP:
		ci.draw_line(arm, arm + Vector2(10 * dir, -18), lc, 6.0)
		ci.draw_line(hip_l, hip_l + Vector2(-10, 12), lc, 7.0)
		ci.draw_line(hip_r, hip_r + Vector2(12, 8), lc, 7.0)
	else:
		var guard := f.is_blocking or f.state == S.BLOCKSTUN
		if guard:
			ci.draw_line(arm, arm + Vector2(14 * dir, -14), lc, 7.0)
			ci.draw_circle(arm + Vector2(14 * dir, -14), 9, lc)
		else:
			var swing := sin(tick * 0.15) * 4
			ci.draw_line(arm, arm + Vector2(-18 * dir, 20 + swing), lc, 6.0)
		var walk := sin(f.state_timer * 0.3) * 8 if f.state == S.WALK_FORWARD or f.state == S.WALK_BACKWARD else 0.0
		_legs(ci, hip_l, hip_r, ry, lc, walk)


static func _legs(ci: CanvasItem, hip_l: Vector2, hip_r: Vector2, ry: float, lc: Color, off: float) -> void:
	ci.draw_line(hip_l, Vector2(hip_l.x - 4 + off, ry), lc, 7.0)
	ci.draw_line(hip_r, Vector2(hip_r.x + 4 - off, ry), lc, 7.0)
