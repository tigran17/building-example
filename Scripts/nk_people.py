"""People for the web model: routes, spots and sun visibility -> Website/assets/people.json (people.js draws them).

Walkers follow the real pavements around the site (OSM streets, cut at junctions like the paving), the new
street's pavements, the park paths, a ring around each block on the plaza, the courtyard loops, walks and
spurs, and a few routes that cross the zebras and end at the building entrances (people dissolve there, as
if they went in). Others sit on the benches, stand in small groups at entrances and playgrounds, and
children run around the playgrounds. Sun visibility along every route is ray-cast against the web scene
(buildings, trees, props) toward the baked sun, like the traffic (nk_trafficshade.py).

blender -b Blender/NewKomitas-Web.blend -P Scripts/nk_people.py
"""
import json
import math
import os
import random
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import nk_osm  # noqa: E402
import nk_site  # noqa: E402
import nk_furniture  # noqa: E402

SITE = os.path.join(PROJECT, 'Website', 'assets')
RADIUS = 280.0          # pavements within this distance of the site centre get pedestrians
STEP = 1.0              # route sample spacing (m)


def resample(pts, closed=False):
    P = [tuple(map(float, p)) for p in pts]
    if closed and P[0] != P[-1]:
        P = P + [P[0]]
    out, s = [], 0.0
    for (x0, y0), (x1, y1) in zip(P, P[1:]):
        L = math.dist((x0, y0), (x1, y1))
        n = max(1, int(math.ceil(L / STEP)))
        for k in range(n):
            x, y = x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n
            if out:
                s += math.dist(out[-1][:2], (x, y))
            out.append([x, y, s])
    x, y = P[-1]
    s += math.dist(out[-1][:2], (x, y))
    out.append([x, y, s])
    return out


def offset_ring(poly, d):
    """Offset a closed axis-aligned CCW polygon by d (outwards if d > 0)."""
    n = len(poly)
    nrm = []
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        L = math.hypot(x1 - x0, y1 - y0)
        nrm.append(((y1 - y0) / L, -(x1 - x0) / L))
    return [(poly[i][0] + d * (nrm[i - 1][0] + nrm[i][0]), poly[i][1] + d * (nrm[i - 1][1] + nrm[i][1])) for i in range(n)]


OUTER_A = [(-111, -48), (-11, -48), (-11, 48), (-76, 48), (-76, 55), (-122, 55), (-122, -3), (-111, -3)]
INNER_A = [(-93.5, -30.5), (-28.5, -30.5), (-28.5, 30.5), (-76, 30.5), (-76, 37.5), (-104.5, 37.5), (-104.5, -3), (-93.5, -3)]


def mirror_ring(poly):
    return [(-x, y) for x, y in poly][::-1]


