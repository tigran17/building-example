"""New Komitas exterior - geometry helpers (Blender 4.5, bpy + numpy).

Everything is built as plain quads in local "facade frames" and flushed into a few
large meshes per block/category. Units: metres, Z up.
"""
import math
import numpy as np
import bpy

UP = np.array([0.0, 0.0, 1.0])


class Frame:
    """Right-handed local frame of a facade run.

    a = along the wall (left -> right when seen from outside), b = up, c = outward.
    world = p0 + a*t + b*up + c*n, with n the right-hand side of t (outward for a CCW
    outer boundary, or for a CW courtyard boundary).
    """

    def __init__(self, p0, t, z0=0.0):
        t = np.array([t[0], t[1], 0.0], float)
        t /= np.linalg.norm(t)
        self.t = t
        self.n = np.array([t[1], -t[0], 0.0])
        self.p0 = np.array([p0[0], p0[1], z0], float)
        self.M = np.stack([self.t, UP, self.n])  # rows: a, b, c axes

    def w(self, pts):
        pts = np.asarray(pts, float).reshape(-1, 3)
        return self.p0 + pts @ self.M


class WorldFrame:
    """Identity mapping for geometry authored directly in world coordinates."""

    def w(self, pts):
        return np.asarray(pts, float).reshape(-1, 3)


WORLD = WorldFrame()

# Box corner order: 0..3 at c0 (b0,b0,b1,b1 / a0,a1,a1,a0), 4..7 at c1.
BOX_FACES = {
    '+c': (4, 5, 6, 7), '-c': (0, 3, 2, 1),
    '-a': (0, 4, 7, 3), '+a': (1, 2, 6, 5),
    '-b': (0, 1, 5, 4), '+b': (3, 7, 6, 2),
}


