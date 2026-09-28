"""Street props: parked cars (procedural sedans / SUVs / hatchbacks) and street lamps,
built once as templates and placed as collection instances."""
import math
import numpy as np
import bpy
from nk_geo import MeshBuilder
from nk_mats import NT, srgb, _principled

PAINTS = {'White': '#E3E1DC', 'Silver': '#A5AAAE', 'Black': '#16181B', 'Graphite': '#45494E',
          'Navy': '#1D2F4A', 'Red': '#7E1F24', 'Beige': '#B9A98E'}

# side profiles (x along the car from the front bumper, z up), beltline index, width, roof inset
BODIES = {
    'Sedan': dict(L=4.65, W=1.82, prof=[(0.0, 0.34), (0.05, 0.68), (0.95, 0.86), (1.62, 0.95), (2.25, 1.43),
                                          (3.35, 1.45), (3.95, 1.02), (4.58, 0.98), (4.65, 0.62), (4.6, 0.34)],
                  belt=0.96),
    'SUV': dict(L=4.75, W=1.92, prof=[(0.0, 0.42), (0.05, 0.82), (0.9, 1.02), (1.45, 1.1), (1.95, 1.7),
                                        (4.35, 1.72), (4.62, 1.2), (4.75, 1.02), (4.72, 0.42)], belt=1.12),
    'Hatch': dict(L=4.15, W=1.78, prof=[(0.0, 0.36), (0.05, 0.7), (0.8, 0.86), (1.35, 0.95), (1.95, 1.47),
                                          (3.55, 1.47), (4.05, 1.08), (4.15, 0.95), (4.12, 0.36)], belt=0.97),
}


def _mat_paint(name, hexcol, metal):
    m = bpy.data.materials.new(name)
    nt = NT(m)
    p, out = _principled(nt, Metallic=metal, Roughness=0.32)
    p.inputs['Base Color'].default_value = srgb(hexcol)
    p.inputs['Coat Weight'].default_value = 1.0
    p.inputs['Coat Roughness'].default_value = 0.03
    return m


def _mat(name, hexcol, rough, metal=0.0, spec=0.5):
    m = bpy.data.materials.new(name)
    nt = NT(m)
    p, out = _principled(nt, Metallic=metal, Roughness=rough)
    p.inputs['Base Color'].default_value = srgb(hexcol)
    p.inputs['Specular IOR Level'].default_value = spec
    return m


def car_mesh(body, paint):
    """Extrude the side profile across the width; greenhouse above the beltline is glass
    and slightly inset (tumblehome). Returns a MeshBuilder in car-local coordinates
    (x forward from the front bumper, y across, z up)."""
    b = BODIES[body]
    mb = MeshBuilder()
    L, W = b['L'], b['W']
    prof = b['prof']
    belt = b['belt']
    n = len(prof)

    def y_at(z, side):
        inset = 0.16 * max(0.0, (z - belt) / 0.5)
        return side * (W / 2 - inset)
    # split each profile edge at the beltline so glass/body faces separate cleanly
    pts = []
    for i in range(n):
        p0, p1 = prof[i], prof[(i + 1) % n]
        pts.append(p0)
        if (p0[1] - belt) * (p1[1] - belt) < 0:
            t = (belt - p0[1]) / (p1[1] - p0[1])
            pts.append((p0[0] + (p1[0] - p0[0]) * t, belt))
    m = len(pts)
    # skin around the profile (top/front/rear surfaces)
    for i in range(m):
        (x0, z0), (x1, z1) = pts[i], pts[(i + 1) % m]
        upper = min(z0, z1) >= belt - 1e-6 and max(z0, z1) > belt + 0.05
        # windshield / rear window are the steep upper edges; roof is flat-ish
        steep = upper and abs(z1 - z0) > 0.25
        mat = 'CAR_Glass' if steep else paint
        V = [(x0, y_at(z0, -1), z0), (x1, y_at(z1, -1), z1), (x1, y_at(z1, 1), z1), (x0, y_at(z0, 1), z0)]
        mb.add(V, [(0, 1, 2, 3)], mat)
    # side panels: fan the profile polygon on each side (body below belt, glass above)
    for side in (-1, 1):
        below = [p for p in pts if p[1] <= belt + 1e-6]
        above = [p for p in pts if p[1] >= belt - 1e-6]
        for poly, mat in ((below, paint), (above, 'CAR_Glass')):
            if len(poly) < 3:
                continue
            V = [(x, y_at(z, side) * 1.0, z) for (x, z) in poly]
            idx = list(range(len(V)))
            if side < 0:          # profile order faces +y; mirror side reversed
                idx = idx[::-1]
            mb.add(V, [tuple(idx)], mat)
    # wheels (octagonal prisms) and a dark underbody
    r, wd = 0.34, 0.22
    for wx in (0.85, L - 0.9):
        for side in (-1, 1):
            cy = side * (W / 2 - wd / 2 + 0.02)
            ring = [(wx + r * math.cos(a), cy, 0.34 + r * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 13)[:-1]]
            outer = [(x, cy + side * wd / 2, z) for (x, _, z) in ring]
            inner = [(x, cy - side * wd / 2, z) for (x, _, z) in ring]
            k = len(ring)
            for j in range(k):
                q = [inner[j], inner[(j + 1) % k], outer[(j + 1) % k], outer[j]]
                mb.add(q[::-1] if side > 0 else q, [(0, 1, 2, 3)], 'CAR_Tyre')
            mb.add(outer if side < 0 else outer[::-1], [tuple(range(k))], 'CAR_Rim')
    mb.add([(0.25, -W / 2 + 0.1, 0.16), (L - 0.25, -W / 2 + 0.1, 0.16), (L - 0.25, W / 2 - 0.1, 0.16),
            (0.25, W / 2 - 0.1, 0.16)], [(0, 3, 2, 1)], 'CAR_Tyre')
    return mb


