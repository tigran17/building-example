"""New Komitas exterior - facade grammar.

A facade run (one straight wall between two corners) is described by a score string:

    "P:f BAL:b7-10 S BAL S F:8.6 S E:g1 BAL:g1 S:g1 BAL:g1 E:g1 S P:f"

Tokens (TYPE[:opt,opt...]):
  BAL   balcony column (default 6.0 m): stacked cantilevered trays + two tall openings/floor
        b7-10  bronze trays on floors 7..10
  S     1.6 m glazed strip (full-height recessed curtain wall)
  F     tall copper frame, width given as number (default 7.3): lower part floors 0-7,
        upper part floors 9-17 rising above the roof; floor 8 is a white band
  f5    (on F) narrow single-part frame used on courtyard facades
  E     0.85 m edge pier carrying the side bar of a picture frame (group gN)
  P / C plain white pier (C = corner clearance) - 'f' makes it flexible
  gN    membership of picture-frame group N (group floors given separately)
"""
import os
import numpy as np
from nk_geo import Frame, fit_score

DETAIL = os.environ.get('NK_DETAIL', 'full')     # 'web' drops window frames / mullions (sub-pixel online)

# ---- vertical grid -------------------------------------------------------------------
GF = 4.2            # ground floor: slab top of floor 1
FH = 3.0            # typical floor-to-floor
NF = 17             # residential floors 1..17 (18 storeys incl. ground floor)
ROOF = GF + NF * FH  # 55.2 structural roof
ROOF_TOP = ROOF + 0.3
PAR = ROOF + 1.2     # 56.4 parapet / balcony-cap top
FRAME_TOP = PAR + 1.8  # copper frames rise above the roofline

TRAY_D = 1.5        # balcony projection
SLAB = 0.22
PARA_H = 1.05
PARA_T = 0.14
WIN_D = 0.25        # window reveal depth
STRIP_D = 0.35
FRAME_E = 0.85      # copper border width
FRAME_P = 1.6       # copper frame projection
PIC_P = 1.75        # picture frame projection (just proud of the balconies)
Z_LOW = None        # set in _levels()


def zf(f):
    """Floor level of residential floor f (1..17); zf(18) == ROOF."""
    return GF + (f - 1) * FH


LOW_TOP = zf(8)      # 25.2 top of the lower frame (floors 1-7)
UP_BOT = zf(9)       # 28.2 bottom of the upper frame (floors 9-17)

NOM = {'BAL': 6.0, 'S': 1.6, 'F': 7.3, 'E': FRAME_E, 'P': 0.8, 'C': 2.0}

WHITE, BWHITE, SOFFIT = 'NK_White', 'NK_BalconyWhite', 'NK_Soffit'
BRONZE, DARK = 'NK_Bronze', 'NK_DarkMetal'
GCUR, GSPA, GWIN, GSHOP, GRAIL = 'NK_GlassCurtain', 'NK_GlassSpandrel', 'NK_GlassWindow', 'NK_GlassShop', 'NK_GlassRail'
TILES, COPING = 'NK_RoofTiles', 'NK_Coping'


def parse_score(s):
    out = []
    for tok in s.split():
        parts = tok.split(':')
        t = parts[0]
        e = {'t': t, 'w': NOM[t], 'flex': 0.0, 'bz': set(), 'g': None, 'kind': None}
        if len(parts) > 1:
            for o in parts[1].split(','):
                if o == 'f':
                    e['flex'] = 1.0
                elif o.startswith('b'):
                    a, b = o[1:].split('-')
                    e['bz'] = set(range(int(a), int(b) + 1))
                elif o.startswith('g'):
                    e['g'] = int(o[1:])
                elif o.startswith('w'):
                    e['w'] = float(o[1:])
                elif o == 'f5':
                    e['kind'] = 'narrow'
                    e['w'] = 5.0
                else:
                    e['w'] = float(o)
        out.append(e)
    return out


