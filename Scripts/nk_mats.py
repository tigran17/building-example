"""New Komitas exterior - PBR materials (Cycles / EEVEE, Blender 4.5 Principled BSDF).

Colours are authored in sRGB (as picked from the developer renders) and converted to
linear. All textures are procedural and driven by the box-mapped UV0 (metres), so the
same UVs work for tiling image textures in Unreal / three.js later.
"""
import bpy


def srgb(h, a=1.0):
    """'#RRGGBB' -> linear RGBA tuple."""
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, a)


class NT:
    """Tiny node-tree helper."""

    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = 0

    def n(self, kind, x=None, y=0, **props):
        node = self.nt.nodes.new(kind)
        node.location = (x if x is not None else self.x, y)
        for k, v in props.items():
            if k.startswith('in_'):
                key = k[3:].replace('_', ' ')
                node.inputs[key].default_value = v
            else:
                setattr(node, k, v)
        return node

    def link(self, a, b):
        self.nt.links.new(a, b)


def _principled(nt, **inputs):
    p = nt.n('ShaderNodeBsdfPrincipled', 400, 0)
    for k, v in inputs.items():
        p.inputs[k.replace('_', ' ')].default_value = v
    out = nt.n('ShaderNodeOutputMaterial', 750, 0)
    nt.link(p.outputs['BSDF'], out.inputs['Surface'])
    return p, out


def _uv(nt, x=-1200, y=0):
    tc = nt.n('ShaderNodeTexCoord', x, y)
    return tc.outputs['UV']


def _noise(nt, vec, scale, detail=3.0, rough=0.5, x=-900, y=0, dims='3D'):
    no = nt.n('ShaderNodeTexNoise', x, y)
    no.noise_dimensions = dims
    no.inputs['Scale'].default_value = scale
    no.inputs['Detail'].default_value = detail
    no.inputs['Roughness'].default_value = rough
    nt.link(vec, no.inputs['Vector'])
    return no


def _mix_col(nt, fac, a, b, x=-300, y=0, blend='MIX'):
    m = nt.n('ShaderNodeMix', x, y)
    m.data_type = 'RGBA'
    m.blend_type = blend
    if isinstance(fac, float):
        m.inputs['Factor'].default_value = fac
    else:
        nt.link(fac, m.inputs['Factor'])
    for sock, val in ((m.inputs[6], a), (m.inputs[7], b)):
        if isinstance(val, tuple):
            sock.default_value = val
        else:
            nt.link(val, sock)
    return m.outputs[2]


def _ramp(nt, fac, stops, x=-600, y=0):
    r = nt.n('ShaderNodeValToRGB', x, y)
    els = r.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], (stops[0][1],) * 3 + (1,)
    els[1].position, els[1].color = stops[1][0], (stops[1][1],) * 3 + (1,)
    nt.link(fac, r.inputs['Fac'])
    return r.outputs['Color']


def _bevel(nt, radius, p, x=150, y=-400):
    """Render-time rounded edges (Cycles only)."""
    bv = nt.n('ShaderNodeBevel', x, y)
    bv.samples = 6
    bv.inputs['Radius'].default_value = radius
    return bv


