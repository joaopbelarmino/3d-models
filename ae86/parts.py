"""Separate parts: glass, wheels, bumpers, skirts, lamps, pop-up headlights,
mirrors, wheel wells.  All geometry is generated here from scratch."""
import math
import numpy as np

import profiles as P
import bl
from geom import (MeshBuilder, mirror_builder, coons, curve, to_blender,
                  smoothstep, spline1d)
from body import fill_region, lin, lift_side, patch2d, arch_pts, theta_at
from sweep import sweep, plan_normals


# ------------------------------------------------------------------ utils
def _offset_grid(G, d, outward_hint):
    G = np.asarray(G, float)
    du = np.gradient(G, axis=0)
    dv = np.gradient(G, axis=1)
    n = np.cross(du, dv)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
    sign = np.sign(np.sum(n * outward_hint))
    return G + n * d * sign


def car_ref(c):
    """Reference point inside the car for outward orientation (Blender m)."""
    return np.array([0.0, float(np.clip(c[1], -1.3, 1.4)), 0.62])


# ------------------------------------------------------------------ glass
def glass(info):
    mb = MeshBuilder()
    base = info['ws_base']
    top = info['ws_top'][:-2]
    ap = info['ap_in']
    n = len(base)
    top_r = curve(top, n)
    centre = curve([base[0], top[0]], len(ap))
    G = coons(base, top_r, centre, ap)
    G = _offset_grid(G, -7.0, np.array([-0.5, 0, 1.0]))
    mb.grid(G, 0)
    a, b = info['hg_c']
    hg_top, hg_bot, hg_side = info['hg_top'], info['hg_bot'], info['hg_side']
    hs = curve(hg_side, 8)
    G = coons(hg_top, hg_bot, curve([a, b], len(hs)), hs)
    G = _offset_grid(G, -6.0, np.array([0.3, 0, 1.0]))
    mb.grid(G, 0)

    # side glass: structured grids from the outline split into 4 sides
    for key, corners in (('door_glass', (0, 2, 5, 9)), ('q_glass', (0, 4, 8, 12))):
        loop = np.array(info[key + '_2d'], float)
        sides = _split_loop(loop, corners)
        g2 = coons(*[np.column_stack([s, np.zeros(len(s))]) for s in sides])[..., :2]
        s, z = g2[..., 0], g2[..., 1]
        G = np.stack([s, P.W_gh(s, z) - 6.0, z], axis=-1)
        mb.grid(G, 0)
    full = mirror_builder(mb, axis=1)
    o = bl.make_object('Glass', full, ['glass'], collection='AE86')
    bl.orient_components(o, lambda c: np.array([0.0, float(np.clip(c[1], -1.0, 1.4)), 0.75]))
    return o


def _plen(c):
    return float(np.sum(np.linalg.norm(np.diff(np.asarray(c), axis=0), axis=1)))


def _split_loop(loop2, corners):
    """Split a closed 2D outline at 4 corner indices into Coons sides
    (bottom, top, left, right) resampled to matching counts."""
    n = len(loop2)
    c0, c1, c2, c3 = corners
    seg = lambda a, b: np.array([loop2[i % n] for i in range(a, b + 1 if b >= a else b + n + 1)])
    bottom = seg(c0, c1)
    right = seg(c1, c2)
    top = seg(c2, c3)[::-1]
    left = seg(c3, c0 + n)[::-1]
    nu = max(4, int(np.ceil(max(_plen(bottom), _plen(top)) / 160.0)) + 1)
    nv = max(3, int(np.ceil(max(_plen(left), _plen(right)) / 140.0)) + 1)
    rs = lambda c, k: curve(c, k, smooth=False)
    return rs(bottom, nu), rs(top, nu), rs(left, nv), rs(right, nv)


# ------------------------------------------------------------------ wheels
def lathe(mb, profile, n, center, mats_by_seg, seg_sharp=(), ang0=0.0, flip=False):
    """Revolve profile [(r, x), ...] (x lateral, outward +) around the axle."""
    cs, cw, cz = center
    rings = []
    for k in range(n):
        a = ang0 + 2 * math.pi * k / n
        rings.append([mb.v(np.array([cs + r * math.cos(a), cw + x, cz + r * math.sin(a)]))
                      for (r, x) in profile])
    for k in range(n):
        r0, r1 = rings[k], rings[(k + 1) % n]
        for j in range(len(profile) - 1):
            q = [r0[j], r0[j + 1], r1[j + 1], r1[j]]
            if flip:
                q = q[::-1]
            mb.poly(q, mats_by_seg[j])
    for j in seg_sharp:
        for k in range(n):
            a, b = rings[k][j], rings[(k + 1) % n][j]
            mb.sharp.add((min(a, b), max(a, b)))
    return rings


