"""Bake the New Komitas web model: Cycles lighting -> display-referred lightmap atlases -> GLB.

Blender -b Blender/NewKomitas-Web.blend -P Scripts/nk_web.py -- [steps]
steps (comma list, default prep,bake,export): prep | bake | export | env | trees
env: NK_BAKE_SAMPLES (96), NK_WEB_WHEN (2026-09-20T16:30), NK_SKIP_EXISTING=1, NK_ONLY=name,name

Everything static and matte is baked with the full Cycles lighting (sun + sky + bounces, the
same AgX view transform as the stills) into textures shown unlit in the browser. Glass stays
PBR so it keeps live reflections. Output: Web-Build/ (float lightmaps, JPEG atlases, GLBs).
"""
import os
import sys
import json
import math
import time
import subprocess
import datetime
import numpy as np
import bpy
import bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nk_build  # noqa: E402

PROJECT = os.path.dirname(HERE)
OUT = os.path.join(PROJECT, 'Web-Build')
LMF = os.path.join(OUT, 'lightmaps-float')
TEX = os.path.join(OUT, 'textures')
for d in (OUT, LMF, TEX):
    os.makedirs(d, exist_ok=True)
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
STEPS = (argv[0] if argv else 'prep,bake,export').split(',')
SAMPLES = int(os.environ.get('NK_BAKE_SAMPLES', '96'))
DARK_TEXEL = 0.004          # scene-linear radiance below which a baked texel counts as unlit (median ~0.4)
# Photographic shadow range (see shadow_fill): soft knee in log space, shadows compressed to 40 % contrast.
SHADOW_KNEE, SHADOW_SLOPE, SHADOW_SHARP = math.log2(1.6), 0.4, 1.5   # see shadow_fill (log2 units)
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)
WHEN = os.environ.get('NK_WEB_WHEN', '2026-09-20T16:30')
ONLY = [s for s in os.environ.get('NK_ONLY', '').split(',') if s]
scene = bpy.context.scene


def log(*a):
    print('[nk_web]', *a, flush=True)


# ---- targets --------------------------------------------------------------------------------------
# name -> (atlas px, source objects joined into it)
MESH_TARGETS = {
    'NK_A_Shell': (4096, ['NK_A_Walls', 'NK_A_Bronze', 'NK_A_Roof']),
    'NK_A_Balconies': (4096, ['NK_A_Balconies']),
    'NK_B_Shell': (4096, ['NK_B_Walls', 'NK_B_Bronze', 'NK_B_Roof']),
    'NK_B_Balconies': (4096, ['NK_B_Balconies']),
    'NK_ContextNearW': (4096, ['NK_Context_NearW']),     # neighbours with window geometry (< 330 m)
    'NK_ContextNearE': (4096, ['NK_Context_NearE']),
    'NK_ContextFar': (4096, ['NK_Context_Far']),         # far city: painted window grid
    'NK_SiteProps': (2048, ['NK_Site_Props']),           # street furniture, playgrounds, roof equipment (v0.12)
}
# ground tiles baked from the layered site meshes (selected -> active); last one is the far field
GX = [-330, -110, 110, 330]
GY = [-230, 0, 230]
GROUND_TILES = {f'NK_Ground_{i}{j}': (2048, (GX[i], GX[i + 1], GY[j], GY[j + 1])) for i in range(3) for j in range(2)}
GROUND_TILES['NK_Ground_Far'] = (2048, (-1600, 1600, -1600, 1600))
GROUND_SOURCES = ['NK_Site_Ground', 'NK_Site_Roads', 'NK_Site_Paving']
Z_TILE, Z_FAR = 0.22, 0.20


def set_sun(when_s):
    when = datetime.datetime.fromisoformat(when_s)
    el, az = nk_build.sun_position(nk_build.LAT, nk_build.LON, when, nk_build.TZ)
    sky = scene.world.node_tree.nodes['Sky Texture']
    sky.sun_elevation = math.radians(el)
    sky.sun_rotation = math.radians(az) % (2 * math.pi)
    if 'CloudAmount' in scene.world.node_tree.nodes:
        scene.world.node_tree.nodes['CloudAmount'].outputs[0].default_value = 0.0
    scene['web_sun'] = [el, az]
    log(f'sun {when_s}: elevation {el:.1f}, azimuth {az:.1f}')
    return el, az


def gpu(samples):
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'GPU'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False