def mat_plaster(name, c1, c2, rough=0.72, panel=(1.5, 0.75), joint=0.006, joint_dark=0.82,
                bevel=0.012, blotch_scale=0.35):
    """Painted fibre-cement / render: two-tone blotches + faint panel joints + bevels."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    uv = _uv(nt)
    # large blotches
    no = _noise(nt, uv, blotch_scale, 4.0, 0.55, -900, 200)
    fac = _ramp(nt, no.outputs['Fac'], [(0.35, 0.0), (0.7, 1.0)], -650, 200)
    base = _mix_col(nt, fac, srgb(c1), srgb(c2), -350, 200)
    # fine speckle
    no2 = _noise(nt, uv, 38.0, 2.0, 0.6, -900, -100)
    sp = _ramp(nt, no2.outputs['Fac'], [(0.4, 0.93), (0.62, 1.0)], -650, -100)
    base = _mix_col(nt, 1.0, base, sp, -150, 150, 'MULTIPLY')
    p, out = _principled(nt, Roughness=rough)
    p.inputs['Specular IOR Level'].default_value = 0.45
    # panel joints (brick texture used as a stack-bond grid)
    if panel:
        br = nt.n('ShaderNodeTexBrick', -900, -400)
        br.offset = 0.0
        br.squash = 1.0
        br.inputs['Scale'].default_value = 1.0
        br.inputs['Mortar Size'].default_value = joint
        br.inputs['Mortar Smooth'].default_value = 0.3
        br.inputs['Brick Width'].default_value = panel[0]
        br.inputs['Row Height'].default_value = panel[1]
        br.inputs['Color1'].default_value = (1, 1, 1, 1)
        br.inputs['Color2'].default_value = (1, 1, 1, 1)
        br.inputs['Mortar'].default_value = (joint_dark,) * 3 + (1,)
        nt.link(uv, br.inputs['Vector'])
        base = _mix_col(nt, 1.0, base, br.outputs['Color'], 100, 250, 'MULTIPLY')
        bump = nt.n('ShaderNodeBump', 150, -250)
        bump.inputs['Strength'].default_value = 0.25
        bump.inputs['Distance'].default_value = 0.004
        bump.invert = True
        nt.link(br.outputs['Fac'], bump.inputs['Height'])
        if bevel:
            bv = _bevel(nt, bevel, p, -100, -450)
            nt.link(bv.outputs['Normal'], bump.inputs['Normal'])
        nt.link(bump.outputs['Normal'], p.inputs['Normal'])
    elif bevel:
        bv = _bevel(nt, bevel, p)
        nt.link(bv.outputs['Normal'], p.inputs['Normal'])
    nt.link(base, p.inputs['Base Color'])
    return mat


def mat_bronze(name, c1='#B0845A', c2='#976F4D', metal=0.25, rough=0.44, bevel=0.012):
    """Wood-effect anodised bronze panels (the copper frames / balcony bands)."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    uv = _uv(nt)
    # streaky grain: noise stretched along U
    mp = nt.n('ShaderNodeMapping', -1050, 150)
    mp.inputs['Scale'].default_value = (0.6, 9.0, 1.0)
    nt.link(uv, mp.inputs['Vector'])
    no = _noise(nt, mp.outputs['Vector'], 1.8, 6.0, 0.62, -850, 150)
    fac = _ramp(nt, no.outputs['Fac'], [(0.3, 0.0), (0.72, 1.0)], -600, 150)
    base = _mix_col(nt, fac, srgb(c1), srgb(c2), -300, 150)
    no2 = _noise(nt, uv, 0.25, 3.0, 0.5, -850, -150)
    f2 = _ramp(nt, no2.outputs['Fac'], [(0.35, 0.9), (0.65, 1.06)], -600, -150)
    base = _mix_col(nt, 1.0, base, f2, -100, 100, 'MULTIPLY')
    p, out = _principled(nt, Metallic=metal, Roughness=rough)
    nt.link(base, p.inputs['Base Color'])
    rr = _ramp(nt, no.outputs['Fac'], [(0.2, rough - 0.08), (0.8, rough + 0.1)], -300, -350)
    nt.link(rr, p.inputs['Roughness'])
    if bevel:
        bv = _bevel(nt, bevel, p)
        nt.link(bv.outputs['Normal'], p.inputs['Normal'])
    return mat


def mat_simple(name, color, rough=0.5, metal=0.0, spec=0.5, noise=0.0, noise_scale=2.0, bevel=0.0):
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    p, out = _principled(nt, Metallic=metal, Roughness=rough)
    p.inputs['Specular IOR Level'].default_value = spec
    if noise > 0:
        uv = _uv(nt)
        no = _noise(nt, uv, noise_scale, 4.0, 0.55, -900, 0)
        f = _ramp(nt, no.outputs['Fac'], [(0.3, 1.0 - noise), (0.7, 1.0 + noise)], -600, 0)
        base = _mix_col(nt, 1.0, srgb(color), f, -300, 0, 'MULTIPLY')
        nt.link(base, p.inputs['Base Color'])
    else:
        p.inputs['Base Color'].default_value = srgb(color)
    if bevel:
        bv = _bevel(nt, bevel, p)
        nt.link(bv.outputs['Normal'], p.inputs['Normal'])
    return mat


