"""New Komitas exterior - site: ground, streets, raised pavements with curbs, courtyards.

Layout (world metres, X east, Y north): blocks A x[-122,-11] and B x[11,122], y[-48,55].
Streets are schematic (the real surroundings are an industrial / low-rise mix); the
courtyard programme follows the developer video (sports courts, pitch, playground, lawns).
"""
import math

import numpy as np
from nk_geo import MeshBuilder, WORLD

Z_ROAD, Z_PAVE, Z_LAWN = 0.02, 0.14, 0.16


def rect(mb, x0, x1, y0, y1, z, mat, curb=False, zb=None):
    mb.add([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [(0, 1, 2, 3)], mat)
    if curb:
        zb = Z_ROAD if zb is None else zb
        for (a, b) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            mb.add([(a[0], a[1], zb), (b[0], b[1], zb), (b[0], b[1], z), (a[0], a[1], z)], [(0, 1, 2, 3)], 'NK_Curb')


def lines_parking(mb, x0, x1, y, n, depth, z, pitch=2.6, facing=1):
    for i in range(n + 1):
        x = x0 + i * pitch
        if x > x1:
            break
        y1 = y + depth * facing
        ya, yb = min(y, y1), max(y, y1)
        rect(mb, x - 0.06, x + 0.06, ya, yb, z + 0.003, 'NK_LineWhite')


def court(mb, cx, cy, sx, sy, mat, z=Z_PAVE + 0.01):
    rect(mb, cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z, mat)
    # white boundary lines
    t = 0.08
    zl = z + 0.003
    rect(mb, cx - sx / 2 + 1, cx + sx / 2 - 1, cy - sy / 2 + 1, cy - sy / 2 + 1 + t, zl, 'NK_LineWhite')
    rect(mb, cx - sx / 2 + 1, cx + sx / 2 - 1, cy + sy / 2 - 1 - t, cy + sy / 2 - 1, zl, 'NK_LineWhite')
    rect(mb, cx - sx / 2 + 1, cx - sx / 2 + 1 + t, cy - sy / 2 + 1, cy + sy / 2 - 1, zl, 'NK_LineWhite')
    rect(mb, cx + sx / 2 - 1 - t, cx + sx / 2 - 1, cy - sy / 2 + 1, cy + sy / 2 - 1, zl, 'NK_LineWhite')
    rect(mb, cx - t / 2, cx + t / 2, cy - sy / 2 + 1, cy + sy / 2 - 1, zl, 'NK_LineWhite')


def courtyard(mb, mirror):
    """Courtyard ground (v0.12 design in nk_furniture.courtyard_layout): lawns with kerb frames on the paved
    walk along the facades, a light stone loop path with spurs to the entrances, flower beds, a sports court
    in a paved surround, a rubber-surfaced playground and a paved floor under the pergola."""
    from nk_furniture import courtyard_layout, ellipse
    C = courtyard_layout('B' if mirror else 'A')
    for (x0, x1, y0, y1) in C['lawns']:
        rect(mb, x0, x1, y0, y1, Z_LAWN, 'NK_LawnCourt', curb=True, zb=Z_PAVE)
    # kerb frames only where a lawn meets the walk (1 m pieces; seams between lawn pieces stay open)
    t = 0.12
    for (x0, x1, y0, y1) in C['lawns']:
        edges = [((x0, y0), (x1, y0), (0, -1)), ((x0, y1), (x1, y1), (0, 1)), ((x0, y0 + t), (x0, y1 - t), (-1, 0)), ((x1, y0 + t), (x1, y1 - t), (1, 0))]
        for (a, b, (ox, oy)) in edges:
            L = math.dist(a, b)
            n = max(1, int(round(L / 1.0)))
            for k in range(n):
                u0, u1 = k / n, (k + 1) / n
                pa = (a[0] + (b[0] - a[0]) * u0, a[1] + (b[1] - a[1]) * u0)
                pb = (a[0] + (b[0] - a[0]) * u1, a[1] + (b[1] - a[1]) * u1)
                mx, my = 0.5 * (pa[0] + pb[0]) + ox * 0.5, 0.5 * (pa[1] + pb[1]) + oy * 0.5
                if _in_lawns(C, mx, my):
                    continue
                if oy:
                    rect(mb, pa[0], pb[0], y0 if oy < 0 else y1 - t, y0 + t if oy < 0 else y1, Z_LAWN + 0.002, 'NK_Curb')
                else:
                    rect(mb, x0 if ox < 0 else x1 - t, x0 + t if ox < 0 else x1, pa[1], pb[1], Z_LAWN + 0.002, 'NK_Curb')
    for (c, r) in C['beds']:
        fill_poly(mb, ellipse(c, r, 28), Z_LAWN + 0.0035, 'NK_Flowers')
    loop = C['loop']
    ribbon(mb, loop + [loop[0]], 2.4, Z_LAWN + 0.0065, 'NK_CourtPath')
    for sp in C['spurs']:
        ribbon(mb, sp, 2.2, Z_LAWN + 0.0058, 'NK_CourtPath')
    x0, x1, y0, y1 = C['court']['rect']
    rect(mb, x0 - 1.0, x1 + 1.0, y0 - 1.0, y1 + 1.0, Z_LAWN + 0.0092, 'NK_PaversDark')
    court(mb, 0.5 * (x0 + x1), 0.5 * (y0 + y1), x1 - x0, y1 - y0, C['court']['mat'], z=Z_LAWN + 0.011)
    x0, x1, y0, y1 = C['playground']
    rect(mb, x0, x1, y0, y1, Z_LAWN + 0.0105, 'NK_PlayRubber')
    sw = 0.5 * (x0 + x1) + (-2.5 if not mirror else 2.5)
    rect(mb, sw - 2.8, sw + 2.8, y1 - 4.3, y1 - 0.5, Z_LAWN + 0.0122, 'NK_RubberGreen')
    x0, x1, y0, y1 = C['pergola']
    rect(mb, x0 - 0.6, x1 + 0.6, y0 - 0.6, y1 + 0.6, Z_LAWN + 0.0095, 'NK_Pavers')


def court_clear(C, x, y, pad=0.0):
    """True if (x, y) keeps clear of the courtyard's paths, court, playground, pergola and flower beds."""
    for P, w in [(C['loop'] + [C['loop'][0]], 2.4)] + [(sp, 2.2) for sp in C['spurs']]:
        if any(_seg_d2(x, y, P[i], P[i + 1]) < (w / 2 + 1.3 + pad) ** 2 for i in range(len(P) - 1)):
            return False
    for key, m in (('playground', 1.2), ('pergola', 1.2)):
        x0, x1, y0, y1 = C[key]
        if x0 - m - pad < x < x1 + m + pad and y0 - m - pad < y < y1 + m + pad:
            return False
    x0, x1, y0, y1 = C['court']['rect']
    if x0 - 1.8 - pad < x < x1 + 1.8 + pad and y0 - 1.8 - pad < y < y1 + 1.8 + pad:
        return False
    for (c, r) in C['beds']:
        if ((x - c[0]) / (r[0] + 0.8 + pad)) ** 2 + ((y - c[1]) / (r[1] + 0.8 + pad)) ** 2 < 1:
            return False
    return True


def _in_lawns(C, x, y):
    return any(l[0] < x < l[1] and l[2] < y < l[3] for l in C['lawns'])


def courtyard_planting(rng, cam_ok=lambda x, y: True):
    """Courtyard trees at the designed spots and shrubs along the lawns' outer edges (not across seams)."""
    from nk_furniture import courtyard_layout
    T = []
    for block in ('A', 'B'):
        C = courtyard_layout(block)
        for (x, y, sp) in C['trees']:
            if cam_ok(x, y):
                T.append((x + float(rng.uniform(-0.3, 0.3)), y + float(rng.uniform(-0.3, 0.3)), Z_LAWN, sp, float(rng.uniform(0.8, 1.02))))
        for (x0, x1, y0, y1) in C['lawns']:
            cand = [(x, y0 + 0.9, 0, -1) for x in np.arange(x0 + 1.2, x1 - 1.0, 2.3)] + \
                   [(x, y1 - 0.9, 0, 1) for x in np.arange(x0 + 1.2, x1 - 1.0, 2.3)] + \
                   [(x0 + 0.9, y, -1, 0) for y in np.arange(y0 + 1.2, y1 - 1.0, 2.3)] + \
                   [(x1 - 0.9, y, 1, 0) for y in np.arange(y0 + 1.2, y1 - 1.0, 2.3)]
            for (x, y, ox, oy) in cand:
                if _in_lawns(C, x + ox * 2.0, y + oy * 2.0):
                    continue                                          # a seam between lawn pieces
                if rng.random() < 0.62 and court_clear(C, x, y, -0.6) and cam_ok(x, y):
                    T.append((float(x + rng.uniform(-0.3, 0.3)), float(y), Z_LAWN, 'Shrub', float(rng.uniform(0.7, 1.25))))
        for (c, r) in C['beds'][1:]:
            for k in range(5):
                a = 2 * math.pi * (k + rng.uniform(0, 0.5)) / 5
                x, y = c[0] + (r[0] + 0.5) * math.cos(a), c[1] + (r[1] + 0.5) * math.sin(a)
                if rng.random() < 0.7 and cam_ok(x, y):
                    T.append((x, y, Z_LAWN, 'Shrub', float(rng.uniform(0.55, 0.9))))
    return T


def plaza_bands(p):
    """Plaza paving pattern: a 1.2 m dark band along both blocks' outer facades and 0.6 m cross bands every
    8 m to the plaza edge (bands under the raised lawn strips stay hidden)."""
    d = 1.2
    OUT = [(-111, -48), (-11, -48), (-11, 48), (-76, 48), (-76, 55), (-122, 55), (-122, -3), (-111, -3)]
    for s in (1, -1):
        P = [(s * x, y) for x, y in OUT]
        if s < 0:
            P = P[::-1]
        n = len(P)
        nrm = []
        for i in range(n):
            (x0, y0), (x1, y1) = P[i], P[(i + 1) % n]
            L = math.hypot(x1 - x0, y1 - y0)
            nrm.append(((y1 - y0) / L, -(x1 - x0) / L))                   # outward for a CCW ring
        off = [(P[i][0] + d * (nrm[i - 1][0] + nrm[i][0]), P[i][1] + d * (nrm[i - 1][1] + nrm[i][1])) for i in range(n)]
        for i in range(n):
            j = (i + 1) % n
            q = [(P[i][0], P[i][1], Z_PAVE + 0.0015), (P[j][0], P[j][1], Z_PAVE + 0.0015),
                 (off[j][0], off[j][1], Z_PAVE + 0.0015), (off[i][0], off[i][1], Z_PAVE + 0.0015)]
            p.add(q, [(0, 1, 2, 3)], 'NK_PaversDark')
        zb = Z_PAVE + 0.0011
        for y in np.arange(-44.0, 63.0, 8.0):                                   # west (A) / east (B) side
            xf = -112.2 if y < -3 else -123.2
            if s > 0:
                rect(p, WEST_LAWN_X[1] + 0.2, xf, y - 0.3, y + 0.3, zb, 'NK_PaversDark')
            else:
                rect(p, -xf, 126.8, y - 0.3, y + 0.3, zb, 'NK_PaversDark')
        for x in np.arange(-118.0, -8.0, 8.0):                                  # north and south sides
            xs = s * x
            yf = 56.2 if x < -76 else 49.2
            rect(p, min(xs - 0.3, xs + 0.3), max(xs - 0.3, xs + 0.3), yf, 63.8, zb, 'NK_PaversDark')
            rect(p, min(xs - 0.3, xs + 0.3), max(xs - 0.3, xs + 0.3), -65.8, -49.2, zb, 'NK_PaversDark')


def ground_details(r, p, roads):
    """Manholes and kerb drains on the streets around the site, oil stains in the parking bays (soft rings),
    tactile paving at the zebra ends."""
    from nk_furniture import ground_details as layout, ellipse
    G = layout(roads)
    for (x, y, z) in G['manholes']:
        fill_poly(r, ellipse((x, y), (0.36, 0.36), 14), z, 'NK_DarkMetal')
    for (x, y, tx, ty, z) in G['drains']:
        nx, ny = -ty, tx
        q = [(x - tx * 0.3 - nx * 0.15, y - ty * 0.3 - ny * 0.15), (x + tx * 0.3 - nx * 0.15, y + ty * 0.3 - ny * 0.15),
             (x + tx * 0.3 + nx * 0.15, y + ty * 0.3 + ny * 0.15), (x - tx * 0.3 + nx * 0.15, y - ty * 0.3 + ny * 0.15)]
        fill_poly(r, q, z, 'NK_DarkMetal')
    rng = np.random.default_rng(41)
    zb = Z_ROAD + 0.0068
    for (x, y) in G['stains']:
        rx, ry = rng.uniform(0.55, 0.85), rng.uniform(0.4, 0.6)
        k = 16
        wob = [1 + 0.18 * math.sin(3 * 2 * math.pi * j / k + rng.uniform(0, 6)) for j in range(k)]
        rings = [(1.0, 0.93), (0.72, 0.82), (0.45, 0.72), (0.2, 0.64)]
        for (f, c) in rings:
            pts = [(x + rx * f * wob[j] * math.cos(2 * math.pi * j / k), y + ry * f * wob[j] * math.sin(2 * math.pi * j / k), zb + 0.0002 * rings.index((f, c)))
                   for j in range(k)]
            r.add(pts, [tuple(range(k))], 'NK_AsphaltStain', (c, c, c, 1.0))
    for (x, y, nx, ny, z) in G['tactile']:
        tx, ty = -ny, nx
        q = [(x - tx * 0.9 - nx * 0.3, y - ty * 0.9 - ny * 0.3, z), (x + tx * 0.9 - nx * 0.3, y + ty * 0.9 - ny * 0.3, z),
             (x + tx * 0.9 + nx * 0.3, y + ty * 0.9 + ny * 0.3, z), (x - tx * 0.9 + nx * 0.3, y - ty * 0.9 + ny * 0.3, z)]
        p.add(q, [(0, 1, 2, 3)], 'NK_Tactile')
    print('ground details:', {k: len(v) for k, v in G.items()})


def build_site(col, M, rng):
    g = MeshBuilder()     # ground / grass
    r = MeshBuilder()     # roads
    p = MeshBuilder()     # pavements, courtyards, curbs, markings
    # big ground plane in tiles (keeps UV magnitudes sane)
    for i in range(-4, 4):
        for j in range(-4, 4):
            rect(g, i * 200, (i + 1) * 200, j * 200, (j + 1) * 200, 0.0, 'NK_Ground')
    for (x0, x1, y0, y1) in ((-3000, 3000, 800, 3000), (-3000, 3000, -3000, -800),
                             (-3000, -800, -800, 800), (800, 3000, -800, 800)):
        rect(g, x0, x1, y0, y1, -0.05, 'NK_Ground')
    # streets
    rect(r, -800, 800, -76, -63, Z_ROAD, 'NK_Asphalt')      # south street
    rect(r, -800, 800, 69, 79, Z_ROAD, 'NK_Asphalt')        # north street (Arghutyan side)
    rect(r, -150, -138, -63, 69, Z_ROAD, 'NK_Asphalt')      # west street
    rect(r, 138, 150, -63, 69, Z_ROAD, 'NK_Asphalt')        # east street (Griboyedov side)
    rect(r, -4.5, 4.5, -63, 69, Z_ROAD, 'NK_Asphalt')       # central drive between blocks
    # centre lines
    for x in np.arange(-790, 790, 9.0):
        rect(r, x, x + 4.5, -69.6, -69.4, Z_ROAD + 0.003, 'NK_LineWhite')
        rect(r, x, x + 4.5, 73.9, 74.1, Z_ROAD + 0.003, 'NK_LineWhite')
    # raised pavements / plazas around the blocks (courtyards included)
    rect(p, -138, -4.5, -63, 69, Z_PAVE, 'NK_Pavers', curb=True)
    rect(p, 4.5, 138, -63, 69, Z_PAVE, 'NK_Pavers', curb=True)
    rect(p, -800, 800, -82, -76, Z_PAVE, 'NK_Pavers', curb=True)   # far pavement south
    rect(p, -800, 800, 79, 85, Z_PAVE, 'NK_Pavers', curb=True)
    # street-side lawn strips along the south facade (as in the renders)
    for sx in (-1, 1):
        for (x0, x1) in ((-130, -100), (-95, -70), (-65, -40), (-35, -14)):
            a, b = sorted((x0 * sx, x1 * sx))
            rect(p, a, b, -61.0, -55.0, Z_LAWN, 'NK_Grass', curb=True, zb=Z_PAVE)
    # parking bays along the west street (block A) and east street (block B)
    for sx in (-1, 1):
        a, b = sorted((sx * -136.5, sx * -131.5))
        rect(p, a, b, -40, 40, Z_ROAD + 0.001, 'NK_Asphalt')
    courtyard(p, mirror=False)
    courtyard(p, mirror=True)
    for mb, name in ((g, 'NK_Site_Ground'), (r, 'NK_Site_Roads'), (p, 'NK_Site_Paving')):
        mb.to_object(name, col, M, merge=False)


# ---- vegetation layout ---------------------------------------------------------------------
BLOCK_ZONE = (-160.0, 160.0, -86.0, 88.0)
ROADS = [(-2000, 2000, -76.5, -62.5), (-2000, 2000, 68.5, 79.5), (-150.5, -137.5, -63, 69),
         (137.5, 150.5, -63, 69)]
FOOTPRINTS = [(-123.0, -10.0, -49.0, 56.0), (10.0, 123.0, -49.0, 56.0)]   # buildings + balconies


def _in(r, x, y, pad=0.0):
    return r[0] - pad <= x <= r[1] + pad and r[2] - pad <= y <= r[3] + pad


def _vnoise(x, y, seed=0, scale=90.0):
    """Cheap smooth value noise for clustering (0..1)."""
    import math
    def h(i, j):
        n = (i * 374761393 + j * 668265263 + seed * 1442695041) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return (n & 0xFFFF) / 65535.0
    fx, fy = x / scale, y / scale
    i, j = math.floor(fx), math.floor(fy)
    tx, ty = fx - i, fy - j
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    a = h(i, j) * (1 - tx) + h(i + 1, j) * tx
    b = h(i, j + 1) * (1 - tx) + h(i + 1, j + 1) * tx
    return a * (1 - ty) + b * ty


def tree_layout(rng, cams, feet=()):
    """Returns [(x, y, z, species, scale)]. cams: [(pos, target)] kept clear of trees;
    feet: [(x, y, r)] context-building footprints to avoid."""
    T = []
    import math
    cell = 60.0
    grid = {}
    for (fx, fy, fr) in feet:
        grid.setdefault((int(math.floor(fx / cell)), int(math.floor(fy / cell))), []).append((fx, fy, fr))

    def near_building(x, y):
        i, j = int(math.floor(x / cell)), int(math.floor(y / cell))
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for (fx, fy, fr) in grid.get((i + di, j + dj), ()):
                    if (x - fx) ** 2 + (y - fy) ** 2 < (fr + 3.0) ** 2:
                        return True
        return False

    def blocked(x, y, r=4.0):
        for (cx, cy), (tx, ty) in cams:
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy < 30.0 ** 2:
                return True
            vx, vy = tx - cx, ty - cy
            L = (vx * vx + vy * vy) ** 0.5
            vx, vy = vx / L, vy / L
            along = dx * vx + dy * vy
            across = abs(-dx * vy + dy * vx)
            if 0 < along < 170 and across < 10 + along * 0.18:
                return True
        if any(_in(rr, x, y, r * 0.6) for rr in ROADS):
            return True
        if any(_in(f, x, y, r) for f in FOOTPRINTS):
            return True
        if near_building(x, y):
            return True
        return False

    def add(x, y, z, sp, s0=0.85, s1=1.12, force=False):
        if force or not blocked(x, y):
            T.append((x, y, z, sp, float(rng.uniform(s0, s1))))

    # street trees
    for sx in (-1, 1):
        for (x0, x1) in ((-130, -100), (-95, -70), (-65, -40), (-35, -14)):
            for x in np.arange(x0 + 4, x1 - 2, 8.5):
                add(sx * x, -58.0 + rng.uniform(-0.5, 0.5), Z_LAWN, 'Linden', 0.8, 1.0)
        for y in np.arange(-52, 64, 10.5):
            add(sx * 129.5, y, Z_PAVE, 'Maple', 0.8, 1.05)
            add(sx * 156.0, y + 4, 0.0, 'Plane', 0.85, 1.1)
    for x in np.arange(-560, 560, 11.0):
        add(x + rng.uniform(-1, 1), -79.0, Z_PAVE, 'Plane', 0.85, 1.1)
        add(x + 5 + rng.uniform(-1, 1), 82.0, Z_PAVE, 'Linden', 0.85, 1.1)
    # courtyards (A courtyard lawns; mirrored for B)
    for sx in (-1, 1):
        for (x0, x1, y0, y1) in ((-90, -64, -27.5, -6), (-58, -32, -27.5, -18), (-60, -32, 18, 27.5), (-101, -80, 4, 34)):
            a, b = sorted((x0 * sx, x1 * sx))
            n = max(2, int((b - a) * (y1 - y0) / 110))
            pts = []
            for _ in range(n * 6):
                if len(pts) >= n:
                    break
                x, y = rng.uniform(a + 2.5, b - 2.5), rng.uniform(y0 + 2.5, y1 - 2.5)
                if all((x - p[0]) ** 2 + (y - p[1]) ** 2 > 36 for p in pts):
                    pts.append((x, y))
            for (x, y) in pts:
                sp = rng.choice(['Maple', 'Birch', 'Linden', 'Maple'])
                T.append((x, y, Z_LAWN, sp, float(rng.uniform(0.7, 0.95))))
            # shrubs along the lawn edges
            for x in np.arange(a + 1.2, b - 1.0, 2.2):
                for y in (y0 + 0.9, y1 - 0.9):
                    if rng.random() < 0.7:
                        T.append((x + rng.uniform(-0.3, 0.3), y, Z_LAWN, 'Shrub', float(rng.uniform(0.7, 1.3))))
    # shrubs in the south lawn strips
    for sx in (-1, 1):
        for (x0, x1) in ((-130, -100), (-95, -70), (-65, -40), (-35, -14)):
            for x in np.arange(x0 + 1.5, x1 - 1, 1.9):
                if rng.random() < 0.75:
                    T.append((sx * x, -55.9 - rng.uniform(0, 0.8), Z_LAWN, 'Shrub', float(rng.uniform(0.8, 1.4))))
    # parkland around the site: clustered, denser near the site, open meadows in between
    step = 13.0
    for gx in np.arange(-620, 620, step):
        for gy in np.arange(-620, 620, step):
            x = gx + rng.uniform(-step * 0.45, step * 0.45)
            y = gy + rng.uniform(-step * 0.45, step * 0.45)
            if _in(BLOCK_ZONE, x, y):
                continue
            dens = _vnoise(x, y, 3, 85.0)
            if dens < 0.27 or rng.random() > (dens - 0.27) * 2.8:
                continue
            r = rng.random()
            sp = 'Plane' if r < 0.35 else 'Linden' if r < 0.62 else 'Maple' if r < 0.8 else 'Poplar' if r < 0.92 else 'Birch'
            add(x, y, 0.0, sp, 0.8, 1.15)
    return T


def meadow(col, M, name, cam, target, depth=65.0, width=90.0, count=450000, seed=1):
    """Foreground grass: hair particles on a patch in front of a ground-level camera."""
    import bpy, math
    cx, cy = cam
    dx, dy = target[0] - cx, target[1] - cy
    L = math.hypot(dx, dy)
    fx, fy = dx / L, dy / L
    sx, sy = fy, -fx
    pts = []
    for (u, v) in ((-width / 2, 2.0), (width / 2, 2.0), (width / 2, depth), (-width / 2, depth)):
        pts.append((cx + sx * u + fx * v, cy + sy * u + fy * v, 0.005))
    me = bpy.data.meshes.new(name)
    me.from_pydata(pts, [], [(0, 1, 2, 3)])
    me.materials.append(M['NK_Grass'])
    me.uv_layers.new(name='UVMap')
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    # subdivide so particles distribute evenly and the ground UVs stay sane
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=24, use_grid_fill=True)
    bm.to_mesh(me)
    bm.free()
    uvl = me.uv_layers[0]
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = (co.x, co.y)
    mod = ob.modifiers.new('Grass', 'PARTICLE_SYSTEM')
    ps = ob.particle_systems[0]
    ps.seed = seed
    st = ps.settings
    st.name = name + '_hair'
    st.type = 'HAIR'
    st.count = count
    st.use_advanced_hair = False
    st.hair_length = 0.30
    st.emit_from = 'FACE'
    st.use_even_distribution = True
    st.distribution = 'RAND'
    st.length_random = 0.6
    st.display_step = 2
    st.render_step = 3
    st.child_type = 'NONE'
    st.root_radius = 1.0
    st.tip_radius = 0.0
    st.radius_scale = 0.006
    st.use_close_tip = True
    me.materials.append(M['NK_GrassBlade'])
    st.material_slot = 'NK_GrassBlade'
    return ob


