"""Vehicle LODs for the web traffic.

The site's car models (vehicles.glb, ~88k triangles per car with its four wheels) are far too
dense for 200+ instanced cars. This decimates every part into two levels:

  LOD0  near cars (< ~75 m from the camera)   decimated originals, ~6k triangles per car incl. wheels
  LOD1  everything farther                    clean low-poly proxies with the same paint/glass/rubber
                                              materials and proportions, ~140 triangles per car incl. wheels

and writes Website/assets/vehicles-lod.glb (nodes <model>__<part>__lod<N>, extras vehicleModel /
vehiclePart / vehicleLod). Materials are kept, so traffic.js styles both levels identically.

blender -b --factory-startup -P Scripts/nk_vehicles.py
"""
import os

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
SRC = os.path.join(PROJECT, 'Website-original', 'assets', 'vehicles.glb')
OUT = os.path.join(PROJECT, 'Website', 'assets', 'vehicles-lod.glb')

# LOD0 target triangles per part (the originals are split into hundreds of loose pieces, so
# collapse stalls above these for trim/alloy; that is fine for the few near cars).
TARGET = {'paint': 1800, 'trim': 520, 'chrome': 300, 'glass': 408, 'lamps': 140, 'plate': 60, 'tail': 140,
          'alloy': 96, 'rubber': 112, 'wheel_trim': 48}
# LOD1 proxy proportions measured from the originals (Blender axes: +Y = front, Z up).
PROXY = {'sedan': dict(roof=1.43, cab_lo=(-1.35, 1.02), cab_hi=(-0.95, 0.55), hood=0.92),
         'suv': dict(roof=1.70, cab_lo=(-1.62, 1.02), cab_hi=(-1.52, 0.58), hood=0.95)}


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def decimate(ob, target):
    n = tris(ob)
    if target >= n:
        return
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    mod = ob.modifiers.new('LOD', 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = target / n
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.shade_smooth_by_angle(angle=0.61)


def box(bm, x0, x1, y0, y1, z0, z1, bottom=False):
    v = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                     (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    quads = [(4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    if bottom:
        quads.append((0, 3, 2, 1))
    for q in quads:
        bm.faces.new([v[i] for i in q])


def prism(bm, profile, half_width):
    """Body side profile [(y, z), ...] (closed, counter-clockwise seen from +X) extruded across the car."""
    left = [bm.verts.new((-half_width, y, z)) for y, z in profile]
    right = [bm.verts.new((half_width, y, z)) for y, z in profile]
    n = len(profile)
    for k in range(n):
        a, b = k, (k + 1) % n
        bm.faces.new((left[a], left[b], right[b], right[a]))
    bm.faces.new(right)
    bm.faces.new(left[::-1])


def frustum(bm_side, bm_top, lo, hi, z0, z1, w0, w1):
    """Cabin: glass sides between the waistline z0 and the roof z1, paint roof on top."""
    for bm, quads in ((bm_side, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]), (bm_top, [(4, 5, 6, 7)])):
        v = [bm.verts.new(p) for p in ((-w0, lo[0], z0), (w0, lo[0], z0), (w0, lo[1], z0), (-w0, lo[1], z0),
                                         (-w1, hi[0], z1), (w1, hi[0], z1), (w1, hi[1], z1), (-w1, hi[1], z1))]
        for q in quads:
            bm.faces.new([v[i] for i in q])


def wheel(bm, radius, half_width, sides=8):
    import math
    ring = []
    for x in (-half_width, half_width):
        ring.append([bm.verts.new((x, radius * math.cos(2 * math.pi * (k + .5) / sides),
                                   radius * math.sin(2 * math.pi * (k + .5) / sides))) for k in range(sides)])
    for k in range(sides):
        a, b = k, (k + 1) % sides
        bm.faces.new((ring[0][a], ring[0][b], ring[1][b], ring[1][a]))
    bm.faces.new(ring[1])
    bm.faces.new(ring[0][::-1])


def proxy_object(name, fill, material, model, part):
    bm = bmesh.new()
    fill(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob['vehicleModel'], ob['vehiclePart'], ob['vehicleLod'] = model, part, 1
    return sum(len(p.vertices) - 2 for p in me.polygons)


def build_proxies():
    M = bpy.data.materials
    n = {}
    for model, p in PROXY.items():
        roof, hood = p['roof'], p['hood']
        # rear bumper -> trunk -> roofline handled by the cabin -> hood -> nose
        body = [(-2.33, .42), (2.33, .42), (2.33, .74), (1.85, hood), (-1.95, hood), (-2.33, .82)]
        n[model] = proxy_object(f'{model}__paint__lod1', lambda bm: (prism(bm, body, .9),
                                                                      frustum(bmesh.new(), bm, p['cab_lo'], p['cab_hi'], hood, roof, .86, .72)),
                                M['paint'], model, 'paint')
        n[model] += proxy_object(f'{model}__glass__lod1', lambda bm: frustum(bm, bmesh.new(), p['cab_lo'], p['cab_hi'], hood, roof - .02, .865, .725),
                                 M['glass'], model, 'glass')
    n['wheel'] = proxy_object('wheel__rubber__lod1', lambda bm: wheel(bm, .345, .11), M['rubber'], 'wheel', 'rubber')
    for k, v in n.items():
        print(f'LOD {k:6s} lod1: {v:6d} tris (proxy)')


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    sources = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    report = {}
    for src in sources:
        model, part = src.name.split('__')[:2]
        key = 'wheel_trim' if (model == 'wheel' and part == 'trim') else part
        ob = src.copy()
        ob.data = src.data.copy()
        ob.name = f'{model}__{part}__lod0'
        bpy.context.scene.collection.objects.link(ob)
        while ob.data.uv_layers:
            ob.data.uv_layers.remove(ob.data.uv_layers[0])
        decimate(ob, TARGET[key])
        ob['vehicleModel'], ob['vehiclePart'], ob['vehicleLod'] = model, part, 0
        report[model] = report.get(model, 0) + tris(ob)
        bpy.data.objects.remove(src)
    for model, n in sorted(report.items()):
        print(f'LOD {model:6s} lod0: {n:6d} tris')
    build_proxies()
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=False, export_extras=True,
                              export_yup=True, export_apply=True, export_texcoords=False, export_normals=True,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                              export_draco_position_quantization=14, export_draco_normal_quantization=10)
    print('WROTE', OUT, os.path.getsize(OUT))


if __name__ == '__main__':
    main()