def mat_glass_facade(name, tint='#2C3B4A', rough=0.015, spec=0.5, interior=None, emit=0.0,
                     use_col=False, ior=1.52):
    """Opaque architectural glass: dark body + strong Fresnel reflection.

    interior: optional (dark, light) sRGB pair mixed by the per-window 'Col' attribute and
    shown as weak emission (a view into a dim room / curtains), unaffected by the sun.
    """
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    # Coated architectural glass reflects 15-30 % at normal incidence: an opaque dielectric
    # with a high IOR reproduces that (F0 = ((ior-1)/(ior+1))^2 * 2*spec).
    p, out = _principled(nt, Metallic=0.0, Roughness=rough, IOR=ior)
    p.inputs['Base Color'].default_value = srgb(tint)
    p.inputs['Specular IOR Level'].default_value = spec
    p.inputs['Coat Weight'].default_value = 0.0
    if interior is not None:
        ca = nt.n('ShaderNodeVertexColor', -900, -250)
        ca.layer_name = 'Col'
        sep = nt.n('ShaderNodeSeparateColor', -700, -250)
        nt.link(ca.outputs['Color'], sep.inputs['Color'])
        col = _mix_col(nt, sep.outputs['Red'], srgb(interior[0]), srgb(interior[1]), -450, -250)
        # green channel scales brightness (lights on/off, curtain density)
        mul = nt.n('ShaderNodeMath', -450, -450, operation='MULTIPLY')
        mul.inputs[1].default_value = emit
        nt.link(sep.outputs['Green'], mul.inputs[0])
        nt.link(col, p.inputs['Emission Color'])
        nt.link(mul.outputs[0], p.inputs['Emission Strength'])
        # base tint also varies slightly (curtain colour behind glass)
        bc = _mix_col(nt, 0.35, srgb(tint), col, -200, -150)
        nt.link(bc, p.inputs['Base Color'])
    return mat


def mat_glass_clear(name, tint='#E6EEEC', rough=0.02):
    """Transmissive glass for balustrades (thin panes)."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    p, out = _principled(nt, Roughness=rough, IOR=1.5)
    p.inputs['Base Color'].default_value = srgb(tint)
    p.inputs['Transmission Weight'].default_value = 1.0
    return mat


def mat_grass(name):
    """Lawns and parks at the end of a dry summer, seen from above: two muted greens in ~7 m patches,
    sun-dried straw areas (~25 m), worn earth spots (~3 m) and fine mottling."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    uv = _uv(nt)
    n1 = _noise(nt, uv, 0.15, 5.0, 0.6, -1000, 400)
    c = _mix_col(nt, _ramp(nt, n1.outputs['Fac'], [(0.35, 0.0), (0.7, 1.0)], -750, 400),
                 srgb('#4B612F'), srgb('#68743F'), -500, 400)
    n2 = _noise(nt, uv, 0.035, 4.0, 0.6, -1000, 150)
    c = _mix_col(nt, _ramp(nt, n2.outputs['Fac'], [(0.55, 0.0), (0.76, 0.55)], -750, 150), c, srgb('#8A8356'), -350, 300)
    n3 = _noise(nt, uv, 0.32, 6.0, 0.7, -1000, -100)
    c = _mix_col(nt, _ramp(nt, n3.outputs['Fac'], [(0.68, 0.0), (0.8, 0.75)], -750, -100), c, srgb('#77694F'), -200, 200)
    n4 = _noise(nt, uv, 3.0, 3.0, 0.7, -1000, -350)
    c = _mix_col(nt, 1.0, c, _ramp(nt, n4.outputs['Fac'], [(0.3, 0.82), (0.7, 1.08)], -750, -350), -50, 100, 'MULTIPLY')
    p, out = _principled(nt, Roughness=0.93)
    p.inputs['Specular IOR Level'].default_value = 0.3
    nt.link(c, p.inputs['Base Color'])
    bump = nt.n('ShaderNodeBump', 150, -250)
    bump.inputs['Strength'].default_value = 0.4
    nt.link(n4.outputs['Fac'], bump.inputs['Height'])
    nt.link(bump.outputs['Normal'], p.inputs['Normal'])
    return mat