def wheel_builder():
    """One wheel (tire + 8-spoke rim) centred at the origin, outer face +w."""
    mb = MeshBuilder(weld=0.01)
    R = P.TIRE_R
    W = 188.0
    RL = 182.0          # rim flange radius (14")
    T, M, D = 0, 1, 2   # tire, rim, dark barrel
    N = 24
    tire = [
        (RL - 2, W * 0.40),
        (R - 44, W * 0.505),
        (R - 13, W * 0.475),
        (R, W * 0.30),
        (R, -W * 0.30),
        (R - 13, -W * 0.475),
        (R - 44, -W * 0.505),
        (RL - 2, -W * 0.40),
    ]
    lathe(mb, tire, N, (0, 0, 0), [T] * 7, seg_sharp=(3, 4))
    # inner side cap so the wheel is closed when seen from under the car
    lathe(mb, [(0.0, -W * 0.40), (RL - 2, -W * 0.40)], N, (0, 0, 0), [D])
    rim = [(RL - 2, W * 0.40), (RL + 2, W * 0.445), (RL - 7, W * 0.455), (RL - 17, W * 0.31)]
    lathe(mb, rim, N, (0, 0, 0), [M] * 3, seg_sharp=(1, 2))
    barrel = [(RL - 17, W * 0.31), (RL - 21, W * 0.02), (0.0, W * 0.02)]
    lathe(mb, barrel, N, (0, 0, 0), [D, D])
    # 8 tapered spokes
    hub_r = 56.0
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        ca, sa = math.cos(a), math.sin(a)
        tx, ty = -sa, ca

        def p(r, t, x):
            return np.array([r * ca + t * tx, x, r * sa + t * ty])
        r0, r1 = hub_r, RL - 19
        x0, x1 = W * 0.36, W * 0.33
        A0, B0 = p(r0, -15, x0), p(r0, 15, x0)
        A1, B1 = p(r1, -24, x1), p(r1, 24, x1)
        dA0, dB0 = p(r0, -17, x0 - 16), p(r0, 17, x0 - 16)
        dA1, dB1 = p(r1, -26, x1 - 16), p(r1, 26, x1 - 16)
        ids = [mb.v(q) for q in (A0, B0, B1, A1, dA0, dB0, dB1, dA1)]
        mb.poly([ids[0], ids[3], ids[2], ids[1]], M)
        mb.poly([ids[0], ids[4], ids[7], ids[3]], M)
        mb.poly([ids[1], ids[2], ids[6], ids[5]], M)
        mb.mark_chain([ids[0], ids[3]])
        mb.mark_chain([ids[1], ids[2]])
    hub = [(hub_r + 6, W * 0.30), (hub_r, W * 0.38), (26, W * 0.42), (0.0, W * 0.43)]
    lathe(mb, hub, 12, (0, 0, 0), [M] * 3, seg_sharp=(1,))
    return mb


def wheels():
    mb = wheel_builder()
    objs = []
    for name, s, track, side in (('Wheel_FL', P.S_FA, P.TRACK_F, 1), ('Wheel_FR', P.S_FA, P.TRACK_F, -1),
                                 ('Wheel_RL', P.S_RA, P.TRACK_R, 1), ('Wheel_RR', P.S_RA, P.TRACK_R, -1)):
        m = MeshBuilder(weld=0.01)
        idmap = {}
        for i, v in enumerate(mb.verts):
            q = v.copy()
            q[1] *= side
            idmap[i] = m.v(q)
        for f, mi in zip(mb.faces, mb.fmat):
            ff = [idmap[i] for i in f]
            m.poly(ff if side > 0 else ff[::-1], mi)
        for a, b in mb.sharp:
            m.sharp.add(tuple(sorted((idmap[a], idmap[b]))))
        # geometry in local mm around the wheel centre -> convert manually
        verts = np.array(m.verts)
        loc = np.array([side * (track / 2.0 - 8.0) / 1000.0, (s - 2063.0) / 1000.0, P.TIRE_R / 1000.0])
        m.verts = [np.array([v[1] / 1000.0 + loc[0], v[0] / 1000.0 + loc[1], v[2] / 1000.0 + loc[2]])
                   for v in verts]
        o = bl.make_object(name, m, ['tire', 'rim', 'interior_black'], collection='AE86', convert=False)
        bl.orient_components(o, None)
        bl.set_origin(o, loc)
        objs.append(o)
    return objs