def routes():
    """[(id, polyline in Blender XY, closed, walkers per metre, kind)]"""
    w = nk_osm.load_world(os.path.join(PROJECT, 'Reference', 'osm_world.json'))
    cand = [rd for rd in w['roads'] if rd['kind'] in nk_site.ROAD_W and (rd.get('nk') or not nk_site.road_in_site(rd, nk_osm.SITE_ZONE, 0.34))]
    jn = nk_site.junctions(cand)
    R = []
    for rd in cand:
        k = rd['kind']
        P = nk_site._clean(rd['pts'])
        if len(P) < 2 or not any(math.hypot(x, y) < RADIUS for x, y in P):
            continue
        J = jn.get(rd['id'], {})
        if rd.get('nk') == 'west':
            wide = nk_osm.WEST_W / 2 + 1.5
            for piece in nk_site._cut(P, J.get(1, [])):
                R.append(('west-pavement', [tuple(q) for q in nk_site._offset(piece, wide)], False, 1 / 22.0, 'street'))
            s_east = math.dist(P[0], P[1]) + (nk_site.WEST_EAST_FROM_Y - P[1][1])
            for piece in nk_site._cut(P, J.get(-1, []) + [(0.0, s_east)]):
                R.append(('west-pavement-e', [tuple(q) for q in nk_site._offset(piece, -wide)], False, 1 / 22.0, 'street'))
        elif k in nk_site.SIDEWALK:
            wr = nk_site.road_width(rd)
            for s in (1, -1):
                for piece in nk_site._cut(P, J.get(s, [])):
                    if nk_site._arclen(piece) < 20:
                        continue
                    line = [tuple(q) for q in nk_site._offset(piece, s * (wr / 2 + 1.6))]
                    near = sum(1 for x, y in line if math.hypot(x, y) < 160) / len(line)
                    R.append((f'pavement-{rd["id"]}-{s}', line, False, (1 / 55.0) if near > 0.5 else (1 / 150.0), 'street'))
        elif k == 'park_path':
            R.append((f'park-{rd["id"]}', P, False, 1 / 24.0, 'park'))
    # plaza: a ring 5 m out from each block's facade
    for name, poly in (('plaza-A', OUTER_A), ('plaza-B', mirror_ring(OUTER_A))):
        R.append((name, offset_ring(poly, 5.0), True, 1 / 17.0, 'plaza'))
    # courtyards: loop, facade walk, spurs to the entrances
    for b, poly in (('A', INNER_A), ('B', mirror_ring(INNER_A))):
        C = nk_furniture.courtyard_layout(b)
        R.append((f'court-loop-{b}', C['loop'], True, 1 / 15.0, 'court'))
        R.append((f'court-walk-{b}', offset_ring(poly, -1.5), True, 1 / 32.0, 'court'))
        for i, sp in enumerate(C['spurs']):
            R.append((f'court-spur-{b}{i}', sp, False, 1 / 14.0, 'court'))
    # zebra crossings into the plaza, ending at a building entrance
    X = [[(-171.0, 0.6), (-156.0, -11.9), (-139.5, -11.9), (-127.0, -11.9), (-116.0, -20.0), (-112.2, -25.5)],
         [(-153.3, -66.0), (-153.3, -60.0), (-140.5, -60.0), (-120.0, -53.2), (-86.0, -49.2)],
         [(-150.0, -75.4), (-132.0, -75.4), (-132.0, -62.5), (-130.8, -53.2), (-61.0, -53.2), (-61.0, -49.2)],
         [(-25.0, -75.4), (-10.0, -75.4), (-10.0, -64.0), (-7.2, -56.0), (-7.2, 0.0), (-11.8, 0.0)],
         [(25.0, -75.4), (10.0, -75.4), (10.0, -64.0), (7.2, -56.0), (7.2, 0.0), (11.8, 0.0)]]
    for i, line in enumerate(X):
        R.append((f'crossing-{i}', line, False, 1 / 30.0, 'crossing'))
    return R


COURT_FILL = 0.35        # courtyard people share the baked courtyard fill (nk_web.court_fill): a floor on sun visibility


def in_court(x, y):
    def pip(px, py, pts):
        c = False
        for i in range(len(pts)):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % len(pts)]
            if (y0 > py) != (y1 > py) and px < (x1 - x0) * (py - y0) / (y1 - y0 + 1e-12) + x0:
                c = not c
        return c
    return pip(x, y, INNER_A) or pip(-x, y, INNER_A)


class Sun:
    def __init__(self):
        pres = json.load(open(os.path.join(SITE, 'scene-presentation.json')))
        sx, sy, sz = pres['lighting']['sunDirection']
        self.dir = Vector((-sx, -sy, -sz)).normalized()
        self.scene = bpy.context.scene
        self.dg = bpy.context.evaluated_depsgraph_get()
        self.rays = 0

    def lit(self, x, y, z=1.25):
        self.rays += 1
        ok = self.scene.ray_cast(self.dg, Vector((x, y, z)), self.dir, distance=900.0)[0]
        v = 0.0 if ok else 1.0
        return max(v, COURT_FILL) if in_court(x, y) else v