def mat_lawn(name):
    """Irrigated courtyard lawn (the park / verge grass is the dry late-summer mix): lusher, lighter greens
    in ~5 m patches, faint mowing stripes 1.6 m wide, fine mottling."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    uv = _uv(nt)
    n1 = _noise(nt, uv, 0.2, 4.0, 0.6, -1000, 400)
    c = _mix_col(nt, _ramp(nt, n1.outputs['Fac'], [(0.35, 0.0), (0.7, 1.0)], -750, 400),
                 srgb('#618739'), srgb('#76A047'), -500, 400)
    wv = nt.n('ShaderNodeTexWave', -1000, 150)
    wv.wave_type = 'BANDS'
    wv.bands_direction = 'X'
    wv.inputs['Scale'].default_value = 0.098          # Blender bands: period 2*pi/20/scale = 3.2 m (1.6 m stripes)
    wv.inputs['Distortion'].default_value = 0.0
    nt.link(uv, wv.inputs['Vector'])
    c = _mix_col(nt, 1.0, c, _ramp(nt, wv.outputs['Fac'], [(0.45, 0.95), (0.55, 1.04)], -750, 150), -350, 300, 'MULTIPLY')
    n4 = _noise(nt, uv, 3.0, 3.0, 0.7, -1000, -350)
    c = _mix_col(nt, 1.0, c, _ramp(nt, n4.outputs['Fac'], [(0.3, 0.86), (0.7, 1.06)], -750, -350), -50, 100, 'MULTIPLY')
    p, out = _principled(nt, Roughness=0.9)
    p.inputs['Specular IOR Level'].default_value = 0.3
    nt.link(c, p.inputs['Base Color'])
    bump = nt.n('ShaderNodeBump', 150, -250)
    bump.inputs['Strength'].default_value = 0.35
    nt.link(n4.outputs['Fac'], bump.inputs['Height'])
    nt.link(bump.outputs['Normal'], p.inputs['Normal'])
    return mat


def mat_grass_blade(name):
    """Hair-strand grass: random green / straw mix per strand, darker at the root."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    hi = nt.n('ShaderNodeHairInfo', -1000, 0)
    r = _ramp(nt, hi.outputs['Random'], [(0.72, 0.0), (0.97, 1.0)], -750, 150)
    c = _mix_col(nt, r, srgb('#55712B'), srgb('#9F9A5A'), -450, 150)
    root = _ramp(nt, hi.outputs['Intercept'], [(0.0, 0.35), (0.7, 1.0)], -750, -150)
    c = _mix_col(nt, 1.0, c, root, -200, 100, 'MULTIPLY')
    p = nt.n('ShaderNodeBsdfPrincipled', 50, 200)
    p.inputs['Roughness'].default_value = 0.55
    p.inputs['Specular IOR Level'].default_value = 0.3
    nt.link(c, p.inputs['Base Color'])
    tr = nt.n('ShaderNodeBsdfTranslucent', 50, -200)
    nt.link(c, tr.inputs['Color'])
    mix = nt.n('ShaderNodeMixShader', 350, 0)
    mix.inputs['Fac'].default_value = 0.25
    nt.link(p.outputs['BSDF'], mix.inputs[1])
    nt.link(tr.outputs['BSDF'], mix.inputs[2])
    out = nt.n('ShaderNodeOutputMaterial', 600, 0)
    nt.link(mix.outputs['Shader'], out.inputs['Surface'])
    return mat


