"""Render cameras of the New Komitas exterior.

Blender -b Blender/NewKomitas-Exterior.blend -P Scripts/nk_render.py -- \
    --cams CAM_Street,CAM_Aerial --scale 0.5 --samples 64 --tag test [--exposure -3.5]
"""
import sys
import os
import time
import bpy

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scene = bpy.context.scene
cams = arg('--cams', 'CAM_Street').split(',')
scale = float(arg('--scale', '0.5'))
samples = int(arg('--samples', '64'))
tag = arg('--tag', 'test')
exposure = arg('--exposure')
outdir = arg('--outdir', os.path.join(PROJECT, 'Renders', tag))
os.makedirs(outdir, exist_ok=True)

prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'METAL'
prefs.get_devices()
for d in prefs.devices:
    d.use = True
scene.cycles.device = 'GPU'
scene.cycles.samples = samples
if exposure is not None:
    scene.view_settings.exposure = float(exposure)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datetime  # noqa: E402
import math  # noqa: E402
import nk_build  # noqa: E402  (safe: main() only runs as a script)


def set_time(when_s):
    when = datetime.datetime.fromisoformat(when_s)
    el, az = nk_build.sun_position(nk_build.LAT, nk_build.LON, when, nk_build.TZ)
    sky = scene.world.node_tree.nodes['Sky Texture']
    sky.sun_elevation = math.radians(el)
    sky.sun_rotation = math.radians(az) % (2 * math.pi)
    haze = nk_build.sky_probe(scene, [(az + d) % 360 for d in (60, 120, 180, 240, 300)])
    for n in scene.node_tree.nodes:
        if n.bl_idname == 'CompositorNodeMixRGB':
            n.inputs[2].default_value = (float(haze[0]), float(haze[1]), float(haze[2]), 1.0)
    nodes = scene.world.node_tree.nodes
    if 'CloudBright' in nodes:
        nodes['CloudBright'].outputs[0].default_value = float(max(haze) * 1.9)
    print(f'TIME {when_s}: sun el {el:.1f} az {az:.1f}, haze {haze.round(2)}')


for cam in cams:
    ob = bpy.data.objects[cam]
    scene.camera = ob
    if arg('--when') or ob.get('when'):
        set_time(arg('--when') or ob['when'])
    wn = scene.world.node_tree.nodes
    if 'CloudAmount' in wn:
        wn['CloudAmount'].outputs[0].default_value = float(arg('--clouds', ob.get('clouds', 0.0)))
    hide = set(filter(None, str(ob.get('hide', '')).split(',')))
    for c in bpy.data.collections:
        if c.name.startswith('NK_Props_'):
            c.hide_render = c.name in hide
    res = ob.get('res', [1920, 1080])
    scene.render.resolution_x, scene.render.resolution_y = int(res[0]), int(res[1])
    scene.render.resolution_percentage = int(round(scale * 100))
    scene.render.filepath = os.path.join(outdir, f'{cam}.png')
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'RENDERED {cam} in {time.time() - t:.1f}s -> {scene.render.filepath}')