def main():
    t0 = time.time()
    rnd = random.Random(2027)
    sun = Sun()
    paths, walkers = [], []
    TYPES = [0] * 40 + [1] * 42 + [3] * 10 + [2] * 8
    for (pid, line, closed, density, kind) in routes():
        S = resample(line, closed)
        L = S[-1][2]
        if L < 8:
            continue
        raw = [sun.lit(x, y) for x, y, _ in S]
        k = 2                                               # smooth over +-2 m
        samples = []
        for i, (x, y, s) in enumerate(S):
            win = raw[max(0, i - k):i + k + 1]
            samples.append([round(x, 2), round(-y, 2), round(s, 2), round(sum(win) / len(win), 2)])
        pi = len(paths)
        paths.append({'id': pid, 'closed': closed, 'length': round(L, 2), 'samples': samples})
        n = max(1, int(round(L * density)))
        for j in range(n):
            run = kind == 'park' and rnd.random() < 0.12
            walkers.append([pi, round((j + rnd.uniform(0.1, 0.9)) / n * L, 2), 1 if rnd.random() < 0.5 else -1,
                            round(rnd.uniform(2.6, 3.1) if run else rnd.uniform(1.1, 1.5), 2),
                            round(rnd.uniform(-0.8, 0.8) if kind != 'crossing' else rnd.uniform(-0.5, 0.5), 2),
                            0 if run else rnd.choice(TYPES), rnd.randint(1, 10 ** 6), 3 if run else 0])
    # sitting, standing, playing
    w = nk_osm.load_world(os.path.join(PROJECT, 'Reference', 'osm_world.json'))
    roads = [rd for rd in w['roads'] if rd['kind'] in nk_site.ROAD_W]
    idle, kids = [], []

    def yaw(fx, fy):                                         # facing (Blender XY) -> three.js yaw
        return round(math.atan2(fx, -fy), 3)
    for (x, y, fx, fy) in nk_furniture.all_benches(roads):
        if rnd.random() < 0.5:
            seats = [-0.45, 0.45] if rnd.random() < 0.45 else [rnd.uniform(-0.5, 0.5)]
            for a in seats:
                px, py = x - fy * a + fx * 0.05, y + fx * a + fy * 0.05       # along the bench, a bit forward
                idle.append([round(px, 2), round(-py, 2), yaw(fx, fy), rnd.choice([0, 1, 1, 3]), rnd.randint(1, 10 ** 6), 2, 0.47,
                             round(sun.lit(px, py, 1.0), 2)])
    P = nk_furniture.plaza_items()
    for (x, y, ox, oy, wd) in P['canopies']:
        if rnd.random() < 0.4:
            cx, cy = x + ox * 3.2, y + oy * 3.2
            m = rnd.choice([2, 2, 3, 4])
            for i in range(m):
                a = 2 * math.pi * i / m + rnd.uniform(-0.3, 0.3)
                px, py = cx + 0.55 * math.cos(a), cy + 0.55 * math.sin(a)
                idle.append([round(px, 2), round(-py, 2), yaw(cx - px, cy - py), rnd.choice([0, 1, 1, 3]), rnd.randint(1, 10 ** 6), 1, 0,
                             round(sun.lit(px, py), 2)])
    for b in ('A', 'B'):
        C = nk_furniture.courtyard_layout(b)
        x0, x1, y0, y1 = C['playground']
        for (cx, cy, rx, ry) in C['kids']:
            for i in range(6):
                kids.append([round(cx + rnd.uniform(-1, 1), 2), round(-cy - rnd.uniform(-1, 1), 2), round(rx * rnd.uniform(0.5, 1), 2),
                             round(ry * rnd.uniform(0.5, 1), 2), rnd.randint(1, 10 ** 6), round(sun.lit(cx, cy), 2)])
        # parents at the playground edge
        for i in range(3):
            px, py = (x0 - 0.8, y0 + 3 + 3 * i) if b == 'A' else (x1 + 0.8, y0 + 3 + 3 * i)
            idle.append([round(px, 2), round(-py, 2), yaw(1 if b == 'A' else -1, 0), rnd.choice([0, 1, 1]), rnd.randint(1, 10 ** 6), 1, 0,
                         round(sun.lit(px, py), 2)])
        # a few players on the court
        cx0, cx1, cy0, cy1 = C['court']['rect']
        for i in range(3):
            kids.append([round(0.5 * (cx0 + cx1), 2), round(-0.5 * (cy0 + cy1), 2), round((cx1 - cx0) * 0.35, 2),
                         round((cy1 - cy0) * 0.35, 2), rnd.randint(1, 10 ** 6), round(sun.lit(0.5 * (cx0 + cx1), 0.5 * (cy0 + cy1)), 2)])
    # small groups on the park lawn
    for (cx, cy) in ((-205.0, -28.0), (-178.0, 2.0), (-228.0, 12.0)):
        m = rnd.choice([2, 3])
        for i in range(m):
            a = 2 * math.pi * i / m
            px, py = cx + 0.6 * math.cos(a), cy + 0.6 * math.sin(a)
            idle.append([round(px, 2), round(-py, 2), yaw(cx - px, cy - py), rnd.choice([0, 1, 2]), rnd.randint(1, 10 ** 6), 1, 0,
                         round(sun.lit(px, py), 2)])
    data = {'version': '0.12.0', 'note': 'Synthetic pedestrians for the demo (nk_people.py); shade = sun visibility 0..1.',
            'paths': paths, 'walkers': walkers, 'idle': idle, 'kids': kids}
    json.dump(data, open(os.path.join(SITE, 'people.json'), 'w'), separators=(',', ':'))
    print(f'PEOPLE paths {len(paths)} ({sum(p["length"] for p in paths):.0f} m), walkers {len(walkers)}, idle {len(idle)}, '
          f'kids {len(kids)}; {sun.rays} rays in {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
