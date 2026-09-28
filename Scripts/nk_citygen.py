"""Realistic neighbouring buildings from OpenStreetMap footprints (Yerevan typologies).

Each OSM footprint becomes one of:
  tuff5   Soviet 4-6 storey block: tuff-stone walls, deep window reveals, cornice, balconies
          (many enclosed by residents), AC units, entrances with canopies, pitched metal roof
  panel   7-12 storey concrete panel block: panel joints, loggia/balcony stack, flat roof, lift room
  tower   13+ storey newer tower: plaster/stone, larger windows, glass-railed balconies
  house   private house: plaster/tuff, small windows, hip or gable tile/metal roof
  public  school/clinic/office: large windows, flat roof;  shop: storefronts
  shed    industrial: corrugated metal walls, high strip windows, shallow gable
  garage  garage rows / sheds / kiosks: roller doors, flat roof

Stable per building (seeded by the OSM id). Geometry detail follows NK_DETAIL like the main
facades; the web build keeps full window geometry only near the complex (see build()).
"""
import math
import os
import zlib
import numpy as np
import bpy
import mathutils
from nk_geo import MeshBuilder, Frame
from nk_mats import NT, srgb, _uv, _noise, _ramp, _mix_col, _principled

DETAIL = os.environ.get('NK_DETAIL', 'full')

TUFF = ['#C89A8A', '#BE8C79', '#CFA385', '#D2B79B', '#B78C7E', '#C7A28F', '#A98A80', '#D9C3A6']
PLASTER = ['#E3DCCB', '#D9CDB1', '#E7E1D5', '#D8C29B', '#CFC6B8', '#E2D4C4', '#C9CFCF', '#D8B9A4']
PANEL = ['#BDB7AC', '#C8C1B4', '#B2AFA8', '#C4BBAB', '#ADA9A1']
METALW = ['#9CA3A6', '#7F8C8E', '#8E7F6E', '#6F7E86', '#A9A69E']
ROOF_METAL = ['#7E8284', '#6F7375', '#8B5A42', '#6E3B30', '#4F6356', '#9A9C9B']
ROOF_TILE = ['#A4553A', '#8F4A33', '#B2654A', '#7E4332']
PANEL_BAL = ['#E8E6E1', '#C9D6DE', '#D8CDB8', '#E2E2DA', '#B9C4C9']
ROOF_FLAT = ['#5C5B58', '#666561', '#52524F', '#74726D', '#8E8D89', '#6E6A63']   # bitumen .. aluminium-coated


def lin(h):
    return tuple(srgb(h)[:3]) + (1.0,)


# ---- materials ---------------------------------------------------------------------------------
def _attr(nt, x=-1100, y=300):
    ca = nt.n('ShaderNodeVertexColor', x, y)
    ca.layer_name = 'Col'
    return ca.outputs['Color']


def _weather(nt, uv, base, streak=0.12, ground=0.22):
    """Vertical rain streaks + darker plinth zone (UV.y is height on walls)."""
    mp = nt.n('ShaderNodeMapping', -1050, -300)
    mp.inputs['Scale'].default_value = (5.0, 0.3, 1.0)
    nt.link(uv, mp.inputs['Vector'])
    st = _noise(nt, mp.outputs['Vector'], 1.6, 5.0, 0.6, -850, -300)
    sf = _ramp(nt, st.outputs['Fac'], [(0.42, 1.0 - streak), (0.72, 1.0)], -650, -300)
    sep = nt.n('ShaderNodeSeparateXYZ', -850, -520)
    nt.link(uv, sep.inputs['Vector'])
    mr = nt.n('ShaderNodeMapRange', -650, -520)
    mr.inputs['From Min'].default_value = 0.0
    mr.inputs['From Max'].default_value = 1.4
    mr.inputs['To Min'].default_value = 1.0 - ground
    mr.inputs['To Max'].default_value = 1.0
    nt.link(sep.outputs['Y'], mr.inputs['Value'])
    base = _mix_col(nt, 1.0, base, sf, -400, -300, 'MULTIPLY')
    g = nt.n('ShaderNodeCombineColor', -450, -520)
    for ch in ('Red', 'Green', 'Blue'):
        nt.link(mr.outputs['Result'], g.inputs[ch])
    return _mix_col(nt, 1.0, base, g.outputs['Color'], -200, -380, 'MULTIPLY')


def _finish(nt, base, rough, bump_fac=None, bump_strength=0.3, invert=True, spec=0.35, metal=0.0):
    p, out = _principled(nt, Roughness=rough, Metallic=metal)
    p.inputs['Specular IOR Level'].default_value = spec
    nt.link(base, p.inputs['Base Color'])
    if bump_fac is not None:
        bump = nt.n('ShaderNodeBump', 150, -300)
        bump.inputs['Strength'].default_value = bump_strength
        bump.inputs['Distance'].default_value = 0.004
        bump.invert = invert
        nt.link(bump_fac, bump.inputs['Height'])
        nt.link(bump.outputs['Normal'], p.inputs['Normal'])
    return p


def mat_tuff(name):
    """Hewn tuff blocks with per-block tone variation, porous surface and weathering."""
    m = bpy.data.materials.new(name)
    nt = NT(m)
    uv = _uv(nt)
    br = nt.n('ShaderNodeTexBrick', -850, 250)
    br.offset = 0.5
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Brick Width'].default_value = 0.64
    br.inputs['Row Height'].default_value = 0.34
    br.inputs['Mortar Size'].default_value = 0.012
    br.inputs['Mortar Smooth'].default_value = 0.35
    br.inputs['Color1'].default_value = (1.0, 1.0, 1.0, 1.0)
    br.inputs['Color2'].default_value = (0.8, 0.77, 0.75, 1.0)
    br.inputs['Mortar'].default_value = (0.9, 0.88, 0.86, 1.0)
    nt.link(uv, br.inputs['Vector'])
    po = _noise(nt, uv, 16.0, 6.0, 0.65, -850, 0)
    pf = _ramp(nt, po.outputs['Fac'], [(0.3, 0.86), (0.7, 1.05)], -650, 0)
    base = _mix_col(nt, 1.0, _attr(nt), br.outputs['Color'], -500, 250, 'MULTIPLY')
    base = _mix_col(nt, 1.0, base, pf, -350, 150, 'MULTIPLY')
    base = _weather(nt, uv, base)
    _finish(nt, base, 0.88, br.outputs['Fac'], 0.4)
    return m


