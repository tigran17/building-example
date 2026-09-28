"""New Komitas residential complex (Metta Group, Arabkir, Yerevan) - exterior build.

Run:  Blender -b -P Scripts/nk_build.py -- [--out path.blend]

World frame: metres, Z up, X = east, Y = north, origin at the centre of the ensemble
(the 22 m drive between the two courtyard blocks). Block A (west, Phase 1) has the
stepped north-west corner; block B (east) is its mirror image, as in the developer's
site-plan video. Dimensions are reconstructed from the official renders + video
(see Reference/NOTES.md) and are parameters here, not surveyed values.
"""
import sys
import os
import math
import datetime
import numpy as np
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib
import nk_geo, nk_mats, nk_facade, nk_site, nk_trees, nk_context, nk_props, nk_osm, nk_citygen, nk_furniture  # noqa: E402
for m in (nk_geo, nk_mats, nk_facade, nk_site, nk_trees, nk_context, nk_props, nk_osm, nk_citygen, nk_furniture):
    importlib.reload(m)
from nk_geo import MeshBuilder, WORLD  # noqa: E402
from nk_facade import Builders, build_run, ROOF_TOP, PAR  # noqa: E402

PROJECT = os.path.dirname(HERE)
LAT, LON, TZ = 40.2140, 44.5102, 4          # site (Yandex pin on newkomitas.am), UTC+4

# ---- block footprint (block-local, main rectangle 100 x 96 m) --------------------------
W, D, WING = 100.0, 96.0, 17.5
SX, SY = 11.0, 7.0          # outward shift of the stepped north-west "L"
CUT_N, CUT_W = 35.0, 45.0   # where the north / west wings step
OUTER = [(0, 0), (W, 0), (W, D), (CUT_N, D), (CUT_N, D + SY), (-SX, D + SY), (-SX, CUT_W), (0, CUT_W)]
INNER = [(WING, WING), (WING, CUT_W), (-SX + WING, CUT_W), (-SX + WING, D + SY - WING),
         (CUT_N, D + SY - WING), (CUT_N, D - WING), (W - WING, D - WING), (W - WING, WING)]
ROOF_RECTS = [(0, 0, W, WING), (W - WING, WING, W, D), (CUT_N, D - WING, W - WING, D),
              (-SX, D + SY - WING, CUT_N, D + SY), (-SX, CUT_W, -SX + WING, D + SY - WING),
              (0, WING, WING, CUT_W)]
GAP = 22.0
OFFSET_A = (-(GAP / 2 + W), -D / 2)       # block-local -> world for block A

G1 = {1: (6, 11), 2: (6, 11)}
# Scores follow the developer elevation of the long south facade (3 copper frames,
# 2 framed balcony groups, bronze balcony bands at the ends) and the same vocabulary
# for the other faces. Courtyard faces use narrow single frames (f5).
SCORES_OUTER = [
    ("P:f BAL:b7-10 S BAL:b7-10 S F:8.6 S E:g1 BAL:g1 S:g1 BAL:g1 E:g1 S F:7.3 S "
     "E:g2 BAL:g2 S:g2 BAL:g2 E:g2 S F:8.6 S BAL:b7-10 S BAL:b7-10 P:f", G1),          # south
    ("P:f BAL S BAL S F:7.3 S BAL:b8-11 S BAL:b8-11 S F:8.6 S E:g1 BAL:g1 S:g1 BAL:g1 "
     "E:g1 S F:7.3 S BAL S BAL P:f", G1),                                               # east
    ("P:f BAL S BAL S F:7.3 S BAL:b7-10 S BAL:b7-10 S F:7.3 S BAL C:f", {}),            # north (E part)
    ("C S P:f", {}),                                                                    # step return
    ("P:f BAL S F:8.6 S BAL:b7-10 S BAL:b7-10 S BAL P:f", {}),                          # north (W part)
    ("P:f BAL S F:8.6 S E:g1 BAL:g1 S:g1 BAL:g1 E:g1 S F:7.3 S BAL P:f", G1),           # west (N part)
    ("P:f BAL C", {}),                                                                  # step return
    ("C BAL S BAL S F:7.3 S BAL:b7-10 S BAL:b7-10 P:f", {}),                            # west (S part)
]
SCORES_INNER = [
    ("C BAL S F:f5 S BAL P:f", {}),
    ("P:f BAL C", {}),
    ("C BAL S BAL:b8-11 S F:f5 S BAL S BAL C:f", {}),
    ("C:f BAL S F:f5 S BAL C:f", {}),
    ("C S P:f", {}),
    ("P:f BAL S F:f5 S BAL:b7-10 S BAL:b7-10 S F:f5 S BAL C", {}),
    ("C:f BAL S BAL S F:f5 S BAL:b7-10 S BAL:b7-10 S F:f5 S BAL C:f", {}),
    ("C:f BAL S BAL S F:f5 S BAL:b8-11 S BAL:b8-11 S F:f5 S BAL S BAL C:f", {}),
]
# rooftop stair / lift overruns (block-local centre x, y, size along x, size along y)
ROOF_BOXES = [(24, 8.75, 8, 6), (62, 8.75, 8, 6), (91.25, 40, 6, 8), (91.25, 70, 6, 8),
              (60, 87.25, 8, 6), (12, 94.25, 8, 6), (-2.25, 66, 6, 8), (8.75, 30, 6, 8)]