class Builders:
    """One MeshBuilder per category so objects stay organised (and bake/export well)."""

    def __init__(self, MB, rng):
        self.wall = MB()     # white walls, reveals, piers
        self.bal = MB()      # balcony trays and caps
        self.glass = MB()    # all glazing + mullions + window frames
        self.bronze = MB()   # copper frames, picture frames, bronze bars
        self.roof = MB()     # roof surface, parapet backs, coping, rooftop plant
        self.rng = rng

    def all(self):
        return {'Walls': self.wall, 'Balconies': self.bal, 'Glazing': self.glass,
                'Bronze': self.bronze, 'Roof': self.roof}

    def wcol(self, shop=False):
        """Random per-window colour: R = curtain amount, G = interior brightness."""
        r = self.rng
        if shop:
            return (r.uniform(0.4, 1.0), r.uniform(0.6, 1.0), 0.0, 1.0)
        curtain = r.uniform(0.55, 1.0) if r.random() < 0.45 else r.uniform(0.0, 0.25)
        return (curtain, r.uniform(0.15, 0.6), 0.0, 1.0)


# ---- element pieces ------------------------------------------------------------------

def window(B, fr, a0, a1, b0, b1, depth=WIN_D, mull=(), shop=False, reveal_mat=WHITE,
           glass=None):
    """Opening already cut in the wall plane: reveals, frame ring, glass, mullions."""
    fw = 0.055
    B.wall.reveal(fr, a0, a1, b0, b1, 0.0, -depth, reveal_mat)
    g = glass or (GSHOP if shop else GWIN)
    if DETAIL == 'web':
        B.glass.rect_c(fr, a0, a1, b0, b1, -depth, g, col=B.wcol(shop))
        return
    B.glass.wall_holes(fr, a0, a1, b0, b1, [(a0 + fw, a1 - fw, b0 + fw, b1 - fw)], DARK, c=-depth + 0.05)
    B.glass.reveal(fr, a0 + fw, a1 - fw, b0 + fw, b1 - fw, -depth + 0.05, -depth, DARK)
    B.glass.rect_c(fr, a0 + fw, a1 - fw, b0 + fw, b1 - fw, -depth, g, col=B.wcol(shop))
    for m in mull:
        B.glass.box(fr, m - 0.03, m + 0.03, b0 + fw, b1 - fw, -depth, -depth + 0.06, DARK, skip=('-c',))


def curtain(B, fr, a0, a1, b0, b1, depth, levels, vmull=(), reveal_mat=WHITE, back=False,
            spandrel=True):
    """Recessed curtain wall: reveals, vision/spandrel glass per floor, transoms, mullions."""
    if reveal_mat:
        B.wall.reveal(fr, a0, a1, b0, b1, 0.0, -depth, reveal_mat)
    cuts = [b0]
    kinds = []
    for z in levels:
        s0, s1 = z - 0.35, z + 0.45
        if spandrel and s1 > b0 + 0.3 and s0 < b1 - 0.3:
            s0, s1 = max(s0, b0), min(s1, b1)
            if s0 > cuts[-1] + 1e-6:
                cuts.append(s0)
                kinds.append(GCUR)
            cuts.append(s1)
            kinds.append(GSPA)
    if cuts[-1] < b1 - 1e-6:
        cuts.append(b1)
        kinds.append(GCUR)
    for i, k in enumerate(kinds):
        B.glass.rect_c(fr, a0, a1, cuts[i], cuts[i + 1], -depth, k)
        if back:
            B.glass.rect_c(fr, a0, a1, cuts[i], cuts[i + 1], -depth - 0.02, k, facing=-1)
    for z in levels:
        if b0 + 0.1 < z < b1 - 0.1:
            B.glass.box(fr, a0, a1, z - 0.03, z + 0.03, -depth, -depth + 0.07, DARK, skip=('-c',))
    if DETAIL == 'web':
        return
    for m in vmull:
        B.glass.box(fr, m - 0.025, m + 0.025, b0, b1, -depth, -depth + 0.07, DARK, skip=('-c',))
    # perimeter profile
    B.glass.box(fr, a0, a1, b0, b0 + 0.05, -depth, -depth + 0.07, DARK, skip=('-c',))
    B.glass.box(fr, a0, a1, b1 - 0.05, b1, -depth, -depth + 0.07, DARK, skip=('-c',))