# ------------------------------------------------------------------ bumpers
def front_bumper(info):
    """Front bumper: plan sweep from the centre around the corner to the arch,
    with a recessed lamp/grille band and the shelf under the nose."""
    mb = MeshBuilder()
    AF = P.ARCH_F
    # plan path of the bumper top-front edge (centre -> side)
    ctrl = np.array([[6, 0], [6, 220], [8, 400], [14, 500], [26, 572], [46, 630],
                     [80, 676], [130, 710], [200, 731], [300, 742], [400, 755], [531, 768]])
    dense = curve(ctrl, 400, smooth=True)
    # adaptive stations: dense around the corner, sparse on the flat faces
    seg = np.linalg.norm(np.diff(dense, axis=0), axis=1)
    L = np.concatenate([[0], np.cumsum(seg)])
    curv = np.zeros(len(dense))
    T = np.gradient(dense, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    curv[1:-1] = np.linalg.norm(T[2:] - T[:-2], axis=1)
    dens = 1.0 + 60.0 * curv
    cum = np.concatenate([[0], np.cumsum(dens[1:] * seg)])
    tgt = np.linspace(0, cum[-1], 24)
    path = np.column_stack([np.interp(tgt, cum, dense[:, 0]), np.interp(tgt, cum, dense[:, 1])])
    path[:, 1] = np.maximum(path[:, 1], 0)
    path[0, 1] = 0.0
    # snap the side part onto the body side surface at the top edge
    for i, (s, w) in enumerate(path):
        if s > 300:
            path[i, 1] = float(P.W_side(s, 585.0))
    N = plan_normals(path)
    N[0] = [-1, 0]
    s_arr = path[:, 0]
    # side blend: 0 at the front, 1 once the bumper runs along the side
    b = smoothstep(150.0, 330.0, s_arr)
    # shelf inner line (under the nose panel / corner lamp)
    shelf_plan = curve(np.array([[168, 0], [168, 600], [160, 655], [150, 690], [175, 716],
                                 [230, 728], [330, 744]]), 200)
    Z = [585, 585, 583, 578, 571, 571, 476, 476, 468, 352, 342, 285, 255, 238, 230]
    band_end = 0.9   # band recess active while b < band_end
    profiles = []
    for i in range(len(path)):
        s, w = path[i]
        # shelf depth: distance from path to the shelf line along -N
        dmin = 0.0
        if b[i] < 0.999:
            d = shelf_plan - path[i]
            proj = -(d @ N[i])
            perp = np.abs(d @ np.array([-N[i, 1], N[i, 0]]))
            k = np.argmin(perp + (proj < 0) * 1e6)
            dmin = max(proj[k], 0.0)
        side_o = lambda z: float(P.W_side(max(s, 300.0), z) - P.W_side(max(s, 300.0), 585.0))
        front_o = {585: None, 583: -5.0, 578: 0.0, 571: 2.0, 476: 2.0, 468: 3.0, 352: 3.0,
                   342: -5.0, 285: -9.0, 255: -16.0, 238: -27.0, 230: -110.0}
        rec = -11.0 * (1 - smoothstep(95.0, 135.0, s))
        prof = []
        for j, z in enumerate(Z):
            if j == 0:
                o_f = -dmin
            elif j == 1:
                o_f = -dmin * 0.45
            elif j in (5, 6):
                o_f = 2.0 + rec
            else:
                o_f = front_o[z]
            o_s = side_o(z) if z < 585 else 0.0
            if j in (0, 1, 2):
                o_s = 0.0
            if j == 14:
                o_s = side_o(238) - 60.0
            o = (1 - b[i]) * o_f + b[i] * o_s
            prof.append((o, z))
        profiles.append(prof)
    G = sweep(path, profiles, N)
    mb.grid(G, 0, flip=True)
    mb.mark_chain([mb.v(p) for p in G[:, 3]])
    mb.mark_chain([mb.v(p) for p in G[:, 4]])
    mb.mark_chain([mb.v(p) for p in G[:, 7]])
    mb.mark_chain([mb.v(p) for p in G[:, 8]])
    mb.mark_chain([mb.v(p) for p in G[:, 9]])
    mb.mark_chain([mb.v(p) for p in G[:, 10]])
    info['fbumper_band'] = (G[:, 5], G[:, 6], path, N, b)
    # side panel between the last sweep station (s=531) and the wheel arch:
    # a triangular Coons patch in side view, lifted onto the body side surface
    end = G[-1]
    col = []
    for q in sorted([q for q in end if q[2] >= AF['z']], key=lambda q: q[2]):
        if not col or np.linalg.norm(q - col[-1]) > 0.5:
            col.append(q)
    col = np.array(col)                                     # bottom -> top
    th_top = np.pi - theta_at(AF, float(col[-1][2]))
    m, n = len(col), 7
    s_top = float(P.arch_s_at(AF, float(col[-1][2]), 'front'))
    arch2 = arch_pts(AF, np.pi, th_top, n)
    arch2[0] = col[0][[0, 2]]
    top2 = np.column_stack([np.linspace(col[-1][0], s_top, n), np.full(n, col[-1][2])])
    left2 = col[:, [0, 2]]
    right2 = np.repeat(arch2[-1:], m, axis=0)
    Gs = patch2d(arch2, top2, left2, right2, lift_side, targets={'l': col})
    mb.grid(Gs, 0, flip=True)
    # return flange along the arch-facing edge (arch + vertical leg)
    leg = np.array([q for q in end if q[2] < AF['z']][::-1])            # top -> bottom
    leg = leg[np.argsort(-leg[:, 2])]
    edge = np.vstack([Gs[::-1, 0], leg])
    inner = edge.copy()
    inner[:, 1] -= 38.0
    mb.grid(np.stack([edge, inner], axis=1), 0)
    full = mirror_builder(mb, axis=1)
    o = bl.make_object('Bumper_Front', full, ['plastic_black'])
    bl.orient_components(o, lambda c: np.array([0.0, -1.0, 0.45]))
    return o


def rear_bumper(info):
    mb = MeshBuilder()
    AR = P.ARCH_R
    zb = 545.0
    s_arch = float(P.arch_s_at(AR, zb, 'rear'))
    ctrl = np.array([[4205, 0], [4205, 250], [4203, 450], [4198, 560], [4186, 640],
                     [4162, 700], [4120, 735], [4050, 752], [3950, 762], [3800, 772],
                     [3650, 778], [s_arch, 782]])
    path = curve(ctrl, 22)
    for i, (s, w) in enumerate(path):
        if s < 4110:
            path[i, 1] = float(P.W_side(s, 540.0))
    # path runs centre(rear) -> side(front); outward normal: rotate other way
    T = np.gradient(path, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    N = np.column_stack([T[:, 1], -T[:, 0]])
    N[0] = [1, 0]
    s_arr = path[:, 0]
    b = 1 - smoothstep(3990.0, 4150.0, s_arr)
    Z = [541, 541, 538, 532, 520, 470, 402, 392, 330, 280, 250, 238]
    tail_s = lambda w: P.S_TAIL + 12 - 0.00003 * w * w
    profiles = []
    for i in range(len(path)):
        s, w = path[i]
        shelf = max(0.0, (s - tail_s(w))) if b[i] < 1 else 0.0
        side_o = lambda z: float(P.W_side(min(s, 4100.0), z) - P.W_side(min(s, 4100.0), 540.0))
        rear_o = [None, None, -4.0, 0.0, 3.0, 4.0, 4.0, -12.0, -17.0, -23.0, -33.0, -110.0]
        prof = []
        for j, z in enumerate(Z):
            if j == 0:
                o_r = -shelf
            elif j == 1:
                o_r = -shelf * 0.5
            else:
                o_r = rear_o[j]
            o_s = 0.0 if j < 3 else side_o(z)
            if j == len(Z) - 1:
                o_s = side_o(240) - 60.0
            o = (1 - b[i]) * o_r + b[i] * o_s
            prof.append((o, z))
        profiles.append(prof)
    G = sweep(path, profiles, N)
    mb.grid(G, 0)
    for j in (3, 6, 7):
        mb.mark_chain([mb.v(p) for p in G[:, j]])
    end = G[-1]
    inner = end.copy()
    inner[:, 1] -= 40
    mb.grid(np.stack([end, inner], axis=1), 0, flip=True)
    full = mirror_builder(mb, axis=1)
    from geom import merge
    merge(full, exhaust_mb())
    o = bl.make_object('Bumper_Rear', full, ['plastic_black', 'metal'])
    bl.orient_components(o, None)
    return o


def side_skirts(info):
    objs = []
    mb = MeshBuilder()
    s0 = P.ARCH_F['s'] + P.ARCH_F['r'] + 2
    s1 = P.ARCH_R['s'] - P.ARCH_R['r'] - 2
    ss = np.linspace(s0, s1, 14)
    rows = []
    for s in ss:
        wt = float(P.W_side(s, P.ROCKER_Z))
        prof = [(wt - 6, P.ROCKER_Z + 8), (wt + 1, P.ROCKER_Z - 2), (wt + 4, 225.0),
                (wt + 3, 190.0), (wt - 4, 176.0), (wt - 18, 172.0), (wt - 120, 172.0)]
        rows.append([(s, w, z) for (w, z) in prof])
    G = np.array(rows)
    mb.grid(G, 0, flip=True)
    mb.mark_chain([mb.v(p) for p in G[:, 1]])
    mb.mark_chain([mb.v(p) for p in G[:, 4]])
    # end caps
    for row in (G[0], G[-1]):
        c = row.mean(axis=0)
        for k in range(len(row) - 1):
            mb.poly([mb.v(row[k]), mb.v(row[k + 1]), mb.v(c)], 0)
    for side, name in ((1, 'Skirt_L'), (-1, 'Skirt_R')):
        m = MeshBuilder()
        idm = {}
        for i, v in enumerate(mb.verts):
            q = v.copy()
            q[1] *= side
            idm[i] = m.v(q)
        for f, mi in zip(mb.faces, mb.fmat):
            ff = [idm[i] for i in f]
            m.poly(ff if side > 0 else ff[::-1], mi)
        for a, bb in mb.sharp:
            m.sharp.add(tuple(sorted((idm[a], idm[bb]))))
        o = bl.make_object(name, m, ['plastic_black'])
        bl.orient_components(o, lambda c, side=side: np.array([side * 0.55, c[1], 0.33]))
        objs.append(o)
    return objs


# ------------------------------------------------------------------ pop-ups
POPUP_ANGLE = 52.0       # degrees the unit rotates (front up) to open


def popups(info):
    """Pop-up headlight units (closed state). Origin = hinge, rotate about the
    local X axis by -POPUP_ANGLE degrees to open."""
    lid = info['lid']
    inner, outer, rear = lid['inner'], lid['outer'], lid['rear']
    GAP = 3.0
    s0, s1 = P.S_NOSE, 326.0
    w0, w1 = 372.0 + GAP, None
    ns, nw = 7, 6
    ss = np.linspace(s0 + 1.5, s1 - GAP, ns)
    objs = []
    hinge = np.array([s1 - 14.0, 0.0, float(P.Z_top(s1, 500.0)) - 24.0])
    th = math.radians(POPUP_ANGLE)
    for side, name in ((1, 'Popup_L'), (-1, 'Popup_R')):
        mb = MeshBuilder()
        rows = []
        for s in ss:
            wa, wb = w0, float(P.w_sh(s)) - GAP
            ws = np.linspace(wa, wb, nw)
            rows.append([(s, w, float(P.Z_top(s, w)) - 1.0) for w in ws])
        Lid = np.array(rows)                      # (ns, nw, 3)
        mb.grid(Lid, 0, flip=True)                # lid (paint)
        front = Lid[0]                            # front edge (w0 -> w1)
        # visor: from lid front edge down to z 592 (black)
        vz = 594.0
        vis = front.copy()
        vis[:, 0] = s0 + 6.0
        vis[:, 2] = vz
        mid = front.copy()
        mid[:, 0] = s0 + 2.0
        mid[:, 2] = (front[:, 2] + vz) / 2 + 6
        mb.grid(np.stack([front, mid, vis], axis=1), 1)
        # lens plane: hangs below/behind the visor, tilted so it faces
        # forward once the unit is rotated open
        lens_h = 182.0
        d_back = np.array([math.sin(th), -math.cos(th)])     # (ds, dz) along lens, top->bottom
        lens_top = vis.copy()
        lens_bot = vis.copy()
        lens_bot[:, 0] += d_back[0] * lens_h
        lens_bot[:, 2] += d_back[1] * lens_h
        # housing back: from lens bottom back up to the lid rear edge
        back = Lid[-1].copy()
        bk1 = back.copy()
        bk1[:, 2] -= 60.0
        bk1[:, 0] -= 10.0
        housing = np.stack([lens_bot, bk1, back], axis=1)
        mb.grid(housing, 1)
        # lens: frame (black) + glass (clear) as a grid
        lens = np.stack([lens_top, lens_bot], axis=1)
        _lens_with_ring(mb, lens_top, lens_bot)
        _reflector(mb, lens_top, lens_bot)
        # side walls (closing loops at both ends)
        for k in (0, -1):
            loop = [Lid[i, k] for i in range(ns)][::-1] + [mid[k], vis[k], lens_bot[k], bk1[k]]
            c = np.mean(loop, axis=0)
            ids = [mb.v(p) for p in loop]
            for a_, b_ in zip(ids, ids[1:] + ids[:1]):
                mb.poly([a_, b_, mb.v(c)], 1)
        mb.mark_chain([mb.v(p) for p in front])
        for k in (0, -1):
            mb.mark_chain([mb.v(p) for p in Lid[:, k]])
        mb.mark_chain([mb.v(p) for p in Lid[-1]])
        # mirror for the right side
        m = MeshBuilder()
        idm = {}
        for i, v in enumerate(mb.verts):
            q = v.copy()
            q[1] *= side
            idm[i] = m.v(q)
        for f, mi in zip(mb.faces, mb.fmat):
            ff = [idm[i] for i in f]
            m.poly(ff if side > 0 else ff[::-1], mi)
        for a_, b_ in mb.sharp:
            m.sharp.add(tuple(sorted((idm[a_], idm[b_]))))
        h = hinge.copy()
        o = bl.make_object(name, m, ['paint_white', 'plastic_black', 'lens_clear', 'chrome'])
        bl.orient_components(o, None)
        hb = to_blender(np.array([h[0], 0.0, h[2]]))
        hb[0] = float(np.mean(np.array(m.verts)[:, 1])) / 1000.0
        bl.set_origin(o, hb)
        o['open_angle_deg'] = POPUP_ANGLE
        o['open_axis'] = 'local X, negative = open (front rises)'
        objs.append(o)
    return objs


def _reflector(mb, top, bot, r_out=64.0, r_in=56.0, n=12):
    """Round sealed-beam element on the square lens (chrome ring + dome)."""
    c = (top.mean(axis=0) + bot.mean(axis=0)) / 2
    u = top[-1] - top[0]
    u /= np.linalg.norm(u)
    v = bot.mean(axis=0) - top.mean(axis=0)
    v /= np.linalg.norm(v)
    nrm = np.cross(u, v)
    nrm /= np.linalg.norm(nrm)
    if nrm[0] > 0:                     # must face forward/down (-s) when closed
        nrm = -nrm
    ring = lambda r, d: [mb.v(c + nrm * d + (u * math.cos(a) + v * math.sin(a)) * r)
                         for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
    o = ring(r_out, 1.5)
    i = ring(r_in, 3.0)
    cen = mb.v(c + nrm * 9.0)
    for k in range(n):
        k2 = (k + 1) % n
        mb.poly([o[k], o[k2], i[k2], i[k]], 3)
        mb.poly([i[k], i[k2], cen], 2)
    mb.mark_chain(i + i[:1])


def _lens_with_ring(mb, top, bot):
    """Square lamp face: black bezel ring + clear lens with round reflector."""
    nw = len(top)
    # frame inset grid: 4x4 points, centre 2x2 = lens
    U = np.linspace(0, 1, nw)
    rows = []
    for t in (0.0, 0.08, 0.92, 1.0):
        rows.append(top * (1 - t) + bot * t)
    G = np.stack(rows, axis=1)                  # (nw, 4, 3)
    # columns: inset first/last
    G2 = G.copy()
    G2[1] = G[0] * 0.75 + G[1] * 0.25
    G2[-2] = G[-1] * 0.75 + G[-2] * 0.25
    # push lens centre slightly outward (convex)
    nrm = np.cross(G2[-1, 0] - G2[0, 0], G2[0, -1] - G2[0, 0])
    nrm /= np.linalg.norm(nrm)
    for i in range(1, nw - 1):
        for j in (1, 2):
            pass
    ids = [[mb.v(G2[i, j]) for j in range(4)] for i in range(nw)]
    for i in range(nw - 1):
        for j in range(3):
            inside = (1 <= i < nw - 2) and j == 1
            mb.poly([ids[i][j], ids[i + 1][j], ids[i + 1][j + 1], ids[i][j + 1]], 2 if inside else 1)


def popup_buckets():
    """Recesses under the pop-up lids (part of the body, black)."""
    mb = MeshBuilder()
    s0, s1 = P.S_NOSE, 326.0
    ss = np.linspace(s0, s1, 7)
    depth = 175.0
    inner = np.array([(s, 372.0, float(P.Z_top(s, 372.0))) for s in ss])
    outer = np.array([(s, float(P.w_sh(s)), float(P.Z_top(s, float(P.w_sh(s))))) for s in ss])
    nw = 6
    rear = np.array([(s1, w, float(P.Z_top(s1, w))) for w in np.linspace(372.0, float(P.w_sh(s1)), nw)])
    dn = lambda a: np.column_stack([a[:, 0], a[:, 1], np.minimum(a[:, 2] - depth, 540.0)])
    mb.grid(np.stack([inner, dn(inner)], axis=1), 0)
    mb.grid(np.stack([outer, dn(outer)], axis=1), 0, flip=True)
    mb.grid(np.stack([rear, dn(rear)], axis=1), 0, flip=True)
    # floor
    fl = np.stack([dn(inner), dn(outer)], axis=1)
    mb.grid(fl, 0)
    # front wall from the bumper shelf level down to the floor
    fr = np.array([(s0 + 20, w, 592.0) for w in np.linspace(372.0, float(P.w_sh(s0)), nw)])
    mb.grid(np.stack([fr, dn(fr)], axis=1), 0)
    return mb


# ------------------------------------------------------------------ lamps
def lamps(info):
    """Front lamps (corner + bumper band) and rear lamps as two objects."""
    CLEAR, AMBER, RED, BLACK = 0, 1, 2, 3
    mats = ['lens_clear', 'lens_amber', 'lens_red', 'plastic_black']
    # ---- front: corner lamps follow the body side and wrap to the front
    mb = MeshBuilder()
    ss = np.linspace(P.S_NOSE + 1, 326.0, 8)
    zs = np.array([591.0, 610.0, 630.0, 649.0])
    G = np.array([[(s, float(P.W_side(s, z)) - 0.6, z) for z in zs] for s in ss])
    wrap = np.array([[(P.S_NOSE + 3, w, z) for z in zs] for w in np.linspace(604, float(G[0, 0, 1]) - 1, 4)])
    full = np.concatenate([wrap, G], axis=0)
    ids = [[mb.v(full[i, j]) for j in range(len(zs))] for i in range(len(full))]
    for i in range(len(full) - 1):
        for j in range(len(zs) - 1):
            mat = AMBER if full[i, 0, 0] > 255 else CLEAR
            mb.poly([ids[i][j], ids[i + 1][j], ids[i + 1][j + 1], ids[i][j + 1]], mat, 'lens')
    for j in (0, -1):
        mb.mark_chain([ids[i][j] for i in range(len(full))])
    # bottom seal under the lens (hides the gap to the bumper shelf)
    lo = full[:, 0]
    lo_in = lo.copy()
    lo_in[:4, 0] += 20.0
    lo_in[4:, 1] -= 20.0
    lo_in[:, 2] -= 6.0
    mb.grid(np.stack([lo, lo_in], axis=1), BLACK, tag='lens')
    top, bot, path, N, b = info['fbumper_band']

    def band_lens(i0, i1, mat):
        for i in range(i0, i1):
            q = [top[i], top[i + 1], bot[i + 1], bot[i]]
            q = [p + np.array([N[k][0] * 2.0, N[k][1] * 2.0, 0]) for p, k in zip(q, (i, i + 1, i + 1, i))]
            mb.poly([mb.v(p) for p in q][::-1], mat, 'lens')
    ws = path[:, 1]
    idx = lambda w: int(np.argmin(np.abs(ws - w)))
    band_lens(idx(470), idx(605), AMBER)
    i_end = int(np.max(np.where(path[:, 0] <= 100.0)[0]))
    band_lens(idx(640), i_end, CLEAR)
    band_lens(0, idx(430), BLACK)
    full = mirror_builder(mb, axis=1)
    of = bl.make_object('Lights_Front', full, mats)
    bl.orient_components(of, car_ref)

    # ---- rear: black bezel from the panel opening, lens set 7 mm in
    mb = MeshBuilder()
    loop = np.array(info['taillamp'])
    inner = loop.copy()
    inner[:, 0] -= 9.0
    ids_o = [mb.v(q) for q in loop]
    ids_i = [mb.v(q) for q in inner]
    n = len(loop)
    for k in range(n):
        k2 = (k + 1) % n
        mb.poly([ids_o[k], ids_o[k2], ids_i[k2], ids_i[k]], BLACK, 'bezel')
    loop2 = np.column_stack([loop[:, 1], loop[:, 2]])
    wmin, wmax = loop2[:, 0].min(), loop2[:, 0].max()
    zmin, zmax = loop2[:, 1].min(), loop2[:, 1].max()
    wsplit = 574.0
    srear = lambda w, z: P.S_TAIL + 12 - (z - 545.0) * (105.0 / 400.0) - 0.00003 * w * w

    def lens_pt(w, z, bulge):
        return np.array([srear(w, z) - 7.0 + bulge, w, z])
    wsg = np.array([wmin, 340, 420, 500, wsplit, wsplit + 2, 640, wmax])
    zsg = np.array([zmin, zmin + 30, (zmin + zmax) / 2, zmax - 30, zmax])
    T = np.array([[lens_pt(w, z, 3.0 * math.sin(math.pi * (z - zmin) / (zmax - zmin))) for z in zsg]
                  for w in wsg])
    ids = [[mb.v(T[i, j]) for j in range(len(zsg))] for i in range(len(wsg))]
    for i in range(len(wsg) - 1):
        for j in range(len(zsg) - 1):
            mat = BLACK if i == 4 else (AMBER if T[i, 0, 1] >= wsplit else RED)
            mb.poly([ids[i][j], ids[i][j + 1], ids[i + 1][j + 1], ids[i + 1][j]], mat, 'lens')
    for j in (1, 3):
        mb.mark_chain([ids[i][j] for i in range(len(wsg))])
    full = mirror_builder(mb, axis=1)
    orr = bl.make_object('Lights_Rear', full, mats)
    tags = full.ftag
    bl.orient_components(orr, car_ref, faces_filter=lambda i: tags[i] == 'lens')
    cz = (zmin + zmax) / 2000.0
    cy = (P.S_TAIL - 40 - 2063.0) / 1000.0
    bl.orient_components(orr, lambda c: np.array([np.sign(c[0]) * 0.50, cy, cz]), toward=True,
                         faces_filter=lambda i: tags[i] == 'bezel')
    return of, orr


# ------------------------------------------------------------------ mirrors
def _rrect(hw, hh, rad, nc=2):
    """Rounded rectangle ring (x lateral, z), counter-clockwise."""
    pts = []
    for cx, cz, a0 in ((hw - rad, hh - rad, 0), (-hw + rad, hh - rad, 90),
                       (-hw + rad, -hh + rad, 180), (hw - rad, -hh + rad, 270)):
        for k in range(nc + 1):
            a = math.radians(a0 + 90.0 * k / nc)
            pts.append((cx + rad * math.cos(a), cz + rad * math.sin(a)))
    return np.array(pts)


def mirrors_mb():
    """Door mirror (left): aero head on a short stalk from the sail panel."""
    mb = MeshBuilder()
    c = np.array([1662.0, 842.0, 936.0])
    back = _rrect(80.0, 50.0, 22.0)
    front = _rrect(62.0, 38.0, 20.0)
    ring_b = [mb.v(c + np.array([42.0, x, z])) for x, z in back]
    ring_m = [mb.v(c + np.array([-8.0, x * 0.98 + 2, z * 0.97])) for x, z in back]
    ring_f = [mb.v(c + np.array([-50.0, x + 6, z])) for x, z in front]
    fc = mb.v(c + np.array([-62.0, 6.0, 0.0]))
    gl = [mb.v(c + np.array([36.0, x * 0.86, z * 0.84])) for x, z in back]
    gc = mb.v(c + np.array([36.0, 0.0, 0.0]))
    n = len(back)
    for k in range(n):
        k2 = (k + 1) % n
        mb.poly([ring_f[k2], ring_f[k], fc], 0)
        mb.poly([ring_m[k2], ring_m[k], ring_f[k], ring_f[k2]], 0)
        mb.poly([ring_b[k2], ring_b[k], ring_m[k], ring_m[k2]], 0)
        mb.poly([gl[k2], gl[k], ring_b[k], ring_b[k2]], 0)
        mb.poly([gc, gl[k], gl[k2]], 1)
    mb.mark_chain([ring_b[k] for k in range(n)] + [ring_b[0]])
    # stalk from the sail to the inner side of the head
    a0 = np.array([1650.0, 738.0, 912.0])
    a1 = np.array([1660.0, 790.0, 920.0])
    sec = [(-34, -10), (26, -10), (26, 10), (-34, 10)]
    rings = [[mb.v(p + np.array([dx, 0, dz])) for dx, dz in sec] for p in (a0, a1)]
    for k in range(4):
        k2 = (k + 1) % 4
        mb.poly([rings[0][k], rings[0][k2], rings[1][k2], rings[1][k]], 0)
    return mb


# ------------------------------------------------------------------ wells
def wheel_wells(info):
    """Arch return flanges (welded to the body arch edge) + well liners."""
    mb = MeshBuilder()
    W_IN = 470.0
    for a, edge in ((P.ARCH_F, info['archF_edge']), (P.ARCH_R, info['archR_edge'])):
        sc, zc, r = a['s'], a['z'], a['r']
        edge = np.asarray(edge, float)
        outer, flange, liner = [], [], []
        for p3 in edge:
            ds, dz = p3[0] - sc, p3[2] - zc
            if dz < 0:
                d = np.array([np.sign(ds), 0.0])
            else:
                d = np.array([ds, dz]) / max(np.hypot(ds, dz), 1e-6)
            outer.append(p3)
            flange.append(np.array([p3[0] + d[0] * 10, p3[1] - 30.0, p3[2] + d[1] * 10]))
            if dz < 0:
                liner.append(np.array([sc + d[0] * (r + 28), W_IN, p3[2]]))
            else:
                liner.append(np.array([sc + d[0] * (r + 28), W_IN, zc + d[1] * (r + 28)]))
        outer, flange, liner = map(np.array, (outer, flange, liner))
        mb.grid(np.stack([outer, flange, liner], axis=1), 0)
        mb.mark_chain([mb.v(q) for q in outer])
        c = np.array([sc, W_IN, zc - 40])
        for k in range(len(liner) - 1):
            mb.poly([mb.v(liner[k]), mb.v(liner[k + 1]), mb.v(c)], 0)
    return mb


def floor_mb():
    """Flat underbody panel that closes the shell from below."""
    mb = MeshBuilder()
    Z, W_IN = 205.0, 470.0
    for (s0, s1, w0, w1) in ((250.0, 4000.0, 0.0, W_IN), (1235.0, 2905.0, W_IN, 735.0)):
        ss = np.linspace(s0, s1, 4)
        g = np.array([[(s, w, Z) for w in (w0, w1)] for s in ss])
        mb.grid(g, 0)
    return mb


# ------------------------------------------------------------------ small body details
def body_details():
    """Door handles, upper grille fins (all merged into the body mesh).
    Material ids: 0 black plastic, 1 chrome/metal."""
    mb = MeshBuilder()
    # door handle: flush black pull with a recessed scoop
    s0, s1, z0, z1 = 2455.0, 2620.0, 752.0, 800.0
    def wpt(s, z, d=0.0):
        return np.array([s, float(P.W_side(s, z)) + d, z])
    ring = [wpt(s0, z0), wpt(s1, z0), wpt(s1, z1), wpt(s0, z1)]
    out = [p + np.array([0, 4.0, 0]) for p in ring]
    ids_r = [mb.v(p) for p in ring]
    ids_o = [mb.v(p) for p in out]
    for k in range(4):
        k2 = (k + 1) % 4
        mb.poly([ids_r[k], ids_r[k2], ids_o[k2], ids_o[k]], 0)
    inner = [wpt(s0 + 12, z0 + 10, 4.0), wpt(s1 - 12, z0 + 10, 4.0), wpt(s1 - 12, z1 - 10, 4.0),
             wpt(s0 + 12, z1 - 10, 4.0)]
    deep = [p - np.array([0, 14.0, 0]) for p in inner]
    ids_i = [mb.v(p) for p in inner]
    ids_d = [mb.v(p) for p in deep]
    for k in range(4):
        k2 = (k + 1) % 4
        mb.poly([ids_o[k], ids_o[k2], ids_i[k2], ids_i[k]], 0)
        mb.poly([ids_i[k], ids_i[k2], ids_d[k2], ids_d[k]], 0)
    mb.poly(ids_d[::-1], 0)
    mb.mark_chain(ids_o + ids_o[:1])
    # upper grille fins between the pop-ups (under the hood front edge)
    for z in (612.0, 632.0):
        a = [np.array([166.0, w, z]) for w in (0.0, 360.0)]
        b = [np.array([150.0, w, z + 4]) for w in (0.0, 360.0)]
        c = [np.array([150.0, w, z - 4]) for w in (0.0, 360.0)]
        ia, ib, ic = [mb.v(p) for p in a], [mb.v(p) for p in b], [mb.v(p) for p in c]
        mb.poly([ia[0], ia[1], ib[1], ib[0]], 0)
        mb.poly([ib[0], ib[1], ic[1], ic[0]], 0)
        mb.poly([ic[0], ic[1], ia[1], ia[0]], 0)
    return mb


def wipers_mb():
    """Wiper blades parked along the windshield base (asymmetric, not mirrored)."""
    mb = MeshBuilder()
    for (sa, wa, sb, wb) in ((1352.0, 520.0, 1336.0, 60.0), (1336.0, -20.0, 1318.0, -470.0)):
        za, zb = float(P.Z_top(sa, abs(wa))) + 12, float(P.Z_top(sb, abs(wb))) + 12
        A, B = np.array([sa, wa, za]), np.array([sb, wb, zb])
        off = [np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, 10.0]), np.array([16.0, 0.0, 4.0])]
        ra = [mb.v(A + o) for o in off]
        rb = [mb.v(B + o) for o in off]
        for k in range(3):
            k2 = (k + 1) % 3
            mb.poly([ra[k], ra[k2], rb[k2], rb[k]], 0)
        mb.poly(ra, 0)
        mb.poly(rb[::-1], 0)
    return mb


def exhaust_mb():
    """Single tail pipe (left rear), part of the rear bumper object."""
    mb = MeshBuilder()
    c = np.array([4150.0, 470.0, 205.0])
    r0, r1, L = 30.0, 24.0, 190.0
    n = 10
    rings = []
    for (ds, r) in ((-L, r0), (0.0, r0), (0.0, r1), (-40.0, r1)):
        rings.append([mb.v(c + np.array([ds, r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)]))
                      for k in range(n)])
    for j in range(3):
        for k in range(n):
            k2 = (k + 1) % n
            mb.poly([rings[j][k], rings[j][k2], rings[j + 1][k2], rings[j + 1][k]], 1 if j else 1)
    mb.mark_chain(rings[1] + rings[1][:1])
    return mb
