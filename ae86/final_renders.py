"""Final validation renders + contact sheets.

    python ae86/final_renders.py model.blend out_dir
"""
import os
import sys
import math
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SETS = {
    'color': ['fq', 'rq', 'fq_r', 'rq_r', 'side', 'front', 'rear', 'top', 'low', 'fq_open', 'front_open'],
    'clay': ['fq', 'rq', 'side', 'front', 'rear', 'top'],
    'wire': ['fq', 'rq', 'side', 'top', 'front', 'rear'],
}


def render_set(blend, out, kind):
    import bpy
    import render
    bpy.ops.wm.open_mainfile(filepath=blend)
    render.setup(clay=(kind != 'color'), wire=(kind == 'wire'), samples=32 if kind == 'color' else 20)
    for v in SETS[kind]:
        name = v.replace('_open', '')
        if v.endswith('_open'):
            for n in ('Popup_L', 'Popup_R'):
                o = bpy.data.objects[n]
                o.rotation_euler.x = -math.radians(o['open_angle_deg'])
        suffix = ('' if kind == 'color' else '_' + kind) + ('_open' if v.endswith('_open') else '')
        render.render_view(name, out, suffix)
        if v.endswith('_open'):
            for n in ('Popup_L', 'Popup_R'):
                bpy.data.objects[n].rotation_euler.x = 0.0
        print('rendered', kind, v)


def sheet(out, kind, files, cols=2, tile=(800, 500)):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22)
    rows = (len(files) + cols - 1) // cols
    S = Image.new('RGB', (tile[0] * cols, tile[1] * rows), 'white')
    for k, (f, label) in enumerate(files):
        im = Image.open(os.path.join(out, f)).convert('RGB')
        im.thumbnail(tile)
        cell = Image.new('RGB', tile, (200, 202, 206))
        cell.paste(im, ((tile[0] - im.width) // 2, (tile[1] - im.height) // 2))
        d = ImageDraw.Draw(cell)
        d.rectangle([0, 0, tile[0], 32], fill=(20, 20, 20))
        d.text((10, 4), label, fill='white', font=font)
        S.paste(cell, ((k % cols) * tile[0], (k // cols) * tile[1]))
    S.save(os.path.join(out, f'sheet_{kind}.png'))


def main():
    blend, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    if len(sys.argv) > 3:                       # worker mode: one set per process
        render_set(blend, out, sys.argv[3])
        return
    for kind in SETS:
        subprocess.check_call([sys.executable, os.path.abspath(__file__), blend, out, kind])
    labels = {'fq': '3/4 dianteira', 'rq': '3/4 traseira', 'fq_r': '3/4 dianteira (dir.)',
              'rq_r': '3/4 traseira (dir.)', 'side': 'lateral', 'front': 'frente', 'rear': 'traseira',
              'top': 'topo', 'low': 'baixa', 'fq_open': 'pop-ups abertos', 'front_open': 'frente, pop-ups abertos'}
    for kind, views in SETS.items():
        suf = '' if kind == 'color' else '_' + kind
        files = []
        for v in views:
            base = v.replace('_open', '')
            fn = f'{base}{suf}_open.png' if v.endswith('_open') else f'{base}{suf}.png'
            files.append((fn, labels[v] + ('' if kind == 'color' else f' ({kind})')))
        sheet(out, kind, files)
    to_jpeg(out)


def to_jpeg(out, quality=88):
    """Keep the repository light: PNG renders -> JPEG."""
    from PIL import Image
    for f in sorted(os.listdir(out)):
        if f.endswith('.png'):
            src = os.path.join(out, f)
            Image.open(src).convert('RGB').save(src[:-4] + '.jpg', quality=quality, optimize=True)
            os.remove(src)


if __name__ == '__main__':
    main()