def tray(B, fr, a0, a1, z, outer=BWHITE, rail='solid', d=TRAY_D):
    """Cantilevered balcony tray whose top of slab is at z."""
    T = PARA_T
    zb, zt = z - SLAB, z + PARA_H
    M = B.bal
    if rail == 'solid':
        k, kz = 0.32, 0.30                                          # angled lower ends
        M.poly(fr, [(a0 + k, zb, d), (a1 - k, zb, d), (a1, zb + kz, d), (a1, zt, d),
                    (a0, zt, d), (a0, zb + kz, d)], outer)          # front
        M.rect_b(fr, a0 + k, a1 - k, 0.0, d, zb, SOFFIT, -1)        # soffit
        M.quad(fr, [(a0, zb + kz, 0.0), (a0, zb + kz, d), (a0 + k, zb, d), (a0 + k, zb, 0.0)], outer)
        M.quad(fr, [(a1 - k, zb, 0.0), (a1 - k, zb, d), (a1, zb + kz, d), (a1, zb + kz, 0.0)], outer)
        M.rect_a(fr, zb + kz, zt, 0.0, d, a0, outer, -1)            # outer sides
        M.rect_a(fr, zb + kz, zt, 0.0, d, a1, outer, +1)
        M.rect_b(fr, a0, a1, d - T, d, zt, outer, +1)               # rims
        M.rect_b(fr, a0, a0 + T, 0.0, d - T, zt, outer, +1)
        M.rect_b(fr, a1 - T, a1, 0.0, d - T, zt, outer, +1)
        M.rect_c(fr, a0 + T, a1 - T, z, zt, d - T, BWHITE, -1)      # inner faces
        M.rect_a(fr, z, zt, 0.0, d - T, a0 + T, BWHITE, +1)
        M.rect_a(fr, z, zt, 0.0, d - T, a1 - T, BWHITE, -1)
        M.rect_b(fr, a0 + T, a1 - T, 0.0, d - T, z, TILES, +1)      # balcony floor
    else:  # slab + glass balustrade
        M.rect_c(fr, a0, a1, zb, z, d, outer)
        M.rect_b(fr, a0, a1, 0.0, d, zb, SOFFIT, -1)
        M.rect_a(fr, zb, z, 0.0, d, a0, outer, -1)
        M.rect_a(fr, zb, z, 0.0, d, a1, outer, +1)
        M.rect_b(fr, a0, a1, 0.0, d, z, TILES, +1)
        gt = z + 1.0
        B.glass.box(fr, a0 + 0.06, a1 - 0.06, z, gt, d - 0.09, d - 0.07, GRAIL)
        B.glass.box(fr, a0 + 0.04, a0 + 0.06, z, gt, 0.0, d - 0.07, GRAIL, skip=('-c',))
        B.glass.box(fr, a1 - 0.06, a1 - 0.04, z, gt, 0.0, d - 0.07, GRAIL, skip=('-c',))
        B.glass.box(fr, a0 + 0.02, a1 - 0.02, gt, gt + 0.05, d - 0.11, d - 0.05, DARK)


# ---- element builders ----------------------------------------------------------------

def el_bal(B, fr, e, pic_floors):
    a0, a1 = e['a0'], e['a1']
    w = a1 - a0
    ow = (w - 1.2) / 2.0
    holes = []
    for f in range(1, NF + 1):
        z = zf(f)
        h1 = (a0 + 0.45, a0 + 0.45 + ow, z, z + 2.5)
        h2 = (a1 - 0.45 - ow, a1 - 0.45, z, z + 2.5)
        holes += [h1, h2]
    # ground floor storefront
    shop = (a0 + 0.3, a1 - 0.3, 0.0, GF - 0.6)
    B.wall.wall_holes(fr, a0, a1, 0.0, PAR, holes + [shop], WHITE)
    for h in holes:
        window(B, fr, *h, mull=((h[0] + h[1]) / 2 + 0.25,))
    n = max(2, int(round((shop[1] - shop[0]) / 1.6)))
    mulls = [shop[0] + (shop[1] - shop[0]) * i / n for i in range(1, n)]
    window(B, fr, *shop, depth=0.45, mull=mulls, shop=True)
    for f in range(1, NF + 1):
        glassy = f in pic_floors
        outer = BRONZE if f in e['bz'] else BWHITE
        tray(B, fr, a0, a1, zf(f), outer=outer, rail='glass' if glassy else 'solid')
    # roof cap over the top balcony
    B.bal.box(fr, a0, a1, ROOF - 0.1, PAR, 0.0, TRAY_D, BWHITE, skip=('-c',),
              mats={'-b': SOFFIT})


def el_strip(B, fr, e):
    a0, a1 = e['a0'], e['a1']
    g = (a0 + 0.2, a1 - 0.2, 0.0, ROOF - 0.15)
    B.wall.wall_holes(fr, a0, a1, 0.0, PAR, [g], WHITE)
    levels = [GF] + [zf(f) for f in range(2, NF + 1)]
    curtain(B, fr, g[0], g[1], g[2], g[3], STRIP_D, levels)