def mat_plaster(name):
    m = bpy.data.materials.new(name)
    nt = NT(m)
    uv = _uv(nt)
    bl = _noise(nt, uv, 0.45, 4.0, 0.55, -850, 250)
    bf = _ramp(nt, bl.outputs['Fac'], [(0.35, 0.9), (0.68, 1.03)], -650, 250)
    fi = _noise(nt, uv, 26.0, 3.0, 0.6, -850, 0)
    ff = _ramp(nt, fi.outputs['Fac'], [(0.35, 0.95), (0.65, 1.02)], -650, 0)
    base = _mix_col(nt, 1.0, _attr(nt), bf, -500, 250, 'MULTIPLY')
    base = _mix_col(nt, 1.0, base, ff, -350, 150, 'MULTIPLY')
    base = _weather(nt, uv, base, streak=0.16)
    _finish(nt, base, 0.8, fi.outputs['Fac'], 0.08, invert=False)
    return m


def mat_panel(name):
    m = bpy.data.materials.new(name)
    nt = NT(m)
    uv = _uv(nt)
    br = nt.n('ShaderNodeTexBrick', -850, 250)
    br.offset = 0.0
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Brick Width'].default_value = 3.0
    br.inputs['Row Height'].default_value = 2.9
    br.inputs['Mortar Size'].default_value = 0.022
    br.inputs['Mortar Smooth'].default_value = 0.2
    br.inputs['Color1'].default_value = (1.0, 1.0, 1.0, 1.0)
    br.inputs['Color2'].default_value = (0.92, 0.9, 0.87, 1.0)
    br.inputs['Mortar'].default_value = (0.62, 0.6, 0.57, 1.0)
    nt.link(uv, br.inputs['Vector'])
    co = _noise(nt, uv, 2.5, 5.0, 0.6, -850, 0)
    cf = _ramp(nt, co.outputs['Fac'], [(0.3, 0.88), (0.7, 1.04)], -650, 0)
    base = _mix_col(nt, 1.0, _attr(nt), br.outputs['Color'], -500, 250, 'MULTIPLY')
    base = _mix_col(nt, 1.0, base, cf, -350, 150, 'MULTIPLY')
    base = _weather(nt, uv, base, streak=0.2, ground=0.25)
    _finish(nt, base, 0.86, br.outputs['Fac'], 0.3)
    return m


def mat_corrugated(name, roof=False):
    """Corrugated metal sheet (walls of sheds, roofs); rust patches."""
    m = bpy.data.materials.new(name)
    nt = NT(m)
    uv = _uv(nt)
    wv = nt.n('ShaderNodeTexWave', -850, 0)
    wv.wave_type = 'BANDS'
    wv.bands_direction = 'Y' if roof else 'X'
    wv.inputs['Scale'].default_value = 7.5
    wv.inputs['Distortion'].default_value = 0.0
    nt.link(uv, wv.inputs['Vector'])
    ru = _noise(nt, uv, 0.8, 6.0, 0.7, -850, 300)
    rf = _ramp(nt, ru.outputs['Fac'], [(0.62, 0.0), (0.72, 1.0)], -650, 300)
    base = _mix_col(nt, rf, _attr(nt), srgb('#6B4630'), -450, 250)
    sh = _ramp(nt, wv.outputs['Fac'], [(0.0, 0.9), (1.0, 1.04)], -650, 0)
    base = _mix_col(nt, 1.0, base, sh, -300, 150, 'MULTIPLY')
    if not roof:
        base = _weather(nt, uv, base, streak=0.1, ground=0.15)
    p = _finish(nt, base, 0.5, wv.outputs['Fac'], 0.5, invert=False, metal=0.55)
    rr = _ramp(nt, rf, [(0.0, 0.42), (1.0, 0.85)], -300, -200)
    nt.link(rr, p.inputs['Roughness'])
    return m


def mat_tile(name):
    m = bpy.data.materials.new(name)
    nt = NT(m)
    uv = _uv(nt)
    br = nt.n('ShaderNodeTexBrick', -850, 250)
    br.offset = 0.5
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Brick Width'].default_value = 0.3
    br.inputs['Row Height'].default_value = 0.2
    br.inputs['Mortar Size'].default_value = 0.018
    br.inputs['Color1'].default_value = (1.0, 1.0, 1.0, 1.0)
    br.inputs['Color2'].default_value = (0.78, 0.74, 0.72, 1.0)
    br.inputs['Mortar'].default_value = (0.35, 0.33, 0.32, 1.0)
    nt.link(uv, br.inputs['Vector'])
    base = _mix_col(nt, 1.0, _attr(nt), br.outputs['Color'], -500, 250, 'MULTIPLY')
    ag = _noise(nt, uv, 0.6, 4.0, 0.6, -850, 0)
    af = _ramp(nt, ag.outputs['Fac'], [(0.3, 0.82), (0.7, 1.05)], -650, 0)
    base = _mix_col(nt, 1.0, base, af, -350, 150, 'MULTIPLY')
    _finish(nt, base, 0.75, br.outputs['Fac'], 0.6)
    return m