def mat_ground(name):
    """Unirrigated urban land in late September: dusty straw grass, green patches under the trees' reach,
    bare earth and gravel, at 50 m / 10 m / 2 m scales plus fine mottling."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    uv = _uv(nt)
    n1 = _noise(nt, uv, 0.02, 4.0, 0.6, -1000, 450)
    c = _mix_col(nt, _ramp(nt, n1.outputs['Fac'], [(0.36, 0.0), (0.56, 1.0)], -750, 450),
                 srgb('#847D55'), srgb('#5A6835'), -500, 450)
    n2 = _noise(nt, uv, 0.1, 5.0, 0.65, -1000, 200)
    c = _mix_col(nt, _ramp(nt, n2.outputs['Fac'], [(0.6, 0.0), (0.72, 0.85)], -750, 200), c, srgb('#7A6A51'), -350, 320)
    n3 = _noise(nt, uv, 0.5, 5.0, 0.7, -1000, -50)
    c = _mix_col(nt, _ramp(nt, n3.outputs['Fac'], [(0.7, 0.0), (0.82, 0.7)], -750, -50), c, srgb('#8C877C'), -200, 200)
    n4 = _noise(nt, uv, 2.5, 3.0, 0.7, -1000, -300)
    c = _mix_col(nt, 1.0, c, _ramp(nt, n4.outputs['Fac'], [(0.3, 0.84), (0.7, 1.08)], -750, -300), -50, 100, 'MULTIPLY')
    p, out = _principled(nt, Roughness=0.95)
    p.inputs['Specular IOR Level'].default_value = 0.25
    nt.link(c, p.inputs['Base Color'])
    bump = nt.n('ShaderNodeBump', 150, -250)
    bump.inputs['Strength'].default_value = 0.35
    nt.link(n4.outputs['Fac'], bump.inputs['Height'])
    nt.link(bump.outputs['Normal'], p.inputs['Normal'])
    return mat


def mat_asphalt(name):
    """Worn city asphalt: mid grey (not the near-black of fresh tar), darker patch repairs, aggregate."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    uv = _uv(nt)
    n1 = _noise(nt, uv, 0.12, 4.0, 0.55, -1000, 300)
    c = _mix_col(nt, _ramp(nt, n1.outputs['Fac'], [(0.58, 0.0), (0.63, 1.0)], -750, 300),
                 srgb('#5A5B5D'), srgb('#47484B'), -500, 300)
    n2 = _noise(nt, uv, 0.6, 5.0, 0.6, -1000, 0)
    c = _mix_col(nt, 1.0, c, _ramp(nt, n2.outputs['Fac'], [(0.3, 0.9), (0.7, 1.06)], -750, 0), -300, 150, 'MULTIPLY')
    n3 = _noise(nt, uv, 6.0, 2.0, 0.7, -1000, -300)
    c = _mix_col(nt, 1.0, c, _ramp(nt, n3.outputs['Fac'], [(0.3, 0.92), (0.7, 1.05)], -750, -300), -100, 100, 'MULTIPLY')
    p, out = _principled(nt, Roughness=0.9)
    p.inputs['Specular IOR Level'].default_value = 0.35
    nt.link(c, p.inputs['Base Color'])
    return mat


def mat_pavers(name, c1='#A09D96', c2='#8C8983', size=(0.6, 0.3), joint=0.012):
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    uv = _uv(nt)
    br = nt.n('ShaderNodeTexBrick', -800, 100)
    br.offset = 0.5
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = joint
    br.inputs['Brick Width'].default_value = size[0]
    br.inputs['Row Height'].default_value = size[1]
    br.inputs['Color1'].default_value = srgb(c1)
    br.inputs['Color2'].default_value = srgb(c2)
    br.inputs['Mortar'].default_value = srgb('#6E6B66')
    br.inputs['Bias'].default_value = 0.0
    nt.link(uv, br.inputs['Vector'])
    no = _noise(nt, uv, 1.5, 4.0, 0.6, -800, -250)
    f = _ramp(nt, no.outputs['Fac'], [(0.3, 0.88), (0.7, 1.06)], -550, -250)
    base = _mix_col(nt, 1.0, br.outputs['Color'], f, -250, 50, 'MULTIPLY')
    p, out = _principled(nt, Roughness=0.8)
    nt.link(base, p.inputs['Base Color'])
    bump = nt.n('ShaderNodeBump', 150, -250)
    bump.inputs['Strength'].default_value = 0.5
    bump.inputs['Distance'].default_value = 0.005
    bump.invert = True
    nt.link(br.outputs['Fac'], bump.inputs['Height'])
    nt.link(bump.outputs['Normal'], p.inputs['Normal'])
    return mat


