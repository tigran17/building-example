"""Street life for the web model and the stills (site v0.12): the redesigned courtyards, street furniture,
roof equipment and ground details. Layouts are plain data (world metres, X east, Y north) shared by the
site geometry (nk_site), the tree layout, the props mesh (NK_Site_Props, its own lightmap atlas) and the
people routes (nk_people.py), so benches, paths and playgrounds line up everywhere.

Block A is authored; block B mirrors it in x with its own sports pitch. The web ground is a single flat
bake at WEB_Z, so in the web build everything that stands on the ground stands on that plane.
"""
import math
import os
import zlib

DETAIL = os.environ.get('NK_DETAIL', 'full')
WEB_Z = 0.22
Z_ROAD, Z_PAVE, Z_LAWN = 0.02, 0.14, 0.16


def gz(z):
    """Height of the ground a prop stands on (the flat web ground in the web build)."""
    return WEB_Z if DETAIL == 'web' else z


def ellipse(c, r, n=48, a0=0.0):
    return [(c[0] + r[0] * math.cos(a0 + 2 * math.pi * k / n), c[1] + r[1] * math.sin(a0 + 2 * math.pi * k / n)) for k in range(n)]


def _mx(pts, s):
    return [(s * x, y) for x, y in pts]


# ---- courtyards ------------------------------------------------------------------------------------------
# Courtyard A (inner facade line): x[-93.5,-28.5] y[-30.5,30.5] + x[-104.5,-76] y[-3,37.5]. A 3 m paved walk runs
# along the facades; the rest is lawn with a loop path, flower beds, trees, a playground, a sports court and a
# pergola, as in the developer's courtyard renders (the first version had four lawn boxes on bare paving).
LAWNS = [(-90.5, -31.5, -27.5, 27.5), (-101.5, -90.5, 0.0, 34.5), (-90.5, -79.0, 27.5, 34.5)]
PERGOLA = (-100.0, -95.4, 5.0, 15.0)
PLAYGROUND = (-49.0, -34.5, 14.5, 27.0)


