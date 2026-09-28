"""Procedural trees and shrubs (recursive branching + leaf geometry) for Cycles instancing.

Each species is one mesh (bark + leaves, two materials) in its own collection; placements
are collection-instance empties, so hundreds of trees cost one copy of each template.
"""
import math
import numpy as np
import bpy
from nk_mats import NT, srgb, _uv, _noise, _ramp, _mix_col, _principled

UPV = np.array([0.0, 0.0, 1.0])


def _norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else np.array([0.0, 0.0, 1.0])


def _perp(d):
    a = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = _norm(np.cross(d, a))
    return u, np.cross(d, u)


def _rotate(v, axis, ang):
    axis = _norm(axis)
    return (v * math.cos(ang) + np.cross(axis, v) * math.sin(ang)
            + axis * np.dot(axis, v) * (1 - math.cos(ang)))


SPECIES = {
    # name: height, trunk height, trunk radius, crown radius, levels, children per level,
    #       branch angle, length ratio, leaves, leaf size, upward bias, bark, leaf palette
    'Plane': dict(h=15.0, th=3.2, tr=0.28, cr=5.6, lv=3, ch=(7, 5, 4), ang=48, ratio=0.62,
                  leaves=46000, ls=0.25, up=0.10, bark='NK_Bark', pal=('#3F5B22', '#5E7C31', '#7A9440')),
    'Linden': dict(h=11.0, th=2.4, tr=0.2, cr=4.2, lv=3, ch=(6, 5, 4), ang=52, ratio=0.64,
                   leaves=36000, ls=0.22, up=0.06, bark='NK_Bark', pal=('#46632A', '#62803A', '#86A04A')),
    'Maple': dict(h=8.0, th=2.0, tr=0.15, cr=3.3, lv=3, ch=(5, 4, 4), ang=55, ratio=0.66,
                  leaves=26000, ls=0.20, up=0.04, bark='NK_Bark', pal=('#4D6B2C', '#6F8B39', '#93A64E')),
    'Poplar': dict(h=17.0, th=1.6, tr=0.22, cr=1.9, lv=3, ch=(10, 4, 3), ang=18, ratio=0.5,
                   leaves=30000, ls=0.19, up=0.35, bark='NK_Bark', pal=('#3E5A26', '#56752F', '#6F8C3A')),
    'Birch': dict(h=12.0, th=3.5, tr=0.14, cr=2.8, lv=3, ch=(6, 4, 4), ang=40, ratio=0.6,
                  leaves=24000, ls=0.17, up=0.05, bark='NK_BarkBirch', pal=('#5B7A2E', '#7E9A3E', '#A2B356')),
    'Shrub': dict(h=1.3, th=0.05, tr=0.03, cr=0.9, lv=2, ch=(9, 4), ang=60, ratio=0.6,
                  leaves=4200, ls=0.12, up=0.1, bark='NK_Bark', pal=('#3F5A25', '#587733', '#6E8B3C')),
}


def grow_tree(sp, rng):
    """Return (branches [(pts, radii, level)], twig points, twig dirs)."""
    branches, twig_p, twig_d = [], [], []
    ccz = sp['th'] + (sp['h'] - sp['th']) * 0.52   # crown centre height
    crh = (sp['h'] - sp['th']) * 0.55              # crown half height
    cr = sp['cr']

    def inside(p):
        return (p[0] ** 2 + p[1] ** 2) / cr ** 2 + ((p[2] - ccz) / crh) ** 2 <= 1.0

    def branch(p0, d, L, r0, level):
        seg = 0.35 if level > 0 else 0.5
        n = max(2, int(L / seg))
        pts, rad = [p0.copy()], [r0]
        p, dd = p0.copy(), d.copy()
        for i in range(n):
            dd = _norm(dd + rng.normal(0, 0.10 if level else 0.04, 3) + UPV * sp['up'] * (0.6 if level else 1.0))
            p = p + dd * (L / n)
            if level > 0 and not inside(p) and i > 0:
                break
            pts.append(p.copy())
            rad.append(r0 * (1.0 - 0.65 * (i + 1) / n))
        pts, rad = np.array(pts), np.array(rad)
        branches.append((pts, rad, level))
        if level < sp['lv']:
            nc = sp['ch'][level]
            base_az = rng.uniform(0, 2 * math.pi)
            for k in range(nc):
                t = 0.35 + 0.6 * (k + rng.uniform(0.2, 0.8)) / nc if level == 0 else rng.uniform(0.25, 0.95)
                if level == 0:
                    t = min(max(t, 0.2), 0.97)
                idx = min(len(pts) - 1, max(1, int(t * (len(pts) - 1))))
                q = pts[idx]
                dpar = _norm(pts[idx] - pts[idx - 1])
                u, v = _perp(dpar)
                az = base_az + k * 2.39996  # golden angle
                side = _norm(u * math.cos(az) + v * math.sin(az))
                ang = math.radians(sp['ang'] + rng.uniform(-12, 12))
                cd = _norm(dpar * math.cos(ang) + side * math.sin(ang))
                if level == 0:
                    # scaffold branches: length from crown envelope
                    Lc = (sp['h'] - q[2]) * 0.55 + cr * 0.75
                    Lc *= rng.uniform(0.8, 1.1)
                else:
                    Lc = L * sp['ratio'] * rng.uniform(0.8, 1.15)
                rc = max(0.006, rad[idx] * 0.62)
                branch(q, cd, Lc, rc, level + 1)
        else:
            for i in range(1, len(pts)):
                twig_p.append(pts[i])
                twig_d.append(_norm(pts[i] - pts[i - 1]))

    trunk_len = sp['th'] + (sp['h'] - sp['th']) * 0.45
    d0 = _norm(np.array([rng.normal(0, 0.05), rng.normal(0, 0.05), 1.0]))
    branch(np.zeros(3), d0, trunk_len, sp['tr'], 0)
    return branches, np.array(twig_p), np.array(twig_d), (ccz, crh)