def el_pier(B, fr, e):
    a0, a1 = e['a0'], e['a1']
    w = a1 - a0
    holes = []
    if w >= 2.2:
        m = 0.5 * (a0 + a1)
        hw = min(0.75, (w - 1.0) / 2)
        for f in range(1, NF + 1):
            holes.append((m - hw, m + hw, zf(f) + 0.9, zf(f) + 2.45))
    shop = None
    if w >= 3.0:
        shop = (a0 + 0.35, a1 - 0.35, 0.0, GF - 0.6)
        holes.append(shop)
    B.wall.wall_holes(fr, a0, a1, 0.0, PAR, holes, WHITE)
    for h in holes:
        if h is shop:
            n = max(1, int(round((h[1] - h[0]) / 1.6)))
            window(B, fr, *h, depth=0.45, mull=[h[0] + (h[1] - h[0]) * i / n for i in range(1, n)], shop=True)
        else:
            window(B, fr, *h)


def el_edge(B, fr, e):
    B.wall.wall_holes(fr, e['a0'], e['a1'], 0.0, PAR, [], WHITE)


def _frame_bars(B, fr, a0, a1, b0, b1, bottom_bar, top_bar, E=FRAME_E, P=FRAME_P):
    """Copper surround; faces against the wall (c=0, below the parapet) are skipped."""
    def bar(x0, x1, y0, y1):
        if y1 <= PAR + 1e-6:
            B.bronze.box(fr, x0, x1, y0, y1, 0.0, P, BRONZE, skip=('-c',))
        elif y0 >= PAR - 1e-6:
            B.bronze.box(fr, x0, x1, y0, y1, 0.0, P, BRONZE)
        else:
            B.bronze.box(fr, x0, x1, y0, PAR, 0.0, P, BRONZE, skip=('-c', '+b'))
            B.bronze.box(fr, x0, x1, PAR, y1, 0.0, P, BRONZE, skip=('-b',))
    bar(a0, a0 + E, b0, b1)
    bar(a1 - E, a1, b0, b1)
    if bottom_bar:
        bar(a0 + E, a1 - E, b0, b0 + E)
    if top_bar:
        bar(a0 + E, a1 - E, b1 - E, b1)


def el_frame(B, fr, e):
    a0, a1 = e['a0'], e['a1']
    E = FRAME_E if e['kind'] != 'narrow' else 0.6
    gi0, gi1 = a0 + E, a1 - E
    mid = 0.5 * (a0 + a1)
    vm = [0.5 * (gi0 + mid - 0.15), 0.5 * (mid + 0.15 + gi1)]
    if e['kind'] == 'narrow':
        # single copper frame floors 2..17, courtyard version
        b0, b1 = zf(2) - 0.6, PAR + E
        g = (gi0, gi1, b0 + E, PAR)
        holes = [g]
        # ground floor entrance + first floor window below the frame
        low = [(a0 + 0.8, a1 - 0.8, zf(1) + 0.9, zf(1) + 2.3)]
        door = (a0 + 0.8, a1 - 0.8, 0.0, 3.0)
        B.wall.wall_holes(fr, a0, a1, 0.0, PAR, holes + low + [door], WHITE)
        for h in low:
            window(B, fr, *h)
        window(B, fr, *door, depth=0.45, mull=((door[0] + door[1]) / 2,), shop=True)
        levels = [zf(f) for f in range(3, NF + 1)]
        curtain(B, fr, *g, WIN_D, levels, vmull=[mid])
        _frame_bars(B, fr, a0, a1, b0, b1, True, True, E=E, P=1.2)
        return
    lo = (gi0, gi1, 0.0, LOW_TOP - FRAME_E)
    hi = (gi0, gi1, UP_BOT + FRAME_E, FRAME_TOP - FRAME_E)
    band = []
    for (x0, x1) in ((a0 + 1.0, mid - 0.6), (mid + 0.6, a1 - 1.0)):
        band.append((x0, x1, zf(8) + 0.9, zf(8) + 2.45))
    B.wall.wall_holes(fr, a0, a1, 0.0, PAR, [lo, (hi[0], hi[1], hi[2], PAR)] + band, WHITE)
    for h in band:
        window(B, fr, *h, mull=((h[0] + h[1]) / 2,))
    lv_lo = [GF] + [zf(f) for f in range(2, 8)]
    lv_hi = [zf(f) for f in range(10, NF + 1)] + [ROOF]
    # glass split around the central copper mullion
    for (x0, x1) in ((gi0, mid - 0.15), (mid + 0.15, gi1)):
        curtain(B, fr, x0, x1, lo[2], lo[3], 0.25, lv_lo, vmull=[0.5 * (x0 + x1)], reveal_mat=None)
        curtain(B, fr, x0, x1, hi[2], PAR, 0.25, lv_hi, vmull=[0.5 * (x0 + x1)], reveal_mat=None)
        # glass screen above the roof (free standing, two-sided)
        curtain(B, fr, x0, x1, PAR, hi[3], 0.25, [], vmull=[0.5 * (x0 + x1)], reveal_mat=None,
                back=True, spandrel=False)
    B.wall.reveal(fr, *lo, 0.0, -0.25, WHITE, sides='lrt')
    B.wall.reveal(fr, hi[0], hi[1], hi[2], PAR, 0.0, -0.25, WHITE, sides='lrb')
    for (b0, b1) in ((lo[2], lo[3]), (hi[2], hi[3])):
        B.bronze.box(fr, mid - 0.15, mid + 0.15, b0, b1, -0.25, 0.45, BRONZE,
                     skip=('-c',) if b1 <= PAR else ())
    _frame_bars(B, fr, a0, a1, 0.0, LOW_TOP, False, True)
    _frame_bars(B, fr, a0, a1, UP_BOT, FRAME_TOP, True, True)