def only_select(objs, active=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (objs[0] if objs else None)


def join(name, parts):
    objs = [bpy.data.objects[p] for p in parts if p in bpy.data.objects]
    if not objs:
        return None
    if len(objs) == 1 and objs[0].name == name:
        return objs[0]
    only_select(objs, objs[0])
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    o.data.name = name
    return o


def lightmap_uvs(o, px):
    """Smart-project islands at true world scale, then pack with ~4 px gutters."""
    me = o.data
    if 'LM' in me.uv_layers:
        me.uv_layers.remove(me.uv_layers['LM'])
    lm = me.uv_layers.new(name='LM')
    me.uv_layers.active = lm
    only_select([o], o)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, rotate_method='CARDINAL', scale=True,
                            merge_overlap=False, margin_method='FRACTION', margin=3.0 / px, pin=False,
                            shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')


def ground_tile(name, rect, z):
    x0, x1, y0, y1 = rect
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='LM')
    for li, (u, v) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[li].uv = (u, v)
    m = bpy.data.materials.new(name + '_mat')
    m.use_nodes = True
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    col = bpy.data.collections.get('NK_WebGround') or bpy.data.collections.new('NK_WebGround')
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    col.objects.link(ob)
    # bake target only: invisible to every lighting ray so it never shadows the layers it samples
    ob.visible_shadow = ob.visible_diffuse = ob.visible_glossy = ob.visible_transmission = False
    ob.visible_volume_scatter = False
    return ob


# ---- bake helpers (lightmap pipeline from the interior viewer) ---------------------------------------
def pixels(img):
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


def float_image(name, arr, colorspace='Non-Color'):
    h, w = arr.shape[:2]
    a4 = np.ones((h, w, 4), np.float32)
    a4[..., :3] = arr[..., :3]
    im = bpy.data.images.new(name, w, h, alpha=True, float_buffer=True)
    im.colorspace_settings.name = colorspace
    im.pixels.foreach_set(a4.ravel())
    return im


def push_pull(rgb, valid):
    H, W = valid.shape
    P = 1 << max(H - 1, W - 1, 1).bit_length()
    c = np.zeros((P, P, rgb.shape[2]), np.float32)
    w = np.zeros((P, P), np.float32)
    c[:H, :W] = rgb * valid[..., None]
    w[:H, :W] = valid
    levels = []
    while c.shape[0] > 1:
        levels.append((c, w))
        h2 = c.shape[0] // 2
        c = c.reshape(h2, 2, h2, 2, -1).sum((1, 3))
        w = w.reshape(h2, 2, h2, 2).sum((1, 3))
    fill = c / np.maximum(w, 1e-8)[..., None]
    for cl, wl in reversed(levels):
        up = np.repeat(np.repeat(fill, 2, 0), 2, 1)
        fill = np.where((wl > 0)[..., None], cl / np.maximum(wl, 1e-8)[..., None], up)
    return fill[:H, :W].astype(np.float32)


def set_bake_target(o, img):
    for m in set(o.data.materials):
        if m is None:
            continue
        m.use_nodes = True
        nt = m.node_tree
        n = nt.nodes.get('LM_BAKE') or nt.nodes.new('ShaderNodeTexImage')
        n.name = 'LM_BAKE'
        n.image = img
        nt.nodes.active = n


def clear_bake_nodes():
    for m in bpy.data.materials:
        if m.use_nodes and 'LM_BAKE' in m.node_tree.nodes:
            m.node_tree.nodes.remove(m.node_tree.nodes['LM_BAKE'])


def bake_one(o, size, kind, sources=None, samples=None):
    """kind: COMBINED | NORMAL | ALBEDO. Returns (H, W, 4) float pixels; alpha < -0.5 = unwritten."""
    img = bpy.data.images.new(f'bk_{o.name}_{kind}', size, size, alpha=True, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(np.full(size * size * 4, -1.0, np.float32))
    set_bake_target(o, img)
    sel = [bpy.data.objects[s] for s in (sources or [])] + [o]
    only_select(sel, o)
    kw = dict(margin=16, margin_type='EXTEND', use_clear=False, uv_layer='LM')
    if sources:
        kw.update(use_selected_to_active=True, cage_extrusion=2.0, max_ray_distance=4.0)
    bk = scene.render.bake
    scene.cycles.samples = samples or SAMPLES
    if kind == 'COMBINED':
        bpy.ops.object.bake(type='COMBINED', pass_filter={'DIRECT', 'INDIRECT', 'DIFFUSE', 'GLOSSY', 'EMIT'}, **kw)
    elif kind == 'NORMAL':
        scene.cycles.samples = 4
        bpy.ops.object.bake(type='NORMAL', normal_space='OBJECT', **kw)
    else:
        scene.cycles.samples = 4
        bk.use_pass_direct = bk.use_pass_indirect = False
        bk.use_pass_color = True
        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, **kw)
    px = pixels(img)
    bpy.data.images.remove(img)
    return px


