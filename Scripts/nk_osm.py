"""OpenStreetMap context (ODbL, (c) OpenStreetMap contributors) -> model world frame.

world = R(+ROT) * (enu - C): ENU metres around the Yandex pin of newkomitas.am, rotated so the
blocks' long axis (OSM construction outline, -3.77 deg from east) becomes world +X, and centred
on the centre of the two traced construction outlines.
"""
import json
import math
import sys
import xml.etree.ElementTree as ET

LAT0, LON0 = 40.213970, 44.510243          # newkomitas.am map pin
C = (208.9, -330.3)                         # centre of the two OSM construction outlines (ENU m)
ROT = math.radians(3.77)
MLAT = 111132.9
MLON = 111319.5 * math.cos(math.radians(LAT0))


def to_world(lon, lat):
    x = (lon - LON0) * MLON - C[0]
    y = (lat - LAT0) * MLAT - C[1]
    c, s = math.cos(ROT), math.sin(ROT)
    return (round(x * c - y * s, 2), round(x * s + y * c, 2))


def world_to_lonlat(x, y):
    c, s = math.cos(-ROT), math.sin(-ROT)
    ex, ey = x * c - y * s + C[0], x * s + y * c + C[1]
    return LON0 + ex / MLON, LAT0 + ey / MLAT


def parse(path):
    root = ET.parse(path).getroot()
    nodes = {n.get('id'): (float(n.get('lon')), float(n.get('lat'))) for n in root.iter('node')}
    ways = {}
    for w in root.iter('way'):
        tags = {t.get('k'): t.get('v') for t in w.iter('tag')}
        refs = [nd.get('ref') for nd in w.iter('nd')]
        pts = [to_world(*nodes[r]) for r in refs if r in nodes]
        ways[w.get('id')] = (tags, pts, refs)
    rels = []
    for r in root.iter('relation'):
        tags = {t.get('k'): t.get('v') for t in r.iter('tag')}
        mem = [(m.get('type'), m.get('ref'), m.get('role')) for m in r.iter('member')]
        rels.append((r.get('id'), tags, mem))
    return ways, rels


def rings_from(members, ways, role):
    """Join member ways into closed rings (simple greedy join)."""
    segs = [list(ways[ref][1]) for (t, ref, rl) in members if t == 'way' and rl == role and ref in ways]
    rings = []
    while segs:
        ring = segs.pop(0)
        changed = True
        while ring[0] != ring[-1] and changed:
            changed = False
            for i, sg in enumerate(segs):
                if sg[0] == ring[-1]:
                    ring += sg[1:]
                elif sg[-1] == ring[-1]:
                    ring += sg[::-1][1:]
                elif sg[-1] == ring[0]:
                    ring = sg + ring[1:]
                elif sg[0] == ring[0]:
                    ring = sg[::-1] + ring[1:]
                else:
                    continue
                segs.pop(i)
                changed = True
                break
        if len(ring) >= 4 and ring[0] == ring[-1]:
            rings.append(ring)
    return rings


def height_of(tags):
    for k in ('height', 'building:height'):
        if k in tags:
            try:
                return float(tags[k].split()[0].replace(',', '.'))
            except ValueError:
                pass
    lv = tags.get('building:levels')
    if lv:
        try:
            return float(lv.split(';')[0]) * 3.1 + 0.8
        except ValueError:
            pass
    return None


BARRIERS = {'wall', 'fence', 'retaining_wall'}


def barrier_height(tags):
    try:
        return float(tags['height'].split()[0].replace(',', '.'))
    except (KeyError, ValueError):
        return None


GREEN = {'park', 'garden', 'grass', 'forest', 'wood', 'scrub', 'meadow', 'village_green', 'orchard',
         'recreation_ground', 'cemetery', 'grassland', 'heath', 'vineyard', 'allotments'}