# ---- real surroundings from OpenStreetMap ---------------------------------------------------------
ROAD_W = {'primary': 15.0, 'secondary': 12.0, 'tertiary': 10.5, 'tertiary_link': 7.0, 'residential': 7.0,
          'unclassified': 6.5, 'living_street': 5.5, 'service': 4.6, 'track': 3.0, 'pedestrian': 5.0,
          'footway': 2.2, 'path': 1.8, 'steps': 2.2, 'cycleway': 2.0, 'park_path': 3.0}
ROAD_Z = {'primary': 0.030, 'secondary': 0.028, 'tertiary': 0.026, 'tertiary_link': 0.025, 'residential': 0.024,
          'unclassified': 0.023, 'living_street': 0.022, 'service': 0.020, 'track': 0.016, 'pedestrian': 0.06,
          'footway': 0.06, 'path': 0.018, 'steps': 0.06, 'cycleway': 0.05, 'park_path': 0.058}
ROAD_M = {'track': 'NK_Soil', 'path': 'NK_Soil', 'footway': 'NK_PaversDark', 'steps': 'NK_PaversDark',
          'pedestrian': 'NK_Pavers', 'cycleway': 'NK_PaversDark', 'park_path': 'NK_ParkPath'}
SIDEWALK = {'primary', 'secondary', 'tertiary', 'residential'}
VEHICLE = {'primary', 'secondary', 'tertiary', 'tertiary_link', 'residential', 'unclassified', 'living_street', 'service'}
MARKED = {'primary', 'secondary', 'tertiary', 'residential'}    # dashed centre line when two-way
MARK_RADIUS = 480.0                                             # markings only where the ground tiles are sharp
Z_ZEBRA = 0.0455                                                # above every residential carriageway (<= 0.042)
OUR_OUTLINES = {'168103776', '1184741103'}     # OSM traces of our two blocks


