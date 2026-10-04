"""Finalise the AE86 for Roblox.

    python ae86/export.py built.blend out_dir

- provisional Smart-UV unwrap on every mesh (final texturing comes later)
- FBX export, triangulated on the fly (custom normals kept), nose = -Z
- pivots.json with hinge data, part list and triangle counts
- PopupHeadlights.server.lua with the hinge offsets filled in
"""
import os
import sys
import json
import math

import bpy
from mathutils import Vector

ORDER = ['Body', 'Glass', 'Bumper_Front', 'Bumper_Rear', 'Skirt_L', 'Skirt_R',
         'Popup_L', 'Popup_R', 'Lights_Front', 'Lights_Rear',
         'Wheel_FL', 'Wheel_FR', 'Wheel_RL', 'Wheel_RR']


def car_frame(v):
    """Blender vector -> car frame [left, up, back] (nose = Blender -Y)."""
    return [v[0], v[2], v[1]]


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def smart_uv(o):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    o.select_set(False)


def bbox_world(o):
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def main(blend_in, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=blend_in)
    meshes = [bpy.data.objects[n] for n in ORDER if n in bpy.data.objects]
    for o in meshes:
        if not o.data.uv_layers:
            smart_uv(o)

    info = {'units': 'metres (1 Blender unit = 1 m)',
            'blender_axes': 'nose -Y, up +Z, car left +X',
            'offsets_frame': '[left, up, back] in metres, relative to the bounding-box centre',
            'parts': {}, 'total_tris': 0}
    for o in meshes:
        mn, mx = bbox_world(o)
        c = (mn + mx) / 2
        size = mx - mn
        entry = {
            'tris': tris(o),
            'origin_blender_m': [round(x, 5) for x in o.location],
            'bbox_center_blender_m': [round(x, 5) for x in c],
            'size_m': [round(abs(x), 5) for x in car_frame(size)],
            'origin_minus_bbox_center_m': [round(x, 5) for x in car_frame(o.location - c)],
        }
        if o.name.startswith('Popup'):
            entry['open_angle_deg'] = float(o.get('open_angle_deg', 52.0))
            entry['hinge_axis'] = 'part X axis; positive rotation opens (front rises)'
        info['parts'][o.name] = entry
        info['total_tris'] += entry['tris']
    with open(os.path.join(out_dir, 'pivots.json'), 'w') as f:
        json.dump(info, f, indent=2)

    # Luau helper with the measured hinge offsets
    pl = info['parts']['Popup_L']
    off = pl['origin_minus_bbox_center_m']
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'roblox',
                            'PopupHeadlights.template.lua')).read()
    lua = (tpl.replace('{{ANGLE}}', '%.1f' % pl['open_angle_deg'])
              .replace('{{BODY_LEN}}', '%.4f' % max(info['parts']['Body']['size_m']))
              .replace('{{HINGE_UP}}', '%.4f' % off[1])
              .replace('{{HINGE_BACK}}', '%.4f' % off[2]))
    with open(os.path.join(out_dir, 'PopupHeadlights.server.lua'), 'w') as f:
        f.write(lua)

    # FBX: triangulate through a temporary modifier so Roblox gets exactly
    # the triangulation (and split normals) we checked in Blender
    for o in meshes:
        m = o.modifiers.new('tri_export', 'TRIANGULATE')
        m.quad_method = 'BEAUTY'
        m.keep_custom_normals = True
    bpy.ops.object.select_all(action='DESELECT')
    fbx = os.path.join(out_dir, 'ae86_trueno.fbx')
    bpy.ops.export_scene.fbx(
        filepath=fbx, use_selection=False, object_types={'MESH'},
        use_mesh_modifiers=True, mesh_smooth_type='FACE', use_custom_props=True,
        add_leaf_bones=False, axis_forward='-Z', axis_up='Y',
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', global_scale=1.0,
        bake_space_transform=False,
        path_mode='AUTO', embed_textures=False)
    for o in meshes:
        o.modifiers.remove(o.modifiers['tri_export'])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'ae86_trueno.blend'))
    print('exported', fbx, 'tris', info['total_tris'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