def extract(path):
    ways, rels = parse(path)
    out = {'buildings': [], 'roads': [], 'green': [], 'water': [], 'construction': [], 'barriers': [],
           'attribution': '(c) OpenStreetMap contributors, ODbL'}
    used = set()
    for rid, tags, mem in rels:
        if tags.get('type') != 'multipolygon':
            continue
        outers = rings_from(mem, ways, 'outer')
        for ring in outers:
            if 'building' in tags:
                out['buildings'].append({'id': 'r' + rid, 'pts': ring[:-1], 'h': height_of(tags),
                                         'kind': tags.get('building'), 'roof': tags.get('roof:shape'),
                                         'levels': tags.get('building:levels')})
            elif tags.get('landuse') in GREEN or tags.get('leisure') in GREEN or tags.get('natural') in GREEN:
                out['green'].append({'id': 'r' + rid, 'pts': ring[:-1],
                                     'kind': tags.get('landuse') or tags.get('leisure') or tags.get('natural')})
        for (t, ref, rl) in mem:
            used.add(ref)
    for wid, (tags, pts, refs) in ways.items():
        closed = len(refs) > 3 and refs[0] == refs[-1]
        if 'building' in tags and closed:
            if tags.get('building') == 'construction':
                out['construction'].append({'id': wid, 'pts': pts[:-1]})
                continue
            out['buildings'].append({'id': wid, 'pts': pts[:-1], 'h': height_of(tags), 'kind': tags.get('building'),
                                     'roof': tags.get('roof:shape'), 'levels': tags.get('building:levels')})
        elif 'highway' in tags:
            out['roads'].append({'id': wid, 'pts': pts, 'kind': tags['highway'], 'name': tags.get('name:en') or tags.get('name'),
                                 'lanes': tags.get('lanes'), 'oneway': tags.get('oneway')})
        elif tags.get('barrier') in BARRIERS and len(pts) >= 2:
            # garden / yard walls, fences and retaining walls as polylines (closed ones keep their end point)
            out['barriers'].append({'id': wid, 'pts': pts, 'kind': tags['barrier'], 'h': barrier_height(tags),
                                    'material': tags.get('material')})
        elif closed and (tags.get('landuse') in GREEN or tags.get('leisure') in GREEN or tags.get('natural') in GREEN):
            out['green'].append({'id': wid, 'pts': pts[:-1], 'kind': tags.get('landuse') or tags.get('leisure') or tags.get('natural')})
        elif closed and (tags.get('natural') == 'water' or tags.get('waterway') == 'riverbank'):
            out['water'].append({'id': wid, 'pts': pts[:-1]})
    return out


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    d = extract(src)
    json.dump(d, open(dst, 'w'))
    from collections import Counter
    print('buildings', len(d['buildings']), 'with height', sum(1 for b in d['buildings'] if b['h']))
    print('roads', Counter(r['kind'] for r in d['roads']).most_common())
    print('green', Counter(g['kind'] for g in d['green']).most_common())
    print('construction', [(c['id'], [p for p in c['pts']][:8]) for c in d['construction']])
    print('barriers', Counter(b['kind'] for b in d['barriers']).most_common())


# ---- placement of the OSM context around the modelled blocks ---------------------------------
# The traced construction outlines are rough; the design (video top-down) blocks are bigger, so the
# context is nudged +8 m east / +4 m north: Griboyedov street then clears block B's stepped corner
# and the north residential road (inside today's construction site) is dropped with the site zone.
OFFSET = (8.0, 4.0)
SITE_ZONE = (-140.0, 127.0, -66.0, 64.0)     # our plaza: OSM features inside it are replaced


def load_world(path, edits=True):
    d = json.load(open(path))
    for k in ('buildings', 'roads', 'green', 'water', 'construction', 'barriers'):
        for f in d.setdefault(k, []):
            f['pts'] = [(x + OFFSET[0], y + OFFSET[1]) for x, y in f['pts']]
    if edits:
        apply_edits(d)
    return d