# cameras: name, location, target, lens, resolution, two-point, shift_y, local time for the sun, clouds
CAMERAS = [
    ('CAM_Aerial', (-215, -235, 250), (-8, 2, 0), 32, (2000, 1300), False, None, '2026-09-20T16:00', 0.0),
    # real viewpoints in the OSM neighbourhood (validated against building footprints)
    ('CAM_Street', (-146, -38, 1.65), (-118, 40, 34), 18, (1536, 1920), True, None, '2026-09-20T17:10', 0.2),
    ('CAM_Corner', (-152, -73, 1.65), (-61, -48, 22), 20, (2000, 1300), True, None, '2026-09-20T14:30', 0.5),
    ('CAM_Courtyard', (-47, -14, 1.65), (-44, 35, 28), 16, (1536, 1920), True, None, '2026-09-20T13:00', 0.4),
    ('CAM_Top', (0, 0, 900), (0, 0.001, 0), 50, (2000, 1400), False, None, '2026-09-20T12:30', 0.0),
]
MEADOWS = {}


def save_layout(layout, path):
    import json
    json.dump([[round(float(x), 2), round(float(y), 2), round(float(z), 3), sp, round(float(s), 3)]
               for (x, y, z, sp, s) in layout], open(path, 'w'))


def cross2(u, v):
    return u[0] * v[1] - u[1] * v[0]


def tvec(p, q):
    return (q[0] - p[0], q[1] - p[1])


FACADE_META = []     # per facade run of block A: frame + element positions (apartment hotspots)


def build_block(B, off):
    ox, oy = off
    for side, (poly, scores) in (('outer', (OUTER, SCORES_OUTER)), ('inner', (INNER, SCORES_INNER))):
        P = [(x + ox, y + oy) for x, y in poly]
        n = len(P)
        for i in range(n):
            p0, p1 = P[i], P[(i + 1) % n]
            pp, pn = P[i - 1], P[(i + 2) % n]
            cs = cross2(tvec(pp, p0), tvec(p0, p1)) > 0
            ce = cross2(tvec(p0, p1), tvec(p1, pn)) > 0
            score, groups = scores[i]
            els, fr, L = build_run(B, p0, p1, score, groups, cs, ce)
            FACADE_META.append({'side': side, 'run': i, 'p0': [float(v) for v in fr.p0[:2]],
                                't': [float(v) for v in fr.t[:2]], 'n': [float(v) for v in fr.n[:2]], 'length': L,
                                'elements': [{'t': e['t'], 'a0': round(e['a0'], 3), 'a1': round(e['a1'], 3),
                                              'g': e['g'], 'bz': sorted(e['bz'])} for e in els]})
    # roof surface
    for (x0, y0, x1, y1) in ROOF_RECTS:
        B.roof.add([(x0 + ox, y0 + oy, ROOF_TOP), (x1 + ox, y0 + oy, ROOF_TOP),
                    (x1 + ox, y1 + oy, ROOF_TOP), (x0 + ox, y1 + oy, ROOF_TOP)], [(0, 1, 2, 3)], 'NK_Roof')
    # rooftop overruns with a door and a thin coping
    for (cx, cy, sx, sy) in ROOF_BOXES:
        x0, x1 = cx - sx / 2 + ox, cx + sx / 2 + ox
        y0, y1 = cy - sy / 2 + oy, cy + sy / 2 + oy
        box_world(B.roof, x0, x1, y0, y1, ROOF_TOP, ROOF_TOP + 3.3, 'NK_White', skip=('-z',))
        box_world(B.roof, x0 - 0.05, x1 + 0.05, y0 - 0.05, y1 + 0.05, ROOF_TOP + 3.3, ROOF_TOP + 3.4,
                  'NK_Coping')
        # door on the -y face
        dx = 0.5 * (x0 + x1)
        B.roof.add([(dx - 0.5, y0 - 0.01, ROOF_TOP), (dx + 0.5, y0 - 0.01, ROOF_TOP),
                    (dx + 0.5, y0 - 0.01, ROOF_TOP + 2.2), (dx - 0.5, y0 - 0.01, ROOF_TOP + 2.2)],
                   [(0, 1, 2, 3)], 'NK_DarkMetal')
    # roof equipment (solar rows, condensers, fans, hatches, walkway pads, drains) is in nk_furniture.roof_props


