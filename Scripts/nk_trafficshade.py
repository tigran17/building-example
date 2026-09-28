"""Sun visibility for the web traffic, precomputed so the browser never ray-casts.

For every lane sample and parked car in Website/assets/traffic-routes.json, five rays toward the baked
sun (scene-presentation.json) start from points on the car (nose, tail, both sides, centre; 1.1 m high)
and are cast against the web scene: both blocks, the neighbouring buildings and the instanced trees.
shade = 0.44 + 0.56 * lit fraction (0.44 = ambient only, as the old runtime test used), smoothed over
~2.5 m along each lane. Written back as a 4th value per lane sample ([x, z, s, shade]) and as 'shade'
per parked car. traffic.js interpolates it; nothing is ray-cast at runtime any more.

blender -b Blender/NewKomitas-Web.blend -P Scripts/nk_trafficshade.py   (after nk_webdata.py)
"""
import json
import math
import os
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
SITE = os.path.join(PROJECT, 'Website', 'assets')
AMBIENT = 0.44
PROBES = ((0.0, 0.0), (1.5, 0.0), (-1.5, 0.0), (0.0, 0.7), (0.0, -0.7))   # (along, across) the car, metres


def main():
    t0 = time.time()
    pres = json.load(open(os.path.join(SITE, 'scene-presentation.json')))
    sx, sy, sz = pres['lighting']['sunDirection']              # direction the light travels
    sun = Vector((-sx, -sy, -sz)).normalized()                  # towards the sun, Blender axes
    path = os.path.join(SITE, 'traffic-routes.json')
    routes = json.load(open(path))
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    hits = {}

    def lit(x, y, ax, ay):
        n = 0
        for a, b in PROBES:
            origin = Vector((x + ax * a - ay * b, y + ay * a + ax * b, 1.1))
            ok, _, _, _, ob, _ = scene.ray_cast(depsgraph, origin, sun, distance=800.0)
            if ok:
                key = ob.name.split('.')[0].split('_')[0] + '_' + ob.name.split('_')[1] if '_' in ob.name else ob.name
                hits[key] = hits.get(key, 0) + 1
            else:
                n += 1
        return n / len(PROBES)

    for row in routes['parked']:
        x, y, _ = row['position']
        r = row['rotation']                                     # nk_webdata: atan2(-fx, fy)
        row['shade'] = round(AMBIENT + (1 - AMBIENT) * lit(x, y, -math.sin(r), math.cos(r)), 3)

    for lane in routes['lanes']:
        S = lane['samples']                                     # [x, -y, s] in three.js axes
        raw = []
        for i, sample in enumerate(S):
            x, z = sample[0], sample[1]                         # re-runs: samples already carry a shade
            j0, j1 = max(0, i - 1), min(len(S) - 1, i + 1)
            dx, dy = S[j1][0] - S[j0][0], -(S[j1][1] - S[j0][1])
            d = math.hypot(dx, dy) or 1.0
            raw.append(lit(x, -z, dx / d, dy / d))
        k = 3                                                   # +-3 samples = +-1.2 m
        for i, sample in enumerate(S):
            win = raw[max(0, i - k):i + k + 1]
            sample[3:] = [round(AMBIENT + (1 - AMBIENT) * sum(win) / len(win), 3)]

    routes['shade'] = {'ambient': AMBIENT, 'probes': len(PROBES), 'sun': [round(v, 4) for v in sun],
                       'source': 'Blender ray casts against the baked web scene (nk_trafficshade.py)'}
    json.dump(routes, open(path, 'w'), separators=(',', ':'))
    n = sum(len(l['samples']) for l in routes['lanes'])
    shaded = sum(1 for l in routes['lanes'] for s in l['samples'] if s[3] < 0.99)
    print(f'SHADE lanes {len(routes["lanes"])} samples {n} ({shaded} in shade), parked {len(routes["parked"])} '
          f'({sum(1 for r in routes["parked"] if r["shade"] < 0.99)} in shade) in {time.time() - t0:.1f}s')
    print('SHADE hits by object', sorted(hits.items(), key=lambda kv: -kv[1])[:12])


if __name__ == '__main__':
    main()