def road_width(rd):
    w = ROAD_W[rd['kind']]
    if rd.get('lanes') and rd['kind'] in ('primary', 'secondary', 'tertiary'):
        try:
            w = max(w, 3.3 * float(rd['lanes']))
        except ValueError:
            pass
    return w


def _offset(pts, d):
    """Polyline offset to the left by d (mitred)."""
    P = [np.array(p, float) for p in pts]
    out = []
    n = len(P)
    for i in range(n):
        if i == 0:
            t = P[1] - P[0]
        elif i == n - 1:
            t = P[-1] - P[-2]
        else:
            a = P[i] - P[i - 1]
            b = P[i + 1] - P[i]
            a /= max(np.linalg.norm(a), 1e-9)
            b /= max(np.linalg.norm(b), 1e-9)
            t = a + b
            if np.linalg.norm(t) < 1e-6:
                t = b
        t /= max(np.linalg.norm(t), 1e-9)
        nl = np.array([-t[1], t[0]])
        m = 1.0
        if 0 < i < n - 1:
            a = P[i] - P[i - 1]
            a /= max(np.linalg.norm(a), 1e-9)
            m = 1.0 / max(0.7, abs(float(np.dot(nl, np.array([-a[1], a[0]])))))
        out.append(P[i] + nl * d * m)
    return out