def box_world(mb, x0, x1, y0, y1, z0, z1, mat, skip=()):
    V = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = {'-z': (0, 3, 2, 1), '+z': (4, 5, 6, 7), '-y': (0, 1, 5, 4), '+y': (2, 3, 7, 6),
             '-x': (3, 0, 4, 7), '+x': (1, 2, 6, 5)}
    for k, f in faces.items():
        if k in skip:
            continue
        mb.add([V[i] for i in f], [(0, 1, 2, 3)], mat)


def mirrored(mb, recolor):
    out = MeshBuilder()
    V = np.concatenate(mb.chunks, axis=0) * np.array([-1.0, 1.0, 1.0])
    out.chunks = [V]
    out.nv = len(V)
    out.faces = [list(reversed(f)) for f in mb.faces]
    out.fmat = list(mb.fmat)
    out.fcol = [recolor(c, m) if c is not None else None for c, m in zip(mb.fcol, mb.fmat)]
    return out


# ---- sun ---------------------------------------------------------------------------------
def sun_position(lat, lon, when_local, tz):
    """NOAA-style approximation. Returns (elevation, azimuth clockwise from north), degrees."""
    dt = when_local - datetime.timedelta(hours=tz)
    n = (dt - datetime.datetime(2000, 1, 1, 12)).total_seconds() / 86400.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24
    ha = math.radians(((gmst + lon / 15.0) % 24) * 15.0) - ra
    la = math.radians(lat)
    el = math.asin(math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.sin(ha), math.tan(dec) * math.cos(la) - math.sin(la) * math.cos(ha))
    return math.degrees(el), (math.degrees(az) + 360.0) % 360.0