def tube_mesh(branches, min_r=0.01):
    V, F = [], []
    for pts, rad, level in branches:
        if rad[0] < min_r:
            continue
        k = 8 if level == 0 else (6 if level == 1 else 4)
        n = len(pts)
        d = _norm(pts[1] - pts[0])
        u, v = _perp(d)
        base = len(V)
        for i in range(n):
            if i > 0:
                dn = _norm(pts[i] - pts[i - 1])
                # parallel transport of the ring frame
                ax = np.cross(d, dn)
                s = np.linalg.norm(ax)
                if s > 1e-6:
                    ang = math.asin(min(1.0, s))
                    u = _rotate(u, ax, ang)
                    v = _rotate(v, ax, ang)
                d = dn
            r = max(rad[i], min_r * 0.5)
            for j in range(k):
                a = 2 * math.pi * j / k
                V.append(pts[i] + (u * math.cos(a) + v * math.sin(a)) * r)
        for i in range(n - 1):
            for j in range(k):
                a0 = base + i * k + j
                a1 = base + i * k + (j + 1) % k
                F.append((a0, a1, a1 + k, a0 + k))
    return V, F


def leaf_mesh(twig_p, twig_d, n, size, rng, crown):
    """n diamond leaves clustered around twig points, facing mostly outwards/upwards."""
    if len(twig_p) == 0:
        return np.zeros((0, 3)), [], np.zeros((0, 4))
    ccz, crh = crown
    idx = rng.integers(0, len(twig_p), n)
    P = twig_p[idx] + rng.normal(0, 0.32, (n, 3)) * np.array([1, 1, 0.8])
    out = P - np.array([0, 0, ccz])
    out /= np.linalg.norm(out, axis=1, keepdims=True) + 1e-9
    nrm = out * 0.6 + np.array([0, 0, 0.5]) + rng.normal(0, 0.55, (n, 3))
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    tmp = np.where(np.abs(nrm[:, 2:3]) < 0.9, np.array([[0, 0, 1.0]]), np.array([[1.0, 0, 0]]))
    ax1 = np.cross(nrm, tmp)
    ax1 /= np.linalg.norm(ax1, axis=1, keepdims=True) + 1e-9
    # rotate the leaf axis randomly inside its plane
    ax2 = np.cross(nrm, ax1)
    th = rng.uniform(0, 2 * math.pi, (n, 1))
    lu = ax1 * np.cos(th) + ax2 * np.sin(th)
    lv = np.cross(nrm, lu)
    s = size * rng.uniform(0.7, 1.3, (n, 1))
    # diamond: base, right, tip, left (length along lu, width along lv)
    V = np.stack([P - lu * s * 0.1, P + lu * s * 0.45 + lv * s * 0.28, P + lu * s * 1.0,
                  P + lu * s * 0.45 - lv * s * 0.28], axis=1).reshape(-1, 3)
    F = [(4 * i, 4 * i + 1, 4 * i + 2, 4 * i + 3) for i in range(n)]
    col = np.stack([rng.uniform(0, 1, n), rng.uniform(0, 1, n), rng.uniform(0, 1, n), np.ones(n)], axis=1)
    return V, F, col


def make_species(name, sp, mats, lib, seed):
    rng = np.random.default_rng(seed)
    br, tp, td, crown = grow_tree(sp, rng)
    bV, bF = tube_mesh(br)
    lV, lF, lcol = leaf_mesh(tp, td, sp['leaves'], sp['ls'], rng, crown)
    V = np.concatenate([np.array(bV).reshape(-1, 3), lV], axis=0)
    off = len(bV)
    F = list(bF) + [tuple(i + off for i in f) for f in lF]
    me = bpy.data.meshes.new('TREE_' + name)
    me.from_pydata(V.tolist(), [], F)
    me.materials.append(mats[sp['bark']])
    me.materials.append(mats['NK_Leaf_' + name])
    mi = np.array([0] * len(bF) + [1] * len(lF))
    me.polygons.foreach_set('material_index', mi)
    ca = me.color_attributes.new(name='Col', type='BYTE_COLOR', domain='CORNER')
    cols = np.concatenate([np.ones((len(bF), 4)) * 0.5, lcol], axis=0)
    lt = np.zeros(len(F), dtype=np.int32)
    me.polygons.foreach_get('loop_total', lt)
    ca.data.foreach_set('color', np.repeat(cols, lt, axis=0).ravel())
    uvl = me.uv_layers.new(name='UVMap')
    me.update()
    c = bpy.data.collections.new('TT_' + name)
    lib.children.link(c)
    ob = bpy.data.objects.new('TREE_' + name, me)
    c.objects.link(ob)
    print(f'tree {name}: {len(bF)} bark faces, {len(lF)} leaves')
    return c