def _clean(pts):
    out = []
    for p in pts:
        if not out or (abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1])) > 0.05:
            out.append(tuple(p))
    return out


def ribbon(mb, pts, w, z, mat):
    pts = _clean(pts)
    if len(pts) < 2:
        return
    L = _offset(pts, w / 2)
    R = _offset(pts, -w / 2)
    for i in range(len(pts) - 1):
        mb.add([(R[i][0], R[i][1], z), (R[i + 1][0], R[i + 1][1], z), (L[i + 1][0], L[i + 1][1], z),
                (L[i][0], L[i][1], z)], [(0, 1, 2, 3)], mat)


def fill_poly(mb, pts, z, mat):
    import mathutils
    pts = _clean(pts)
    if len(pts) < 3:
        return
    V = [(x, y, z) for x, y in pts]
    for t in mathutils.geometry.tessellate_polygon([[mathutils.Vector(v) for v in V]]):
        a, b, c = V[t[0]], V[t[1]], V[t[2]]
        nz = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        mb.add([a, b, c] if nz > 0 else [a, c, b], [(0, 1, 2)], mat)


def _arclen(P):
    return sum(math.dist(P[i], P[i + 1]) for i in range(len(P) - 1))


def _sub(P, a, b):
    """Part of polyline P between arc lengths a < b."""
    out, s = [], 0.0
    for i in range(len(P) - 1):
        p, q = P[i], P[i + 1]
        L = math.dist(p, q)
        if L < 1e-9:
            continue
        if s + L >= a and s <= b:
            u0, u1 = max(0.0, (a - s) / L), min(1.0, (b - s) / L)
            for u in (u0, u1):
                pt = (p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u)
                if not out or math.dist(out[-1], pt) > 1e-6:
                    out.append(pt)
        s += L
        if s >= b:
            break
    return out