def add_clouds(nt, sky_col):
    """Flat cumulus layer projected on the sky dome (background + reflections only).
    'CloudAmount' (0 = clear sky) and 'CloudBright' (linear radiance) are set per camera."""
    def n(kind, **kw):
        node = nt.nodes.new(kind)
        for k, v in kw.items():
            setattr(node, k, v)
        return node
    tc = n('ShaderNodeTexCoord')
    sep = n('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs['Vector'])
    dz = n('ShaderNodeMath', operation='MAXIMUM')
    dz.inputs[1].default_value = 0.03
    nt.links.new(sep.outputs['Z'], dz.inputs[0])
    u = n('ShaderNodeMath', operation='DIVIDE')
    v = n('ShaderNodeMath', operation='DIVIDE')
    nt.links.new(sep.outputs['X'], u.inputs[0])
    nt.links.new(dz.outputs[0], u.inputs[1])
    nt.links.new(sep.outputs['Y'], v.inputs[0])
    nt.links.new(dz.outputs[0], v.inputs[1])
    cmb = n('ShaderNodeCombineXYZ')
    nt.links.new(u.outputs[0], cmb.inputs['X'])
    nt.links.new(v.outputs[0], cmb.inputs['Y'])
    no = n('ShaderNodeTexNoise')
    no.inputs['Scale'].default_value = 1.1
    no.inputs['Detail'].default_value = 9.0
    no.inputs['Roughness'].default_value = 0.62
    nt.links.new(cmb.outputs['Vector'], no.inputs['Vector'])
    ramp = n('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.56
    ramp.color_ramp.elements[1].position = 0.72
    nt.links.new(no.outputs['Fac'], ramp.inputs['Fac'])
    hz = n('ShaderNodeMapRange')
    hz.inputs['From Min'].default_value = 0.02
    hz.inputs['From Max'].default_value = 0.22
    nt.links.new(sep.outputs['Z'], hz.inputs['Value'])
    amt = n('ShaderNodeValue', name='CloudAmount', label='CloudAmount')
    amt.outputs[0].default_value = 0.0
    m1 = n('ShaderNodeMath', operation='MULTIPLY')
    nt.links.new(ramp.outputs['Color'], m1.inputs[0])
    nt.links.new(hz.outputs['Result'], m1.inputs[1])
    m2 = n('ShaderNodeMath', operation='MULTIPLY')
    nt.links.new(m1.outputs[0], m2.inputs[0])
    nt.links.new(amt.outputs[0], m2.inputs[1])
    # cloud shading: brighter tops, grey bases (second, offset noise)
    shade = n('ShaderNodeTexNoise')
    shade.inputs['Scale'].default_value = 2.3
    shade.inputs['Detail'].default_value = 4.0
    nt.links.new(cmb.outputs['Vector'], shade.inputs['Vector'])
    bright = n('ShaderNodeValue', name='CloudBright', label='CloudBright')
    bright.outputs[0].default_value = 6.0
    sm = n('ShaderNodeMath', operation='MULTIPLY_ADD')
    sm.inputs[1].default_value = 0.9
    sm.inputs[2].default_value = 0.35
    nt.links.new(shade.outputs['Fac'], sm.inputs[0])
    cb = n('ShaderNodeMath', operation='MULTIPLY')
    nt.links.new(sm.outputs[0], cb.inputs[0])
    nt.links.new(bright.outputs[0], cb.inputs[1])
    ccol = n('ShaderNodeCombineColor')
    for ch, f in (('Red', 1.0), ('Green', 0.985), ('Blue', 0.96)):
        mm = n('ShaderNodeMath', operation='MULTIPLY')
        mm.inputs[1].default_value = f
        nt.links.new(cb.outputs[0], mm.inputs[0])
        nt.links.new(mm.outputs[0], ccol.inputs[ch])
    mix = n('ShaderNodeMix', data_type='RGBA')
    nt.links.new(m2.outputs[0], mix.inputs['Factor'])
    nt.links.new(sky_col, mix.inputs[6])
    nt.links.new(ccol.outputs['Color'], mix.inputs[7])
    return mix.outputs[2]


def setup_world(when, dust=1.2):
    el, az = sun_position(LAT, LON, when, TZ)
    world = bpy.data.worlds.new('NK_Sky')
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new('ShaderNodeTexSky')
    sky.sky_type = 'NISHITA'
    sky.sun_disc = True
    sky.sun_size = math.radians(0.545)
    sky.sun_intensity = 1.0
    sky.sun_elevation = math.radians(el)
    # Blender's Nishita sun_rotation is the compass azimuth (clockwise from +Y = north);
    # verified with a top-down shadow render.
    sky.sun_rotation = math.radians(az) % (2 * math.pi)
    sky.altitude = 1000.0         # Yerevan ~1000 m a.s.l.
    sky.air_density = 1.0
    sky.dust_density = dust
    sky.ozone_density = 1.0
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = 1.0
    out = nt.nodes.new('ShaderNodeOutputWorld')
    col = add_clouds(nt, sky.outputs['Color'])
    nt.links.new(col, bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    world['sun_elevation_deg'] = el
    world['sun_azimuth_deg'] = az
    world['when'] = when.isoformat()
    return el, az


# ---- cameras -----------------------------------------------------------------------------
def camera(name, loc, target, lens, res, two_point=True, shift_x=0.0, shift_y=None, col=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.sensor_height = 24.0
    cd.sensor_fit = 'VERTICAL' if res[1] > res[0] else 'HORIZONTAL'
    cd.clip_start = 0.5
    cd.clip_end = 6000.0
    ob = bpy.data.objects.new(name, cd)
    (col or bpy.context.scene.collection).objects.link(ob)
    ob.location = loc
    dx, dy, dz = (target[0] - loc[0], target[1] - loc[1], target[2] - loc[2])
    yaw = math.atan2(-dx, dy)
    if two_point:
        ob.rotation_euler = (math.pi / 2, 0.0, yaw)
        if shift_y is None:
            # shift so the target sits at frame centre while verticals stay vertical
            fitdim = 24.0 if cd.sensor_fit == 'VERTICAL' else 36.0
            shift_y = math.tan(math.atan2(dz, math.hypot(dx, dy))) * lens / fitdim
        cd.shift_y = shift_y
        cd.shift_x = shift_x
    else:
        pitch = math.atan2(dz, math.hypot(dx, dy))
        ob.rotation_euler = (math.pi / 2 + pitch, 0.0, yaw)
    ob['res'] = list(res)
    return ob


def setup_render(scene):
    scene.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = 'GPU'
    except Exception as ex:  # noqa: BLE001
        print('GPU setup failed:', ex)
    c = scene.cycles
    c.samples = 256
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.use_denoising = True
    c.denoiser = 'OPENIMAGEDENOISE'
    c.max_bounces = 8
    c.diffuse_bounces = 3
    c.glossy_bounces = 4
    c.transmission_bounces = 8
    c.transparent_max_bounces = 8
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 8.0
    c.use_light_tree = True
    scene.render.film_transparent = False
    vs = scene.view_settings
    vs.view_transform = 'AgX'
    for look in ('AgX - Punchy', 'Punchy', 'AgX - Medium High Contrast', 'Medium High Contrast'):
        try:
            vs.look = look
            break
        except TypeError:
            pass
    vs.exposure = -2.8          # Nishita sun/sky are physically bright
    # Late-afternoon warmth like the developer's renders (5900 K was neutral; a higher white point warms
    # the image), and a small toe lift so shadows read as sky-lit grey instead of crushed black.
    vs.use_white_balance = True
    vs.white_balance_temperature = 6700.0
    vs.white_balance_tint = 8.0
    vs.use_curve_mapping = True
    cm = vs.curve_mapping
    cm.curves[3].points[0].location = (0.0, 0.01)
    cm.curves[3].points[-1].location = (1.0, 1.0)
    cm.update()
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_depth = '8'



def sky_probe(scene, az_list, el_deg=3.0, res=24):
    """Mean linear radiance of the sky just above the horizon (for the haze colour)."""
    import tempfile
    cd = bpy.data.cameras.new('probe')
    cd.lens = 18
    ob = bpy.data.objects.new('probe', cd)
    scene.collection.objects.link(ob)
    old = (scene.camera, scene.render.resolution_x, scene.render.resolution_y,
           scene.render.resolution_percentage, scene.cycles.samples, scene.render.filepath,
           scene.render.image_settings.file_format)
    scene.camera = ob
    scene.render.resolution_x = scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.cycles.samples = 8
    scene.render.image_settings.file_format = 'OPEN_EXR'
    acc = np.zeros(3)
    hidden = [o for o in scene.objects if o.type in ('MESH', 'EMPTY') and not o.hide_render]
    for o in hidden:
        o.hide_render = True
    for az in az_list:
        ob.location = (0, 0, 2000)
        ob.rotation_euler = (math.radians(90 + el_deg), 0, -math.radians(az))
        path = os.path.join(tempfile.gettempdir(), 'nk_probe.exr')
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(path, check_existing=False)
        px = np.array(img.pixels[:]).reshape(-1, 4)[:, :3]
        acc += px.mean(axis=0)
        bpy.data.images.remove(img)
    for o in hidden:
        o.hide_render = False
    (scene.camera, scene.render.resolution_x, scene.render.resolution_y,
     scene.render.resolution_percentage, scene.cycles.samples, scene.render.filepath,
     scene.render.image_settings.file_format) = old
    bpy.data.objects.remove(ob)
    return acc / len(az_list)


def setup_compositor(scene, haze, strength=0.55, start=50.0, depth=2200.0):
    """Aerial perspective: mix toward the horizon-sky colour by the mist pass, then put the
    rendered sky (environment pass) back behind the transparent film."""
    vl = scene.view_layers[0]
    vl.use_pass_mist = True
    vl.use_pass_environment = True
    scene.render.film_transparent = True
    ms = scene.world.mist_settings
    ms.start, ms.depth, ms.falloff = start, depth, 'LINEAR'
    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers')
    mul = nt.nodes.new('CompositorNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = strength
    nt.links.new(rl.outputs['Mist'], mul.inputs[0])
    mix = nt.nodes.new('CompositorNodeMixRGB')
    mix.blend_type = 'MIX'
    mix.use_alpha = False
    nt.links.new(mul.outputs[0], mix.inputs[0])
    nt.links.new(rl.outputs['Image'], mix.inputs[1])
    mix.inputs[2].default_value = (float(haze[0]), float(haze[1]), float(haze[2]), 1.0)
    setal = nt.nodes.new('CompositorNodeSetAlpha')
    setal.mode = 'REPLACE_ALPHA'
    nt.links.new(mix.outputs[0], setal.inputs['Image'])
    nt.links.new(rl.outputs['Alpha'], setal.inputs['Alpha'])
    over = nt.nodes.new('CompositorNodeAlphaOver')
    nt.links.new(rl.outputs['Env'], over.inputs[1])
    nt.links.new(setal.outputs[0], over.inputs[2])
    comp = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(over.outputs[0], comp.inputs['Image'])
    scene['haze'] = [float(h) for h in haze]


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = os.path.join(PROJECT, 'Blender', 'NewKomitas-Exterior.blend')
    if '--out' in argv:
        out = argv[argv.index('--out') + 1]

    web = '--web' in argv
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = 'NewKomitas'
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    M = nk_mats.build_library()

    def coll(name, parent=None):
        c = bpy.data.collections.new(name)
        (parent or scene.collection).children.link(c)
        return c

    c_bld = coll('NK_Buildings')
    rng = np.random.default_rng(2026)
    BA = Builders(MeshBuilder, rng)
    build_block(BA, OFFSET_A)

    def recolor(_c, mat):
        return BA.wcol(shop=(mat == 'NK_GlassShop'))

    parts_b = {k: mirrored(v, recolor) for k, v in BA.all().items()}
    for blk, parts in (('A', BA.all()), ('B', parts_b)):
        cb = coll(f'Block_{blk}', c_bld)
        for cat, mb in parts.items():
            ob = mb.to_object(f'NK_{blk}_{cat}', cb, M)
            print(f'Block {blk} {cat}: {len(mb)} faces')

    generic = '--generic' in argv
    c_site = coll('NK_Site')
    c_ctx = coll('NK_Context')
    lib, species = nk_trees.build_library(M, scene.collection)
    scene.view_layers[0].layer_collection.children[lib.name].exclude = True
    c_veg = coll('NK_Vegetation')
    # stills keep trees out of their ground-level camera views; the web scene (free camera, baked tree
    # shadows) must not depend on where the stills' cameras happen to be
    cams_clear = [] if web else [(tuple(c[1][:2]), tuple(c[2][:2])) for c in CAMERAS if c[1][2] < 5]
    if generic:
        nk_site.build_site(c_site, M, rng)
        keep = [nk_site.BLOCK_ZONE, (-10, 430, -430, -84), (-270, -140, 84, 210), (-150, 30, -320, -84)]
        feet = nk_context.build_context(c_ctx, M, np.random.default_rng(5), keep, nk_site.ROADS)
        layout = nk_site.tree_layout(np.random.default_rng(11), cams_clear, feet)
        roads = []
    else:
        # real surroundings: OpenStreetMap (ODbL) roads, parks and buildings around our plaza
        osm = nk_osm.load_world(os.path.join(PROJECT, 'Reference', 'osm_world.json'))
        roads = nk_site.build_site_osm(c_site, M, rng, osm)
        feet = nk_citygen.build(c_ctx, M, osm, [nk_osm.SITE_ZONE], roads=roads)
        layout = nk_site.tree_layout_osm(np.random.default_rng(11), cams_clear, feet, roads, osm)
    # street life (v0.12): lights, benches, bins, bike stands, bollards, canopies, signs, playgrounds, courts,
    # pergolas, roof equipment -> one object with its own lightmap atlas
    props = MeshBuilder()
    nk_furniture.build(props, props, roads)
    props.to_object('NK_Site_Props', c_site, M, merge=False)
    nk_trees.place(c_veg, species, layout, np.random.default_rng(12))
    print('trees placed:', len(layout))
    save_layout(layout, os.path.splitext(out)[0] + '_trees.json')
    if not web:
        # street props: parked cars and lamps (instanced templates); the web app animates its own cars
        plib = bpy.data.collections.new('NK_PropLibrary')
        scene.collection.children.link(plib)
        scene.view_layers[0].layer_collection.children[plib.name].exclude = True
        car_colls = nk_props.build_cars(M, plib)
        c_props = coll('NK_Props')
        # procedural cars only read well small in frame: keep them out of the street-view foreground
        near = [(c[1][0], c[1][1], 80) for c in CAMERAS if c[0] == 'CAM_Street']
        if generic:
            cars = nk_props.layout_cars(np.random.default_rng(31), car_colls, keep_clear=near)
            lamp = nk_props.build_lamp(M, plib)
            nk_props.place(c_props, None, nk_props.layout_lamps(lamp), 'Lamp')
        else:
            cars = nk_props.layout_cars_osm(np.random.default_rng(31), car_colls, roads)
        # cars the street-level stills keep out of their foreground go in their own collection, hidden only
        # for those cameras (camera property 'hide'); the aerial keeps them (bays full, not empty)
        clear, rest = [], []
        for c in cars:
            (clear if any((c[0] - cx) ** 2 + (c[1] - cy) ** 2 < r * r for (cx, cy, r) in near) else rest).append(c)
        nk_props.place(c_props, None, rest, 'Car')
        nk_props.place(coll('NK_Props_StreetClear', c_props), None, clear, 'CarNear')
        print('cars placed:', len(cars), f'({len(clear)} hidden for the street-level stills)')
        for (nm, loc, tgt, *_r) in CAMERAS:
            if nm in MEADOWS:
                nk_site.meadow(c_veg, M, 'NK_Meadow_' + nm, loc[:2], tgt[:2], seed=hash(nm) % 97, **MEADOWS[nm])
        scene.cycles_curves.shape = 'RIBBONS'

    # lighting: late-afternoon September sun (warm, long shadows - matches the renders)
    when = datetime.datetime(2026, 9, 20, 17, 10)
    el, az = setup_world(when)
    print(f'Sun {when}: elevation {el:.1f} deg, azimuth {az:.1f} deg')
    setup_render(scene)
    haze = sky_probe(scene, [(az + d) % 360 for d in (60, 120, 180, 240, 300)])
    print('haze colour (linear):', haze)
    setup_compositor(scene, haze)

    # cameras (world frame, see module doc)
    c_cam = coll('NK_Cameras')
    # 'when' = local time used for the sun when that camera renders (facades it sees are lit)
    for (nm, loc, tgt, lens, res, tp, sh, when_s, clouds) in CAMERAS:
        ob = camera(nm, loc, tgt, lens, res, two_point=tp, shift_y=sh, col=c_cam)
        ob['when'] = when_s
        ob['clouds'] = clouds
        if nm in ('CAM_Street', 'CAM_Corner'):
            ob['hide'] = 'NK_Props_StreetClear'
    scene.camera = bpy.data.objects['CAM_Street']

    os.makedirs(os.path.dirname(out), exist_ok=True)
    import json
    json.dump({'blockA_runs': FACADE_META, 'mirror': 'block B = block A mirrored in x',
               'roof_rects_A': [[x0 + OFFSET_A[0], y0 + OFFSET_A[1], x1 + OFFSET_A[0], y1 + OFFSET_A[1]]
                                for (x0, y0, x1, y1) in ROOF_RECTS]},
              open(os.path.splitext(out)[0] + '_facades.json', 'w'))
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('Saved', out)


if __name__ == '__main__':
    main()
