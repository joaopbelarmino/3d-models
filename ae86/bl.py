"""Blender helpers: turn MeshBuilder data into objects, materials, shading."""
import math
import bpy
import bmesh
import numpy as np
from mathutils import Vector

from geom import to_blender

MATERIALS = {
    # name: (base colour, metallic, roughness, extra)
    'paint_white': ((0.82, 0.82, 0.80, 1), 0.0, 0.35),
    'paint_black': ((0.025, 0.025, 0.028, 1), 0.0, 0.4),
    'plastic_black': ((0.03, 0.03, 0.03, 1), 0.0, 0.7),
    'rubber': ((0.012, 0.012, 0.012, 1), 0.0, 0.9),
    'glass': ((0.01, 0.012, 0.015, 1), 0.0, 0.05),
    'tire': ((0.02, 0.02, 0.02, 1), 0.0, 0.85),
    'metal': ((0.55, 0.55, 0.56, 1), 1.0, 0.3),
    'rim': ((0.06, 0.06, 0.06, 1), 0.6, 0.4),
    'lens_clear': ((0.32, 0.34, 0.36, 1), 0.0, 0.05),
    'lens_amber': ((0.85, 0.35, 0.02, 1), 0.0, 0.1),
    'lens_red': ((0.55, 0.02, 0.02, 1), 0.0, 0.1),
    'chrome': ((0.8, 0.8, 0.8, 1), 1.0, 0.12),
    'interior_black': ((0.01, 0.01, 0.01, 1), 0.0, 0.9),
}


def get_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m
    col, met, rough = MATERIALS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = col
    bsdf.inputs['Metallic'].default_value = met
    bsdf.inputs['Roughness'].default_value = rough
    if name == 'glass':
        bsdf.inputs['Specular IOR Level'].default_value = 0.8
    m.diffuse_color = col
    return m


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def get_collection(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def make_object(name, mb, mats, collection='AE86', convert=True, auto_sharp_deg=50.0,
                origin=None, outward=None):
    """Create a mesh object from a MeshBuilder.

    mats: list of material names indexed by the builder's material ids.
    outward: optional callable(center_mm, normal) -> bool telling whether a
             face normal points the right way; faces failing it get flipped.
    origin: object origin in Blender metres (geometry stays in place)."""
    verts = np.array(mb.verts)
    if convert:
        verts = to_blender(verts)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in mb.faces])
    me.update(calc_edges=True)
    for mname in mats:
        me.materials.append(get_mat(mname))
    for poly, mi in zip(me.polygons, mb.fmat):
        poly.material_index = mi
    obj = bpy.data.objects.new(name, me)
    get_collection(collection).objects.link(obj)

    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    if outward is not None:
        for f in bm.faces:
            c = f.calc_center_median()
            if not outward(np.array(c), np.array(f.normal)):
                f.normal_flip()
    # sharp edges from builder tags
    sharp_pairs = mb.sharp
    for e in bm.edges:
        a, b = e.verts[0].index, e.verts[1].index
        if (min(a, b), max(a, b)) in sharp_pairs:
            e.smooth = False
        if auto_sharp_deg is not None and e.is_manifold:
            if e.calc_face_angle(0) > math.radians(auto_sharp_deg):
                e.smooth = False
        if not e.is_manifold:
            pass
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    me.update()
    if origin is not None:
        set_origin(obj, origin)
    return obj


def set_origin(obj, origin_m):
    o = Vector(origin_m)
    me = obj.data
    for v in me.vertices:
        v.co = v.co + obj.location - o
    obj.location = o
    me.update()


def triangle_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def apply_flip_to_outside(obj, center_fn):
    """Flip faces so normals point away from center_fn(face_center)."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    for f in bm.faces:
        c = f.calc_center_median()
        ref = Vector(center_fn(c))
        if f.normal.dot(c - ref) < 0:
            f.normal_flip()
    bm.to_mesh(me)
    bm.free()


def orient_components(obj, ref_fn=None, toward=False, faces_filter=None):
    """Make normals consistent per connected component, then flip a whole
    component when its area-weighted normals point the wrong way.

    ref_fn(face_center) -> reference point (Blender m).  None = component
    centroid.  toward=True means normals should point at the reference."""
    import bmesh
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    faces = [f for f in bm.faces if faces_filter is None or faces_filter(f.index)]
    fset = set(f.index for f in faces)
    seen = set()
    for f0 in faces:
        if f0.index in seen:
            continue
        comp, stack = [], [f0]
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            comp.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen and g.index in fset:
                        seen.add(g.index)
                        stack.append(g)
        bmesh.ops.recalc_face_normals(bm, faces=comp)
        cen = Vector((0, 0, 0))
        atot = 0.0
        for f in comp:
            a = f.calc_area()
            cen += f.calc_center_median() * a
            atot += a
        cen /= max(atot, 1e-12)
        vote = 0.0
        for f in comp:
            c = f.calc_center_median()
            r = Vector(ref_fn(np.array(c))) if ref_fn else cen
            vote += f.calc_area() * f.normal.dot(c - r)
        if (vote < 0) != toward:
            for f in comp:
                f.normal_flip()
    bm.to_mesh(me)
    bm.free()
    me.update()