def denoise(rgb, normal, albedo, tag):
    sc = bpy.data.scenes.get('LMDenoise')
    if sc is None:
        sc = bpy.data.scenes.new('LMDenoise')
        cam = bpy.data.objects.new('LMDenoiseCam', bpy.data.cameras.new('LMDenoiseCam'))
        sc.collection.objects.link(cam)
        sc.camera = cam
        sc.render.engine = 'BLENDER_WORKBENCH'
        sc.use_nodes = True
        sc.view_settings.view_transform = 'Standard'
    nt = sc.node_tree
    nt.nodes.clear()
    ims = [float_image(f'dn_{tag}_c', rgb)]
    ni = nt.nodes.new('CompositorNodeImage')
    ni.image = ims[0]
    nd = nt.nodes.new('CompositorNodeDenoise')
    nd.use_hdr = True
    if hasattr(nd, 'quality'):
        nd.quality = 'HIGH'
    nd.prefilter = 'NONE'
    nt.links.new(ni.outputs['Image'], nd.inputs['Image'])
    for key, arr in (('Normal', normal), ('Albedo', albedo)):
        im = float_image(f'dn_{tag}_{key}', arr)
        ims.append(im)
        n = nt.nodes.new('CompositorNodeImage')
        n.image = im
        nt.links.new(n.outputs['Image'], nd.inputs[key])
    no = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(nd.outputs['Image'], no.inputs['Image'])
    h, w = rgb.shape[:2]
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    path = os.path.join(TEX, f'_dn_{tag}.exr')
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    d = bpy.data.images.load(path, check_existing=False)
    out = pixels(d)[..., :3].copy()
    bpy.data.images.remove(d)
    for im in ims:
        bpy.data.images.remove(im)
    os.remove(path)
    return out


def shadow_fill(rgb):
    """Photographic shadow range: a soft knee in log space. Above ~1.6 (sunlit) radiance passes through;
    below it the log-contrast is compressed to 40 %, applied as a gain so colours keep their ratios.
    Measured through the lightmaps' view transform (AgX Punchy, -2.8 EV, 8-bit): radiance 0.005 -> 15/255,
    0.02 -> 30, 0.05 -> 40, 0.2 (shaded courtyard lawn) -> 60, 0.44 (shaded path) -> 76, 1.0 -> 94,
    2.2 -> 121, 5 (sunlit plaza) -> 162. Before (v0.10-0.12 additive fill) 0.2 showed at 28 and deep shade at 14."""
    L = np.maximum(rgb[..., :3] @ LUMA, 1e-6)
    x = np.log2(L)
    z = SHADOW_SHARP * (SHADOW_KNEE - x)
    soft = np.where(z > 30, z, np.log1p(np.exp(np.minimum(z, 30)))) / SHADOW_SHARP
    k = np.exp2((1.0 - SHADOW_SLOPE) * soft)
    return rgb[..., :3] * k[..., None]


def write_display(rgb, stem, quality=90):
    """Scene-referred lightmap -> shadow range -> the stills' view transform (AgX, exposure, white balance) -> JPEG."""
    im = float_image(f'disp_{stem}', shadow_fill(rgb), colorspace='Linear Rec.709')
    ims = scene.render.image_settings
    prev = (ims.file_format, ims.color_depth, ims.color_mode)
    ims.file_format, ims.color_depth, ims.color_mode = 'PNG', '8', 'RGB'
    png = os.path.join(TEX, stem + '.png')
    im.save_render(png, scene=scene)
    ims.file_format, ims.color_depth, ims.color_mode = prev
    bpy.data.images.remove(im)
    jpg = os.path.join(TEX, stem + '.jpg')
    subprocess.run(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-y', '-i', png, '-q:v', '2', jpg], check=True)
    half = os.path.join(TEX, stem + '_half.jpg')
    subprocess.run(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-y', '-i', png, '-vf', 'scale=iw/2:ih/2:flags=area',
                    '-q:v', '3', half], check=True)
    os.remove(png)
    return jpg


def bake_target(o, size, sources=None):
    stem = 'lm_' + o.name
    exr = os.path.join(LMF, stem + '.npy')
    if os.environ.get('NK_SKIP_EXISTING') and os.path.exists(os.path.join(TEX, stem + '.jpg')):
        log('kept', stem)
        return
    t0 = time.time()
    nrm = bake_one(o, size, 'NORMAL', sources)
    alb = bake_one(o, size, 'ALBEDO', sources)
    px = bake_one(o, size, 'COMBINED', sources)
    tb = time.time() - t0
    valid = px[..., 3] > -0.5
    # Texels that see no light at all (ground under buildings, faces hidden inside the model) bake pure
    # black. Refill them from their surroundings like empty atlas space: left black they bleed into
    # visible ground and walls at lower mip levels (dark halos that shift while the camera moves).
    lit = valid & (px[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32) > DARK_TEXEL)
    rgb = push_pull(np.maximum(px[..., :3], 0.0), lit)
    nrm = push_pull(nrm[..., :3] * 2.0 - 1.0, valid)
    alb = push_pull(np.clip(alb[..., :3], 0, 1), valid)
    t1 = time.time()
    rgb = np.maximum(denoise(rgb, nrm, alb, stem), 0.0)
    np.save(exr, rgb.astype(np.float16))
    write_display(rgb, stem)
    L = rgb[valid] if valid.any() else np.zeros((1, 3))
    log(f'baked {o.name} {size}px: {valid.mean():.0%} texels used ({(valid & ~lit).mean():.0%} unlit refilled), '
        f'bake {tb:.0f}s + denoise {time.time() - t1:.0f}s, '
        f'radiance p5/median/p99 = {np.percentile(L, 5):.2f}/{np.median(L):.2f}/{np.percentile(L, 99):.2f}')