def mat_flatroof(name):
    """Flat roofs: bitumen or coated membrane in each building's own tone ('Col'), roll seams every ~1 m,
    repair patches and grime (two greys blended in 8 m blotches looked smudgy from above)."""
    m = bpy.data.materials.new(name)
    nt = NT(m)
    uv = _uv(nt)
    br = nt.n('ShaderNodeTexBrick', -850, 350)
    br.offset = 0.0
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Brick Width'].default_value = 7.5
    br.inputs['Row Height'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = 0.025
    br.inputs['Mortar Smooth'].default_value = 0.3
    br.inputs['Color1'].default_value = (1.0, 1.0, 1.0, 1.0)
    br.inputs['Color2'].default_value = (0.94, 0.94, 0.93, 1.0)
    br.inputs['Mortar'].default_value = (0.78, 0.78, 0.77, 1.0)
    nt.link(uv, br.inputs['Vector'])
    pa = _noise(nt, uv, 0.35, 4.0, 0.6, -850, 100)
    pf = _ramp(nt, pa.outputs['Fac'], [(0.6, 1.0), (0.66, 0.8)], -650, 100)
    fi = _noise(nt, uv, 7.0, 3.0, 0.7, -850, -150)
    ff = _ramp(nt, fi.outputs['Fac'], [(0.3, 0.9), (0.7, 1.06)], -650, -150)
    base = _mix_col(nt, 1.0, _attr(nt), br.outputs['Color'], -450, 300, 'MULTIPLY')
    base = _mix_col(nt, 1.0, base, pf, -300, 200, 'MULTIPLY')
    base = _mix_col(nt, 1.0, base, ff, -150, 100, 'MULTIPLY')
    _finish(nt, base, 0.85, fi.outputs['Fac'], 0.1, invert=False)
    return m


def mat_enclosure(name):
    """Resident-built balcony glazing: aluminium/PVC frames on a pane grid over dark glass."""
    m = bpy.data.materials.new(name)
    nt = NT(m)
    uv = _uv(nt)
    br = nt.n('ShaderNodeTexBrick', -850, 150)
    br.offset = 0.0
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Brick Width'].default_value = 0.78
    br.inputs['Row Height'].default_value = 0.8
    br.inputs['Mortar Size'].default_value = 0.055
    br.inputs['Mortar Smooth'].default_value = 0.0
    nt.link(uv, br.inputs['Vector'])
    glass = nt.n('ShaderNodeBsdfPrincipled', -300, 250)
    glass.inputs['Base Color'].default_value = srgb('#1C2024')
    glass.inputs['Roughness'].default_value = 0.04
    glass.inputs['IOR'].default_value = 1.9
    glass.inputs['Specular IOR Level'].default_value = 0.7
    ca = _attr(nt, -850, -150)
    fr = nt.n('ShaderNodeBsdfPrincipled', -300, -150)
    fr.inputs['Roughness'].default_value = 0.45
    nt.link(ca, fr.inputs['Base Color'])
    mix = nt.n('ShaderNodeMixShader', 100, 0)
    nt.link(br.outputs['Fac'], mix.inputs['Fac'])
    nt.link(glass.outputs['BSDF'], mix.inputs[1])
    nt.link(fr.outputs['BSDF'], mix.inputs[2])
    out = nt.n('ShaderNodeOutputMaterial', 350, 0)
    nt.link(mix.outputs['Shader'], out.inputs['Surface'])
    return m


def mat_plain(name, hexcol, rough, metal=0.0, tint=False, noise=0.06):
    m = bpy.data.materials.new(name)
    nt = NT(m)
    uv = _uv(nt)
    no = _noise(nt, uv, 3.0, 4.0, 0.6, -850, 0)
    nf = _ramp(nt, no.outputs['Fac'], [(0.3, 1.0 - noise), (0.7, 1.0 + noise * 0.5)], -650, 0)
    base = _attr(nt) if tint else srgb(hexcol)
    base = _mix_col(nt, 1.0, base, nf, -350, 150, 'MULTIPLY')
    _finish(nt, base, rough, metal=metal)
    return m


def mat_windowgrid(name, bay, floor, win_w, win_h, sill):
    """Far-field walls (web build only): wall tint from 'Col' with a painted window grid."""
    m = bpy.data.materials.new(name)
    nt = NT(m)
    uv = _uv(nt)
    sep = nt.n('ShaderNodeSeparateXYZ', -1200, 0)
    nt.link(uv, sep.inputs['Vector'])

    def band(sock, period, width, offset, x, y):
        d = nt.n('ShaderNodeMath', x, y, operation='DIVIDE')
        d.inputs[1].default_value = period
        nt.link(sock, d.inputs[0])
        a = nt.n('ShaderNodeMath', x + 150, y, operation='ADD')
        a.inputs[1].default_value = offset
        nt.link(d.outputs[0], a.inputs[0])
        f = nt.n('ShaderNodeMath', x + 300, y, operation='FRACT')
        nt.link(a.outputs[0], f.inputs[0])
        s = nt.n('ShaderNodeMath', x + 450, y, operation='SUBTRACT')
        s.inputs[1].default_value = 0.5
        nt.link(f.outputs[0], s.inputs[0])
        ab = nt.n('ShaderNodeMath', x + 600, y, operation='ABSOLUTE')
        nt.link(s.outputs[0], ab.inputs[0])
        lt = nt.n('ShaderNodeMath', x + 750, y, operation='LESS_THAN')
        lt.inputs[1].default_value = width / period / 2
        nt.link(ab.outputs[0], lt.inputs[0])
        return lt.outputs[0]
    gx = band(sep.outputs['X'], bay, win_w, 0.0, -1000, 250)
    gy = band(sep.outputs['Y'], floor, win_h, -(sill + win_h / 2) / floor + 0.5, -1000, -50)
    mm = nt.n('ShaderNodeMath', -100, 100, operation='MULTIPLY')
    nt.link(gx, mm.inputs[0])
    nt.link(gy, mm.inputs[1])
    wall = _weather(nt, uv, _attr(nt, -700, 350))
    col = _mix_col(nt, mm.outputs[0], wall, srgb('#1E2327'), 150, 100)
    p, out = _principled(nt, Roughness=0.8)
    nt.link(col, p.inputs['Base Color'])
    r = _mix_col(nt, mm.outputs[0], (0.85, 0.85, 0.85, 1), (0.08, 0.08, 0.08, 1), 150, -150)
    nt.link(r, p.inputs['Roughness'])
    return m


def build_materials(M):
    for name, fn in (('CX_Tuff', mat_tuff), ('CX_Plaster', mat_plaster), ('CX_Panel', mat_panel),
                     ('CX_Tile', mat_tile), ('CX_FlatRoof', mat_flatroof), ('CX_Enclosure', mat_enclosure)):
        if name not in M:
            M[name] = fn(name)
    if 'CX_MetalWall' not in M:
        M['CX_MetalWall'] = mat_corrugated('CX_MetalWall')
        M['CX_MetalRoof'] = mat_corrugated('CX_MetalRoof', roof=True)
        M['CX_Concrete'] = mat_plain('CX_Concrete', '#A29F98', 0.85)
        M['CX_Sheet'] = mat_plain('CX_Sheet', '#FFFFFF', 0.5, metal=0.3, tint=True)
        M['CX_Frame'] = mat_plain('CX_Frame', '#E4E4E0', 0.45, noise=0.02)
        M['CX_ACUnit'] = mat_plain('CX_ACUnit', '#D9D9D4', 0.5, noise=0.04)
        M['CX_Door'] = mat_plain('CX_Door', '#2A2522', 0.45, metal=0.5)
        M['CX_Roller'] = mat_corrugated('CX_Roller')
        M['CX_Grid5'] = mat_windowgrid('CX_Grid5', 3.3, 3.1, 1.3, 1.6, 0.85)
    if 'CX_Wood' not in M:
        M['CX_Wood'] = mat_plain('CX_Wood', '#8A6B4E', 0.7, noise=0.12)


# ---- typology --------------------------------------------------------------------------------------
SPEC = {
    #          floor  base  bay   win (w, h, sill)    depth  balconies
    'tuff5': dict(fh=3.1, base=0.9, bay=3.3, win=(1.3, 1.6, 0.85), depth=0.3, bal=0.45, cornice=True),
    'panel': dict(fh=2.9, base=0.6, bay=3.0, win=(1.5, 1.5, 0.85), depth=0.18, bal=0.8, cornice=False),
    'tower': dict(fh=3.1, base=0.9, bay=3.4, win=(1.8, 1.9, 0.6), depth=0.22, bal=0.5, cornice=False),
    'house': dict(fh=3.0, base=0.45, bay=3.2, win=(1.2, 1.4, 0.9), depth=0.25, bal=0.0, cornice=False),
    'public': dict(fh=3.6, base=0.6, bay=3.8, win=(2.4, 2.1, 0.9), depth=0.25, bal=0.0, cornice=True),
    'shop': dict(fh=3.8, base=0.2, bay=4.0, win=(3.0, 2.7, 0.3), depth=0.3, bal=0.0, cornice=False),
    'shed': dict(fh=0.0, base=0.0, bay=6.0, win=(3.6, 1.2, 5.2), depth=0.15, bal=0.0, cornice=False),
    'garage': dict(fh=0.0, base=0.0, bay=3.4, win=(2.6, 2.2, 0.0), depth=0.12, bal=0.0, cornice=False),
}


def classify(b, area, rng):
    kind = (b.get('kind') or 'yes').lower()
    lv = None
    if b.get('levels'):
        try:
            lv = int(float(str(b['levels']).split(';')[0]))
        except ValueError:
            lv = None
    if lv is None and b.get('h'):
        lv = max(1, int(round((b['h'] - 0.8) / 3.1)))
    if kind in ('garages', 'garage', 'carport', 'shed', 'kiosk', 'hut', 'service', 'transformer_tower', 'roof'):
        return 'garage', 1
    if kind in ('industrial', 'warehouse', 'hangar', 'manufacture'):
        return 'shed', 1
    if kind == 'house' or (lv is None and area < 170):
        return 'house', lv or (1 if area < 70 else 2)
    if kind in ('school', 'kindergarten', 'university', 'college', 'hospital', 'public', 'civic', 'government', 'office'):
        return 'public', lv or 3
    if kind in ('commercial', 'retail', 'supermarket'):
        return 'shop', lv or (1 if area < 400 else 2)
    if lv is None:
        if area < 420:
            lv = 3
        elif area < 2600:
            lv = 5
        else:
            return 'shed', 1
    if lv <= 3:
        return ('house' if area < 260 else 'tuff5'), lv
    if lv <= 6:
        return 'tuff5', lv
    if lv <= 12:
        return 'panel', lv
    return ('tower' if rng.random() < 0.6 else 'panel'), lv


# ---- geometry pieces ------------------------------------------------------------------------------
def window(mb, fr, a0, a1, b0, b1, depth, wall_mat, tint, wcol, frame=True, sill=True, glass='NK_GlassWindow'):
    mb.reveal(fr, a0, a1, b0, b1, 0.0, -depth, wall_mat)
    if DETAIL != 'web' and frame:
        fw = 0.06
        mb.wall_holes(fr, a0, a1, b0, b1, [(a0 + fw, a1 - fw, b0 + fw, b1 - fw)], 'CX_Frame', c=-depth + 0.06)
        mb.reveal(fr, a0 + fw, a1 - fw, b0 + fw, b1 - fw, -depth + 0.06, -depth, 'CX_Frame')
        mb.rect_c(fr, a0 + fw, a1 - fw, b0 + fw, b1 - fw, -depth, glass, col=wcol)
        m = 0.5 * (a0 + a1)
        mb.box(fr, m - 0.035, m + 0.035, b0 + fw, b1 - fw, -depth, -depth + 0.06, 'CX_Frame', skip=('-c',))
    else:
        mb.rect_c(fr, a0, a1, b0, b1, -depth, glass, col=wcol)
    if sill and DETAIL != 'web':
        mb.box(fr, a0 - 0.06, a1 + 0.06, b0 - 0.06, b0, -depth + 0.04, 0.07, 'CX_Concrete', skip=('-c',))


def balcony(mb, fr, a0, a1, z, d, style, tint_sheet, glass_col):
    """style: 'open' (slab + painted sheet parapet), 'enclosed' (resident glazing), 'glass' (railing)."""
    mb.box(fr, a0, a1, z - 0.16, z, 0.0, d, 'CX_Concrete', skip=('-c',))
    if style == 'enclosed':
        mb.box(fr, a0, a1, z, z + 1.0, 0.0, d, 'CX_Sheet', skip=('-c', '+b'), col=tint_sheet)
        mb.box(fr, a0, a1, z + 1.0, z + 2.55, 0.02, d - 0.03, 'CX_Enclosure', skip=('-c', '-b', '+b'), col=glass_col)
        mb.box(fr, a0 - 0.03, a1 + 0.03, z + 2.55, z + 2.7, 0.0, d + 0.03, 'CX_Sheet', skip=('-c',), col=tint_sheet)
    elif style == 'glass':
        mb.box(fr, a0 + 0.05, a1 - 0.05, z, z + 1.0, d - 0.06, d - 0.04, 'NK_GlassRail')
        mb.box(fr, a0, a1, z + 1.0, z + 1.05, d - 0.08, d - 0.02, 'NK_DarkMetal')
    else:
        mb.box(fr, a0, a1, z, z + 1.0, d - 0.05, d, 'CX_Sheet', col=tint_sheet)
        mb.box(fr, a0, a0 + 0.05, z, z + 1.0, 0.0, d - 0.05, 'CX_Sheet', skip=('-c',), col=tint_sheet)
        mb.box(fr, a1 - 0.05, a1, z, z + 1.0, 0.0, d - 0.05, 'CX_Sheet', skip=('-c',), col=tint_sheet)


def roof_hip(mb, pts, h, rise, mat, col, over=0.45):
    """Hip roof over a (near) rectangle: 2 trapezoids + 2 triangles."""
    from nk_context import _obb
    gx, gy, rot, hx, hy = _obb(pts)
    if hy > hx:
        rot += math.pi / 2
        hx, hy = hy, hx
    c, s = math.cos(rot), math.sin(rot)

    def T(x, y, z):
        return (gx + x * c - y * s, gy + x * s + y * c, z)
    ex, ey = hx + over, hy + over
    top = h + rise
    r = max(0.0, ex - ey)
    A, B, C, D = T(-ex, -ey, h), T(ex, -ey, h), T(ex, ey, h), T(-ex, ey, h)
    R0, R1 = T(-r, 0, top), T(r, 0, top)
    mb.add([A, B, R1, R0], [(0, 1, 2, 3)], mat, col)
    mb.add([C, D, R0, R1], [(0, 1, 2, 3)], mat, col)
    mb.add([B, C, R1], [(0, 1, 2)], mat, col)
    mb.add([D, A, R0], [(0, 1, 2)], mat, col)


def roof_flat(mb, pts, h, parapet, wall_mat, tint, roof_col=None):
    V = [(x, y, h) for x, y in pts]
    for t in mathutils.geometry.tessellate_polygon([[mathutils.Vector(v) for v in V]]):
        a, b, cc = V[t[0]], V[t[1]], V[t[2]]
        nz = (b[0] - a[0]) * (cc[1] - a[1]) - (b[1] - a[1]) * (cc[0] - a[0])
        mb.add([a, b, cc] if nz > 0 else [a, cc, b], [(0, 1, 2)], 'CX_FlatRoof', roof_col)
    if parapet <= 0:
        return
    n = len(pts)
    for i in range(n):
        p0, p1 = np.array(pts[i]), np.array(pts[(i + 1) % n])
        L = float(np.linalg.norm(p1 - p0))
        if L < 0.8:
            continue
        fr = Frame(p0, p1 - p0)
        mb.box(fr, 0.26, L - 0.26, h, h + parapet, -0.25, 0.0, wall_mat, skip=('-b', '+c'), col=tint)
        mb.rect_c(fr, 0.0, L, h, h + parapet, 0.0, wall_mat, col=tint)
        mb.box(fr, 0.0, L, h + parapet, h + parapet + 0.05, -0.28, 0.04, 'CX_Concrete', skip=('-b',))


# ---- one building ---------------------------------------------------------------------------------
def building(mb, b, pts, area, near, rng, feet):
    typ, lv = classify(b, area, rng)
    sp = SPEC[typ]
    n = len(pts)
    edges = []
    for i in range(n):
        p0, p1 = np.array(pts[i], float), np.array(pts[(i + 1) % n], float)
        edges.append((p0, p1, float(np.linalg.norm(p1 - p0))))
    longest = max(range(n), key=lambda i: edges[i][2])
    # heights
    if typ == 'shed':
        H = float(b.get('h') or rng.uniform(7.5, 10.5))
    elif typ == 'garage':
        H = float(b.get('h') or rng.uniform(2.8, 3.4))
    else:
        H = sp['base'] + lv * sp['fh'] + (0.4 if typ in ('tuff5', 'public') else 0.2)
        if typ == 'shop':
            H = sp['base'] + sp['fh'] + max(0, lv - 1) * 3.4 + 0.3
    # materials and tints
    if typ in ('tuff5',):
        wall = 'CX_Tuff' if rng.random() < 0.72 else 'CX_Plaster'
    elif typ == 'panel':
        wall = 'CX_Panel'
    elif typ == 'tower':
        wall = 'CX_Plaster' if rng.random() < 0.6 else 'CX_Tuff'
    elif typ == 'house':
        wall = 'CX_Plaster' if rng.random() < 0.6 else 'CX_Tuff'
    elif typ == 'shed':
        wall = 'CX_MetalWall' if rng.random() < 0.6 else 'CX_Panel'
    elif typ == 'garage':
        wall = 'CX_Panel'
    else:
        wall = 'CX_Plaster'
    pal = TUFF if wall == 'CX_Tuff' else PANEL if wall == 'CX_Panel' else METALW if wall == 'CX_MetalWall' else PLASTER
    tint = lin(pal[int(rng.integers(len(pal)))])
    sheet = lin(PANEL_BAL[int(rng.integers(len(PANEL_BAL)))])
    detailed = near or DETAIL != 'web'
    if not detailed:
        # far field in the web build: plain extrusion, windows painted by the grid material
        gmat = 'CX_Grid5' if typ not in ('shed', 'garage') else wall
        for (p0, p1, L) in edges:
            fr = Frame(p0, p1 - p0)
            mb.rect_c(fr, 0.0, L, 0.0, H, 0.0, gmat, col=tint)
        roof(mb, typ, pts, H, rng, wall, tint, simple=True)
        return typ, H
    storefront = typ == 'shop' or (typ in ('tuff5', 'tower') and rng.random() < 0.3)
    bal_side = longest if rng.random() < 0.5 else (longest + n // 2) % n
    entrances = set()
    for ei, (p0, p1, L) in enumerate(edges):
        fr = Frame(p0, p1 - p0)
        holes, wins = [], []
        extra = []
        if typ == 'garage':
            if ei == longest and L > 3:
                nb = max(1, int(L / sp['bay']))
                for k in range(nb):
                    a = (k + 0.5) * L / nb
                    holes.append((a - 1.25, a + 1.25, 0.0, min(2.3, H - 0.3)))
                    extra.append(('roller', holes[-1]))
        elif typ == 'shed':
            if L > 8:
                nb = int((L - 2) / sp['bay'])
                for k in range(nb):
                    a = 1 + (k + 0.5) * (L - 2) / nb
                    if H > 7.2:
                        holes.append((a - 1.8, a + 1.8, H - 2.6, H - 1.4))
                        wins.append(holes[-1])
                if ei == longest:
                    a = L / 2
                    holes.append((a - 2.2, a + 2.2, 0.0, 4.2))
                    extra.append(('roller', holes[-1]))
        elif L >= 2.6:
            nb = max(1, int((L - 1.2) / sp['bay']))
            bay = (L - 1.2) / nb
            w, hh, sill = sp['win']
            w = min(w, bay - 0.5)
            ent_bays = set()
            if typ in ('tuff5', 'panel', 'tower') and ei == longest and nb >= 3:
                k = max(1, nb // 4)
                ent_bays = {k, nb - 1 - k} if nb >= 8 else {nb // 2}
            for f in range(lv):
                z0 = sp['base'] + f * sp['fh']
                if typ == 'shop' and f > 0:
                    z0 = sp['base'] + sp['fh'] + (f - 1) * 3.4
                for k in range(nb):
                    ac = 0.6 + (k + 0.5) * bay
                    if f == 0 and k in ent_bays:
                        holes.append((ac - 0.65, ac + 0.65, 0.0, 2.35))
                        extra.append(('door', holes[-1]))
                        continue
                    if f == 0 and storefront and typ != 'house':
                        sw = min(bay - 0.4, 3.4)
                        holes.append((ac - sw / 2, ac + sw / 2, 0.25, min(3.0, sp['fh'] - 0.6)))
                        wins.append(holes[-1] + ('shop',))
                        continue
                    if rng.random() < (0.06 if typ != 'house' else 0.25):
                        continue          # blank bay (stairs, bathroom, missing window)
                    hole = (ac - w / 2, ac + w / 2, z0 + sill, z0 + sill + hh)
                    holes.append(hole)
                    wins.append(hole)
                    if f >= 1 and sp['bal'] > 0 and ei == bal_side and rng.random() < sp['bal']:
                        if typ == 'tower':
                            style = 'glass' if rng.random() < 0.7 else 'enclosed'
                        else:
                            style = 'enclosed' if rng.random() < (0.62 if typ == 'tuff5' else 0.72) else 'open'
                        extra.append(('balcony', (ac - bay / 2 + 0.18, ac + bay / 2 - 0.18, z0, style)))
                    elif f >= 1 and rng.random() < 0.13:
                        extra.append(('ac', (ac, z0 + sill)))
        mb.wall_holes(fr, 0.0, L, 0.0, H, holes, wall, col=tint)
        for hole in wins:
            shop = len(hole) > 4
            h4 = hole[:4]
            wcol = (rng.uniform(0.3, 1.0), rng.uniform(0.6, 1.0), 0.0, 1.0) if shop else \
                (rng.uniform(0.55, 1.0) if rng.random() < 0.45 else rng.uniform(0.0, 0.25), rng.uniform(0.1, 0.5), 0.0, 1.0)
            window(mb, fr, *h4, sp['depth'] if not shop else 0.4, wall, tint, wcol,
                   frame=(typ not in ('shed',)), sill=(not shop and typ not in ('shed', 'public')),
                   glass='NK_GlassShop' if shop else 'NK_GlassWindow')
        for kind, data in extra:
            if kind == 'door':
                a0, a1, b0, b1 = data
                mb.reveal(fr, a0, a1, b0, b1, 0.0, -0.18, wall)
                mb.rect_c(fr, a0, a1, b0, b1, -0.18, 'CX_Door')
                mb.box(fr, a0 - 0.6, a1 + 0.6, b1 + 0.3, b1 + 0.42, 0.0, 1.3, 'CX_Concrete', skip=('-c',))
            elif kind == 'roller':
                a0, a1, b0, b1 = data
                mb.reveal(fr, a0, a1, b0, b1, 0.0, -0.12, wall)
                mb.rect_c(fr, a0, a1, b0, b1, -0.12, 'CX_Roller', col=lin(METALW[int(rng.integers(len(METALW)))]))
            elif kind == 'balcony':
                a0, a1, z0, style = data
                balcony(mb, fr, a0, a1, z0, rng.uniform(1.0, 1.25), style, sheet, sheet)
            elif kind == 'ac':
                ac, zs = data
                mb.box(fr, ac - 0.42, ac + 0.42, zs - 0.78, zs - 0.2, 0.0, 0.3, 'CX_ACUnit', skip=('-c',))
        if sp['cornice'] and L > 1.0:
            # [0, L]: overlapping corner pieces would be coplanar twins (black shadow acne)
            mb.box(fr, 0.0, L, H - 0.55, H - 0.2, 0.0, 0.32, 'CX_Concrete', skip=('-c',))
        # plinth band
        if typ in ('tuff5', 'panel', 'tower', 'public') and L > 1.0:
            mb.box(fr, 0.0, L, 0.0, sp['base'] - 0.05, 0.0, 0.05, 'CX_Concrete', skip=('-c',))
    roof(mb, typ, pts, H, rng, wall, tint, simple=False)
    return typ, H


def roof(mb, typ, pts, H, rng, wall, tint, simple):
    rect = len(pts) == 4
    if typ == 'house' and rect:
        if rng.random() < 0.55:
            roof_hip(mb, pts, H, rng.uniform(1.6, 2.4), 'CX_Tile', lin(ROOF_TILE[int(rng.integers(len(ROOF_TILE)))]))
        else:
            roof_hip(mb, pts, H, rng.uniform(1.4, 2.2), 'CX_MetalRoof', lin(ROOF_METAL[int(rng.integers(len(ROOF_METAL)))]))
        return
    if typ == 'tuff5' and rect and rng.random() < 0.7:
        from nk_context import _obb, _gable
        gx, gy, rot, hx, hy = _obb(pts)
        if hy > hx:
            rot += math.pi / 2
            hx, hy = hy, hx
        rm = lin(ROOF_METAL[int(rng.integers(len(ROOF_METAL)))])
        _gable(mb, hx, hy, H, min(3.2, hy * 0.42), 'CX_MetalRoof', wall, rot, gx, gy, 0.55)
        # colour the new roof faces (last 2 quads + 2 gable triangles)
        for k in range(1, 5):
            mb.fcol[-k] = rm if k > 2 else tint
        return
    if typ == 'shed' and rect:
        from nk_context import _obb, _gable
        gx, gy, rot, hx, hy = _obb(pts)
        if hy > hx:
            rot += math.pi / 2
            hx, hy = hy, hx
        rm = lin(ROOF_METAL[int(rng.integers(len(ROOF_METAL)))])
        _gable(mb, hx, hy, H, min(2.2, hy * 0.18), 'CX_MetalRoof', wall, rot, gx, gy, 0.3)
        for k in range(1, 5):
            mb.fcol[-k] = rm if k > 2 else tint
        return
    parapet = 0.0 if typ in ('garage', 'house') or simple else (0.9 if typ in ('panel', 'tower', 'public') else 0.6)
    # drawn after every other choice of this building, so walls/windows/balconies stay as they were
    rcol = lin(ROOF_FLAT[int(rng.integers(len(ROOF_FLAT)))])
    roof_flat(mb, pts, H, parapet, wall, tint, rcol)
    avoid = None
    if not simple and typ in ('panel', 'tower'):
        from nk_osm import centroid
        cx, cy = centroid(pts)
        s = 2.6
        V = [(cx - s, cy - s * 1.4, H), (cx + s, cy - s * 1.4, H), (cx + s, cy + s * 1.4, H), (cx - s, cy + s * 1.4, H)]
        top = [(x, y, H + 3.0) for x, y, _ in V]
        for i in range(4):
            j = (i + 1) % 4
            mb.add([V[i], V[j], top[j], top[i]], [(0, 1, 2, 3)], wall, tint)
        mb.add(top, [(0, 1, 2, 3)], 'CX_FlatRoof', rcol)
        avoid = (cx, cy, s + 1.0, s * 1.4 + 1.0)
    if not simple and typ != 'garage':
        roof_clutter(mb, pts, H, rng, avoid)


def roof_clutter(mb, pts, h, rng, avoid=None):
    """Water tanks, AC condensers, vent stacks and satellite dishes: the typical Yerevan roofscape."""
    from nk_osm import poly_area
    from nk_site import _pip, _seg_d2
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    n = int(min(12, 1 + abs(poly_area(pts)) / 70))
    k = max(range(len(pts)), key=lambda i: math.dist(pts[i], pts[(i + 1) % len(pts)]))
    axis = (pts[(k + 1) % len(pts)][0] - pts[k][0], pts[(k + 1) % len(pts)][1] - pts[k][1])
    placed = []
    for _ in range(n * 8):
        if len(placed) >= n:
            break
        x, y = rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys))
        if not _pip(x, y, pts) or any((x - a) ** 2 + (y - b) ** 2 < 5.0 for a, b in placed):
            continue
        if any(_seg_d2(x, y, pts[i], pts[(i + 1) % len(pts)]) < 1.6 ** 2 for i in range(len(pts))):
            continue
        if avoid and abs(x - avoid[0]) < avoid[2] and abs(y - avoid[1]) < avoid[3]:
            continue
        placed.append((x, y))
        fr = Frame((x, y), axis, h)
        r = rng.random()
        if r < 0.3:                   # galvanised water tank on a concrete stand
            mb.box(fr, -0.75, 0.75, 0.25, 1.45, -0.6, 0.6, 'CX_Sheet', skip=('-b',), col=lin(METALW[int(rng.integers(len(METALW)))]))
            mb.box(fr, -0.6, 0.6, 0.0, 0.25, -0.45, 0.45, 'CX_Concrete', skip=('-b', '+b'))
        elif r < 0.7:                 # AC condenser
            mb.box(fr, -0.45, 0.45, 0.0, 0.65, -0.18, 0.18, 'CX_ACUnit', skip=('-b',))
        elif r < 0.88:                # vent stack
            mb.box(fr, -0.2, 0.2, 0.0, 1.3, -0.2, 0.2, 'CX_Concrete', skip=('-b',))
        else:                         # satellite dish on a post
            mb.box(fr, -0.03, 0.03, 0.0, 0.7, -0.03, 0.03, 'CX_Frame', skip=('-b',))
            mb.box(fr, -0.33, 0.33, 0.55, 1.15, 0.05, 0.1, 'CX_Frame')


# ---- walls and fences (OSM barrier=wall / fence / retaining_wall) -----------------------------------------
BARRIER = {  # default height, thickness (m)
    'wall': (2.1, 0.30), 'retaining_wall': (1.2, 0.40), 'fence': (1.75, 0.22)}


def _up_quad(mb, pts, mat, col=None):
    """Horizontal quad facing +Z whatever the input winding."""
    a = sum(pts[i][0] * pts[(i + 1) % 4][1] - pts[(i + 1) % 4][0] * pts[i][1] for i in range(4))
    mb.add(pts if a > 0 else pts[::-1], [(0, 1, 2, 3)], mat, col)


def _strip(mb, run, h, t, side_mat, top_mat, col, z0=0.0):
    """Mitred wall strip along a polyline run: both faces, top, end caps (outward windings)."""
    from nk_site import _offset
    L = [tuple(p) for p in _offset(run, t / 2)]
    R = [tuple(p) for p in _offset(run, -t / 2)]
    for i in range(len(run) - 1):
        l0, l1, r0, r1 = L[i], L[i + 1], R[i], R[i + 1]
        mb.add([(l1[0], l1[1], z0), (l0[0], l0[1], z0), (l0[0], l0[1], h), (l1[0], l1[1], h)], [(0, 1, 2, 3)], side_mat, col)
        mb.add([(r0[0], r0[1], z0), (r1[0], r1[1], z0), (r1[0], r1[1], h), (r0[0], r0[1], h)], [(0, 1, 2, 3)], side_mat, col)
        _up_quad(mb, [(l0[0], l0[1], h), (r0[0], r0[1], h), (r1[0], r1[1], h), (l1[0], l1[1], h)], top_mat, col)
    (l0, r0), (ln, rn) = (L[0], R[0]), (L[-1], R[-1])
    mb.add([(l0[0], l0[1], z0), (r0[0], r0[1], z0), (r0[0], r0[1], h), (l0[0], l0[1], h)], [(0, 1, 2, 3)], side_mat, col)
    mb.add([(rn[0], rn[1], z0), (ln[0], ln[1], z0), (ln[0], ln[1], h), (rn[0], rn[1], h)], [(0, 1, 2, 3)], side_mat, col)


def _fence(mb, run, h, rng):
    """Low tuff/concrete plinth, square steel posts every ~2.4 m and two rails."""
    plinth = rng.uniform(0.35, 0.55)
    _strip(mb, run, plinth, 0.24, 'CX_Concrete', 'CX_Concrete', None)
    metal = lin(METALW[int(rng.integers(len(METALW)))])
    for idx, (a, b) in enumerate(zip(run, run[1:])):
        seg = math.dist(a, b)
        if seg < 0.3:
            continue
        fr = Frame(a, (b[0] - a[0], b[1] - a[1]), 0.0)
        n = max(1, int(round(seg / 2.4)))
        for k in range(0 if idx == 0 else 1, n + 1):      # one post per corner (no coincident twins)
            s = min(seg - 0.04, max(0.04, seg * k / n))
            mb.box(fr, s - 0.04, s + 0.04, plinth, h, -0.04, 0.04, 'CX_Sheet', skip=('-b',), col=metal)
        for z in (plinth + 0.12, h - 0.1):
            mb.box(fr, 0.0, seg, z, z + 0.05, -0.025, 0.025, 'CX_Sheet', col=metal)


def barriers(builders, osm, keepout, polys, roads, near_radius):
    """OSM walls / fences clipped out of carriageways, building footprints and our site."""
    from nk_osm import inside
    from nk_site import ROAD_W, _Grid, _pip, _seg_d2
    bgrid, rgrid = _Grid(30.0), _Grid(30.0)
    for pts in polys:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        bgrid.add((pts, (min(xs), min(ys), max(xs), max(ys))), (min(xs), min(ys), max(xs), max(ys)))
    for rd in roads:
        hw = ROAD_W.get(rd['kind'], 5.0) / 2 + 0.3
        for a, b in zip(rd['pts'], rd['pts'][1:]):
            rgrid.add((a, b, hw), (min(a[0], b[0]) - hw, min(a[1], b[1]) - hw, max(a[0], b[0]) + hw, max(a[1], b[1]) + hw))

    def blocked(x, y):
        if any(inside(r, x, y, 2.0) for r in keepout):
            return True
        for pts, bb in bgrid.near(x, y):
            if bb[0] - 0.2 <= x <= bb[2] + 0.2 and bb[1] - 0.2 <= y <= bb[3] + 0.2 and _pip(x, y, pts):
                return True
        return any(_seg_d2(x, y, a, b) < hw * hw for a, b, hw in rgrid.near(x, y))

    stats = {}
    for bar in osm.get('barriers', []):
        kind = bar['kind']
        h0, t = BARRIER[kind]
        h = min(3.5, bar['h']) if bar.get('h') else h0
        if kind == 'fence' and bar.get('h') and bar['h'] < 1.0:
            continue                                     # knee-high garden edging: not visible at this scale
        rng = np.random.default_rng(zlib.crc32(('barrier' + str(bar['id'])).encode()))
        # resample every 0.5 m, then keep maximal unblocked runs (mitred polylines)
        runs, cur = [], []
        pts = [tuple(p) for p in bar['pts']]
        for a, b in zip(pts, pts[1:]):
            seg = math.dist(a, b)
            n = max(1, int(math.ceil(seg / 0.5)))
            for k in range(n + 1 if (a, b) == (pts[-2], pts[-1]) else n):
                x, y = a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n
                if blocked(x, y):
                    if len(cur) > 1:
                        runs.append(cur)
                    cur = []
                elif not cur or math.dist(cur[-1], (x, y)) > 1e-3:
                    cur.append((x, y))
        if len(cur) > 1:
            runs.append(cur)
        for run in runs:
            # drop the resampled interior points of straight stretches (keep corners)
            simple = [run[0]]
            for i in range(1, len(run) - 1):
                (x0, y0), (x1, y1), (x2, y2) = simple[-1], run[i], run[i + 1]
                if abs((x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)) > 0.02:
                    simple.append(run[i])
            simple.append(run[-1])
            length = sum(math.dist(p, q) for p, q in zip(simple, simple[1:]))
            if length < 1.0:
                continue
            cx, cy = sum(p[0] for p in simple) / len(simple), sum(p[1] for p in simple) / len(simple)
            mb = builders[0 if cx < 0 else 1] if math.hypot(cx, cy) < near_radius else builders[2]
            if kind == 'fence':
                _fence(mb, simple, h, rng)
            else:
                wall = 'CX_Concrete' if kind == 'retaining_wall' else ('CX_Tuff' if rng.random() < 0.65 else 'CX_Plaster')
                pal = TUFF if wall == 'CX_Tuff' else PLASTER
                _strip(mb, simple, h, t, wall, 'CX_Concrete', lin(pal[int(rng.integers(len(pal)))]) if wall != 'CX_Concrete' else None)
            stats[kind] = stats.get(kind, 0.0) + length
    print('OSM barriers built (m):', {k: round(v) for k, v in stats.items()})


# ---- all buildings ----------------------------------------------------------------------------------
def build(col, M, osm, keepout, near_radius=330.0, roads=()):
    """Returns feet [(cx, cy, r, pts)] for the tree layout (same footprints as before)."""
    from nk_osm import poly_area, centroid, inside
    build_materials(M)
    near_w, near_e, far_mb = MeshBuilder(), MeshBuilder(), MeshBuilder()
    feet = []
    counts = {}
    for b in osm['buildings']:
        pts = [tuple(p) for p in b['pts']]
        if len(pts) < 3:
            continue
        if pts[0] == pts[-1]:
            pts = pts[:-1]
        A = poly_area(pts)
        if A < 0:
            pts = pts[::-1]
            A = -A
        if A < 12:
            continue
        cx, cy = centroid(pts)
        if any(inside(r, cx, cy) for r in keepout) or any(inside(r, x, y) for r in keepout for x, y in pts):
            continue
        rng = np.random.default_rng(zlib.crc32(str(b.get('id')).encode()))
        near = math.hypot(cx, cy) < near_radius
        mb = (near_w if cx < 0 else near_e) if near else far_mb
        typ, H = building(mb, b, pts, A, near, rng, feet)
        counts[typ] = counts.get(typ, 0) + 1
        r = max(math.hypot(x - cx, y - cy) for x, y in pts)
        feet.append((cx, cy, r, pts))
    barriers((near_w, near_e, far_mb), osm, keepout, [f[3] for f in feet], roads, near_radius)
    near_w.to_object('NK_Context_NearW', col, M, merge=False)
    near_e.to_object('NK_Context_NearE', col, M, merge=False)
    far_mb.to_object('NK_Context_Far', col, M, merge=False)
    print('OSM context buildings:', len(feet), counts, 'faces near W/E, far:', len(near_w), len(near_e), len(far_mb))
    return feet