def courtyard_layout(block):
    """Everything in world coordinates for block 'A' or 'B'."""
    s = 1.0 if block == 'A' else -1.0
    if block == 'A':
        loop_c, loop_r = (-66.0, 0.0), (17.0, 16.0)
        court = {'rect': (-44.0, -33.0, -11.0, 11.0), 'kind': 'basket', 'mat': 'NK_CourtBlue'}
    else:
        loop_c, loop_r = (-71.0, 0.0), (14.0, 15.0)
        court = {'rect': (-55.0, -34.0, -13.5, 13.5), 'kind': 'football', 'mat': 'NK_CourtGreen'}
    cx, cy = loop_c
    rx, ry = loop_r
    loop = ellipse(loop_c, loop_r, 56)
    west_y = -8.0
    west_x = cx - rx * math.sqrt(1 - (west_y - cy) ** 2 / ry ** 2)
    a_nw = math.radians(135)
    nw = (cx + rx * math.cos(a_nw), cy + ry * math.sin(a_nw))
    spurs = [[(cx, cy - ry), (cx, -29.2)], [(cx, cy + ry), (cx, 29.2)], [(west_x, west_y), (-92.2, west_y)],
             [nw, (-90.0, 24.0), (-98.6, 32.8), (-103.2, 36.2)]]
    beds = [((cx, cy), (4.6 if block == 'A' else 3.8, 4.0)), ((-86.0, -21.5), (3.2, 2.1)), ((-56.5, 21.0), (2.6, 1.9)),
            ((-96.5, 24.5), (2.4, 2.4)), ((-75.5, -24.0), (2.8, 1.7))]
    trees = [(-86.0, -23.0, 'Linden'), (-77.0, -24.6, 'Maple'), (-57.0, -24.2, 'Birch'), (-46.5, -22.3, 'Maple'),
             (-37.5, -21.5, 'Linden'), (-87.4, 4.5, 'Maple'), (-74.2, 21.8, 'Birch'), (-58.0, 23.4, 'Linden'),
             (-97.2, 21.8, 'Maple'), (-84.2, 31.3, 'Linden'), (-93.6, 31.8, 'Birch'), (-84.5, -14.5, 'Linden'),
             (-52.5, -20.0, 'Birch'), (-79.0, 27.0, 'Maple'), (-99.8, 2.6, 'Linden'), (-62.5, -25.0, 'Maple')]
    if block == 'B':
        trees = [t for t in trees if not (-56.0 <= t[0] <= -33.0 and -14.5 <= t[1] <= 14.5)]
    benches = []
    spur_angles = [90.0, 270.0, math.degrees(math.atan2((west_y - cy) / ry, (west_x - cx) / rx)) % 360, 135.0]
    for k in range(10):
        a = 18.0 + 36.0 * k
        if min(abs((a - b + 180) % 360 - 180) for b in spur_angles) < 16:
            continue
        ar = math.radians(a)
        ux, uy = math.cos(ar), math.sin(ar)
        px, py = cx + (rx + 2.3) * ux, cy + (ry + 2.3) * uy
        n = math.hypot(ux / rx, uy / ry)
        fx, fy = -(ux / rx) / n, -(uy / ry) / n                   # facing the loop (inwards)
        benches.append((px, py, fx, fy))
    x0, x1, y0, y1 = PLAYGROUND
    benches += [(x0 - 1.0, 18.0, 1.0, 0.0), (x0 - 1.0, 23.5, 1.0, 0.0)]
    p0, p1, q0, q1 = PERGOLA
    benches += [(p0 + 0.9, 8.8, 1.0, 0.0), (p1 - 0.9, 11.4, -1.0, 0.0)]
    lamps = [(cx + (rx + 1.4) * math.cos(math.radians(a)), cy + (ry + 1.4) * math.sin(math.radians(a))) for a in (0, 58, 112, 175, 235, 300)]
    out = {'loop': loop, 'spurs': spurs, 'beds': beds, 'trees': trees, 'benches': benches, 'lamps': lamps,
           'court': court, 'playground': PLAYGROUND, 'pergola': PERGOLA, 'lawns': LAWNS,
           'kids': [((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 - 1.5, (y1 - y0) / 2 - 1.5)]}
    if block == 'B':
        out = mirror_layout(out)
    return out


def mirror_layout(L):
    m = dict(L)
    m['loop'] = _mx(L['loop'], -1)[::-1]
    m['spurs'] = [_mx(p, -1) for p in L['spurs']]
    m['beds'] = [((-c[0], c[1]), r) for c, r in L['beds']]
    m['trees'] = [(-x, y, sp) for x, y, sp in L['trees']]
    m['benches'] = [(-x, y, -fx, fy) for x, y, fx, fy in L['benches']]
    m['lamps'] = [(-x, y) for x, y in L['lamps']]
    x0, x1, y0, y1 = L['court']['rect']
    m['court'] = dict(L['court'], rect=(-x1, -x0, y0, y1))
    for k in ('playground', 'pergola'):
        x0, x1, y0, y1 = L[k]
        m[k] = (-x1, -x0, y0, y1)
    m['lawns'] = [(-x1, -x0, y0, y1) for x0, x1, y0, y1 in L['lawns']]
    m['kids'] = [(-cx, cy, rx, ry) for cx, cy, rx, ry in L['kids']]
    return m


# ---- plaza furniture ----------------------------------------------------------------------------------
SOUTH_STRIPS = ((-130, -100), (-95, -70), (-65, -40), (-35, -14))


def plaza_items():
    """Benches (x, y, facing x, facing y), bins, bike racks (x, y, along x, along y, n), bollards,
    entrance canopies (x, y, outward x, outward y, width) for both blocks."""
    from nk_site import WEST_LAWNS, WEST_LAWN_X
    benches, bins, racks, bollards, canopies = [], [], [], [], []
    for sx in (-1, 1):
        for (a, b) in SOUTH_STRIPS:
            x0, x1 = sorted((a * sx, b * sx))
            for x in (x0 + (x1 - x0) * 0.3, x0 + (x1 - x0) * 0.7):
                benches.append((x, -54.3, 0.0, 1.0))               # backs to the lawn strip, facing the building
            bins.append((x0 + (x1 - x0) * 0.5, -54.2))
    for (y0, y1) in WEST_LAWNS:
        y = 0.5 * (y0 + y1)
        benches.append((WEST_LAWN_X[1] + 0.75, y, 1.0, 0.0))
        bins.append((WEST_LAWN_X[1] + 0.6, y + 1.6))
    for sx in (-1, 1):
        racks.append((sx * -116.5, -51.8, 1.0, 0.0, 6))
        racks.append((sx * -8.5, -51.8, 1.0, 0.0, 5))
        racks.append((sx * -126.0, 58.6, 1.0, 0.0, 5))
    for y in (-13.6, -11.9, -10.2):                                 # the crossing from the park onto the plaza
        bollards.append((-139.55, y))
    for x in (-136.0, -134.2, -132.4):                              # the plaza corner at the south crossing
        bollards.append((x, -65.55))
    # entrance canopies at the middle of the main outer runs and on the courtyard side where the paths arrive
    A = [(-61.0, -48.0, 0.0, -1.0, 4.2), (-86.0, -48.0, 0.0, -1.0, 3.6), (-36.0, -48.0, 0.0, -1.0, 3.6),
         (-111.0, -25.5, -1.0, 0.0, 3.6), (-122.0, 26.0, -1.0, 0.0, 3.6), (-43.5, 48.0, 0.0, 1.0, 3.6),
         (-99.0, 55.0, 0.0, 1.0, 3.6), (-11.0, 0.0, 1.0, 0.0, 3.6),
         (-66.0, -30.5, 0.0, 1.0, 3.2), (-66.0, 30.5, 0.0, -1.0, 3.2)]
    canopies = A + [(-x, y, -ox, oy, w) for x, y, ox, oy, w in A]
    return {'benches': benches, 'bins': bins, 'racks': racks, 'bollards': bollards, 'canopies': canopies}


def park_items(roads):
    """Park lights and benches along the park paths (x, y, facing x, facing y)."""
    from nk_site import _clean, _arclen, _sub
    import numpy as np
    lamps, benches = [], []
    for rd in roads:
        if rd['kind'] != 'park_path':
            continue
        P = _clean(rd['pts'])
        L = _arclen(P)
        rng = np.random.default_rng(zlib.crc32(('park' + str(rd['id'])).encode()))
        s, k = rng.uniform(4, 10), 0
        while s < L - 3:
            q = _sub(P, s - 0.3, s + 0.3)
            if len(q) >= 2:
                (ax, ay), (bx, by) = q[0], q[-1]
                d = math.hypot(bx - ax, by - ay) or 1.0
                tx, ty = (bx - ax) / d, (by - ay) / d
                side = 1 if k % 2 == 0 else -1
                nx, ny = -ty * side, tx * side
                lamps.append((ax + nx * 2.0, ay + ny * 2.0))
                if k % 2 == 1:
                    benches.append((ax + tx * 6.0 - nx * 2.3, ay + ty * 6.0 - ny * 2.3, nx, ny))
            s += 22.0
            k += 1
    return lamps, benches


def all_benches(roads):
    """Every bench in the scene (x, y, facing x, facing y) for the people who sit on them."""
    out = list(park_items(roads)[1]) + plaza_items()['benches']
    for b in ('A', 'B'):
        out += courtyard_layout(b)['benches']
    return out


# ---- roofs -------------------------------------------------------------------------------------------------
ROOF_Z = 55.5
# block A roof wings (world x0, y0, x1, y1) - nk_build.ROOF_RECTS + OFFSET_A
ROOF_RECTS = [(-111.0, -48.0, -11.0, -30.5), (-28.5, -30.5, -11.0, 48.0), (-76.0, 30.5, -28.5, 48.0),
              (-122.0, 37.5, -76.0, 55.0), (-122.0, -3.0, -104.5, 37.5), (-111.0, -30.5, -93.5, -3.0)]
# block A roof overruns (world centre, size x, size y) - mirrored from nk_build.ROOF_BOXES
OVERRUNS = [(-87.0, -39.25, 8, 6), (-49.0, -39.25, 8, 6), (-19.75, -8.0, 6, 8), (-19.75, 22.0, 6, 8),
            (-51.0, 39.25, 8, 6), (-99.0, 46.25, 8, 6), (-113.25, 18.0, 6, 8), (-102.25, -18.0, 6, 8)]


def roof_items():
    """Block A (B mirrors): solar rows on the south wing, condenser groups, exhaust fans, hatches, walkway pads
    from the overrun doors, drains along the parapets, two dishes."""
    pv = []
    for (x0, x1) in ((-81.5, -55.5), (-43.5, -17.0), (-108.0, -92.5)):
        for y in (-46.3, -43.9, -41.5):
            pv.append((x0, x1, y))
    ac = [(-16.5, 4.0, 2, 4), (-24.5, 36.0, 3, 2), (-66.0, 42.5, 4, 2), (-116.0, 3.0, 2, 3), (-104.0, -26.0, 2, 2),
          (-33.0, 44.0, 2, 2)]
    fans = [(-84.0, -34.6), (-52.5, -34.5), (-14.5, -12.6), (-24.8, 27.0), (-47.0, 35.0), (-95.0, 42.0), (-117.5, 23.5),
            (-106.5, -13.0)]
    hatches = [(-30.0, -38.0), (-19.0, 42.0), (-110.0, 47.0)]
    pads = []

    def on_roof(x, y, m=1.0):
        return any(x0 + m < x < x1 - m and y0 + m < y < y1 - m for (x0, y0, x1, y1) in ROOF_RECTS)
    for (x, y, sx, sy) in OVERRUNS:
        door = (x, y - sy / 2 - 0.6)
        # walkway pads to the nearest condenser group that can be reached without leaving the roof
        for target in sorted((a[:2] for a in ac), key=lambda a: math.dist(a, door)):
            d = math.dist(door, target)
            n = max(2, int(d / 0.75))
            pts = [(door[0] + (target[0] - door[0]) * k / n, door[1] + (target[1] - door[1]) * k / n) for k in range(1, n)]
            if d < 45 and all(on_roof(px, py) for px, py in pts):
                pads += pts
                break
    drains = []
    for (x0, y0, x1, y1) in ((-110.2, -47.2, -11.8, -47.2), (-11.8, -47.2, -11.8, 47.2), (-121.2, 54.2, -76.8, 54.2),
                             (-121.2, -2.2, -121.2, 54.2)):
        L = math.dist((x0, y0), (x1, y1))
        for k in range(1, int(L / 14.0) + 1):
            t = k / (int(L / 14.0) + 1)
            drains.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    dishes = [(-27.0, 12.0), (-116.5, 40.5)]
    return {'pv': pv, 'ac': ac, 'fans': fans, 'hatches': hatches, 'pads': pads, 'drains': drains, 'dishes': dishes}


# ---- ground details -----------------------------------------------------------------------------------------
def ground_details(roads):
    """Manholes (x, y, z), kerb drains (x, y, dir x, dir y, z), oil stains in the bays (x, y), tactile paving
    at the zebra ends (x, y, dir x, dir y, z)."""
    from nk_osm import ZEBRAS, WEST_X, BAY_X, west_bays, SITE_ZONE, inside
    from nk_site import ROAD_Z, _clean, _arclen, _sub, road_width
    manholes, drains, stains, tactile = [], [], [], []
    for rd in roads:
        if rd['kind'] != 'residential' or not any(math.hypot(x, y) < 260 for x, y in rd['pts']):
            continue
        P = _clean(rd['pts'])
        L = _arclen(P)
        w = road_width(rd)
        z = ROAD_Z['residential'] + (0.0035 if rd.get('nk') else 0.019) + 0.0045
        s = 11.0
        while s < L - 6:
            q = _sub(P, s - 0.2, s + 0.2)
            if len(q) >= 2 and all(math.hypot(q[0][0], q[0][1]) < 260 for _ in (0,)):
                (ax, ay), (bx, by) = q[0], q[-1]
                d = math.hypot(bx - ax, by - ay) or 1.0
                tx, ty = (bx - ax) / d, (by - ay) / d
                if not inside(SITE_ZONE, ax, ay, 1.0):
                    manholes.append((ax - ty * 1.1, ay + tx * 1.1, z))
                    for side in (1, -1):
                        o = side * (w / 2 - 0.35)
                        drains.append((ax + tx * 9.0 - ty * o, ay + ty * 9.0 + tx * o, tx, ty, z))
            s += 31.0
    rng_state = zlib.crc32(b'stains')
    for (y0, y1) in west_bays()[0]:
        rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
        if rng_state % 100 < 62:
            stains.append((0.5 * (BAY_X[0] + BAY_X[1]) + ((rng_state >> 8) % 60 - 30) / 100.0,
                           0.5 * (y0 + y1) + ((rng_state >> 14) % 40 - 20) / 100.0))
    for (c, t, w) in ZEBRAS:
        nx, ny = -t[1], t[0]
        for side in (1, -1):
            x, y = c[0] + nx * side * (w / 2 + 0.75), c[1] + ny * side * (w / 2 + 0.75)
            tactile.append((x, y, nx, ny, 0.1435 if inside(SITE_ZONE, x, y, 0.2) or (BAY_X[0] <= x <= BAY_X[1]) else 0.1235))
    return {'manholes': manholes, 'drains': drains, 'stains': stains, 'tactile': tactile}


# ---- props geometry ------------------------------------------------------------------------------------------
def _wbox(mb, x0, x1, y0, y1, z0, z1, mat, col=None, skip=()):
    """Axis-aligned world box (Frame t=+x: a = x, c = -y)."""
    from nk_geo import Frame
    mb.box(Frame((0.0, 0.0), (1.0, 0.0), 0.0), x0, x1, z0, z1, -y1, -y0, mat, skip=skip, col=col)


def _cyl(mb, cx, cy, z0, z1, r0, r1, mat, col=None, k=8, cap=True):
    ring = [(math.cos(2 * math.pi * (j + 0.5) / k), math.sin(2 * math.pi * (j + 0.5) / k)) for j in range(k)]
    for j in range(k):
        a, b = ring[j], ring[(j + 1) % k]
        mb.add([(cx + a[0] * r0, cy + a[1] * r0, z0), (cx + b[0] * r0, cy + b[1] * r0, z0),
                (cx + b[0] * r1, cy + b[1] * r1, z1), (cx + a[0] * r1, cy + a[1] * r1, z1)], [(0, 1, 2, 3)], mat, col)
    if cap:
        mb.add([(cx + a[0] * r1, cy + a[1] * r1, z1) for a in ring], [tuple(range(k))], mat, col)


def _bar(mb, p, q, r, mat, col=None):
    """Thin square bar between two 3D points (chains, rails, ladder sides)."""
    import numpy as np
    p, q = np.array(p, float), np.array(q, float)
    d = q - p
    L = float(np.linalg.norm(d))
    if L < 1e-6:
        return
    d /= L
    up = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(d, up)
    u /= np.linalg.norm(u)
    v = np.cross(u, d)
    c = [p + (u * a + v * b) * r for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    e = [x + d * L for x in c]
    for i in range(4):
        j = (i + 1) % 4
        mb.add([c[i], c[j], e[j], e[i]], [(0, 1, 2, 3)], mat, col)
    mb.add([c[3], c[2], c[1], c[0]], [(0, 1, 2, 3)], mat, col)
    mb.add([e[0], e[1], e[2], e[3]], [(0, 1, 2, 3)], mat, col)


def _lin(h):
    from nk_citygen import lin
    return lin(h)


def street_light(mb, x, y, ax, ay, z0):
    """8.4 m steel column on a concrete footing, one outreach arm over the carriageway, flat LED lantern."""
    from nk_geo import Frame
    metal = _lin('#737A7E')
    fr = Frame((x, y), (ax, ay), z0)
    mb.box(fr, -0.16, 0.16, 0.0, 0.4, -0.16, 0.16, 'CX_Concrete', skip=('-b',))
    _cyl(mb, x, y, z0 + 0.4, z0 + 8.4, 0.085, 0.055, 'CX_Sheet', metal)
    mb.box(fr, 0.0, 1.75, 8.16, 8.24, -0.035, 0.035, 'CX_Sheet', col=metal)
    mb.box(fr, 1.3, 2.05, 8.08, 8.22, -0.17, 0.17, 'CX_Sheet', col=_lin('#4B5053'))


def park_light(mb, x, y, z0):
    from nk_geo import Frame
    metal = _lin('#3F4447')
    fr = Frame((x, y), (1.0, 0.0), z0)
    _cyl(mb, x, y, z0, z0 + 3.28, 0.06, 0.045, 'CX_Sheet', metal)
    mb.box(fr, -0.15, 0.15, 3.3, 3.75, -0.15, 0.15, 'CX_Frame', skip=('+b',))
    mb.box(fr, -0.2, 0.2, 3.75, 3.85, -0.2, 0.2, 'CX_Sheet', col=metal)


def bench(mb, x, y, fx, fy, z0):
    """Timber seat and back on two concrete legs, facing (fx, fy)."""
    from nk_geo import Frame
    fr = Frame((x, y), (-fy, fx), z0)
    for a in (-0.7, 0.62):
        mb.box(fr, a, a + 0.08, 0.0, 0.415, -0.25, 0.2, 'CX_Concrete', skip=('-b', '+b'))
    mb.box(fr, -0.9, 0.9, 0.42, 0.47, -0.28, 0.22, 'CX_Wood')
    mb.box(fr, -0.9, 0.9, 0.5, 0.88, -0.3, -0.26, 'CX_Wood')


def bin_(mb, x, y, z0):
    _cyl(mb, x, y, z0, z0 + 0.85, 0.24, 0.26, 'CX_Sheet', _lin('#39443F'), k=10)


def bike_rack(mb, x, y, ax, ay, n, z0):
    """Row of steel hoops (Sheffield stands) 0.9 m apart."""
    metal = _lin('#8A9094')
    nx, ny = -ay, ax
    for k in range(n):
        cx, cy = x + ax * k * 0.9, y + ay * k * 0.9
        a = (cx - nx * 0.35, cy - ny * 0.35)
        b = (cx + nx * 0.35, cy + ny * 0.35)
        _bar(mb, (a[0], a[1], z0), (a[0], a[1], z0 + 0.82), 0.025, 'CX_Sheet', metal)
        _bar(mb, (b[0], b[1], z0), (b[0], b[1], z0 + 0.82), 0.025, 'CX_Sheet', metal)
        _bar(mb, (a[0], a[1], z0 + 0.82), (b[0], b[1], z0 + 0.82), 0.025, 'CX_Sheet', metal)


def bollard(mb, x, y, z0):
    _cyl(mb, x, y, z0, z0 + 0.9, 0.1, 0.09, 'CX_Sheet', _lin('#43494D'), k=8)


def canopy(mb, x, y, ox, oy, w):
    """Glass-and-steel entrance canopy on the ground floor, 2.3 m deep (it shows beyond the balconies)."""
    from nk_geo import Frame
    fr = Frame((x, y), (oy, -ox), 3.35)      # a along the facade, c outward
    mb.box(fr, -w / 2, w / 2, 0.0, 0.14, 0.0, 2.3, 'CX_Sheet', col=_lin('#3E4347'))
    mb.box(fr, -w / 2 + 0.1, w / 2 - 0.1, 0.14, 0.18, 0.1, 2.2, 'CX_Frame')


def sign(mb, x, y, fx, fy, z0, kind):
    """Road sign on a 2.6 m post facing (fx, fy): 'crossing' (blue square, white triangle) or 'parking' (blue, white P)."""
    from nk_geo import Frame
    _cyl(mb, x, y, z0, z0 + 2.62, 0.035, 0.035, 'CX_Sheet', _lin('#9A9FA3'), k=6)
    fr = Frame((x, y), (-fy, fx), z0)                     # a across, c towards the reader
    mb.box(fr, -0.3, 0.3, 2.0, 2.6, 0.04, 0.07, 'NK_SignBlue')
    if kind == 'crossing':
        c = 0.072
        mb.add([fr.w([(-0.21, 2.1, c)])[0], fr.w([(0.21, 2.1, c)])[0], fr.w([(0.0, 2.48, c)])[0]], [(0, 1, 2)], 'NK_SignWhite')
    else:
        c = 0.072
        mb.box(fr, -0.13, -0.06, 2.1, 2.5, 0.07, c, 'NK_SignWhite')
        mb.box(fr, -0.06, 0.1, 2.43, 2.5, 0.07, c, 'NK_SignWhite')
        mb.box(fr, -0.06, 0.1, 2.28, 2.35, 0.07, c, 'NK_SignWhite')
        mb.box(fr, 0.1, 0.15, 2.3, 2.48, 0.07, c, 'NK_SignWhite')


def swing(mb, cx, cy, z0, along=(1.0, 0.0)):
    ax, ay = along
    nx, ny = -ay, ax
    frame = _lin('#2F6FA8')
    top = z0 + 2.3
    for s in (-1, 1):
        ex, ey = cx + ax * s * 2.0, cy + ay * s * 2.0
        for t in (-1, 1):
            _bar(mb, (ex + nx * t * 0.8, ey + ny * t * 0.8, z0), (ex, ey, top), 0.045, 'CX_Sheet', frame)
    _bar(mb, (cx - ax * 2.05, cy - ay * 2.05, top), (cx + ax * 2.05, cy + ay * 2.05, top), 0.055, 'CX_Sheet', frame)
    for s in (-0.8, 0.8):
        px, py = cx + ax * s, cy + ay * s
        for t in (-0.2, 0.2):
            _bar(mb, (px + ax * t, py + ay * t, top), (px + ax * t, py + ay * t, z0 + 0.5), 0.012, 'CX_Sheet', _lin('#8C9094'))
        _wbox_rot(mb, px, py, ax, ay, -0.24, 0.24, z0 + 0.46, z0 + 0.52, -0.12, 0.12, 'CX_Sheet', _lin('#C8392E'))


def _wbox_rot(mb, cx, cy, ax, ay, a0, a1, z0, z1, c0, c1, mat, col=None):
    from nk_geo import Frame
    mb.box(Frame((cx, cy), (ax, ay), 0.0), a0, a1, z0, z1, c0, c1, mat, col=col)


def slide_tower(mb, cx, cy, z0):
    """Play tower: platform on four posts, pitched roof, ladder, slide chute running +y."""
    post, deck, roof, chute = _lin('#E0B43A'), _lin('#8A6B4E'), _lin('#C8392E'), _lin('#3E8E4F')
    for dx in (-0.75, 0.75):
        for dy in (-0.75, 0.75):
            _cyl(mb, cx + dx, cy + dy, z0, z0 + 2.9, 0.06, 0.06, 'CX_Sheet', post, k=6)
    _wbox(mb, cx - 0.85, cx + 0.85, cy - 0.85, cy + 0.85, z0 + 1.35, z0 + 1.45, 'CX_Wood', deck)
    mb.add([(cx - 1.0, cy - 1.0, z0 + 2.9), (cx + 1.0, cy - 1.0, z0 + 2.9), (cx, cy, z0 + 3.55)], [(0, 1, 2)], 'CX_Sheet', roof)
    mb.add([(cx + 1.0, cy - 1.0, z0 + 2.9), (cx + 1.0, cy + 1.0, z0 + 2.9), (cx, cy, z0 + 3.55)], [(0, 1, 2)], 'CX_Sheet', roof)
    mb.add([(cx + 1.0, cy + 1.0, z0 + 2.9), (cx - 1.0, cy + 1.0, z0 + 2.9), (cx, cy, z0 + 3.55)], [(0, 1, 2)], 'CX_Sheet', roof)
    mb.add([(cx - 1.0, cy + 1.0, z0 + 2.9), (cx - 1.0, cy - 1.0, z0 + 2.9), (cx, cy, z0 + 3.55)], [(0, 1, 2)], 'CX_Sheet', roof)
    # chute from the deck edge down to the ground, 3.2 m long
    y0, y1 = cy + 0.85, cy + 4.0
    for s in (-1, 1):
        mb.add([(cx + s * 0.3, y0, z0 + 1.45), (cx + s * 0.3, y1, z0 + 0.3), (cx + s * 0.3, y1, z0 + 0.55), (cx + s * 0.3, y0, z0 + 1.7)],
               [(0, 1, 2, 3) if s > 0 else (3, 2, 1, 0)], 'CX_Sheet', chute)
    mb.add([(cx - 0.3, y0, z0 + 1.45), (cx + 0.3, y0, z0 + 1.45), (cx + 0.3, y1, z0 + 0.3), (cx - 0.3, y1, z0 + 0.3)], [(0, 1, 2, 3)], 'CX_Sheet', chute)
    # ladder on the -y side
    for s in (-0.25, 0.25):
        _bar(mb, (cx + s, cy - 1.6, z0), (cx + s, cy - 0.85, z0 + 1.45), 0.03, 'CX_Sheet', post)
    for k in range(1, 5):
        t = k / 5
        _bar(mb, (cx - 0.25, cy - 1.6 + 0.75 * t, z0 + 1.45 * t), (cx + 0.25, cy - 1.6 + 0.75 * t, z0 + 1.45 * t), 0.02, 'CX_Sheet', post)


def sandbox(mb, x0, x1, y0, y1, z0):
    w = 0.14
    for (a0, a1, b0, b1) in ((x0, x1, y0, y0 + w), (x0, x1, y1 - w, y1), (x0, x0 + w, y0 + w, y1 - w), (x1 - w, x1, y0 + w, y1 - w)):
        _wbox(mb, a0, a1, b0, b1, z0, z0 + 0.3, 'CX_Wood', skip=('-b',))
    mb.add([(x0 + w, y0 + w, z0 + 0.12), (x1 - w, y0 + w, z0 + 0.12), (x1 - w, y1 - w, z0 + 0.12), (x0 + w, y1 - w, z0 + 0.12)],
           [(0, 1, 2, 3)], 'NK_Sand')


def spring_rider(mb, x, y, z0, col):
    _cyl(mb, x, y, z0, z0 + 0.35, 0.09, 0.09, 'CX_Sheet', _lin('#6F7478'), k=6)
    _wbox(mb, x - 0.35, x + 0.35, y - 0.14, y + 0.14, z0 + 0.35, z0 + 0.75, 'CX_Sheet', _lin(col))


def seesaw(mb, cx, cy, z0):
    _wbox(mb, cx - 0.12, cx + 0.12, cy - 0.2, cy + 0.2, z0, z0 + 0.45, 'CX_Sheet', _lin('#2F6FA8'))
    _wbox(mb, cx - 1.8, cx + 1.8, cy - 0.13, cy + 0.13, z0 + 0.45, z0 + 0.52, 'CX_Sheet', _lin('#E0B43A'))


def court_gear(mb, court, z0):
    """Low perimeter fence (posts, two rails) and basketball hoops or football goals."""
    x0, x1, y0, y1 = court['rect']
    metal = _lin('#5E676C')
    m = 0.6
    X0, X1, Y0, Y1 = x0 - m, x1 + m, y0 - m, y1 + m
    for (a, b) in (((X0, Y0), (X1, Y0)), ((X1, Y0), (X1, Y1)), ((X1, Y1), (X0, Y1)), ((X0, Y1), (X0, Y0))):
        L = math.dist(a, b)
        n = max(1, int(L / 2.5))
        for k in range(n):
            t = k / n
            px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            _cyl(mb, px, py, z0, z0 + 1.25, 0.03, 0.03, 'CX_Sheet', metal, k=6)
        for h in (0.6, 1.2):
            _bar(mb, (a[0], a[1], z0 + h), (b[0], b[1], z0 + h), 0.02, 'CX_Sheet', metal)
    cx = 0.5 * (x0 + x1)
    if court['kind'] == 'basket':
        for s, yb in ((1, y1), (-1, y0)):
            py = yb + s * 1.2
            _cyl(mb, cx, py, z0, z0 + 3.4, 0.07, 0.07, 'CX_Sheet', metal, k=8)
            _bar(mb, (cx, py, z0 + 3.2), (cx, py - s * 1.05, z0 + 3.2), 0.04, 'CX_Sheet', metal)
            _wbox(mb, cx - 0.9, cx + 0.9, py - s * 1.1 - 0.03, py - s * 1.1 + 0.03, z0 + 2.9, z0 + 3.95, 'CX_Frame')
            for k in range(8):
                a0, a1 = 2 * math.pi * k / 8, 2 * math.pi * (k + 1) / 8
                c = (cx, py - s * 1.1 - s * 0.3)
                _bar(mb, (c[0] + 0.23 * math.cos(a0), c[1] + 0.23 * math.sin(a0), z0 + 3.05),
                     (c[0] + 0.23 * math.cos(a1), c[1] + 0.23 * math.sin(a1), z0 + 3.05), 0.012, 'CX_Sheet', _lin('#D2542C'))
    else:
        white = _lin('#EDEDE8')
        for yb in (y0 + 0.3, y1 - 0.3):
            for s in (-1.5, 1.5):
                _bar(mb, (cx + s, yb, z0), (cx + s, yb, z0 + 2.0), 0.05, 'CX_Sheet', white)
            _bar(mb, (cx - 1.5, yb, z0 + 2.0), (cx + 1.5, yb, z0 + 2.0), 0.05, 'CX_Sheet', white)


def pergola(mb, rect, z0):
    """Timber pergola: posts, two long beams, slats every 0.45 m (they draw a striped shade from above)."""
    x0, x1, y0, y1 = rect
    for x in (x0 + 0.15, x1 - 0.15):
        for y in (y0 + 0.2, 0.5 * (y0 + y1), y1 - 0.2):
            _wbox(mb, x - 0.09, x + 0.09, y - 0.09, y + 0.09, z0, z0 + 2.55, 'CX_Wood', skip=('-b',))
        _wbox(mb, x - 0.1, x + 0.1, y0, y1, z0 + 2.55, z0 + 2.75, 'CX_Wood')
    y = y0 + 0.2
    while y < y1 - 0.1:
        _wbox(mb, x0 - 0.3, x1 + 0.3, y - 0.04, y + 0.04, z0 + 2.75, z0 + 2.87, 'CX_Wood')
        y += 0.45
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    _wbox(mb, cx - 0.4, cx + 0.4, cy - 1.0, cy + 1.0, z0 + 0.72, z0 + 0.77, 'CX_Wood')
    _wbox(mb, cx - 0.1, cx + 0.1, cy - 0.6, cy + 0.6, z0, z0 + 0.72, 'CX_Concrete', skip=('-b',))


def solar_row(mb, x0, x1, y, z0):
    """A row of panels tilted 15 deg to the south on a low frame (panel depth 1.1 m)."""
    d, tilt = 1.1, math.radians(15)
    zl, zh = z0 + 0.25, z0 + 0.25 + d * math.sin(tilt)
    yl, yh = y - d * math.cos(tilt) / 2, y + d * math.cos(tilt) / 2
    mb.add([(x0, yl, zl), (x1, yl, zl), (x1, yh, zh), (x0, yh, zh)], [(0, 1, 2, 3)], 'NK_PV')
    mb.add([(x0, yh, zh), (x1, yh, zh), (x1, yh, z0), (x0, yh, z0)], [(0, 1, 2, 3)], 'CX_Sheet', _lin('#8C9094'))
    for x in (x0 + 0.1, 0.5 * (x0 + x1), x1 - 0.1):
        _wbox(mb, x - 0.04, x + 0.04, yl, yh, z0, zl - 0.01, 'CX_Sheet', _lin('#8C9094'), skip=('-b',))


def condenser(mb, x, y, z0):
    _wbox(mb, x - 0.5, x + 0.5, y - 0.38, y + 0.38, z0, z0 + 0.95, 'CX_ACUnit', skip=('-b',))
    k = 12
    c = (x, y)
    mb.add([(c[0] + 0.3 * math.cos(2 * math.pi * j / k), c[1] + 0.3 * math.sin(2 * math.pi * j / k), z0 + 0.955) for j in range(k)],
           [tuple(range(k))], 'NK_DarkMetal')


def roof_props(mb):
    """Roof equipment of block A (world coordinates; the caller mirrors it for B)."""
    R = roof_items()
    z = ROOF_Z
    for (x0, x1, y) in R['pv']:
        solar_row(mb, x0, x1, y, z)
    for (x, y, nx, ny) in R['ac']:
        for i in range(nx):
            for j in range(ny):
                condenser(mb, x + (i - (nx - 1) / 2) * 1.35, y + (j - (ny - 1) / 2) * 1.1, z)
    for (x, y) in R['fans']:
        _cyl(mb, x, y, z, z + 0.55, 0.22, 0.22, 'CX_ACUnit', None, k=10)
        _cyl(mb, x, y, z + 0.55, z + 0.72, 0.36, 0.1, 'CX_ACUnit', None, k=10)
    for (x, y) in R['hatches']:
        _wbox(mb, x - 0.55, x + 0.55, y - 0.55, y + 0.55, z, z + 0.45, 'CX_Sheet', _lin('#9A9C9B'), skip=('-b',))
    for (x, y) in R['pads']:
        _wbox(mb, x - 0.3, x + 0.3, y - 0.3, y + 0.3, z, z + 0.05, 'CX_Concrete', skip=('-b',))
    for (x, y) in R['drains']:
        mb.add([(x - 0.18, y - 0.18, z + 0.004), (x + 0.18, y - 0.18, z + 0.004), (x + 0.18, y + 0.18, z + 0.004), (x - 0.18, y + 0.18, z + 0.004)],
               [(0, 1, 2, 3)], 'NK_DarkMetal')
    for (x, y) in R['dishes']:
        _cyl(mb, x, y, z, z + 0.9, 0.03, 0.03, 'CX_Sheet', _lin('#8C9094'), k=6)
        _wbox(mb, x - 0.4, x + 0.4, y - 0.05, y + 0.05, z + 0.7, z + 1.4, 'CX_Frame')


def build(mb_w, mb_e, roads):
    """Everything above the ground that is new in v0.12 (plus the v0.11 street and park lights), split
    west/east (x < 0 / x >= 0) like the context atlases. Returns counts."""
    from nk_osm import street_lamps, SITE_ZONE, inside, ZEBRAS, BAY_X, west_bays
    n = {}

    def mb_at(x):
        return mb_w if x < 0 else mb_e

    def add(k, v=1):
        n[k] = n.get(k, 0) + v
    for (x, y, ax, ay, _kind) in street_lamps():
        street_light(mb_at(x), x, y, ax, ay, gz(0.14 if inside(SITE_ZONE, x, y) else 0.10))
        add('street lights')
    lamps, benches = park_items(roads)
    for (x, y) in lamps:
        park_light(mb_at(x), x, y, gz(0.06))
        add('park lights')
    for (x, y, fx, fy) in benches:
        bench(mb_at(x), x, y, fx, fy, gz(0.06))
        add('benches')
    P = plaza_items()
    for (x, y, fx, fy) in P['benches']:
        bench(mb_at(x), x, y, fx, fy, gz(Z_PAVE))
        add('benches')
    for (x, y) in P['bins']:
        bin_(mb_at(x), x, y, gz(Z_PAVE))
        add('bins')
    for (x, y, ax, ay, k) in P['racks']:
        bike_rack(mb_at(x), x, y, ax, ay, k, gz(Z_PAVE))
        add('bike stands', k)
    for (x, y) in P['bollards']:
        bollard(mb_at(x), x, y, gz(Z_PAVE))
        add('bollards')
    for (x, y, ox, oy, w) in P['canopies']:
        canopy(mb_at(x), x, y, ox, oy, w)
        add('canopies')
    for block in ('A', 'B'):
        C = courtyard_layout(block)
        z = gz(Z_LAWN)
        for (x, y, fx, fy) in C['benches']:
            bench(mb_at(x), x, y, fx, fy, z)
            add('benches')
        for (x, y) in C['lamps']:
            park_light(mb_at(x), x, y, z)
            add('park lights')
        x0, x1, y0, y1 = C['playground']
        s = 1.0 if block == 'A' else -1.0
        mb = mb_at(x0)
        cxp = 0.5 * (x0 + x1)
        swing(mb, cxp - s * 2.5, y1 - 2.4, z)
        slide_tower(mb, cxp + s * 3.8, y0 + 3.0, z)
        sandbox(mb, cxp - s * 4.5 - 1.6, cxp - s * 4.5 + 1.6, y0 + 1.8, y0 + 4.6, z)
        spring_rider(mb, cxp + s * 0.6, y0 + 7.4, z, '#E0B43A')
        spring_rider(mb, cxp - s * 0.8, y0 + 8.4, z, '#3E8E4F')
        seesaw(mb, cxp + s * 4.2, y1 - 2.2, z)
        court_gear(mb_at(C['court']['rect'][0]), C['court'], z)
        pergola(mb_at(C['pergola'][0]), C['pergola'], z)
        add('playgrounds')
    # road signs: crossing signs on both kerbs of every zebra, one parking sign at the bays
    for (c, t, w) in ZEBRAS:
        nx, ny = -t[1], t[0]
        for side in (1, -1):
            x, y = c[0] + nx * side * (w / 2 + 0.55) + t[0] * 2.1, c[1] + ny * side * (w / 2 + 0.55) + t[1] * 2.1
            sign(mb_at(x), x, y, t[0], t[1], gz(0.14 if inside(SITE_ZONE, x, y) or BAY_X[0] <= x <= BAY_X[1] else 0.10), 'crossing')
            add('signs')
    y0 = west_bays()[0][0][0]
    sign(mb_w, BAY_X[1] + 0.35, y0 - 0.6, 0.0, -1.0, gz(Z_PAVE), 'parking')
    add('signs')
    # roofs: block A, mirrored for B
    from nk_geo import MeshBuilder
    ra = MeshBuilder()
    roof_props(ra)
    mb_w.chunks += ra.chunks
    base = mb_w.nv
    mb_w.faces += [[base + i for i in f] for f in ra.faces]
    mb_w.fmat += ra.fmat
    mb_w.fcol += ra.fcol
    mb_w.nv += ra.nv
    import numpy as np
    Vb = np.concatenate(ra.chunks, axis=0) * np.array([-1.0, 1.0, 1.0])
    base = mb_e.nv
    mb_e.chunks.append(Vb)
    mb_e.faces += [[base + i for i in reversed(f)] for f in ra.faces]
    mb_e.fmat += ra.fmat
    mb_e.fcol += ra.fcol
    mb_e.nv += len(Vb)
    add('roof items', len(ra.faces))
    print('street life props:', n)
    return n