def build_cars(M, lib):
    M['CAR_Glass'] = _mat('CAR_Glass', '#0C0F12', 0.03, spec=0.9)
    M['CAR_Tyre'] = _mat('CAR_Tyre', '#141414', 0.85)
    M['CAR_Rim'] = _mat('CAR_Rim', '#8E9296', 0.3, metal=0.9)
    colls = []
    rng = np.random.default_rng(21)
    for body in BODIES:
        for pname, hexcol in PAINTS.items():
            if rng.random() < 0.35 and pname not in ('White', 'Silver', 'Black'):
                continue
            mname = f'CAR_Paint_{pname}'
            if mname not in M:
                M[mname] = _mat_paint(mname, hexcol, 0.0 if pname in ('White', 'Black', 'Red') else 0.6)
            mb = car_mesh(body, mname)
            c = bpy.data.collections.new(f'TC_{body}_{pname}')
            lib.children.link(c)
            ob = mb.to_object(f'CAR_{body}_{pname}', c, M, merge=True)
            # centre the car on its footprint
            ob.data.transform(__import__('mathutils').Matrix.Translation((-BODIES[body]['L'] / 2, 0, 0)))
            colls.append(c)
    return colls


def build_lamp(M, lib):
    M['NK_LampMetal'] = M.get('NK_LampMetal') or _mat('NK_LampMetal', '#3A3D40', 0.4, metal=0.8)
    M['NK_LampLens'] = M.get('NK_LampLens') or _mat('NK_LampLens', '#E8E6DF', 0.2)
    mb = MeshBuilder()
    k = 10
    for (z0, z1, r0, r1) in ((0.0, 7.6, 0.09, 0.06),):
        ring0 = [(r0 * math.cos(a), r0 * math.sin(a), z0) for a in np.linspace(0, 2 * math.pi, k + 1)[:-1]]
        ring1 = [(r1 * math.cos(a), r1 * math.sin(a), z1) for a in np.linspace(0, 2 * math.pi, k + 1)[:-1]]
        for j in range(k):
            mb.add([ring0[j], ring0[(j + 1) % k], ring1[(j + 1) % k], ring1[j]], [(0, 1, 2, 3)], 'NK_LampMetal')
    # arm + head
    def box(x0, x1, y0, y1, z0, z1, mat, bottom=None):
        V = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for f, m in (((4, 5, 6, 7), mat), ((0, 3, 2, 1), bottom or mat), ((0, 1, 5, 4), mat), ((1, 2, 6, 5), mat),
                     ((2, 3, 7, 6), mat), ((3, 0, 4, 7), mat)):
            mb.add([V[i] for i in f], [(0, 1, 2, 3)], m)
    box(-0.04, 1.4, -0.04, 0.04, 7.5, 7.6, 'NK_LampMetal')
    box(1.1, 1.85, -0.16, 0.16, 7.42, 7.58, 'NK_LampMetal', bottom='NK_LampLens')
    c = bpy.data.collections.new('TL_StreetLamp')
    lib.children.link(c)
    mb.to_object('LAMP_Street', c, M)
    return c


def place(col, coll, items, prefix):
    """items: [(x, y, z, heading_rad, collection)]"""
    for i, (x, y, z, h, cc) in enumerate(items):
        e = bpy.data.objects.new(f'{prefix}_{i:04d}', None)
        e.instance_type = 'COLLECTION'
        e.instance_collection = cc
        e.location = (x, y, z)
        e.rotation_euler = (0, 0, h)
        col.objects.link(e)