def mat_leaf(name, pal):
    """Two-sided leaf: per-leaf colour from the 'Col' attribute, 30 % translucency."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    ca = nt.n('ShaderNodeVertexColor', -1100, 0)
    ca.layer_name = 'Col'
    sep = nt.n('ShaderNodeSeparateColor', -900, 0)
    nt.link(ca.outputs['Color'], sep.inputs['Color'])
    gm = nt.n('ShaderNodeMath', -700, -150, operation='GREATER_THAN')
    gm.inputs[1].default_value = 0.82
    nt.link(sep.outputs['Green'], gm.inputs[0])
    c = _mix_col(nt, sep.outputs['Red'], srgb(pal[0]), srgb(pal[1]), -650, 100)
    c = _mix_col(nt, gm.outputs[0], c, srgb(pal[2]), -400, 100)
    p = nt.n('ShaderNodeBsdfPrincipled', -150, 200)
    p.inputs['Roughness'].default_value = 0.5
    p.inputs['Specular IOR Level'].default_value = 0.35
    nt.link(c, p.inputs['Base Color'])
    tr = nt.n('ShaderNodeBsdfTranslucent', -150, -250)
    lt = _mix_col(nt, 1.0, c, (0.9, 1.0, 0.45, 1.0), -350, -250, 'MULTIPLY')
    nt.link(lt, tr.inputs['Color'])
    mix = nt.n('ShaderNodeMixShader', 200, 0)
    mix.inputs['Fac'].default_value = 0.3
    nt.link(p.outputs['BSDF'], mix.inputs[1])
    nt.link(tr.outputs['BSDF'], mix.inputs[2])
    out = nt.n('ShaderNodeOutputMaterial', 450, 0)
    nt.link(mix.outputs['Shader'], out.inputs['Surface'])
    return mat


def mat_bark(name, c1, c2, birch=False):
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    tc = nt.n('ShaderNodeTexCoord', -1200, 0)
    mp = nt.n('ShaderNodeMapping', -1000, 0)
    mp.inputs['Scale'].default_value = (6.0, 6.0, 1.2) if not birch else (3.0, 3.0, 9.0)
    nt.link(tc.outputs['Object'], mp.inputs['Vector'])
    no = nt.n('ShaderNodeTexNoise', -800, 0)
    no.inputs['Scale'].default_value = 4.0
    no.inputs['Detail'].default_value = 8.0
    nt.link(mp.outputs['Vector'], no.inputs['Vector'])
    f = _ramp(nt, no.outputs['Fac'], [(0.45, 0.0), (0.55, 1.0)] if birch else [(0.3, 0.0), (0.7, 1.0)], -600, 0)
    c = _mix_col(nt, f, srgb(c1), srgb(c2), -350, 0)
    p, out = _principled(nt, Roughness=0.9)
    nt.link(c, p.inputs['Base Color'])
    bump = nt.n('ShaderNodeBump', 100, -250)
    bump.inputs['Strength'].default_value = 0.6
    nt.link(no.outputs['Fac'], bump.inputs['Height'])
    nt.link(bump.outputs['Normal'], p.inputs['Normal'])
    return mat


def build_library(M, scene_collection):
    lib = bpy.data.collections.new('NK_TreeLibrary')
    scene_collection.children.link(lib)
    M['NK_Bark'] = mat_bark('NK_Bark', '#4A423B', '#6A5F55')
    M['NK_BarkBirch'] = mat_bark('NK_BarkBirch', '#DCD8CF', '#3A3632', birch=True)
    colls = {}
    for i, (name, sp) in enumerate(SPECIES.items()):
        M['NK_Leaf_' + name] = mat_leaf('NK_Leaf_' + name, sp['pal'])
        colls[name] = make_species(name, sp, M, lib, 100 + i)
    return lib, colls


def place(col, colls, placements, rng):
    """placements: list of (x, y, z, species, scale)."""
    for i, (x, y, z, sp, s) in enumerate(placements):
        e = bpy.data.objects.new(f'Tree_{sp}_{i:04d}', None)
        e.instance_type = 'COLLECTION'
        e.instance_collection = colls[sp]
        e.location = (x, y, z)
        e.rotation_euler = (0, 0, rng.uniform(0, 2 * math.pi))
        e.scale = (s, s, s * rng.uniform(0.92, 1.08))
        e.empty_display_size = 2.0
        col.objects.link(e)