# ---- steps ------------------------------------------------------------------------------------------
def step_prep():
    set_sun(WHEN)
    for name, (px, parts) in MESH_TARGETS.items():
        o = join(name, parts)
        if o is None:
            log('missing', name)
            continue
        t = time.time()
        lightmap_uvs(o, px)
        log(f'uv {name}: {len(o.data.polygons)} faces in {time.time() - t:.1f}s')
    for name, (px, rect) in GROUND_TILES.items():
        if name not in bpy.data.objects:
            ground_tile(name, rect, Z_FAR if name.endswith('Far') else Z_TILE)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(PROJECT, 'Blender', 'NewKomitas-Web-baked.blend'), compress=True)
    log('prep saved')


# Courtyard fill: the 56 m deep courtyards only see a strip of sky and three bounces off their walls, so at
# 16:30 their floors bake at ~12 % of the sunlit ground. Soft area lights just under the roofline, facing down,
# stand in for the light the sunlit upper facades throw into them (the developer's renders show bright courtyards).
# (centre x, centre y, size x, size y); block B mirrors A.
COURT_FILL = [(-61.0, 0.0, 63.0, 59.0), (-99.0, 17.3, 9.8, 39.0), (-85.0, 34.0, 16.0, 6.0)]
COURT_FILL_Z = 52.0
COURT_FILL_W = float(os.environ.get('NK_COURT_FILL', '16'))     # W per m2 of light (calibrated, see README); 0 = off


def court_fill(w_per_m2):
    n = 0
    for s in (1.0, -1.0):
        for i, (cx, cy, sx, sy) in enumerate(COURT_FILL):
            name = f'WEB_CourtFill_{"A" if s > 0 else "B"}{i}'
            ld = bpy.data.lights.get(name) or bpy.data.lights.new(name, 'AREA')
            ld.shape = 'RECTANGLE'
            ld.size, ld.size_y = sx, sy
            ld.energy = w_per_m2 * sx * sy
            ld.color = (1.0, 0.965, 0.92)            # warm: bounced off sunlit white and copper facades
            ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, ld)
            if ob.name not in scene.collection.objects:
                scene.collection.objects.link(ob)
            ob.location = (s * cx, cy, COURT_FILL_Z)
            ob.rotation_euler = (0.0, 0.0, 0.0)       # area lights emit along -Z
            ob.visible_glossy = False
            n += 1
    log(f'courtyard fill: {n} area lights, {w_per_m2:.1f} W/m2')


def step_bake():
    gpu(SAMPLES)
    set_sun(WHEN)
    if COURT_FILL_W > 0:
        court_fill(COURT_FILL_W)
    for name, (px, parts) in MESH_TARGETS.items():
        if ONLY and name not in ONLY:
            continue
        bake_target(bpy.data.objects[name], px)
    for name, (px, rect) in GROUND_TILES.items():
        if ONLY and name not in ONLY:
            continue
        bake_target(bpy.data.objects[name], px, sources=GROUND_SOURCES)
    clear_bake_nodes()


# ---- export -----------------------------------------------------------------------------------------
SITE = os.path.join(PROJECT, 'Website', 'assets')