def mat_membrane(name):
    """Flat-roof membrane (light grey coated sheet): welded roll seams every 2 m with staggered end laps,
    large weathering / ponding blotches and a fine grain (a single grey read as a plastic slab from above)."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    uv = _uv(nt)
    br = nt.n('ShaderNodeTexBrick', -900, 350)
    br.offset = 0.37
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Brick Width'].default_value = 16.0
    br.inputs['Row Height'].default_value = 2.0
    br.inputs['Mortar Size'].default_value = 0.03
    br.inputs['Mortar Smooth'].default_value = 0.5
    br.inputs['Color1'].default_value = (1.0, 1.0, 1.0, 1.0)
    br.inputs['Color2'].default_value = (0.965, 0.965, 0.96, 1.0)
    br.inputs['Mortar'].default_value = (0.78, 0.78, 0.77, 1.0)
    nt.link(uv, br.inputs['Vector'])
    n1 = _noise(nt, uv, 0.07, 4.0, 0.62, -900, 100)
    f1 = _ramp(nt, n1.outputs['Fac'], [(0.3, 0.8), (0.7, 1.06)], -650, 100)
    n3 = _noise(nt, uv, 0.25, 5.0, 0.7, -900, -20)
    f3 = _ramp(nt, n3.outputs['Fac'], [(0.55, 1.0), (0.72, 0.84)], -650, -20)   # darker ponding / dirt patches
    n2 = _noise(nt, uv, 4.0, 3.0, 0.6, -900, -150)
    f2 = _ramp(nt, n2.outputs['Fac'], [(0.3, 0.94), (0.7, 1.03)], -650, -150)
    base = _mix_col(nt, 1.0, srgb('#A4A39D'), br.outputs['Color'], -450, 300, 'MULTIPLY')
    base = _mix_col(nt, 1.0, base, f1, -300, 200, 'MULTIPLY')
    base = _mix_col(nt, 1.0, base, f3, -220, 150, 'MULTIPLY')
    base = _mix_col(nt, 1.0, base, f2, -150, 100, 'MULTIPLY')
    p, out = _principled(nt, Roughness=0.86)
    p.inputs['Specular IOR Level'].default_value = 0.35
    nt.link(base, p.inputs['Base Color'])
    return mat


def mat_flowers(name):
    """Flower bed seen from a few metres up: clumps of pink, red, purple, yellow, white and orange over foliage."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    uv = _uv(nt)
    vo = nt.n('ShaderNodeTexVoronoi', -900, 250)
    vo.inputs['Scale'].default_value = 3.5
    nt.link(uv, vo.inputs['Vector'])
    sep = nt.n('ShaderNodeSeparateColor', -700, 250)
    nt.link(vo.outputs['Color'], sep.inputs['Color'])
    r = nt.n('ShaderNodeValToRGB', -500, 250)
    r.color_ramp.interpolation = 'CONSTANT'
    els = r.color_ramp.elements
    cols = ['#D9537B', '#C23B3B', '#8A5AA6', '#E3C04A', '#EFEDE4', '#E07A3A', '#5E7F34']
    els[0].position, els[0].color = 0.0, srgb(cols[0])
    els[1].position, els[1].color = 1.0 / len(cols), srgb(cols[1])
    for i, c in enumerate(cols[2:], 2):
        e = els.new(i / len(cols))
        e.color = srgb(c)
    nt.link(sep.outputs['Red'], r.inputs['Fac'])
    no = _noise(nt, uv, 6.0, 3.0, 0.6, -900, -50)
    m = _ramp(nt, no.outputs['Fac'], [(0.45, 0.0), (0.55, 1.0)], -650, -50)
    base = _mix_col(nt, m, srgb('#4A6A2C'), r.outputs['Color'], -250, 150)
    p, out = _principled(nt, Roughness=0.8)
    p.inputs['Specular IOR Level'].default_value = 0.3
    nt.link(base, p.inputs['Base Color'])
    return mat


def mat_asphalt_stain(name):
    """Asphalt darkened by the face colour 'Col' (oil stains in the parking bays, soft concentric rings)."""
    mat = mat_asphalt(name)
    nt = mat.node_tree
    p = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    src = p.inputs['Base Color'].links[0].from_socket
    ca = nt.nodes.new('ShaderNodeVertexColor')
    ca.layer_name = 'Col'
    mul = nt.nodes.new('ShaderNodeMix')
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    nt.links.new(src, mul.inputs[6])
    nt.links.new(ca.outputs['Color'], mul.inputs[7])
    nt.links.new(mul.outputs[2], p.inputs['Base Color'])
    return mat


def mat_pv(name):
    """Solar panels: 1.0 x 1.2 m modules in thin silver frames, dark blue glass with a slight per-module tone
    change (fine 16 cm cells turned into a plaid moire at close range)."""
    mat = bpy.data.materials.new(name)
    nt = NT(mat)
    uv = _uv(nt)
    br = nt.n('ShaderNodeTexBrick', -800, 150)
    br.offset = 0.0
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Brick Width'].default_value = 1.0
    br.inputs['Row Height'].default_value = 1.2
    br.inputs['Mortar Size'].default_value = 0.025
    br.inputs['Color1'].default_value = srgb('#1B2737')
    br.inputs['Color2'].default_value = srgb('#22303F')
    br.inputs['Mortar'].default_value = srgb('#9AA2AA')
    nt.link(uv, br.inputs['Vector'])
    p, out = _principled(nt, Roughness=0.28)
    p.inputs['Specular IOR Level'].default_value = 0.6
    nt.link(br.outputs['Color'], p.inputs['Base Color'])
    return mat