# ---- design edits to the mapped surroundings (not OSM) --------------------------------------------
# User brief 2026-09-27: the three 14-storey towers west of block A go, their plot becomes a park like
# the one in the developer's aerial render, and the lane between that park and block A is built out as
# a real street (two lanes, parking bays, pavements, lamps). World coordinates (after OFFSET).
REMOVED_BUILDINGS = {'804972711', '804972712', '804972713',    # the towers
                     '579196570'}                               # small house standing on the new street's pavement
REMOVED_ROADS = {'1429891454', '1429891455', '1429891456', '1429892301'}   # tower access stubs on the new street's line
TO_PATH = {'1099923725', '1099929314'}                                        # the towers' access loop -> park paths
PARK_EDGE_X = -156.0                  # park paths stop at the new street's west pavement
WEST_X = -148.3                       # centreline of the new street (continues Griboyedov 4th lane north)
WEST_W = 7.0                          # carriageway
BAY_X = (-144.8, -140.0)              # perpendicular parking bays between the carriageway and our plaza
WEST_PARK = [(-157.0, -66.0), (-157.0, 46.0), (-175.0, 50.0), (-205.0, 52.0), (-222.0, 58.0), (-243.0, 10.0),
             (-241.0, -10.0), (-205.0, -40.0), (-185.0, -62.0)]
PARK_PATHS = [[(-213.5, 42.0), (-203.0, 22.0), (-192.0, 4.0), (-188.5, -14.0), (-192.5, -30.0), (-196.0, -37.5)]]


def _arc(corner, d_in, d_out, r, n=6):
    """Points of a circular fillet of radius r between two straight directions meeting at corner."""
    ax, ay = d_in
    bx, by = d_out
    turn = math.atan2(ax * by - ay * bx, ax * bx + ay * by)
    t = r * math.tan(abs(turn) / 2)
    p0 = (corner[0] - ax * t, corner[1] - ay * t)
    nx, ny = (-ay, ax) if turn > 0 else (ay, -ax)
    c = (p0[0] + nx * r, p0[1] + ny * r)
    a0 = math.atan2(p0[1] - c[1], p0[0] - c[0])
    return [(c[0] + r * math.cos(a0 + turn * k / n), c[1] + r * math.sin(a0 + turn * k / n)) for k in range(n + 1)]


def west_street(roads):
    """Centreline: north from the Griboyedov 4th lane corner (OSM node), then a 12 m bend into the mapped
    diagonal of way 407098315 up to Hovsep Arghutian street (its south-east part ran through today's
    construction site and stays dropped). Ends are the exact OSM junction nodes."""
    R = {r['id']: r for r in roads}
    south = tuple(R['441514107']['pts'][-1])            # corner with way 375967213
    nw = [tuple(p) for p in R['407098315']['pts']]
    k = min(range(len(nw)), key=lambda i: math.dist(nw[i], (-158.5, 80.2)))
    a, diag = nw[k - 1], nw[k:]
    d_out = (diag[0][0] - a[0], diag[0][1] - a[1])
    L = math.hypot(*d_out)
    d_out = (d_out[0] / L, d_out[1] / L)
    t = (WEST_X - a[0]) / d_out[0]                       # the diagonal line meets x = WEST_X here
    corner = (WEST_X, a[1] + d_out[1] * t)
    bend = _arc(corner, (0.0, 1.0), d_out, 12.0)
    return [south, (WEST_X, south[1] + 6.7)] + bend + diag


def _clip_west(pts, xmax):
    """Keep the part of a polyline west of x = xmax (the park side); the crossing becomes the end point."""
    out = []
    for i, p in enumerate(pts):
        if p[0] <= xmax:
            if out and i > 0 and pts[i - 1][0] > xmax:
                q = pts[i - 1]
                t = (xmax - q[0]) / (p[0] - q[0])
                out.append((xmax, q[1] + (p[1] - q[1]) * t))
            out.append(p)
        elif out and out[-1][0] < xmax:
            q = out[-1]
            t = (xmax - q[0]) / (p[0] - q[0])
            out.append((xmax, q[1] + (p[1] - q[1]) * t))
            break
    return out