def _cut(P, gaps, min_len=1.0):
    """P minus the arc-length intervals in gaps -> list of polylines."""
    L = _arclen(P)
    keep, s = [], 0.0
    for g0, g1 in sorted((max(0.0, a), min(L, b)) for a, b in gaps if b > 0 and a < L):
        if g0 > s:
            keep.append((s, g0))
        s = max(s, g1)
    if s < L:
        keep.append((s, L))
    return [q for q in (_sub(P, a, b) for a, b in keep if b - a >= min_len) if len(q) >= 2]


def junctions(roads):
    """Shared OSM nodes between vehicle roads. Per road id: {+1 / -1: arc-length intervals where that side's
    pavement and kerb stop (side-street mouths, crossings, ends on another street), 'dash': intervals
    without centre line}. +1 = left of the way's direction."""
    nodes = {}
    for rd in roads:
        if rd['kind'] not in VEHICLE:
            continue
        P = _clean(rd['pts'])
        s = 0.0
        for i, p in enumerate(P):
            if i:
                s += math.dist(P[i - 1], p)
            nodes.setdefault((round(p[0], 1), round(p[1], 1)), []).append((rd, i, s, P))

    def unit(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        return dx / L, dy / L
    out = {}
    for inc in nodes.values():
        if len(inc) < 2:
            continue
        for (rd, i, s, P) in inc:
            info = out.setdefault(rd['id'], {1: [], -1: [], 'dash': []})
            n, L = len(P), _arclen(P)
            t = unit(P[max(i - 1, 0)], P[min(i + 1, n - 1)])
            end = i == 0 or i == n - 1
            inward = unit(P[i], P[1 if i == 0 else n - 2]) if end else None
            for (q, j, _s, Q) in inc:
                if q is rd:
                    continue
                wq = road_width(q)
                for nb in (j - 1, j + 1):
                    if not 0 <= nb < len(Q):
                        continue
                    d = unit(Q[j], Q[nb])
                    if end and d[0] * inward[0] + d[1] * inward[1] < -0.82:
                        continue                                  # the same street continuing
                    cr = t[0] * d[1] - t[1] * d[0]
                    side = 1 if cr > 0 else -1
                    sn = max(0.35, abs(cr))
                    if end:
                        reach = (wq / 2 + 3.1) / sn
                        info[side].append((0.0, reach) if i == 0 else (L - reach, L))
                    else:
                        half = (wq / 2 + 1.5) / sn
                        info[side].append((s - half, s + half))
                    dz = (wq / 2 + 2.0) / sn
                    info['dash'].append((s - dz, s + dz))
    return out


def centre_line(mb, P, z, skip, dash=3.0, gap=5.0, width=0.15):
    """Dashed centre line (3 m / 5 m) along P, not through junctions or zebra crossings."""
    L = _arclen(P)
    s = 4.0
    while s + dash < L - 4.0:
        if not any(s < b and s + dash > a for a, b in skip):
            seg = _sub(P, s, s + dash)
            if len(seg) >= 2:
                ribbon(mb, seg, width, z, 'NK_LineWhite')
        s += dash + gap


def zebra(mb, c, t, w, z=Z_ZEBRA, length=3.0, pitch=1.0, stripe=0.5):
    tx, ty = t
    nx, ny = -ty, tx
    k = int((w - 1.0) / pitch)
    for i in range(k):
        o = (i - (k - 1) / 2) * pitch
        cx, cy = c[0] + nx * o, c[1] + ny * o
        ribbon(mb, [(cx - tx * length / 2, cy - ty * length / 2), (cx + tx * length / 2, cy + ty * length / 2)],
               stripe, z, 'NK_LineWhite')


def frame(mb, x0, x1, y0, y1, z, t, mat):
    """Kerb frame (seen from above) just inside a rectangle."""
    rect(mb, x0, x1, y0, y0 + t, z, mat)
    rect(mb, x0, x1, y1 - t, y1, z, mat)
    rect(mb, x0, x0 + t, y0 + t, y1 - t, z, mat)
    rect(mb, x1 - t, x1, y0 + t, y1 - t, z, mat)


def _zebra_skip(P):
    """Arc-length intervals of P that cross one of the zebra crossings (no centre line there)."""
    from nk_osm import ZEBRAS
    out, s = [], 0.0
    for i in range(len(P) - 1):
        L = math.dist(P[i], P[i + 1])
        for (c, _t, _w) in ZEBRAS:
            if _seg_d2(c[0], c[1], P[i], P[i + 1]) < 1.0:
                ax, ay = P[i]
                u = ((c[0] - ax) * (P[i + 1][0] - ax) + (c[1] - ay) * (P[i + 1][1] - ay)) / max(L * L, 1e-9)
                out.append((s + u * L - 3.5, s + u * L + 3.5))
        s += L
    return out


# The new street between the park and block A (nk_osm.west_street): carriageway, a park-side pavement,
# perpendicular bays against our plaza in groups of five with planted strips between them, a paved
# mid-block crossing, then a pavement on both sides where the street bends away north of the plaza.
WEST_EAST_FROM_Y = 58.0
WEST_LAWN_X = (-137.6, -131.6)
WEST_LAWNS = [(-58.0, -36.0), (-32.0, -16.5), (-7.5, 14.0), (18.0, 38.0), (42.0, 60.0)]


def west_street_site(r, p, rd, jn):
    from nk_osm import WEST_W, BAY_X, BAY_RUNS, west_bays
    P = _clean(rd['pts'])
    zr = ROAD_Z['residential'] + 0.0035
    ribbon(r, P, WEST_W, zr, 'NK_Asphalt')
    # arc length where the straight part reaches y = WEST_EAST_FROM_Y (east pavement starts there)
    s_east = math.dist(P[0], P[1]) + (WEST_EAST_FROM_Y - P[1][1])
    for side in (1, -1):
        gaps = list(jn.get(side, []))
        if side < 0:
            gaps.append((0.0, s_east))
        for piece in _cut(P, gaps):
            zs = 0.10 + _dz() + 0.0007           # off the 1.5 mm grid: never coplanar with a mapped pavement
            ribbon(p, [tuple(q) for q in _offset(piece, side * (WEST_W / 2 + 1.5))], 3.0, zs, 'NK_Pavers')
            ribbon(p, [tuple(q) for q in _offset(piece, side * (WEST_W / 2 + 0.1))], 0.2, zs + 0.0023, 'NK_Curb')
    centre_line(r, P, zr + 0.004, list(jn.get('dash', [])) + _zebra_skip(P))
    bays, planters = west_bays()
    zb = Z_ROAD + 0.006
    for (y0, y1) in bays:
        rect(r, BAY_X[0], BAY_X[1], y0, y1, zb, 'NK_Asphalt')
    for y in sorted({round(v, 3) for b in bays for v in b}):
        rect(r, BAY_X[0] + 0.2, BAY_X[1] - 0.3, y - 0.06, y + 0.06, zb + 0.003, 'NK_LineWhite')
    for (y0, y1) in planters:
        rect(p, BAY_X[0], BAY_X[1], y0, y1, Z_LAWN, 'NK_Grass', curb=True, zb=Z_ROAD)
        frame(p, BAY_X[0], BAY_X[1], y0, y1, Z_LAWN + 0.002, 0.15, 'NK_Curb')
    # plaza-level paving where there are no bays: the south corner, the crossing, north of the bays
    (a0, a1), (b0, b1) = BAY_RUNS
    for (y0, y1) in ((-66.0, a0), (a1, b0), (b1, 64.0)):
        rect(p, BAY_X[0], BAY_X[1], y0, y1, Z_PAVE, 'NK_Pavers', curb=True)
        rect(p, BAY_X[0], BAY_X[0] + 0.2, y0, y1, Z_PAVE + 0.003, 'NK_Curb')


def road_in_site(r, zone, frac=0.5):
    from nk_osm import inside
    pts = r['pts']
    k = sum(1 for x, y in pts if inside(zone, x, y, 3.0))
    return k >= max(1, frac * len(pts))


_LAYER = [0]


def _dz():
    """Unique millimetre lift per ribbon / fill: overlapping OSM ways must never be coplanar,
    or shadow rays from one face hit its twin and the overlap renders (and bakes) black."""
    _LAYER[0] += 1
    return (_LAYER[0] % 13) * 0.0015


def build_site_osm(col, M, rng, osm):
    from nk_osm import SITE_ZONE, inside
    g, r, p = MeshBuilder(), MeshBuilder(), MeshBuilder()
    for i in range(-4, 4):
        for j in range(-4, 4):
            rect(g, i * 200, (i + 1) * 200, j * 200, (j + 1) * 200, 0.0, 'NK_Ground')
    for (x0, x1, y0, y1) in ((-3000, 3000, 800, 3000), (-3000, 3000, -3000, -800),
                             (-3000, -800, -800, 800), (800, 3000, -800, 800)):
        rect(g, x0, x1, y0, y1, -0.05, 'NK_Ground')
    # parks, lawns, woods; other construction sites as bare soil
    for gr in osm['green']:
        if all(inside(SITE_ZONE, x, y) for x, y in gr['pts']):
            continue
        fill_poly(g, gr['pts'], (0.004 if gr['kind'] != 'grass' else 0.006) + _dz() * 0.5, 'NK_Grass')
    for c in osm['construction']:
        if c['id'] in OUR_OUTLINES:
            continue
        fill_poly(g, c['pts'], 0.013 + _dz() * 0.2, 'NK_Soil')
    # streets (OSM), minus anything inside our plaza; pavements, kerbs and centre lines stop at junctions
    candidates = [rd for rd in osm['roads'] if rd['kind'] in ROAD_W and (rd.get('nk') or not road_in_site(rd, SITE_ZONE, 0.34))]
    jn = junctions(candidates)
    kept = []
    for rd in candidates:
        k = rd['kind']
        if rd.get('nk') == 'west':
            west_street_site(r, p, rd, jn.get(rd['id'], {}))
            kept.append(rd)
            continue
        w = road_width(rd)
        P = _clean(rd['pts'])
        zr = ROAD_Z[k] + _dz()
        ribbon(r, P, w, zr, ROAD_M.get(k, 'NK_Asphalt'))
        J = jn.get(rd['id'], {})
        if k in SIDEWALK:
            for s in (1, -1):
                for piece in _cut(P, J.get(s, [])):
                    zs = 0.10 + _dz()
                    ribbon(p, [tuple(q) for q in _offset(piece, s * (w / 2 + 1.6))], 3.0, zs, 'NK_Pavers')
                    # kerb stones: a bright 0.2 m line between carriageway and pavement (the web ground is a flat bake)
                    ribbon(p, [tuple(q) for q in _offset(piece, s * (w / 2 + 0.1))], 0.2, zs + 0.0023, 'NK_Curb')
        elif k == 'park_path' and len(P) >= 2:
            for s in (1, -1):         # concrete edging
                ribbon(p, [tuple(q) for q in _offset(P, s * (w / 2 - 0.06))], 0.12, zr + 0.0021, 'NK_Curb')
        if k in MARKED and rd.get('oneway') != 'yes' and any(math.hypot(x, y) < MARK_RADIUS for x, y in P):
            centre_line(r, P, zr + 0.004, list(J.get('dash', [])) + _zebra_skip(P))
        kept.append(rd)
    from nk_osm import ZEBRAS
    for (c, t, w) in ZEBRAS:
        zebra(r, c, t, w)
    # our plaza: raised paving around both blocks (courtyards included), drive between them
    rect(p, -140, -4.5, -66, 64, Z_PAVE, 'NK_Pavers', curb=True)
    rect(p, 4.5, 127, -66, 64, Z_PAVE, 'NK_Pavers', curb=True)
    from nk_osm import BAY_RUNS
    frame(p, 4.5, 127, -66, 64, Z_PAVE + 0.003, 0.2, 'NK_Curb')
    zc = Z_PAVE + 0.003
    rect(p, -140, -4.5, -66, -65.8, zc, 'NK_Curb')
    rect(p, -140, -4.5, 63.8, 64, zc, 'NK_Curb')
    rect(p, -4.7, -4.5, -65.8, 63.8, zc, 'NK_Curb')
    for (y0, y1) in BAY_RUNS:          # west edge: only where the bays meet the plaza
        rect(p, -140, -139.8, y0, y1, zc, 'NK_Curb')
    rect(r, -4.5, 4.5, -68, 66, Z_ROAD, 'NK_Asphalt')
    centre_line(r, [(0.0, -66.0), (0.0, 64.0)], Z_ROAD + 0.004, _zebra_skip([(0.0, -66.0), (0.0, 64.0)]))
    for sx in (-1, 1):
        for (x0, x1) in ((-130, -100), (-95, -70), (-65, -40), (-35, -14)):
            a, b = sorted((x0 * sx, x1 * sx))
            rect(p, a, b, -61.0, -55.0, Z_LAWN, 'NK_Grass', curb=True, zb=Z_PAVE)
    # planted strip between the new street's parking bays and block A (the bays replaced the old strip here)
    for (y0, y1) in WEST_LAWNS:
        rect(p, WEST_LAWN_X[0], WEST_LAWN_X[1], y0, y1, Z_LAWN, 'NK_Grass', curb=True, zb=Z_PAVE)
        frame(p, WEST_LAWN_X[0], WEST_LAWN_X[1], y0, y1, Z_LAWN + 0.002, 0.15, 'NK_Curb')
    courtyard(p, mirror=False)
    courtyard(p, mirror=True)
    plaza_bands(p)
    ground_details(r, p, kept)
    for mb, name in ((g, 'NK_Site_Ground'), (r, 'NK_Site_Roads'), (p, 'NK_Site_Paving')):
        mb.face_up()              # vertical curb faces have zero projected area and stay as they are
        mb.to_object(name, col, M, merge=False)
    return kept


class _Grid:
    """Spatial hash of polygons / segments for fast point queries."""

    def __init__(self, cell=40.0):
        self.cell = cell
        self.g = {}

    def _keys(self, x0, y0, x1, y1):
        c = self.cell
        for i in range(int(np.floor(x0 / c)), int(np.floor(x1 / c)) + 1):
            for j in range(int(np.floor(y0 / c)), int(np.floor(y1 / c)) + 1):
                yield (i, j)

    def add(self, item, bbox):
        for k in self._keys(*bbox):
            self.g.setdefault(k, []).append(item)

    def near(self, x, y):
        return self.g.get((int(np.floor(x / self.cell)), int(np.floor(y / self.cell))), ())


def _pip(x, y, pts):
    c = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0:
            c = not c
    return c


def _seg_d2(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-9 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    qx, qy = ax + t * dx, ay + t * dy
    return (px - qx) ** 2 + (py - qy) ** 2


def tree_layout_osm(rng, cams, feet, roads, osm):
    """Street trees along real roads, OSM parks / woods / lawns, yard trees, shrubs along the walls
    and hedges along the mapped fences, our site. Densities follow the developer's aerial render
    (Arabkir is largely under mature tree cover); the first version was about a third as dense."""
    from nk_osm import SITE_ZONE, inside
    bgrid = _Grid(40.0)
    for f in feet:
        pts = f[3]
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        bgrid.add(pts, (min(xs) - 3, min(ys) - 3, max(xs) + 3, max(ys) + 3))
    rgrid = _Grid(40.0)
    for rd in roads:
        # the new street keeps its pavements free too (its trees are placed below)
        w = 13.0 if rd.get('nk') == 'west' else ROAD_W.get(rd['kind'], 5.0)
        P = _clean(rd['pts'])
        for i in range(len(P) - 1):
            a, b = P[i], P[i + 1]
            rgrid.add((a, b, w), (min(a[0], b[0]) - w, min(a[1], b[1]) - w, max(a[0], b[0]) + w, max(a[1], b[1]) + w))
    ogrid = _Grid(60.0)
    for c in osm['construction']:
        xs, ys = [q[0] for q in c['pts']], [q[1] for q in c['pts']]
        ogrid.add(c['pts'], (min(xs), min(ys), max(xs), max(ys)))
    T = []

    def cam_ok(x, y):
        """Ground-level still cameras keep a clear view (no cameras in the web build)."""
        for (cx, cy), (tx, ty) in cams:
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy < 25.0 ** 2:
                return False
            vx, vy = tx - cx, ty - cy
            L = (vx * vx + vy * vy) ** 0.5
            vx, vy = vx / L, vy / L
            along = dx * vx + dy * vy
            across = abs(-dx * vy + dy * vx)
            if 0 < along < 150 and across < 8 + along * 0.16:
                return False
        return True

    def free(x, y, clear_road=1.0, bpad=2.5):
        if inside(SITE_ZONE, x, y, 2.0) or abs(x) > 760 or abs(y) > 760:
            return False
        if not cam_ok(x, y):
            return False
        for pts in bgrid.near(x, y):
            if _pip(x, y, pts):
                return False
            for i in range(len(pts)):
                if _seg_d2(x, y, pts[i], pts[(i + 1) % len(pts)]) < bpad * bpad:
                    return False
        for (a, b, w) in rgrid.near(x, y):
            if _seg_d2(x, y, a, b) < (w / 2 + clear_road) ** 2:
                return False
        for pts in ogrid.near(x, y):
            if _pip(x, y, pts):
                return False
        return True

    def pick(kind):
        r = rng.random()
        if kind == 'street':
            return 'Plane' if r < 0.45 else 'Linden' if r < 0.8 else 'Maple'
        if kind == 'wood':
            return 'Poplar' if r < 0.3 else 'Linden' if r < 0.55 else 'Birch' if r < 0.75 else 'Plane'
        return 'Maple' if r < 0.35 else 'Linden' if r < 0.6 else 'Plane' if r < 0.8 else 'Birch' if r < 0.9 else 'Poplar'

    # 1. street trees on both kerbs of the real streets
    for rd in roads:
        if rd['kind'] not in ('tertiary', 'residential', 'primary', 'living_street', 'secondary') or rd.get('nk'):
            continue
        w = ROAD_W[rd['kind']]
        P = _clean(rd['pts'])
        if len(P) < 2:
            continue
        for side in (1, -1):
            line = _offset(P, side * (w / 2 + 1.3))
            acc = rng.uniform(0, 6)
            for i in range(len(line) - 1):
                a, b = line[i], line[i + 1]
                L = float(np.linalg.norm(b - a))
                t = acc
                while t < L:
                    q = a + (b - a) * (t / L)
                    if rng.random() < 0.92 and free(q[0], q[1], clear_road=0.3, bpad=2.0):
                        T.append((float(q[0]), float(q[1]), 0.10, pick('street'), float(rng.uniform(0.85, 1.2))))
                    t += rng.uniform(6.5, 9.5)
                acc = t - L
    # 2. parks / woods / lawns from OSM
    dens = {'park': 1 / 50.0, 'wood': 1 / 28.0, 'forest': 1 / 28.0, 'garden': 1 / 65.0, 'grass': 1 / 150.0,
            'scrub': 1 / 35.0, 'cemetery': 1 / 60.0, 'orchard': 1 / 45.0, 'nk_park': 1 / 62.0}
    from nk_osm import WEST_PARK
    for gr in osm['green']:
        pts = gr['pts']
        from nk_osm import poly_area
        A = abs(poly_area(pts))
        n = int(A * dens.get(gr['kind'], 1 / 180.0))
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        tries = 0
        placed = 0
        while placed < n and tries < n * 6:
            tries += 1
            x, y = rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys))
            if gr['kind'] == 'nk_park':
                # the new park (former tower plot): groves of mature trees around open lawns, as in the
                # developer's aerial render, instead of an even scatter
                g = _vnoise(x, y, 23, 38.0)
                if rng.random() > min(1.0, max(0.0, (g - 0.32) / 0.22)):
                    continue
            if _pip(x, y, pts) and free(x, y, clear_road=2.0 if gr['kind'] == 'nk_park' else 1.0):
                sp = 'Shrub' if gr['kind'] == 'scrub' else pick('wood' if gr['kind'] in ('wood', 'forest') else 'park')
                s0, s1 = (0.9, 1.35) if gr['kind'] == 'nk_park' else (0.75, 1.15)
                T.append((x, y, 0.0, sp, float(rng.uniform(s0, s1))))
                placed += 1
    # 3. yard trees everywhere else, clustered, mostly mature
    step = 9.0
    for gx in np.arange(-740, 740, step):
        for gy in np.arange(-740, 740, step):
            x, y = gx + rng.uniform(-4, 4), gy + rng.uniform(-4, 4)
            d = _vnoise(x, y, 9, 70.0)
            if d < 0.3 or rng.random() > (d - 0.3) * 2.0:
                continue
            if free(x, y) and not _pip(x, y, WEST_PARK):
                T.append((x, y, 0.0, pick('yard'), float(rng.uniform(0.8, 1.3))))
    # 3b. shrubs along the walls of the nearer buildings (front gardens, foundation planting)
    for (cx, cy, r, pts) in feet:
        if math.hypot(cx, cy) > 450:
            continue
        n = len(pts)
        for i in range(n):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
            L = math.hypot(x1 - x0, y1 - y0)
            if L < 3:
                continue
            nx, ny = (y1 - y0) / L, -(x1 - x0) / L           # outward for the CCW footprints
            t = rng.uniform(0.5, 3.0)
            while t < L - 0.5:
                if rng.random() < 0.3:
                    x, y = x0 + (x1 - x0) * t / L + nx * 2.0, y0 + (y1 - y0) * t / L + ny * 2.0
                    if free(x, y, bpad=1.4):
                        T.append((x, y, 0.0, 'Shrub', float(rng.uniform(0.8, 1.5))))
                t += rng.uniform(2.6, 4.0)
    # 3c. hedges along the mapped garden fences
    for bar in osm.get('barriers', []):
        if bar['kind'] != 'fence':
            continue
        P = _clean(bar['pts'])
        if len(P) < 2:
            continue
        line = _offset(P, 0.8)
        for i in range(len(line) - 1):
            a, b = line[i], line[i + 1]
            L = float(np.linalg.norm(b - a))
            t = rng.uniform(0.3, 1.5)
            while t < L:
                q = a + (b - a) * (t / L)
                if rng.random() < 0.55 and free(float(q[0]), float(q[1]), clear_road=0.5, bpad=1.0):
                    T.append((float(q[0]), float(q[1]), 0.0, 'Shrub', float(rng.uniform(0.7, 1.1))))
                t += rng.uniform(1.4, 2.0)
    # 4. our site: courtyards, lawn strips, plaza edge (reuse the original generator's rules)
    for sx in (-1, 1):
        for (x0, x1) in ((-130, -100), (-95, -70), (-65, -40), (-35, -14)):
            for x in np.arange(x0 + 4, x1 - 2, 8.5):
                T.append((sx * x, -58.0 + rng.uniform(-0.5, 0.5), Z_LAWN, 'Linden', float(rng.uniform(0.8, 1.0))))
            for x in np.arange(x0 + 1.5, x1 - 1, 1.9):
                if rng.random() < 0.75:
                    T.append((sx * x, -55.9 - rng.uniform(0, 0.8), Z_LAWN, 'Shrub', float(rng.uniform(0.8, 1.4))))
    # courtyards (v0.12 design): trees at the designed spots, shrubs along the lawn edges and around the beds
    T += courtyard_planting(rng, cam_ok)
    # 5. the new street: planes on the park-side pavement (between the lamps, clear of the crossings),
    #    lindens in the planted strips between the parking bays, maples in the plaza's lawn strip
    from nk_osm import WEST_X, WEST_W, BAY_X, ZEBRAS, west_bays, street_lamps
    crossings = [c[1] for (c, _t, _w) in ZEBRAS if abs(c[0] - WEST_X) < 1.0]
    lamps_y = [l[1] for l in street_lamps() if abs(l[0] - (WEST_X - WEST_W / 2 - 0.6)) < 0.5]
    for y in np.arange(-57.5, 64.0, 9.0):
        if all(abs(y - c) > 3.2 for c in crossings) and all(abs(y - l) > 3.0 for l in lamps_y) and cam_ok(WEST_X - 5.6, y):
            T.append((WEST_X - 5.6, float(y) + rng.uniform(-0.3, 0.3), 0.10, 'Plane', float(rng.uniform(0.9, 1.15))))
    for (y0, y1) in west_bays()[1]:
        if cam_ok(0.5 * (BAY_X[0] + BAY_X[1]), 0.5 * (y0 + y1)):
            T.append((0.5 * (BAY_X[0] + BAY_X[1]), 0.5 * (y0 + y1), Z_LAWN, 'Linden', float(rng.uniform(0.85, 1.05))))
    for (y0, y1) in WEST_LAWNS:
        n = max(1, int(round((y1 - y0) / 8.5)))
        for k in range(n):
            y = y0 + (k + 0.5) * (y1 - y0) / n
            if cam_ok(-134.6, y):
                T.append((-134.6 + rng.uniform(-0.4, 0.4), y, Z_LAWN, 'Maple', float(rng.uniform(0.8, 1.0))))
        for y in np.arange(y0 + 1.2, y1 - 1.0, 2.1):
            for x in (WEST_LAWN_X[0] + 0.8, WEST_LAWN_X[1] - 0.8):
                if rng.random() < 0.55 and cam_ok(x, y):
                    T.append((x, y + rng.uniform(-0.3, 0.3), Z_LAWN, 'Shrub', float(rng.uniform(0.7, 1.2))))
    # shrub groups along the park paths
    for rd in roads:
        if rd['kind'] != 'park_path':
            continue
        P = _clean(rd['pts'])
        L = _arclen(P)
        s = rng.uniform(2, 8)
        while s < L - 2:
            if rng.random() < 0.35:
                q = _sub(P, max(0.0, s - 0.5), min(L, s + 0.5))
                (ax, ay), (bx, by) = q[0], q[-1]
                d = math.hypot(bx - ax, by - ay) or 1.0
                side = 1 if rng.random() < 0.5 else -1
                for kk in range(int(rng.integers(2, 5))):
                    off = side * (2.6 + rng.uniform(0, 1.6))
                    x = ax - (by - ay) / d * off + (bx - ax) / d * kk * 1.3
                    y = ay + (bx - ax) / d * off + (by - ay) / d * kk * 1.3
                    if free(x, y, clear_road=0.6, bpad=1.5):
                        T.append((x, y, 0.0, 'Shrub', float(rng.uniform(0.8, 1.4))))
            s += rng.uniform(5.0, 11.0)
    return T