class MeshBuilder:
    """Accumulates polygons (with a material name and optional colour per face)."""

    def __init__(self):
        self.chunks = []
        self.faces = []
        self.fmat = []
        self.fcol = []
        self.nv = 0

    def __len__(self):
        return len(self.faces)

    def face_up(self):
        """Make every polygon face +Z (ground layers: ribbons can fold at sharp turns)."""
        V = np.concatenate(self.chunks, axis=0)
        for k, f in enumerate(self.faces):
            p = V[f]
            nz = 0.0
            for i in range(len(p)):
                a, b = p[i], p[(i + 1) % len(p)]
                nz += (a[0] - b[0]) * (a[1] + b[1])
            if nz < 0:
                self.faces[k] = f[::-1]

    def add(self, verts, faces, mat, col=None):
        verts = np.asarray(verts, float).reshape(-1, 3)
        base = self.nv
        self.chunks.append(verts)
        for f in faces:
            self.faces.append([base + i for i in f])
            self.fmat.append(mat)
            self.fcol.append(col)
        self.nv += len(verts)

    # ---- primitives (local coordinates of a Frame) -------------------------------
    def quad(self, fr, pts, mat, col=None):
        """4 local points in CCW order seen from the side the face should face."""
        self.add(fr.w(pts), [(0, 1, 2, 3)], mat, col)

    def poly(self, fr, pts, mat, col=None):
        self.add(fr.w(pts), [tuple(range(len(pts)))], mat, col)

    def box(self, fr, a0, a1, b0, b1, c0, c1, mat, skip=(), mats=None, col=None):
        if a1 - a0 <= 1e-6 or b1 - b0 <= 1e-6 or c1 - c0 <= 1e-6:
            return
        P = [(a0, b0, c0), (a1, b0, c0), (a1, b1, c0), (a0, b1, c0),
             (a0, b0, c1), (a1, b0, c1), (a1, b1, c1), (a0, b1, c1)]
        V = fr.w(P)
        for key, idx in BOX_FACES.items():
            if key in skip:
                continue
            m = mat if mats is None else mats.get(key, mat)
            if m is None:
                continue
            self.add(V[list(idx)], [(0, 1, 2, 3)], m, col)

    def rect_c(self, fr, a0, a1, b0, b1, c, mat, facing=+1, col=None):
        """Rectangle in the plane c=const facing +c (facing=+1) or -c."""
        if a1 - a0 <= 1e-6 or b1 - b0 <= 1e-6:
            return
        if facing > 0:
            pts = [(a0, b0, c), (a1, b0, c), (a1, b1, c), (a0, b1, c)]
        else:
            pts = [(a0, b0, c), (a0, b1, c), (a1, b1, c), (a1, b0, c)]
        self.quad(fr, pts, mat, col)

    def rect_b(self, fr, a0, a1, c0, c1, b, mat, facing=+1, col=None):
        """Rectangle in the plane b=const facing up (+1) or down (-1)."""
        if a1 - a0 <= 1e-6 or c1 - c0 <= 1e-6:
            return
        if facing > 0:
            pts = [(a0, b, c0), (a0, b, c1), (a1, b, c1), (a1, b, c0)]
        else:
            pts = [(a0, b, c0), (a1, b, c0), (a1, b, c1), (a0, b, c1)]
        self.quad(fr, pts, mat, col)

    def rect_a(self, fr, b0, b1, c0, c1, a, mat, facing=+1, col=None):
        """Rectangle in the plane a=const facing +a (+1) or -a (-1)."""
        if b1 - b0 <= 1e-6 or c1 - c0 <= 1e-6:
            return
        if facing > 0:
            pts = [(a, b0, c0), (a, b1, c0), (a, b1, c1), (a, b0, c1)]
        else:
            pts = [(a, b0, c0), (a, b0, c1), (a, b1, c1), (a, b1, c0)]
        self.quad(fr, pts, mat, col)

    def wall_holes(self, fr, a0, a1, b0, b1, holes, mat, c=0.0, facing=+1, col=None):
        """Plane rectangle minus rectangular holes, as a watertight grid of quads."""
        hs = [h for h in holes if h[1] > a0 and h[0] < a1 and h[3] > b0 and h[2] < b1]
        xs = sorted({a0, a1, *[min(max(h[0], a0), a1) for h in hs], *[min(max(h[1], a0), a1) for h in hs]})
        ys = sorted({b0, b1, *[min(max(h[2], b0), b1) for h in hs], *[min(max(h[3], b0), b1) for h in hs]})
        for i in range(len(xs) - 1):
            x0, x1 = xs[i], xs[i + 1]
            if x1 - x0 < 1e-6:
                continue
            cx = 0.5 * (x0 + x1)
            col_holes = [h for h in hs if h[0] < cx < h[1]]
            for j in range(len(ys) - 1):
                y0, y1 = ys[j], ys[j + 1]
                if y1 - y0 < 1e-6:
                    continue
                cy = 0.5 * (y0 + y1)
                if any(h[2] < cy < h[3] for h in col_holes):
                    continue
                self.rect_c(fr, x0, x1, y0, y1, c, mat, facing, col)

    def reveal(self, fr, a0, a1, b0, b1, c_front, c_back, mat, sides='lrtb'):
        """Inner faces of a rectangular opening between two c planes (facing inwards)."""
        if 'l' in sides:
            self.rect_a(fr, b0, b1, c_back, c_front, a0, mat, +1)
        if 'r' in sides:
            self.rect_a(fr, b0, b1, c_back, c_front, a1, mat, -1)
        if 'b' in sides:
            self.rect_b(fr, a0, a1, c_back, c_front, b0, mat, +1)
        if 't' in sides:
            self.rect_b(fr, a0, a1, c_back, c_front, b1, mat, -1)

    # ---- output ------------------------------------------------------------------
    def to_object(self, name, collection, materials, merge=True, uv_scale=1.0):
        """Create a Blender mesh object. materials: dict name -> bpy material."""
        if not self.faces:
            return None
        V = np.concatenate(self.chunks, axis=0)
        faces = self.faces
        mat_names = []
        mat_index = {}
        for m in self.fmat:
            if m not in mat_index:
                mat_index[m] = len(mat_names)
                mat_names.append(m)
        me = bpy.data.meshes.new(name)
        me.from_pydata(V.tolist(), [], faces)
        for m in mat_names:
            me.materials.append(materials[m])
        me.polygons.foreach_set('material_index', [mat_index[m] for m in self.fmat])

        # Box-mapped UVs in metres (UV0) - consistent texel density for tiling textures.
        uvl = me.uv_layers.new(name='UVMap')
        nloops = len(me.loops)
        loop_v = np.zeros(nloops, dtype=np.int32)
        me.loops.foreach_get('vertex_index', loop_v)
        lstart = np.zeros(len(faces), dtype=np.int32)
        ltotal = np.zeros(len(faces), dtype=np.int32)
        me.polygons.foreach_get('loop_start', lstart)
        me.polygons.foreach_get('loop_total', ltotal)
        normals = np.zeros(len(faces) * 3)
        me.polygons.foreach_get('normal', normals)
        normals = normals.reshape(-1, 3)
        face_of_loop = np.repeat(np.arange(len(faces)), ltotal)
        P = V[loop_v]
        N = normals[face_of_loop]
        ax = np.abs(N)
        dom = np.argmax(ax, axis=1)
        uv = np.zeros((nloops, 2))
        # z dominant -> (x, y); x dominant -> (+-y, z); y dominant -> (-+x, z)
        m = dom == 2
        uv[m, 0] = P[m, 0]
        uv[m, 1] = P[m, 1] * np.sign(N[m, 2] + 1e-9)
        m = dom == 0
        uv[m, 0] = P[m, 1] * np.sign(N[m, 0] + 1e-9)
        uv[m, 1] = P[m, 2]
        m = dom == 1
        uv[m, 0] = -P[m, 0] * np.sign(N[m, 1] + 1e-9)
        uv[m, 1] = P[m, 2]
        uvl.data.foreach_set('uv', (uv * uv_scale).ravel())

        # Per-face colour (used for per-window variation of glass/curtains).
        if any(c is not None for c in self.fcol):
            ca = me.color_attributes.new(name='Col', type='BYTE_COLOR', domain='CORNER')
            cols = np.array([c if c is not None else (1.0, 1.0, 1.0, 1.0) for c in self.fcol], float)
            ca.data.foreach_set('color', cols[face_of_loop].ravel())

        me.validate(clean_customdata=False)
        me.update()
        ob = bpy.data.objects.new(name, me)
        collection.objects.link(ob)
        if merge:
            weld(ob)
        return ob


def weld(ob, dist=1e-4):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def fit_score(score, length):
    """score: list of dicts {t: type, w: nominal width, flex: weight, ...}.
    Flexible elements share (length - sum of nominals) by weight. Returns elements
    with absolute a0/a1 positions."""
    nominal = sum(e['w'] for e in score)
    rem = length - nominal
    fw = sum(e.get('flex', 0) for e in score)
    if fw <= 0 and abs(rem) > 1e-3:
        raise ValueError(f'score does not fit: nominal {nominal:.2f} vs {length:.2f}')
    if rem < -1e-3:
        raise ValueError(f'score too long: nominal {nominal:.2f} > {length:.2f}')
    out = []
    a = 0.0
    for e in score:
        e = dict(e)
        w = e['w'] + (rem * e.get('flex', 0) / fw if fw > 0 else 0.0)
        e['a0'], e['a1'], e['w'] = a, a + w, w
        a += w
        out.append(e)
    return out
