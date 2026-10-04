"""Validation renders (Cycles CPU, headless).

python ae86/render.py model.blend outdir [views...] [--clay] [--wire] [--overlay]
Views: side front rear top fq rq fq_r rq_r low
"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy
from mathutils import Vector, Euler

VIEWS = {
    # name: (ortho, location, look_at, ortho_scale/lens, up, resolution)
    'side': (True, (10, 0.04, 0.62), (0, 0.04, 0.62), 4.5, (0, 0, 1), (1800, 600)),
    'front': (True, (0, -10, 0.66), (0, 0, 0.66), 2.0, (0, 0, 1), (1000, 750)),
    'rear': (True, (0, 10, 0.66), (0, 0, 0.66), 2.0, (0, 0, 1), (1000, 750)),
    'top': (True, (0, 0.04, 10), (0, 0.04, 0), 4.5, (-1, 0, 0), (1800, 800)),
    'fq': (False, (4.6, -5.4, 1.75), (0, -0.25, 0.55), 50, None, (1400, 900)),
    'rq': (False, (4.6, 5.2, 1.9), (0, 0.3, 0.55), 50, None, (1400, 900)),
    'fq_r': (False, (-4.4, -5.5, 1.3), (0, -0.2, 0.55), 50, None, (1400, 900)),
    'rq_r': (False, (-4.6, 5.0, 1.5), (0, 0.3, 0.6), 50, None, (1400, 900)),
    'low': (False, (3.2, -4.2, 0.45), (0, -0.4, 0.6), 40, None, (1400, 900)),
    'fhi': (False, (2.2, -5.2, 3.4), (0, -0.4, 0.5), 50, None, (1400, 900)),
}


def look_at(obj, target, up=None):
    d = Vector(target) - obj.location
    if up is None:
        obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    else:
        # build rotation with explicit up
        f = d.normalized()
        u = Vector(up)
        r = f.cross(u).normalized()
        u2 = r.cross(f)
        from mathutils import Matrix
        m = Matrix((r, u2, -f)).transposed()
        obj.rotation_euler = m.to_euler()


def setup(clay=False, wire=False, samples=24):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    world = bpy.data.worlds.new('W') if not sc.world else sc.world
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get('Background')
    # simple studio gradient: sky + ground via a light path trick
    bg.inputs['Color'].default_value = (0.75, 0.78, 0.82, 1)
    bg.inputs['Strength'].default_value = 0.9
    # key + rim lights
    for nm, loc, energy, size in (('Key', (4, -3, 6), 900, 4), ('Fill', (-5, -2, 3), 350, 6),
                                  ('Rim', (0, 6, 4), 500, 5)):
        if bpy.data.objects.get(nm):
            continue
        ld = bpy.data.lights.new(nm, 'AREA')
        ld.energy = energy
        ld.size = size
        lo = bpy.data.objects.new(nm, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        look_at(lo, (0, 0, 0.5))
    # ground
    if not bpy.data.objects.get('Ground'):
        bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
        g = bpy.context.active_object
        g.name = 'Ground'
        m = bpy.data.materials.new('ground')
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (0.5, 0.5, 0.52, 1)
        b.inputs['Roughness'].default_value = 0.8
        g.data.materials.append(m)
    if clay:
        bg.inputs['Strength'].default_value = 0.35
        sc.view_settings.exposure = -1.0
        for nm in ('Key', 'Fill', 'Rim'):
            lo = bpy.data.objects.get(nm)
            if lo:
                lo.data.energy *= {'Key': 1.6, 'Fill': 0.5, 'Rim': 1.0}[nm]
        clay_m = bpy.data.materials.new('clay')
        clay_m.use_nodes = True
        b = clay_m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (0.42, 0.40, 0.37, 1)
        b.inputs['Roughness'].default_value = 0.45
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.name != 'Ground':
                o.data.materials.clear()
                o.data.materials.append(clay_m)
    if wire:
        add_wire_mod()


def add_wire_mod(thickness=0.0035):
    """Real polygon-edge wireframe: wireframe-modifier copies over the model."""
    wm = bpy.data.materials.new('wire')
    wm.use_nodes = True
    nt = wm.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.02, 0.06, 0.35, 1)
    em.inputs['Strength'].default_value = 1.0
    nt.links.new(em.outputs['Emission'], nt.nodes['Material Output'].inputs['Surface'])
    for o in list(bpy.data.objects):
        if o.type != 'MESH' or o.name == 'Ground':
            continue
        c = o.copy()
        c.data = o.data.copy()
        bpy.context.scene.collection.objects.link(c)
        c.data.materials.clear()
        c.data.materials.append(wm)
        m = c.modifiers.new('wf', 'WIREFRAME')
        m.thickness = thickness
        m.use_replace = True
        m.use_even_offset = True


def add_wire_overlay():
    """Mix a wireframe node into every material."""
    for m in bpy.data.materials:
        if not m.use_nodes or m.name == 'ground':
            continue
        nt = m.node_tree
        out = nt.nodes.get('Material Output')
        src = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].links else None
        if src is None:
            continue
        wf = nt.nodes.new('ShaderNodeWireframe')
        wf.use_pixel_size = True
        wf.inputs['Size'].default_value = 1.1
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = (0.02, 0.05, 0.25, 1)
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(wf.outputs['Fac'], mix.inputs['Fac'])
        nt.links.new(src, mix.inputs[1])
        nt.links.new(em.outputs['Emission'], mix.inputs[2])
        nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])


def render_view(name, outdir, suffix=''):
    sc = bpy.context.scene
    ortho, loc, tgt, sc_or_lens, up, res = VIEWS[name]
    cam = bpy.data.objects.get('Cam')
    if cam is None:
        cd = bpy.data.cameras.new('Cam')
        cam = bpy.data.objects.new('Cam', cd)
        sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = loc
    look_at(cam, tgt, up)
    cd = cam.data
    cd.clip_end = 100
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = sc_or_lens
    else:
        cd.type = 'PERSP'
        cd.lens = sc_or_lens
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    g = bpy.data.objects.get('Ground')
    if g:
        g.hide_render = (name == 'top')
    sc.render.filepath = os.path.join(outdir, f'{name}{suffix}.png')
    bpy.ops.render.render(write_still=True)
    return sc.render.filepath


def main():
    args = sys.argv[1:]
    blend, outdir = args[0], args[1]
    flags = [a for a in args[2:] if a.startswith('--')]
    views = [a for a in args[2:] if not a.startswith('--')] or ['side', 'front', 'rear', 'top', 'fq', 'rq']
    os.makedirs(outdir, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=blend)
    clay = '--clay' in flags
    wire = '--wire' in flags
    samples = 12 if '--fast' in flags else 32
    setup(clay=clay, wire=wire, samples=samples)
    suffix = ('_clay' if clay else '') + ('_wire' if wire else '')
    for v in views:
        render_view(v, outdir, suffix)
        print('rendered', v)


if __name__ == '__main__':
    main()


def backface_check_materials():
    """Override every mesh material: front faces grey, back faces red."""
    m = bpy.data.materials.new('bfcheck')
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1)
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    red = nt.nodes.new('ShaderNodeEmission')
    red.inputs['Color'].default_value = (1, 0, 0, 1)
    red.inputs['Strength'].default_value = 2.0
    mix = nt.nodes.new('ShaderNodeMixShader')
    # only camera rays turn red, so red emission does not light neighbours
    lp = nt.nodes.new('ShaderNodeLightPath')
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    nt.links.new(geo.outputs['Backfacing'], mul.inputs[0])
    nt.links.new(lp.outputs['Is Camera Ray'], mul.inputs[1])
    nt.links.new(mul.outputs['Value'], mix.inputs['Fac'])
    nt.links.new(bsdf.outputs['BSDF'], mix.inputs[1])
    nt.links.new(red.outputs['Emission'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], nt.nodes['Material Output'].inputs['Surface'])
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name != 'Ground':
            o.data.materials.clear()
            o.data.materials.append(m)