def layout_cars(rng, colls, keep_clear=()):
    """Parallel-parked cars along the streets + perpendicular bays at the west/east streets."""
    items = []

    def ok(x, y):
        return all((x - cx) ** 2 + (y - cy) ** 2 > r * r for (cx, cy, r) in keep_clear)
    # south street, north kerb lane (y ~ -64.4) and south kerb lane (y ~ -74.8), both sides of the site
    for (y, h) in ((-64.6, 0.0), (-74.6, math.pi), (70.6, math.pi), (77.6, 0.0)):
        x = -330.0
        while x < 330:
            x += rng.uniform(5.4, 9.0)
            if abs(x) < 8 or rng.random() < 0.35:
                continue
            if ok(x, y):
                items.append((x, y + rng.uniform(-0.1, 0.1), 0.02, h + rng.normal(0, 0.02), colls[rng.integers(len(colls))]))
    # perpendicular bays beside the west (A) and east (B) streets
    for sx in (-1, 1):
        for y in np.arange(-38, 39, 2.6):
            if rng.random() < 0.72:
                items.append((sx * 134.0, y, 0.02, (0.0 if rng.random() < 0.5 else math.pi) + rng.normal(0, 0.03),
                              colls[rng.integers(len(colls))]))
    return items


def layout_lamps(lamp):
    items = []
    for x in np.arange(-320, 321, 26.0):
        items.append((x, -62.3, 0.14, math.pi / 2 * 3, lamp))   # arm reaches over the south street
        items.append((x + 13, 67.8, 0.14, math.pi / 2, lamp))
    for sx in (-1, 1):
        for y in np.arange(-50, 66, 26.0):
            items.append((sx * 137.2, y, 0.14, 0.0 if sx > 0 else math.pi, lamp))
    return items


def layout_cars_osm(rng, colls, roads, keep_clear=(), radius=320.0):
    """Parallel-parked cars along the kerbs of real streets near the site."""
    from nk_site import ROAD_W, _clean, _offset, _seg_d2
    from nk_osm import SITE_ZONE, inside
    items = []
    segs = []
    for rd in roads:
        P = _clean(rd['pts'])
        for i in range(len(P) - 1):
            segs.append((P[i], P[i + 1], ROAD_W.get(rd['kind'], 5.0)))

    def junction(x, y, own):
        for (a, b, w) in segs:
            if w != own[2] or a != own[0]:
                if _seg_d2(x, y, a, b) < (w / 2 + 0.5) ** 2 and (a, b) != (own[0], own[1]):
                    return True
        return False
    for rd in roads:
        if rd['kind'] not in ('residential', 'tertiary', 'living_street', 'service') or rd.get('nk'):
            continue
        w = ROAD_W[rd['kind']]
        P = _clean(rd['pts'])
        if len(P) < 2 or all(abs(x) > radius or abs(y) > radius for x, y in P):
            continue
        for side in (1, -1):
            if rd['kind'] == 'service' and side < 0:
                continue
            line = _offset(P, side * (w / 2 - 1.05))
            for i in range(len(line) - 1):
                a, b = line[i], line[i + 1]
                L = float(np.linalg.norm(b - a))
                if L < 6:
                    continue
                h = math.atan2(b[1] - a[1], b[0] - a[0]) + (0.0 if side < 0 else math.pi)
                t = rng.uniform(1, 5)
                while t < L - 3:
                    q = a + (b - a) * (t / L)
                    x, y = float(q[0]), float(q[1])
                    ok = (rng.random() < 0.5 and abs(x) < radius and abs(y) < radius
                          and not inside(SITE_ZONE, x, y, 1.0)
                          and all((x - cx) ** 2 + (y - cy) ** 2 > r * r for (cx, cy, r) in keep_clear))
                    if ok:
                        items.append((x, y, 0.03, h + rng.normal(0, 0.02), colls[rng.integers(len(colls))]))
                    t += rng.uniform(5.4, 8.5)
    # perpendicular bays of the new street west of block A (nk_osm.west_bays), mostly nosed in
    from nk_osm import west_bays, BAY_X
    bx = 0.5 * (BAY_X[0] + BAY_X[1]) - 0.15
    for (y0, y1) in west_bays()[0]:
        y = 0.5 * (y0 + y1)
        if rng.random() < 0.76 and all((bx - cx) ** 2 + (y - cy) ** 2 > r * r for (cx, cy, r) in keep_clear):
            items.append((bx, y, 0.03, (0.0 if rng.random() < 0.8 else math.pi) + rng.normal(0, 0.03),
                          colls[rng.integers(len(colls))]))
    return items