def srgb_lin(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def web_pbr(name, base, rough, metal=0.0, ior=1.5, spec=0.5, alpha=1.0, vcol=False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    p.inputs['Base Color'].default_value = (*srgb_lin(base), 1.0)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    p.inputs['IOR'].default_value = ior
    p.inputs['Specular IOR Level'].default_value = spec
    if vcol:
        ca = nt.nodes.new('ShaderNodeVertexColor')
        ca.layer_name = 'WebCol'
        nt.links.new(ca.outputs['Color'], p.inputs['Base Color'])
    if alpha < 1.0:
        p.inputs['Alpha'].default_value = alpha
        if hasattr(m, 'surface_render_method'):
            m.surface_render_method = 'BLENDED'
        m.blend_method = 'BLEND'
    return m


GLASS_WEB = {
    'NK_GlassWindow': lambda: web_pbr('Glass_Window', '#FFFFFF', 0.04, ior=1.9, spec=0.7, vcol=True),
    'NK_GlassShop': lambda: web_pbr('Glass_Shop', '#FFFFFF', 0.04, ior=1.9, spec=0.7, vcol=True),
    'NK_GlassCurtain': lambda: web_pbr('Glass_Curtain', '#1B2631', 0.03, ior=2.3, spec=0.8),
    'NK_GlassSpandrel': lambda: web_pbr('Glass_Spandrel', '#232B33', 0.08, ior=2.0, spec=0.7),
    'NK_DarkMetal': lambda: web_pbr('Metal_Dark', '#2E3033', 0.4, metal=0.6),
    'NK_GlassRail': lambda: web_pbr('Glass_Rail', '#DCE6E4', 0.05, ior=1.5, alpha=0.28),
}


def glass_colors(me):
    """Per-window web tint from the build's 'Col' attribute (R curtain amount, G interior light)."""
    if 'Col' not in me.color_attributes:
        return
    src = me.color_attributes['Col']
    n = len(me.loops)
    a = np.zeros(n * 4, np.float32)
    src.data.foreach_get('color', a)
    a = a.reshape(-1, 4)
    dark = np.array(srgb_lin('#161C22'))       # dim interiors, not black holes (glass reflects ~10% only)
    curtain = np.array(srgb_lin('#7A7162'))
    shop = np.array(srgb_lin('#9C8A6A'))
    mi = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get('material_index', mi)
    lt = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get('loop_total', lt)
    loop_mat = np.repeat(mi, lt)
    names = [m.name if m else '' for m in me.materials]
    is_shop = np.array([names[k].startswith('Glass_Shop') or names[k] == 'NK_GlassShop' for k in loop_mat])
    R, G = a[:, 0:1], a[:, 1:2]
    col = dark * (1 - R * 0.55) + curtain * (R * 0.55)
    col = col * (0.75 + 0.5 * G)
    col = np.where(is_shop[:, None], dark * 0.5 + shop * 0.5 * (0.6 + 0.6 * G), col)
    out = me.color_attributes.get('WebCol') or me.color_attributes.new('WebCol', 'FLOAT_COLOR', 'CORNER')
    rgba = np.concatenate([col, np.ones((n, 1))], axis=1).astype(np.float32)
    out.data.foreach_set('color', rgba.ravel())


def web_copy(src_name, new_name):
    src = bpy.data.objects[src_name]
    ob = src.copy()
    ob.data = src.data.copy()
    ob.name = new_name
    ob.data.name = new_name
    col = bpy.data.collections.get('WEB_EXPORT') or bpy.data.collections.new('WEB_EXPORT')
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    col.objects.link(ob)
    ob.visible_camera = True
    return ob


def baked_material(name, jpg):
    m = bpy.data.materials.new('Baked_' + name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = bpy.data.images.load(jpg, check_existing=True)
    tx.interpolation = 'Linear'
    nt.links.new(tx.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 1.0
    p.inputs['Specular IOR Level'].default_value = 0.0
    return m, tx


def make_export_objects():
    objs = []
    texnodes = []
    targets = list(MESH_TARGETS.items()) + [(k, (v[0], None)) for k, v in GROUND_TILES.items()]
    for name, (px, _) in targets:
        jpg = os.path.join(TEX, f'lm_{name}.jpg')
        if not os.path.exists(jpg):
            log('no lightmap for', name, '- skipped')
            continue
        tag = 'site' if name == 'NK_Ground_Far' else name.replace('NK_', '')
        ob = web_copy(name, 'WEB_' + name)
        me = ob.data
        for uv in [u for u in me.uv_layers if u.name != 'LM']:
            me.uv_layers.remove(uv)
        for ca in list(me.color_attributes):
            me.color_attributes.remove(ca)
        me.materials.clear()
        m, tx = baked_material(tag, jpg)
        me.materials.append(m)
        me.polygons.foreach_set('material_index', np.zeros(len(me.polygons), np.int32))
        ob.visible_shadow = ob.visible_diffuse = ob.visible_glossy = True
        objs.append(ob)
        texnodes.append((tx, jpg))
    for blk in ('A', 'B'):
        ob = web_copy(f'NK_{blk}_Glazing', f'WEB_NK_{blk}_Glazing')
        me = ob.data
        glass_colors(me)
        for i, m in enumerate(me.materials):
            if m and m.name in GLASS_WEB:
                me.materials[i] = GLASS_WEB[m.name]()
        for uv in list(me.uv_layers):
            me.uv_layers.remove(uv)
        objs.append(ob)
    return objs, texnodes


def export_glb(objs, path):
    only_select(objs, objs[0])
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                              export_yup=True, export_texcoords=True, export_normals=True,
                              export_materials='EXPORT', export_image_format='AUTO',
                              export_vertex_color='MATERIAL', export_cameras=False, export_lights=False,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                              export_draco_position_quantization=16, export_draco_normal_quantization=10,
                              export_draco_texcoord_quantization=14, export_draco_color_quantization=10,
                              export_extras=False)
    log(f'exported {path} ({os.path.getsize(path) / 1e6:.1f} MB)')


def step_export():
    os.makedirs(SITE, exist_ok=True)
    objs, texnodes = make_export_objects()
    export_glb(objs, os.path.join(SITE, 'new-komitas-complex.glb'))
    for tx, jpg in texnodes:
        tx.image = bpy.data.images.load(jpg.replace('.jpg', '_half.jpg'), check_existing=True)
    export_glb(objs, os.path.join(SITE, 'new-komitas-complex-mobile.glb'))
    # phones load a KTX2 (ETC1S) copy of the mobile model; the JPEG one stays as the fallback
    subprocess.run(['/usr/bin/python3', os.path.join(HERE, 'nk_ktx2.py'), os.path.join(SITE, 'new-komitas-complex-mobile.glb'),
                    os.path.join(SITE, 'new-komitas-complex-mobile-ktx2.glb')], check=True)
    # desktops open with that model too, then stream the full-resolution lightmaps from assets/lm/
    subprocess.run(['/usr/bin/python3', os.path.join(HERE, 'nk_ktx2.py'), '--textures', os.path.join(SITE, 'new-komitas-complex.glb'),
                    os.path.join(SITE, 'lm')], check=True)
    # tree instances straight from the scene (same rotations/scales as the baked shadows)
    rows = []
    rng = np.random.default_rng(3)
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and o.instance_collection and o.instance_collection.name.startswith('TT_'):
            sp = o.instance_collection.name[3:]
            t = [float(round(v, 3)) for v in rng.uniform(0.9, 1.06, 3)]
            rows.append({'position': [round(o.location.x, 2), round(o.location.y, 2), round(o.location.z, 3)],
                         'scale': round(o.scale.x, 3), 'rotation': round(o.rotation_euler.z % (2 * math.pi), 4),
                         'species': sp, 'tint': t})
    json.dump(rows, open(os.path.join(SITE, 'tree-instances.json'), 'w'), separators=(',', ':'))
    log('trees exported:', len(rows))


# ---- environment, sky, presentation -------------------------------------------------------------------
def pano_camera(loc):
    cd = bpy.data.cameras.get('WEB_Pano') or bpy.data.cameras.new('WEB_Pano')
    cd.type = 'PANO'
    cd.panorama_type = 'EQUIRECTANGULAR'
    ob = bpy.data.objects.get('WEB_Pano') or bpy.data.objects.new('WEB_Pano', cd)
    if ob.name not in scene.collection.objects:
        scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (math.pi / 2, 0.0, -math.pi / 2)      # looks along +X: Blender/three world HDRI convention
    return ob


def render_to(path, fmt, w, h, samples, transparent=False, compositor=False, depth='8'):
    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.film_transparent = transparent
    scene.use_nodes = compositor
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    r.image_settings.file_format = fmt
    if fmt == 'PNG':
        r.image_settings.color_depth = depth
        r.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    elif fmt == 'OPEN_EXR':
        r.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    r.filepath = path
    bpy.ops.render.render(write_still=True)


def hide_for(names_prefix_keep=None, hide_prefixes=()):
    changed = []
    for o in scene.objects:
        if o.type in ('MESH', 'EMPTY', 'CURVE') and any(o.name.startswith(p) for p in hide_prefixes) and not o.hide_render:
            o.hide_render = True
            changed.append(o)
    return changed


def step_env():
    gpu(64)
    el, az = set_sun(WHEN)
    os.makedirs(SITE, exist_ok=True)
    sky = scene.world.node_tree.nodes['Sky Texture']
    cam = pano_camera((0.0, 0.0, 28.0))
    scene.camera = cam
    # 1. reflections: real surroundings + sky, our blocks hidden, sun disc off (no PMREM fireflies)
    hidden = hide_for(hide_prefixes=('NK_A_', 'NK_B_', 'WEB_', 'NK_Ground_'))
    sky.sun_disc = False
    tmp = os.path.join(TEX, 'env_linear.exr')
    render_to(tmp, 'OPEN_EXR', 2048, 1024, 48)
    img = bpy.data.images.load(tmp, check_existing=False)
    px = pixels(img)[..., :3] * (2.0 ** scene.view_settings.exposure)   # pre-apply the -3 EV exposure
    bpy.data.images.remove(img)
    hdr = float_image('env_hdr', np.minimum(px, 60.0), colorspace='Linear Rec.709')
    hdr.filepath_raw = os.path.join(SITE, 'komitas-env.hdr')
    hdr.file_format = 'HDR'
    hdr.save()
    # phones: PMREM builds 256 px cube faces from a 1024 px panorama, which is all glass needs there
    hdr.scale(1024, 512)
    hdr.filepath_raw = os.path.join(SITE, 'komitas-env-1k.hdr')
    hdr.save()
    bpy.data.images.remove(hdr)
    for o in hidden:
        o.hide_render = False
    # 2. background sky: every object hidden, sun disc on, through the stills' view transform
    sky.sun_disc = True
    hidden = [o for o in scene.objects if o.type in ('MESH', 'EMPTY') and not o.hide_render]
    for o in hidden:
        o.hide_render = True
    png = os.path.join(TEX, 'sky.png')
    render_to(png, 'PNG', 2048, 1024, 32)
    for o in hidden:
        o.hide_render = False
    img = bpy.data.images.load(png, check_existing=False)
    sk = pixels(img)
    bpy.data.images.remove(img)
    H = sk.shape[0]
    band = sk[H // 2 + 4:H // 2 + 28, :, :3].reshape(-1, 3).mean(0)      # just above the horizon (rows bottom-up)
    horizon = '#' + ''.join(f'{int(round(np.clip(v, 0, 1) * 255)):02x}' for v in band)
    # below the horizon the web shows fogged ground; make the sky's lower half the horizon colour so
    # nothing dark ever peeks out beyond the far ground (rows are bottom-up in Blender pixel buffers)
    k = np.clip((np.arange(H) - (H // 2 - 6)) / 12.0, 0.0, 1.0)[:, None, None]
    sk[..., :3] = sk[..., :3] * k + band[None, None, :] * (1 - k)
    out = bpy.data.images.new('sky_fixed', sk.shape[1], H, alpha=True)
    out.pixels.foreach_set(sk.ravel())
    out.filepath_raw = png
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(out)
    subprocess.run(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-y', '-i', png, '-q:v', '2',
                    os.path.join(SITE, 'komitas-sky.jpg')], check=True)
    # sun for the live materials (glass, cars): pre-scaled like the environment
    d = (math.sin(math.radians(az)) * math.cos(math.radians(el)), math.cos(math.radians(az)) * math.cos(math.radians(el)),
         math.sin(math.radians(el)))
    pres = {'version': '0.8.0', 'environment': 'komitas-env.hdr', 'environmentMobile': 'komitas-env-1k.hdr',
            'sky': 'komitas-sky.jpg', 'horizon': horizon,
            'fog': [700, 1500], 'terrainEdge': horizon,
            'lighting': {'sunEnergy': 14.0, 'sunColor': [1.0, 0.9, 0.78],
                         'sunDirection': [round(-d[0] * 100, 2), round(-d[1] * 100, 2), round(-d[2] * 100, 2)],
                         'skyStrength': 1.0, 'hemisphere': 0.35, 'exposure': 1.0, 'look': 'Blender AgX Punchy, 6700 K, toe lift (baked)',
                         'when': WHEN, 'sunElevation': round(el, 2), 'sunAzimuth': round(az, 2),
                         'intent': 'True sun position for Yerevan (40.21 N, 44.51 E) on 20 September, late afternoon.'}}
    json.dump(pres, open(os.path.join(SITE, 'scene-presentation.json'), 'w'), indent=2)
    log('env + sky written, horizon', horizon)


def display_rgba(lin):
    """Scene-linear premultiplied RGBA render -> shadow range + view transform, as display values (the
    convention of a loaded PNG), with the render's alpha."""
    a = lin[..., 3:4]
    straight = np.where(a > 1e-4, lin[..., :3] / np.maximum(a, 1e-4), 0.0)
    im = float_image('tree_disp', shadow_fill(straight), colorspace='Linear Rec.709')
    ims = scene.render.image_settings
    prev = (ims.file_format, ims.color_depth, ims.color_mode)
    # 8-bit like the render PNGs: a 16-bit PNG written by save_render is read back darker (curve applied twice)
    ims.file_format, ims.color_depth, ims.color_mode = 'PNG', '8', 'RGB'
    png = os.path.join(TEX, '_tree_display.png')
    im.save_render(png, scene=scene)
    ims.file_format, ims.color_depth, ims.color_mode = prev
    bpy.data.images.remove(im)
    back = bpy.data.images.load(png, check_existing=False)
    d = pixels(back)
    bpy.data.images.remove(back)
    os.remove(png)
    d[..., 3:4] = a
    return d


def step_regrade():
    """Re-apply the display transform (grade + shadow range) to the saved scene-linear lightmaps: a new look
    without re-baking."""
    for f in sorted(os.listdir(LMF)):
        if f.endswith('.npy'):
            write_display(np.load(os.path.join(LMF, f)).astype(np.float32), f[:-4])
            log('regraded', f[:-4])


# ---- tree view atlases -----------------------------------------------------------------------------------
def step_trees(cell=256):
    gpu(48)
    set_sun(WHEN)
    tdir = os.path.join(SITE, 'tree')
    os.makedirs(tdir, exist_ok=True)
    # hide everything except the species templates (their instances are what we capture)
    hidden = [o for o in scene.objects if o.type in ('MESH', 'EMPTY') and not o.hide_render
              and not o.name.startswith('TREE_')]
    for o in hidden:
        o.hide_render = True
    col = bpy.data.collections.new('WEB_TreeCapture')
    scene.collection.children.link(col)
    cd = bpy.data.cameras.new('WEB_TreeCam')
    cd.type = 'ORTHO'
    cam = bpy.data.objects.new('WEB_TreeCam', cd)
    col.objects.link(cam)
    scene.camera = cam
    manifest = {'species': []}
    for c in bpy.data.collections:
        if not c.name.startswith('TT_'):
            continue
        name = c.name[3:]
        e = bpy.data.objects.new('cap_' + name, None)
        e.instance_type = 'COLLECTION'
        e.instance_collection = c
        col.objects.link(e)
        src = c.objects[0]
        co = np.array([v.co[:] for v in src.data.vertices])
        lo, hi = co.min(0), co.max(0)
        height = float(hi[2])
        center = np.array([0.0, 0.0, 0.5 * (lo[2] + hi[2])])
        size = float(max(hi[2] - lo[2], 2 * max(abs(lo[0]), abs(hi[0]), abs(lo[1]), abs(hi[1])))) * 1.08
        cd.ortho_scale = size
        cd.clip_start, cd.clip_end = 0.1, 400.0
        tiles = np.zeros((3 * cell, 8 * cell, 4), np.float32)
        for j, elv in enumerate((25, 50, 75)):
            for i in range(8):
                phi = math.radians(i * 45.0)
                ev = math.radians(elv)
                dvec = np.array([math.sin(phi) * math.cos(ev), -math.cos(phi) * math.cos(ev), math.sin(ev)])
                cam.location = tuple(center + dvec * 150.0)
                look = -dvec
                # camera -Z along look, +Y up (roll free)
                import mathutils
                q = mathutils.Vector(look.tolist()).to_track_quat('-Z', 'Y')
                cam.rotation_euler = q.to_euler()
                exr = os.path.join(TEX, f'_tree_{name}_{j}_{i}.exr')
                render_to(exr, 'OPEN_EXR', cell, cell, 48, transparent=True)
                im = bpy.data.images.load(exr, check_existing=False)
                t = display_rgba(pixels(im))[::-1]            # same grade + shadow range as the lightmaps; top-down rows
                bpy.data.images.remove(im)
                os.remove(exr)
                tiles[j * cell:(j + 1) * cell, i * cell:(i + 1) * cell] = t
        e.hide_render = True
        bpy.data.objects.remove(e)
        # straight alpha, rows top-down -> PNG via Blender image (bottom-up rows)
        for tag, px in (('', cell), ('-mobile', cell // 2)):
            arr = tiles if px == cell else tiles.reshape(3 * px, 2, 8 * px, 2, 4).mean((1, 3))
            im = bpy.data.images.new(f'atlas_{name}{tag}', arr.shape[1], arr.shape[0], alpha=True)
            im.pixels.foreach_set(np.ascontiguousarray(arr[::-1]).ravel())
            im.filepath_raw = os.path.join(tdir, f'{name}{tag}.png')
            im.file_format = 'PNG'
            im.save()
            bpy.data.images.remove(im)
            # WebP with lossless alpha: a quarter of the PNG size, identical cut-outs
            subprocess.run(['/opt/homebrew/bin/cwebp', '-quiet', '-q', '88', '-alpha_q', '100', '-exact', '-sharp_yuv', '-m', '6',
                            os.path.join(tdir, f'{name}{tag}.png'), '-o', os.path.join(tdir, f'{name}{tag}.webp')], check=True)
        prof = {'prefix': name, 'height': round(height, 3), 'center': [0.0, 0.0, round(float(center[2]), 3)],
                'captureSize': round(size, 3), 'elevations': [25, 50, 75], 'azimuthCount': 8,
                'source': 'procedural (nk_trees.py), captured in Cycles under the baked sun'}
        manifest['species'].append({'name': name, 'atlas': f'tree/{name}.webp', 'atlasMobile': f'tree/{name}-mobile.webp',
                                    'profile': prof})
        log(f'tree atlas {name}: size {size:.1f} m, height {height:.1f} m')
    json.dump(manifest, open(os.path.join(tdir, 'species.json'), 'w'), indent=1)
    for o in hidden:
        o.hide_render = False


if __name__ == '__main__':
    t0 = time.time()
    if 'prep' in STEPS:
        step_prep()
    if 'bake' in STEPS:
        step_bake()
    if 'regrade' in STEPS:
        step_regrade()
    if 'env' in STEPS:
        step_env()
    if 'trees' in STEPS:
        step_trees()
    if 'export' in STEPS:
        step_export()
    log(f'done {STEPS} in {time.time() - t0:.0f}s')