def mat_court(name, color, line='#F2F2EE'):
    return mat_simple(name, color, rough=0.75, noise=0.05, noise_scale=0.5)


def build_library():
    """Create all project materials; returns dict name -> material."""
    M = {}

    def add(m):
        M[m.name] = m
        return m

    # Facade whites - measured from the renders (lit white ~#E4E4E0, shade ~#B9BCC0).
    add(mat_plaster('NK_White', '#DADAD5', '#CFCFCA', rough=0.7, panel=(1.5, 0.75)))
    add(mat_plaster('NK_BalconyWhite', '#E0E0DB', '#D5D5D0', rough=0.62, panel=None, bevel=0.018))
    add(mat_plaster('NK_Soffit', '#D8D8D3', '#CDCDC8', rough=0.8, panel=None, bevel=0.0))
    add(mat_plaster('NK_GreyPanel', '#8E8F8E', '#7F807F', rough=0.75, panel=(1.2, 0.6)))
    add(mat_bronze('NK_Bronze'))
    add(mat_glass_facade('NK_GlassCurtain', tint='#1B2631', rough=0.012, spec=0.8, ior=2.4))
    add(mat_glass_facade('NK_GlassSpandrel', tint='#232B33', rough=0.05, spec=0.7, ior=2.0))
    add(mat_glass_facade('NK_GlassWindow', tint='#0E1318', rough=0.01, spec=0.7, ior=1.9,
                         interior=('#2A2622', '#D9D2C3'), emit=0.6))
    add(mat_glass_facade('NK_GlassShop', tint='#12171C', rough=0.01, spec=0.7, ior=1.9,
                         interior=('#3A342C', '#E8DCC4'), emit=1.4))
    add(mat_glass_clear('NK_GlassRail'))
    add(mat_simple('NK_DarkMetal', '#2E3033', rough=0.38, metal=0.7))
    add(mat_simple('NK_Coping', '#B9BAB7', rough=0.35, metal=0.6))
    add(mat_membrane('NK_Roof'))
    add(mat_simple('NK_RoofTiles', '#B5B3AD', rough=0.85, noise=0.05, noise_scale=1.0))
    add(mat_asphalt('NK_Asphalt'))
    add(mat_pavers('NK_Pavers'))
    add(mat_pavers('NK_PaversDark', '#6F6D69', '#63615D', size=(0.4, 0.2)))
    add(mat_pavers('NK_ParkPath', '#B6AFA1', '#A89F90', size=(0.5, 0.5), joint=0.008))   # light park paths (developer's aerial)
    add(mat_simple('NK_Curb', '#BDBBB5', rough=0.7, noise=0.05))
    add(mat_grass('NK_Grass'))
    add(mat_ground('NK_Ground'))
    add(mat_grass_blade('NK_GrassBlade'))
    add(mat_simple('NK_Soil', '#6B5A45', rough=0.95, noise=0.15, noise_scale=0.8))
    add(mat_court('NK_CourtBlue', '#2F6E9E'))
    add(mat_court('NK_CourtGreen', '#3F7F48'))
    add(mat_court('NK_PlayRubber', '#C8643A'))
    add(mat_simple('NK_LineWhite', '#EDEDE8', rough=0.7))
    # v0.12 street life: flower beds, sand, tactile paving, oil stains, solar panels, road signs, green rubber
    add(mat_flowers('NK_Flowers'))
    add(mat_simple('NK_Sand', '#D6C39C', rough=0.95, noise=0.1, noise_scale=6.0))
    add(mat_simple('NK_Tactile', '#C8A64A', rough=0.8, noise=0.06, noise_scale=3.0))
    add(mat_asphalt_stain('NK_AsphaltStain'))
    add(mat_pv('NK_PV'))
    add(mat_simple('NK_SignBlue', '#1F5FA8', rough=0.4))
    add(mat_simple('NK_SignWhite', '#F2F2EE', rough=0.4))
    add(mat_court('NK_RubberGreen', '#4E8A55'))
    add(mat_lawn('NK_LawnCourt'))
    add(mat_pavers('NK_CourtPath', '#CFC8BB', '#C2BAAC', size=(0.6, 0.4), joint=0.006))
    return M
