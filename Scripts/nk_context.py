"""Generic surrounding city context (Arabkir character): 4-5 storey tuff / plaster blocks with
gable roofs, private houses, sheds and a few newer towers. Procedural and schematic -
it gives aerials a believable setting; it is NOT a survey of the real neighbours.
"""
import math
import numpy as np
import bpy
from nk_geo import MeshBuilder
from nk_mats import NT, srgb, _principled, _uv, _noise, _ramp, _mix_col

WALLS = ['#C9A488', '#D6C0A2', '#BFB3A3', '#D9D2C4', '#B98D72', '#CFC7BA']
ROOFS = ['#6E6A66', '#7C4E3E', '#8A8A86', '#5E5A57']


def mat_context_wall(name, color, win=(3.2, 3.0), frac=(0.42, 0.5)):
    """Plaster/tuff wall with a procedural window grid driven by UV (metres)."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    uv = _uv(nt)
    sep = nt.n('ShaderNodeSeparateXYZ', -1000, 0)
    nt.link(uv, sep.inputs['Vector'])

    def grid(sock, period, width, offset, x, y):
        d = nt.n('ShaderNodeMath', x, y, operation='DIVIDE')
        d.inputs[1].default_value = period
        nt.link(sock, d.inputs[0])
        a = nt.n('ShaderNodeMath', x + 150, y, operation='ADD')
        a.inputs[1].default_value = offset
        nt.link(d.outputs[0], a.inputs[0])
        f = nt.n('ShaderNodeMath', x + 300, y, operation='FRACT')
        nt.link(a.outputs[0], f.inputs[0])
        s = nt.n('ShaderNodeMath', x + 450, y, operation='SUBTRACT')
        s.inputs[1].default_value = 0.5
        nt.link(f.outputs[0], s.inputs[0])
        ab = nt.n('ShaderNodeMath', x + 600, y, operation='ABSOLUTE')
        nt.link(s.outputs[0], ab.inputs[0])
        lt = nt.n('ShaderNodeMath', x + 750, y, operation='LESS_THAN')
        lt.inputs[1].default_value = width / 2
        nt.link(ab.outputs[0], lt.inputs[0])
        return lt.outputs[0]

    gx = grid(sep.outputs['X'], win[0], frac[0], 0.0, -900, 250)
    gy = grid(sep.outputs['Y'], win[1], frac[1], -0.15, -900, -50)
    m = nt.n('ShaderNodeMath', -50, 100, operation='MULTIPLY')
    nt.link(gx, m.inputs[0])
    nt.link(gy, m.inputs[1])
    no = _noise(nt, uv, 0.2, 3.0, 0.5, -700, -350)
    f = _ramp(nt, no.outputs['Fac'], [(0.3, 0.86), (0.7, 1.08)], -450, -350)
    wall = _mix_col(nt, 1.0, srgb(color), f, -200, -300, 'MULTIPLY')
    col = _mix_col(nt, m.outputs[0], wall, srgb('#23262A'), 150, 100)
    p, out = _principled(nt, Roughness=0.8)
    nt.link(col, p.inputs['Base Color'])
    r = _mix_col(nt, m.outputs[0], (0.85, 0.85, 0.85, 1), (0.08, 0.08, 0.08, 1), 150, -150)
    nt.link(r, p.inputs['Roughness'])
    return mat


def _box(mb, x0, x1, y0, y1, z0, z1, mat, rot, cx, cy):
    c, s = math.cos(rot), math.sin(rot)

    def T(x, y, z):
        return (cx + x * c - y * s, cy + x * s + y * c, z)
    V = [T(x0, y0, z0), T(x1, y0, z0), T(x1, y1, z0), T(x0, y1, z0),
         T(x0, y0, z1), T(x1, y0, z1), T(x1, y1, z1), T(x0, y1, z1)]
    for f in ((4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        mb.add([V[i] for i in f], [(0, 1, 2, 3)], mat)


def _gable(mb, hx, hy, z0, rise, mat, wall_mat, rot, cx, cy, over=0.4):
    """Gable roof along local x over a footprint [-hx,hx] x [-hy,hy]."""
    c, s = math.cos(rot), math.sin(rot)

    def T(x, y, z):
        return (cx + x * c - y * s, cy + x * s + y * c, z)
    ex, ey = hx + over, hy + over
    a, b = T(-ex, -ey, z0), T(ex, -ey, z0)
    r0, r1 = T(-ex, 0, z0 + rise), T(ex, 0, z0 + rise)
    d, e = T(ex, ey, z0), T(-ex, ey, z0)
    mb.add([a, b, r1, r0], [(0, 1, 2, 3)], mat)
    mb.add([d, e, r0, r1], [(0, 1, 2, 3)], mat)
    # gable end walls
    mb.add([T(-hx, -hy, z0), T(-hx, 0, z0 + rise), T(-hx, hy, z0)], [(0, 1, 2)], wall_mat)
    mb.add([T(hx, -hy, z0), T(hx, 0, z0 + rise), T(hx, hy, z0)], [(0, 2, 1)], wall_mat)


def build_context(col, M, rng, keepout, roads, radius=700.0):
    """Place context buildings on a loose street grid. Returns footprints (for trees)."""
    for i, c in enumerate(WALLS):
        M[f'NK_CtxWall{i}'] = mat_context_wall(f'NK_CtxWall{i}', c)
    M['NK_CtxShed'] = mat_context_wall('NK_CtxShed', '#A9ABAA', win=(6.0, 5.0), frac=(0.2, 0.25))
    for i, c in enumerate(ROOFS):
        m = bpy.data.materials.new(f'NK_CtxRoof{i}')
        nt = NT(m)
        p, out = _principled(nt, Roughness=0.6, Metallic=0.3)
        p.inputs['Base Color'].default_value = srgb(c)
        M[m.name] = m
    M['NK_CtxFlat'] = M['NK_Roof']
    mb = MeshBuilder()
    feet = []

    def free(cx, cy, r):
        if math.hypot(cx, cy) > radius:
            return False
        for (x0, x1, y0, y1) in keepout + roads:
            if x0 - r <= cx <= x1 + r and y0 - r <= cy <= y1 + r:
                return False
        return all((cx - fx) ** 2 + (cy - fy) ** 2 > (r + fr) ** 2 for fx, fy, fr in feet)

    # urban blocks 110 x 85 m, some left as parks
    for bx in np.arange(-770, 770, 110.0):
        for by in np.arange(-770, 770, 85.0):
            if rng.random() < 0.28:
                continue   # park / open land
            rot = math.radians(rng.normal(0, 4) + (90 if rng.random() < 0.25 else 0))
            kind = rng.choice(['soviet', 'soviet', 'soviet', 'houses', 'shed', 'tower'], p=None)
            if kind == 'soviet':
                n = rng.integers(1, 3)
                for k in range(n):
                    L, Dp = rng.uniform(38, 78), 12.5
                    fl = rng.choice([4, 5, 5, 5, 9])
                    cx = bx + rng.uniform(-18, 18)
                    cy = by + (k - (n - 1) / 2) * 34 + rng.uniform(-4, 4)
                    r = L / 2 + 3
                    if not free(cx, cy, r):
                        continue
                    wm = f'NK_CtxWall{rng.integers(0, len(WALLS))}'
                    h = fl * 3.0 + 0.6
                    _box(mb, -L / 2, L / 2, -Dp / 2, Dp / 2, 0, h, wm, rot, cx, cy)
                    if fl <= 5 and rng.random() < 0.8:
                        _gable(mb, L / 2, Dp / 2, h, 2.4, f'NK_CtxRoof{rng.integers(0, len(ROOFS))}', wm, rot, cx, cy)
                    else:
                        _box(mb, -L / 2, L / 2, -Dp / 2, Dp / 2, h, h + 0.05, 'NK_CtxFlat', rot, cx, cy)
                    feet.append((cx, cy, r))
            elif kind == 'houses':
                for k in range(rng.integers(3, 7)):
                    cx, cy = bx + rng.uniform(-40, 40), by + rng.uniform(-30, 30)
                    s = rng.uniform(8, 13)
                    if not free(cx, cy, s * 0.8):
                        continue
                    wm = f'NK_CtxWall{rng.integers(0, len(WALLS))}'
                    h = rng.choice([3.3, 6.3, 6.3])
                    rr = rot + math.radians(rng.normal(0, 8))
                    _box(mb, -s / 2, s / 2, -s * 0.42, s * 0.42, 0, h, wm, rr, cx, cy)
                    _gable(mb, s / 2, s * 0.42, h, 2.2, f'NK_CtxRoof{rng.integers(0, len(ROOFS))}', wm, rr, cx, cy, 0.5)
                    feet.append((cx, cy, s * 0.8))
            elif kind == 'shed':
                L, Dp = rng.uniform(40, 80), rng.uniform(20, 36)
                cx, cy = bx + rng.uniform(-10, 10), by + rng.uniform(-8, 8)
                r = L / 2 + 3
                if free(cx, cy, r):
                    h = rng.uniform(7, 11)
                    _box(mb, -L / 2, L / 2, -Dp / 2, Dp / 2, 0, h, 'NK_CtxShed', rot, cx, cy)
                    _gable(mb, L / 2, Dp / 2, h, 1.6, 'NK_CtxRoof2', 'NK_CtxShed', rot, cx, cy, 0.3)
                    feet.append((cx, cy, r))
            else:
                L, Dp = rng.uniform(22, 34), rng.uniform(14, 18)
                cx, cy = bx + rng.uniform(-20, 20), by + rng.uniform(-15, 15)
                r = L / 2 + 4
                if free(cx, cy, r):
                    fl = int(rng.integers(9, 17))
                    wm = f'NK_CtxWall{rng.integers(0, len(WALLS))}'
                    _box(mb, -L / 2, L / 2, -Dp / 2, Dp / 2, 0, fl * 3.0 + 1.0, wm, rot, cx, cy)
                    _box(mb, -L / 2, L / 2, -Dp / 2, Dp / 2, fl * 3.0 + 1.0, fl * 3.0 + 1.05, 'NK_CtxFlat', rot, cx, cy)
                    feet.append((cx, cy, r))
    mb.to_object('NK_Context_Buildings', col, M, merge=False)
    print('context buildings:', len(feet))
    return feet


# ---- real neighbours from OpenStreetMap -------------------------------------------------------
def _obb(pts):
    """Oriented box of a quad-ish footprint along its longest edge: (cx, cy, rot, hx, hy)."""
    best = None
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        L = math.hypot(x1 - x0, y1 - y0)
        if best is None or L > best[0]:
            best = (L, math.atan2(y1 - y0, x1 - x0))
    rot = best[1]
    c, s = math.cos(-rot), math.sin(-rot)
    loc = [(x * c - y * s, x * s + y * c) for x, y in pts]
    xs, ys = [p[0] for p in loc], [p[1] for p in loc]
    lx, ly = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    cr, sr = math.cos(rot), math.sin(rot)
    return (lx * cr - ly * sr, lx * sr + ly * cr, rot, (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2)


def build_osm_context(col, M, osm, rng, keepout):
    """Extrude OSM building footprints (heights from tags, else by footprint size) with the
    window-grid facades; flat roofs, gables on small houses. Returns [(cx, cy, r)] for trees."""
    import mathutils
    from nk_osm import poly_area, centroid, inside
    for i, c in enumerate(WALLS):
        if f'NK_CtxWall{i}' not in M:
            M[f'NK_CtxWall{i}'] = mat_context_wall(f'NK_CtxWall{i}', c)
    if 'NK_CtxShed' not in M:
        M['NK_CtxShed'] = mat_context_wall('NK_CtxShed', '#A9ABAA', win=(6.0, 5.0), frac=(0.2, 0.25))
    for i, c in enumerate(ROOFS):
        if f'NK_CtxRoof{i}' not in M:
            m = bpy.data.materials.new(f'NK_CtxRoof{i}')
            nt = NT(m)
            p, out = _principled(nt, Roughness=0.6, Metallic=0.3)
            p.inputs['Base Color'].default_value = srgb(c)
            M[m.name] = m
    mb = MeshBuilder()
    feet = []
    kept = 0
    for b in osm['buildings']:
        pts = [tuple(p) for p in b['pts']]
        if len(pts) < 3:
            continue
        if pts[0] == pts[-1]:
            pts = pts[:-1]
        A = poly_area(pts)
        if A < 0:
            pts = pts[::-1]
            A = -A
        if A < 12:
            continue
        cx, cy = centroid(pts)
        if any(inside(r, cx, cy) for r in keepout) or any(inside(r, x, y) for r in keepout for x, y in pts):
            continue
        kind = (b.get('kind') or 'yes').lower()
        h = b.get('h')
        if not h:
            h = 6.2 if A < 180 else 9.5 if A < 600 else 15.8 if A < 2200 else 10.0
            if kind in ('garages', 'garage', 'shed', 'kiosk', 'roof'):
                h = 3.2
            elif kind == 'house':
                h = 6.2
            elif kind in ('industrial', 'warehouse', 'hangar'):
                h = 9.0
        shed = kind in ('industrial', 'warehouse', 'hangar', 'garages', 'garage', 'shed', 'roof')
        wm = 'NK_CtxShed' if shed else f'NK_CtxWall{int(rng.integers(0, len(WALLS)))}'
        n = len(pts)
        for i in range(n):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
            mb.add([(x0, y0, 0.0), (x1, y1, 0.0), (x1, y1, h), (x0, y0, h)], [(0, 1, 2, 3)], wm)
        gable = (n == 4 and A < 260 and not shed and h <= 7.0) or (b.get('roof') in ('gabled', 'hipped') and n == 4)
        if gable:
            gx, gy, rot, hx, hy = _obb(pts)
            if hy > hx:
                rot += math.pi / 2
                hx, hy = hy, hx
            _gable(mb, hx, hy, h, min(2.6, hy * 0.6), f'NK_CtxRoof{int(rng.integers(0, len(ROOFS)))}', wm, rot, gx, gy, 0.35)
        else:
            tris = mathutils.geometry.tessellate_polygon([[mathutils.Vector((x, y, h)) for x, y in pts]])
            V = [(x, y, h) for x, y in pts]
            for t in tris:
                a, bb, c = (V[t[0]], V[t[1]], V[t[2]])
                nz = (bb[0] - a[0]) * (c[1] - a[1]) - (bb[1] - a[1]) * (c[0] - a[0])
                mb.add([a, bb, c] if nz > 0 else [a, c, bb], [(0, 1, 2)], 'NK_Roof')
        r = max(math.hypot(x - cx, y - cy) for x, y in pts)
        feet.append((cx, cy, r, pts))
        kept += 1
    mb.to_object('NK_Context_Buildings', col, M, merge=False)
    print('OSM context buildings:', kept)
    return feet
