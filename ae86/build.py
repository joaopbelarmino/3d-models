"""Build the AE86 Trueno game model from scratch and save it as a .blend.

Run with Blender's Python (bpy 5.0):
    python ae86/build.py [out.blend]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy
import bmesh
import numpy as np
from mathutils import Vector

import geom
import bl
import body
import parts


def recalc_normals(obj):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.update()


def orient_by_probe(obj, probe_point, probe_dir):
    me = obj.data
    best, bd = None, 1e9
    for p in me.polygons:
        d = (p.center - probe_point).length
        if d < bd:
            best, bd = p, d
    if best is not None and best.normal.dot(probe_dir) < 0:
        bm = bmesh.new()
        bm.from_mesh(me)
        for f in bm.faces:
            f.normal_flip()
        bm.to_mesh(me)
        bm.free()
        me.update()


def main(out_path):
    bl.clear_scene()
    mb, info = body.build()
    # body extras that belong to the body mesh (black / inner material)
    geom.merge(mb, parts.popup_buckets(), {0: body.M_INNER}, tag='bucket')
    geom.merge(mb, parts.wheel_wells(info), {0: body.M_INNER}, tag='well')
    geom.merge(mb, parts.floor_mb(), {0: body.M_INNER}, tag='floor')
    geom.merge(mb, parts.mirrors_mb(), {0: body.M_BLACK, 1: body.M_RUBBER}, tag='mirror')
    geom.merge(mb, parts.body_details(), {0: body.M_BLACK, 1: body.M_BLACK}, tag='detail')
    full = geom.mirror_builder(mb, axis=1)
    geom.merge(full, parts.wipers_mb(), {0: body.M_BLACK}, tag='wiper')
    obj = bl.make_object('Body', full, body.BODY_MATS)
    # shell normals: propagate, then make sure the roof faces up
    recalc_normals(obj)
    orient_by_probe(obj, Vector((0, 0.5, 1.4)), Vector((0, 0, 1)))
    tags = full.ftag
    sgn = lambda v: 1.0 if v >= 0 else -1.0
    S0 = geom.S_ORIGIN
    # small separate components inside the body mesh: orient per component
    bl.orient_components(obj, lambda c: np.array([sgn(c[0]) * 0.505, (235 - S0) / 1000, 0.62]),
                         toward=True, faces_filter=lambda i: tags[i] == 'bucket')
    bl.orient_components(obj, lambda c: np.array([sgn(c[0]) * 0.62, (873 - S0) / 1000 if c[1] < 0
                                                  else (3255 - S0) / 1000, 0.35]),
                         toward=True, faces_filter=lambda i: tags[i] == 'well')
    bl.orient_components(obj, lambda c: np.array([sgn(c[0]) * 0.80, (1662 - S0) / 1000, 0.93]),
                         faces_filter=lambda i: tags[i] == 'mirror')
    bl.orient_components(obj, lambda c: np.array([0.0, c[1] + 0.3, 0.62]),
                         faces_filter=lambda i: tags[i] == 'detail')
    bl.orient_components(obj, None, faces_filter=lambda i: tags[i] == 'wiper')
    bl.orient_components(obj, lambda c: c + np.array([0, 0, 1.0]),
                         faces_filter=lambda i: tags[i] == 'floor')
    print('body tris', bl.triangle_count(obj))

    parts.glass(info)
    parts.wheels()
    parts.front_bumper(info)
    parts.rear_bumper(info)
    parts.side_skirts(info)
    parts.popups(info)
    parts.lamps(info)

    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    total = 0
    for o in bpy.data.objects:
        if o.type == 'MESH':
            t = bl.triangle_count(o)
            total += t
            print(f'  {o.name:28s} {t:6d}')
    print('TOTAL TRIS', total)


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'ae86_trueno.blend')
    main(out)