def el_picture(B, fr, a_s, a_e, fa, fb):
    """Copper 'picture frame' around a group of balconies, floors fa..fb."""
    E = FRAME_E
    bot0 = zf(fa) - SLAB - E
    top1 = zf(fb) + 1.9 + E

    def bar(x0, x1, y0, y1):
        B.bronze.box(fr, x0, x1, y0, y1, 0.0, PIC_P, BRONZE, skip=('-c',))
    bar(a_s, a_s + E, bot0, top1)
    bar(a_e - E, a_e, bot0, top1)
    bar(a_s + E, a_e - E, bot0, bot0 + E)
    bar(a_s + E, a_e - E, top1 - E, top1)


def bronze_links(B, fr, els):
    """Continuous bronze bars across a strip between two bronze balconies."""
    for i in range(1, len(els) - 1):
        e = els[i]
        if e['t'] != 'S':
            continue
        l, r = els[i - 1], els[i + 1]
        if l['t'] == 'BAL' and r['t'] == 'BAL':
            for f in sorted(l['bz'] & r['bz']):
                z = zf(f)
                B.bal.box(fr, e['a0'], e['a1'], z - SLAB, z + PARA_H, 0.0, TRAY_D, BRONZE,
                          skip=('-c', '-a', '+a'), mats={'-b': SOFFIT})


def build_run(B, p0, p1, score, groups, start_convex, end_convex):
    """Build one facade run from p0 to p1 (outward normal on the right)."""
    p0 = np.asarray(p0, float)
    p1 = np.asarray(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    fr = Frame(p0, p1 - p0)
    els = fit_score(parse_score(score), L)
    for e in els:
        pf = set()
        if e['g'] is not None:
            fa, fb = groups[e['g']]
            pf = set(range(fa, fb + 1))
        t = e['t']
        if t == 'BAL':
            el_bal(B, fr, e, pf)
        elif t == 'S':
            el_strip(B, fr, e)
        elif t == 'F':
            el_frame(B, fr, e)
        elif t == 'E':
            el_edge(B, fr, e)
        else:
            el_pier(B, fr, e)
    for g, (fa, fb) in groups.items():
        mem = [e for e in els if e['g'] == g]
        if mem:
            el_picture(B, fr, mem[0]['a0'], mem[-1]['a1'], fa, fb)
    bronze_links(B, fr, els)
    # parapet back face + coping (lengths adjusted so corners neither gap nor overlap)
    s = 0.3
    x0 = s if start_convex else -s
    x1 = L - s if end_convex else L + s
    B.roof.rect_c(fr, x0, x1, ROOF_TOP, PAR, -s, WHITE, facing=-1)
    k0 = 0.36 if start_convex else 0.04
    k1 = L + 0.04 if end_convex else L + 0.36
    B.roof.box(fr, k0, k1, PAR, PAR + 0.06, -0.36, 0.04, COPING, skip=('-b',))
    return els, fr, L