BAY_W, PLANTER_W, BAYS_PER_GROUP = 2.6, 2.4, 5
BAY_RUNS = [(-56.0, -14.4), (-9.4, 50.8)]      # bays along the plaza; the gap is the mid-block crossing
CROSS_Y = -11.9                                # the park's east entrance (path end) <-> the plaza


def west_bays():
    """Perpendicular bays in groups of five with a planted strip (one tree) between groups.
    Returns (bays, planters) as lists of (y0, y1)."""
    bays, planters = [], []
    for y0, y1 in BAY_RUNS:
        y, k = y0, 0
        while y + BAY_W <= y1 + 1e-6:
            if k == BAYS_PER_GROUP and y + PLANTER_W + BAY_W <= y1 + 1e-6:
                planters.append((y, y + PLANTER_W))
                y, k = y + PLANTER_W, 0
                continue
            bays.append((y, y + BAY_W))
            y, k = y + BAY_W, k + 1
    return bays, planters


def south_street_y(x):
    """Centreline of Griboyedov 4th lane along our south side (OSM way 375967213, after OFFSET)."""
    P = [(83.7, -70.8), (42.3, -70.4), (-25.2, -69.9), (-105.9, -70.0), (-147.8, -70.7)]
    for (x0, y0), (x1, y1) in zip(P, P[1:]):
        if min(x0, x1) <= x <= max(x0, x1):
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return -70.4


# zebra crossings: centre, road direction, carriageway width
ZEBRAS = [((WEST_X, CROSS_Y), (0.0, 1.0), WEST_W), ((WEST_X, -60.0), (0.0, 1.0), WEST_W),
          ((-132.0, south_street_y(-132.0)), (1.0, 0.0), 7.0), ((-10.0, south_street_y(-10.0)), (1.0, 0.0), 7.0),
          ((10.0, south_street_y(10.0)), (1.0, 0.0), 7.0), ((0.0, -58.0), (0.0, 1.0), 9.0)]


def street_lamps():
    """(x, y, arm direction x, arm direction y, kind): 8 m steel street lights on the streets around our
    plaza, arms over the carriageway; kind 'street'."""
    out = []
    for y in (-53.0, -26.0, 1.0, 28.0, 55.0):                      # new street, park-side pavement
        out.append((WEST_X - WEST_W / 2 - 0.6, y, 1.0, 0.0, 'street'))
    for x in range(-122, 84, 28):                                   # Griboyedov 4th lane, south pavement
        out.append((float(x), south_street_y(x) - 3.5 - 0.6, 0.0, 1.0, 'street'))
    for i, y in enumerate(range(-52, 60, 22)):                      # the drive between the blocks
        s = -1.0 if i % 2 == 0 else 1.0
        out.append((s * 5.3, float(y), -s, 0.0, 'street'))
    return out


def apply_edits(d):
    d['buildings'] = [b for b in d['buildings'] if b['id'] not in REMOVED_BUILDINGS]
    roads = []
    for r in d['roads']:
        if r['id'] in REMOVED_ROADS:
            continue
        if r['id'] in TO_PATH:
            r = dict(r, kind='park_path', name='park path', pts=_clip_west(r['pts'], PARK_EDGE_X))
            if len(r['pts']) < 2:
                continue
        roads.append(r)
    for i, pts in enumerate(PARK_PATHS):
        roads.append({'id': f'nk_path{i}', 'pts': pts, 'kind': 'park_path', 'name': 'park path', 'lanes': None, 'oneway': None})
    roads.append({'id': 'nk_west', 'pts': west_street(d['roads']), 'kind': 'residential', 'name': 'Griboyedov street 4th lane',
                  'lanes': '2', 'oneway': 'no', 'nk': 'west'})
    d['roads'] = roads
    d['green'].append({'id': 'nk_west_park', 'pts': WEST_PARK, 'kind': 'nk_park'})


def inside(rect, x, y, pad=0.0):
    return rect[0] - pad <= x <= rect[1] + pad and rect[2] - pad <= y <= rect[3] + pad


def poly_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
