"""Web data for the interactive site, generated from the model:

  demo-apartments.json  one synthetic apartment per balcony column per floor, hotspot on its balcony
  traffic-routes.json   right-hand lanes on the real (OSM) streets around the site + kerb parking
  scene-presentation.json  sun direction/colour of the bake, fog/terrain colours

python3 Scripts/nk_webdata.py
then  blender -b Blender/NewKomitas-Web.blend -P Scripts/nk_trafficshade.py   (sun visibility per lane sample / car)
"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import nk_osm  # noqa: E402

SITE = os.path.join(PROJECT, 'Website', 'assets')
GF, FH, NF, TRAY_D, PAR = 4.2, 3.0, 17, 1.5, 56.4
SIDE = {('outer', 0): 'SO', ('outer', 1): 'EO', ('outer', 2): 'NO', ('outer', 3): 'NO', ('outer', 4): 'NO',
        ('outer', 5): 'WO', ('outer', 6): 'WO', ('outer', 7): 'WO'}


def side_code(side, n):
    """Facade orientation code from the outward normal (world X east, Y north)."""
    nx, ny = n
    d = 'E' if abs(nx) > abs(ny) and nx > 0 else 'W' if abs(nx) > abs(ny) else 'N' if ny > 0 else 'S'
    return d + ('O' if side == 'outer' else 'I')


def to_three(x, y, z):
    return [round(x, 3), round(z, 3), round(-y, 3)]


def apartments(meta, rnd):
    rows = []
    for blk, mx in (('A', 1.0), ('B', -1.0)):
        per_floor = {}
        for run in meta['blockA_runs']:
            p0, t, n = run['p0'], run['t'], run['n']
            for e in run['elements']:
                if e['t'] != 'BAL':
                    continue
                am = 0.5 * (e['a0'] + e['a1'])
                w = e['a1'] - e['a0']
                for f in range(1, NF + 1):
                    z = GF + (f - 1) * FH
                    x = p0[0] + t[0] * am + n[0] * (TRAY_D + 0.06)
                    y = p0[1] + t[1] * am + n[1] * (TRAY_D + 0.06)
                    nx, ny = n
                    x, nx = x * mx, nx * mx
                    per_floor.setdefault(f, []).append({
                        'x': x, 'y': y, 'z': z + 1.35, 'w': w, 'n': (nx, ny), 'side': run['side'],
                        'glass': e['g'] is not None and 6 <= f <= 11, 'bronze': f in e['bz']})
        for f, units in sorted(per_floor.items()):
            # stable order around the ring: by angle about the block centre
            cx = -61.0 * mx
            units.sort(key=lambda u: math.atan2(u['y'], u['x'] - cx))
            for k, u in enumerate(units, 1):
                beds = 3 if u['glass'] else rnd.choice([1, 2, 2, 3])
                area = {1: rnd.uniform(46, 58), 2: rnd.uniform(66, 82), 3: rnd.uniform(86, 118)}[beds]
                st = rnd.random()
                status = 'sold' if st < 0.38 else 'reserved' if st < 0.52 else 'available'
                code = side_code(u['side'], u['n'])
                rot = math.atan2(u['n'][0], -u['n'][1])
                rows.append({
                    'id': f'NK-DEMO-{blk}-{f + 1:02d}-{code}-{k:02d}', 'building': blk, 'floor': f + 1,
                    'side': code, 'courtyardFacing': u['side'] == 'inner', 'bedrooms': beds,
                    'area': round(area, 1), 'status': status, 'isDemo': True,
                    'planType': f'demo-{beds}-bed', 'floorPlan': f'./assets/plans/demo-{beds}-bed.svg',
                    'region': {'center': to_three(u['x'], u['y'], u['z']), 'size': [round(u['w'] - 0.2, 2), 2.9, 0.08],
                               'rotationY': round(rot, 5)},
                    'source': 'synthetic', 'updatedAt': '2026-09-26T00:00:00Z', 'label': f'{blk}-{f + 1:02d}{k:02d}'})
    return rows


def buildings(meta):
    out = []
    for blk, mx in (('A', 1.0), ('B', -1.0)):
        rects = []
        for (x0, y0, x1, y1) in meta['roof_rects_A']:
            a, b = sorted((x0 * mx, x1 * mx))
            rects.append([round(a, 2), round(y0, 2), round(b, 2), round(y1, 2)])
        out.append({'id': blk, 'label': 'West courtyard (Phase 1)' if blk == 'A' else 'East courtyard (Phase 2)',
                    'center': [round(-61.0 * mx, 2), 0.0], 'width': 100, 'depth': 96, 'wingDepth': 17.5,
                    'residentialFloors': NF, 'groundHeight': GF, 'floorHeight': FH, 'height': PAR,
                    'footprint': 'stepped-corner-v3', 'rects': rects})
    return out


def lanes_and_parking(osm, rnd):
    """Two right-hand lanes per major street segment near the site; samples in three.js (x, z, s)."""
    lanes = []
    keep = ('tertiary', 'primary', 'secondary', 'residential')
    R = 360.0
    for rd in osm['roads']:
        if rd['kind'] not in keep:
            continue
        pts = [p for p in rd['pts']]
        if len(pts) < 2 or all(abs(x) > R or abs(y) > R for x, y in pts):
            continue
        if any(nk_osm.inside(nk_osm.SITE_ZONE, x, y, 0.0) for x, y in pts):
            continue
        # clip to the neighbourhood
        pts = [p for p in pts if abs(p[0]) < R + 60 and abs(p[1]) < R + 60]
        if len(pts) < 2:
            continue
        L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        if L < 90:
            continue
        w = {'primary': 15.0, 'secondary': 12.0, 'tertiary': 10.5, 'residential': 7.0}[rd['kind']]
        off = w / 4 if rd['kind'] != 'residential' else 1.7
        for direction in (1, -1):
            if rd.get('oneway') == 'yes' and direction < 0:
                continue
            P = pts if direction > 0 else pts[::-1]
            # right-hand offset
            samples = []
            s_acc = 0.0
            prev = None
            for i in range(len(P) - 1):
                (x0, y0), (x1, y1) = P[i], P[i + 1]
                seg = math.dist((x0, y0), (x1, y1))
                if seg < 0.05:
                    continue
                tx, ty = (x1 - x0) / seg, (y1 - y0) / seg
                rx, ry = ty, -tx
                k = 0.0
                while k < seg:
                    x = x0 + tx * k + rx * off
                    y = y0 + ty * k + ry * off
                    if prev is not None:
                        s_acc += math.dist(prev, (x, y))
                    samples.append([round(x, 3), round(-y, 3), round(s_acc, 3)])
                    prev = (x, y)
                    k += 0.4
            if len(samples) < 10:
                continue
            length = samples[-1][2]
            lanes.append({'id': f"{rd['id']}:{direction}", 'sourceRoadIds': [int(rd['id']) if rd['id'].isdigit() else rd['id']],
                          'road': rd.get('name') or rd['kind'], 'speed': rnd.uniform(6.0, 9.0) if rd['kind'] != 'residential' else 5.0,
                          'count': max(1, int(length / (55 if rd['kind'] != 'residential' else 90))),
                          'length': round(length, 3), 'fadeMeters': 14, 'samples': samples})
    return lanes


def parked(osm, rnd):
    rows = []
    paints = ['carWhite', 'carSilver', 'carBlue', 'carDark', 'carRed']
    zebras = [c for (c, _t, _w) in nk_osm.ZEBRAS]
    for rd in osm['roads']:
        if rd['kind'] not in ('residential', 'living_street') or rd.get('nk'):
            continue
        pts = rd['pts']
        if all(abs(x) > 260 or abs(y) > 260 for x, y in pts):
            continue
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            seg = math.dist((x0, y0), (x1, y1))
            if seg < 8:
                continue
            tx, ty = (x1 - x0) / seg, (y1 - y0) / seg
            for side in (1, -1):
                k = rnd.uniform(2, 6)
                while k < seg - 3:
                    if rnd.random() < 0.45:
                        off = side * 2.55
                        x = x0 + tx * k + ty * off
                        y = y0 + ty * k - tx * off
                        if (not nk_osm.inside(nk_osm.SITE_ZONE, x, y, 2.0) and abs(x) < 260 and abs(y) < 260
                                and all(math.dist((x, y), c) > 6.0 for c in zebras)):
                            fx, fy = (tx, ty) if side < 0 else (-tx, -ty)
                            rows.append({'position': [round(x, 2), round(y, 2), 0.05],
                                         'rotation': round(math.atan2(-fx, fy), 5),
                                         'style': 'suv' if rnd.random() < 0.35 else 'sedan',
                                         'paint': rnd.choice(paints)})
                    k += rnd.uniform(5.6, 8.0)
    # the perpendicular bays of the new street west of block A: ~3/4 taken, mostly nosed in towards the plaza
    bays, _planters = nk_osm.west_bays()
    x = 0.5 * (nk_osm.BAY_X[0] + nk_osm.BAY_X[1]) - 0.15
    for (y0, y1) in bays:
        if rnd.random() < 0.76:
            nose_in = rnd.random() < 0.8
            rows.append({'position': [round(x + rnd.uniform(-0.12, 0.12), 2), round(0.5 * (y0 + y1) + rnd.uniform(-0.1, 0.1), 2), 0.05],
                         'rotation': round((-math.pi / 2 if nose_in else math.pi / 2) + rnd.uniform(-0.03, 0.03), 5),
                         'style': 'suv' if rnd.random() < 0.35 else 'sedan', 'paint': rnd.choice(paints)})
    return rows


def main():
    rnd = random.Random(2026)
    meta = json.load(open(os.path.join(PROJECT, 'Blender', 'NewKomitas-Web_facades.json')))
    osm = nk_osm.load_world(os.path.join(PROJECT, 'Reference', 'osm_world.json'))
    apts = apartments(meta, rnd)
    data = {'mode': 'synthetic_demo',
            'notice': 'All apartments, locations, areas, plans and statuses are invented for this experiment. Not a sales listing.',
            'coordinateSystem': "glTF/Three.js Y-up; metres; converted from Blender [x,y,z] to [x,z,-y]; X east, Y north (rotated 3.77 deg to the blocks' axis)",
            'buildings': buildings(meta), 'apartments': apts}
    json.dump(data, open(os.path.join(SITE, 'demo-apartments.json'), 'w'), separators=(',', ':'))
    old = json.load(open(os.path.join(PROJECT, 'Website-original', 'assets', 'traffic-routes.json')))
    tr = {'version': '0.8.0', 'models': old['models'], 'parked': parked(osm, rnd), 'lanes': lanes_and_parking(osm, rnd),
          'notes': 'Demo traffic on the real streets around New Komitas (OSM, ODbL), right-hand lanes.'}
    json.dump(tr, open(os.path.join(SITE, 'traffic-routes.json'), 'w'), separators=(',', ':'))
    print('apartments', len(apts), 'per block', sum(1 for a in apts if a['building'] == 'A'),
          '| lanes', len(tr['lanes']), 'parked', len(tr['parked']))


if __name__ == '__main__':
    main()
