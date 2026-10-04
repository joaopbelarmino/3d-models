"""AE86 main body shell (left half, mirrored at the end).

Regions:
  side   : lower body side, laid out in side view (s,z) and lifted with W_side
  top    : hood + fender tops, laid out in plan (s,w) and lifted with Z_top
  gh     : greenhouse side (window frames, B-pillar) in side view, W_gh
  roof, a-pillar, c-pillar, hatch lip, tail panel, nose
Holes are left for every separate part (glass, pop-ups, lamps, bumpers).
"""
import numpy as np
from mathutils.geometry import delaunay_2d_cdt
from mathutils import Vector

import profiles as P
from geom import (curve, coons, MeshBuilder, smoothstep, ease_both, ease_end,
                  ease_start, lin1d)

# material slots of the body object
M_PAINT, M_LOWER, M_BLACK, M_RUBBER, M_INNER = range(5)
BODY_MATS = ['paint_white', 'paint_black', 'plastic_black', 'rubber', 'interior_black']


# ------------------------------------------------------------------ helpers
def lin(a, b, n, bias=None):
    a, b = np.asarray(a, float), np.asarray(b, float)
    t = np.linspace(0, 1, n)
    if bias is not None:
        t = np.array([bias(x) for x in t])
    return a[None] * (1 - t[:, None]) + b[None] * t[:, None]


def lift_side(G):
    """(…,2) array of (s,z) -> (…,3) (s,w,z) on the body side surface."""
    s, z = G[..., 0], G[..., 1]
    return np.stack([s, P.W_side(s, z), z], axis=-1)


def lift_gh(G):
    s, z = G[..., 0], G[..., 1]
    return np.stack([s, P.W_gh(s, z), z], axis=-1)


def lift_top(G):
    s, w = G[..., 0], G[..., 1]
    return np.stack([s, w, P.Z_top(s, w)], axis=-1)


def lift_roof(G):
    s, w = G[..., 0], G[..., 1]
    return np.stack([s, w, P.Z_roof(s, w)], axis=-1)


def patch2d(b, t, l, r, lift, targets=None):
    """Coons patch laid out in 2D, lifted to 3D by a field, then corrected so
    the boundaries hit the given 3D target curves exactly."""
    L = coons(*(np.column_stack([x, np.zeros(len(x))]) for x in (b, t, l, r)))[..., :2]
    G = lift(L)
    if targets:
        sl = {'b': (slice(None), 0), 't': (slice(None), -1),
              'l': (0, slice(None)), 'r': (-1, slice(None))}
        res = {}
        for key, idx in sl.items():
            tgt = targets.get(key)
            if tgt is not None:
                res[key] = np.asarray(tgt, float) - G[idx]
        # corner residuals from targeted boundaries (b/t run along u, l/r along v)
        corners = {}
        for key, (ka, kb) in {'b': ('00', '10'), 't': ('01', '11'),
                              'l': ('00', '01'), 'r': ('10', '11')}.items():
            if key in res:
                corners.setdefault(ka, res[key][0])
                corners.setdefault(kb, res[key][-1])
        z3 = np.zeros(3)
        for key, (ka, kb) in {'b': ('00', '10'), 't': ('01', '11'),
                              'l': ('00', '01'), 'r': ('10', '11')}.items():
            if key not in res:
                n = G[sl[key]].shape[0]
                t = np.linspace(0, 1, n)[:, None]
                res[key] = corners.get(ka, z3) * (1 - t) + corners.get(kb, z3) * t
        R = coons(res['b'], res['t'], res['l'], res['r'])
        G = G + R
    return G


def fill_region(mb, loops3d, proj, lift, mat, tag=None, steiner=None, flip=False,
                min_dist=12.0):
    """Constrained-Delaunay fill of a region given by 3D boundary loops.

    loops3d[0] is the outer loop, the rest are holes.  proj maps 3D->2D,
    lift maps 2D->3D for interior (Steiner) points, whose position is
    corrected by an inverse-distance blend of the boundary residuals."""
    pts2, pts3, edges, loops_idx = [], [], [], []
    for loop in loops3d:
        loop = np.asarray(loop, float)
        start = len(pts2)
        idx = []
        for p in loop:
            pts2.append(proj(p))
            pts3.append(p)
            idx.append(len(pts2) - 1)
        loops_idx.append(idx)
        for a, b in zip(idx, idx[1:] + idx[:1]):
            edges.append((a, b))
    bnd2 = np.array(pts2)
    bnd3 = np.array(pts3)
    res = bnd3 - np.array([lift(np.array([q]))[0] for q in bnd2])

    polys2 = [np.array([pts2[i] for i in idx]) for idx in loops_idx]

    def inside(q):
        if not _pip(q, polys2[0]):
            return False
        return not any(_pip(q, h) for h in polys2[1:])

    extra2 = []
    if steiner is not None:
        for q in steiner:
            q = np.asarray(q, float)
            if inside(q) and np.min(np.linalg.norm(bnd2 - q, axis=1)) > min_dist:
                extra2.append(q)
    all2 = list(pts2) + extra2
    out = delaunay_2d_cdt([Vector((float(x), float(y))) for x, y in all2], edges, [], 0, 1e-6)
    overts, oedges, ofaces = out[0], out[1], out[2]
    orig = out[3]
    # map output verts to our indices
    vmap = {}
    for k, o in enumerate(orig):
        vmap[k] = o[0] if o else None
    ids3 = []
    for k, q in enumerate(all2):
        if k < len(pts3):
            ids3.append(mb.v(pts3[k], tag))
        else:
            q = np.asarray(q)
            d = np.linalg.norm(bnd2 - q, axis=1)
            wgt = 1.0 / np.maximum(d, 1e-3) ** 2
            corr = (res * wgt[:, None]).sum(0) / wgt.sum()
            p = lift(np.array([q]))[0] + corr
            ids3.append(mb.v(p, tag))
    for f in ofaces:
        if len(f) != 3:
            continue
        src = [vmap.get(i) for i in f]
        if any(s is None for s in src):
            continue
        c = np.mean([all2[s] for s in src], axis=0)
        if not inside(c):
            continue
        a, b, c3 = (np.asarray(all2[s]) for s in src)
        cross = (b[0] - a[0]) * (c3[1] - a[1]) - (b[1] - a[1]) * (c3[0] - a[0])
        if abs(cross) < 1e-3:
            continue
        tri = [ids3[s] for s in src]
        if (cross < 0) ^ flip:
            tri = tri[::-1]
        mb.poly(tri, mat, tag)


def _pip(q, poly):
    x, y = q
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xin = (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            if x < xin:
                inside = not inside
        j = i
    return inside


def arch_pts(a, th0, th1, n):
    th = np.linspace(th0, th1, n)
    return np.column_stack([a['s'] + a['r'] * np.cos(th), a['z'] + a['r'] * np.sin(th)])


def theta_at(a, z):
    return np.arcsin(np.clip((z - a['z']) / a['r'], -1, 1))


# ------------------------------------------------------------------ build
def build():
    mb = MeshBuilder(weld=0.02)
    info = {}
    AF, AR = P.ARCH_F, P.ARCH_R
    CZ = P.CREASE_Z

    # ---------------- key stations
    sF = P.S_NOSE
    sL = 326.0                                   # lamp / lid rear edge
    sA1 = P.arch_s_at(AF, CZ, 'front')
    sA2 = P.arch_s_at(AF, CZ, 'rear')
    sAP = 1440.0                                 # A-pillar foot
    sB1 = P.arch_s_at(AR, CZ, 'front')
    sB2 = P.arch_s_at(AR, CZ, 'rear')
    sQ = 3740.0                                  # end of quarter-glass frame
    LAMP_TOP = 650.0

    # side top boundary helper (2D)
    def top2d(svals):
        svals = np.asarray(svals, float)
        return np.column_stack([svals, P.side_top(svals)])

    FV = np.array([0.0, 0.24, 0.47, 0.68, 0.86, 1.0])     # vertical fractions

    def vcol(s, z0, fr=FV):
        zt = float(P.side_top(s))
        return np.column_stack([np.full(len(fr), s), z0 + (zt - z0) * fr])

    # ---- SA: above the corner lamp (front, collapses at the nose)
    nSA = 6
    sa_s = np.linspace(sF, sL, nSA)
    sa_bot = np.column_stack([sa_s, LAMP_TOP + (655 - LAMP_TOP) * (1 - smoothstep(sF, 200, sa_s))])
    sa_top = top2d(sa_s)
    fa = np.array([0.0, 0.42, 0.78, 1.0])
    sa_left = np.column_stack([np.full(4, sF), sa_bot[0, 1] + (sa_top[0, 1] - sa_bot[0, 1]) * fa])
    sa_right = np.column_stack([np.full(4, sL), sa_bot[-1, 1] + (sa_top[-1, 1] - sa_bot[-1, 1]) * fa])
    G = patch2d(sa_bot, sa_top, sa_left, sa_right, lift_side)
    mb.grid(G, M_PAINT, tag='side')
    side_top3 = [G[:, -1]]

    # ---- SB: fender ahead of the arch
    nSB = 8
    sb_s = np.linspace(sL, sA1, nSB)
    sb_left = np.vstack([np.column_stack([[sL, sL], [CZ, (CZ + LAMP_TOP) / 2]]), sa_right])
    frB = (sb_left[:, 1] - CZ) / (sb_left[-1, 1] - CZ)
    sb_right = vcol(sA1, CZ, frB)
    G = patch2d(np.column_stack([sb_s, np.full(nSB, CZ)]), top2d(sb_s), sb_left, sb_right, lift_side)
    mb.grid(G, M_PAINT, tag='side')
    side_top3.append(G[:, -1])
    crease_front = G[:, 0]

    # ---- SC: above the front arch
    thA1, thA2 = theta_at(AF, CZ), np.pi - theta_at(AF, CZ)
    nSC = 15
    arch_top = arch_pts(AF, thA2, thA1, nSC)            # front -> rear
    sc_top = top2d(arch_top[:, 0])
    G = patch2d(arch_top, sc_top, sb_right, vcol(sA2, CZ, frB), lift_side)
    mb.grid(G, M_PAINT, tag='side')
    side_top3.append(G[:, -1])
    archF_top3 = G[:, 0]

    # ---- SD1 / SD2: behind the front arch to the rear arch
    nSD1 = 7
    sd1_s = np.linspace(sA2, sAP, nSD1)
    G = patch2d(np.column_stack([sd1_s, np.full(nSD1, CZ)]), top2d(sd1_s),
                vcol(sA2, CZ, frB), vcol(sAP, CZ, frB), lift_side)
    mb.grid(G, M_PAINT, tag='side')
    side_top3.append(G[:, -1])
    crease_mid = [G[:, 0]]
    sd2_s = np.concatenate([np.linspace(sAP, 1530, 4)[:-1], np.linspace(1530, sB1, 16)])
    nSD2 = len(sd2_s)
    G = patch2d(np.column_stack([sd2_s, np.full(nSD2, CZ)]), top2d(sd2_s),
                vcol(sAP, CZ, frB), vcol(sB1, CZ, frB), lift_side)
    mb.grid(G, M_PAINT, tag='side')
    side_top3.append(G[:, -1])
    crease_mid.append(G[:, 0])

    # ---- SE: above the rear arch
    thB1, thB2 = theta_at(AR, CZ), np.pi - theta_at(AR, CZ)
    nSE = 15
    archR_top = arch_pts(AR, thB2, thB1, nSE)
    G = patch2d(archR_top, top2d(archR_top[:, 0]), vcol(sB1, CZ, frB), vcol(sB2, CZ, frB), lift_side)
    mb.grid(G, M_PAINT, tag='side')
    side_top3.append(G[:, -1])
    archR_top3 = G[:, 0]

    # ---- SF: rear quarter, split at s=3990 where the black tail band wraps
    # around the corner (rows aligned to the band top at z=812)
    def s_tail(z):
        return P.S_TAIL - (np.asarray(z, float) - CZ) * (95.0 / 350.0)
    S_WRAP, Z_BAND = 3990.0, 812.0
    zt_w = float(P.side_top(S_WRAP))
    col_w = np.column_stack([np.full(6, S_WRAP), [CZ, 650.0, 725.0, Z_BAND, (Z_BAND + zt_w) / 2 + 8, zt_w]])
    sfa_top_s = np.concatenate([np.linspace(sB2, sQ, 8)[:-1], np.linspace(sQ, S_WRAP, 4)])
    nSFa = len(sfa_top_s)
    G = patch2d(np.column_stack([np.linspace(sB2, S_WRAP, nSFa), np.full(nSFa, CZ)]),
                top2d(sfa_top_s), vcol(sB2, CZ, frB), col_w, lift_side)
    mb.grid(G, M_PAINT, tag='side')
    side_top3.append(G[:, -1])
    crease_rear_a = G[:, 0]
    nSFb = 4
    sfb_top = top2d(np.linspace(S_WRAP, 4058.0, nSFb))
    zt_end = sfb_top[-1, 1]
    zr = np.array([CZ, 650.0, 725.0, Z_BAND, (Z_BAND + zt_end) / 2 + 8, zt_end])
    sf_right = np.column_stack([s_tail(zr), zr])
    sf_right[-1] = sfb_top[-1]
    G = patch2d(np.column_stack([np.linspace(S_WRAP, P.S_TAIL, nSFb), np.full(nSFb, CZ)]),
                sfb_top, col_w, sf_right, lift_side)
    mb.grid(G[:, :4], M_BLACK, tag='side')
    mb.grid(G[:, 3:], M_PAINT, tag='side')
    mb.mark_chain([mb.v(p) for p in G[:, 3]])
    mb.mark_chain([mb.v(p) for p in G[0, :4]])
    side_top3.append(G[1:, -1] if False else G[:, -1])
    crease_rear = np.vstack([crease_rear_a, G[1:, 0]])
    tail_edge_side = G[-1, :]          # rear corner of the quarter (bottom->top)
    nSF = len(crease_rear)

    # ---- SG: lower door (below crease, between the arches)
    nG = len(np.concatenate(crease_mid)) - 1
    crease_mid3 = np.vstack([crease_mid[0], crease_mid[1][1:]])
    thFz = theta_at(AF, CZ)
    leftF = np.vstack([np.column_stack([[AF['s'] + AF['r']] * 2, [P.ROCKER_Z, AF['z']]]),
                       arch_pts(AF, 0.0, thFz, 5)[1:]])
    thRz = np.pi - theta_at(AR, CZ)
    rightR = np.vstack([np.column_stack([[AR['s'] - AR['r']] * 2, [P.ROCKER_Z, AR['z']]]),
                        arch_pts(AR, np.pi, thRz, 5)[1:]])
    bot = np.column_stack([np.linspace(leftF[0, 0], rightR[0, 0], len(crease_mid3)),
                           np.full(len(crease_mid3), P.ROCKER_Z)])
    top2 = crease_mid3[:, [0, 2]]
    G = patch2d(bot, top2, leftF, rightR, lift_side, targets={'t': crease_mid3})
    mb.grid(G, M_LOWER, tag='side')
    rocker3 = G[:, 0]
    archF_rear3 = G[0, :]
    archR_front3 = G[-1, :]
    mb.mark_points_sharp(crease_mid3)

    # ---- SH: band behind the rear arch below the crease
    zb = 545.0
    th545 = theta_at(AR, zb)
    sh_left = arch_pts(AR, th545, theta_at(AR, CZ), 3)
    sh_bot_s = np.linspace(sh_left[0, 0], P.S_TAIL + 12, nSF)
    sh_right = np.column_stack([[P.S_TAIL + 12, P.S_TAIL], [zb, CZ]])
    sh_right = lin(sh_right[0], sh_right[1], 3)
    G = patch2d(np.column_stack([sh_bot_s, np.full(nSF, zb)]), crease_rear[:, [0, 2]],
                sh_left, sh_right, lift_side, targets={'t': crease_rear})
    mb.grid(G, M_LOWER, tag='side')
    rear_bumper_top3 = G[:, 0]
    tail_edge_low = G[-1, :]
    archR_low3 = G[0, :]
    mb.mark_points_sharp(crease_rear)
    mb.mark_points_sharp(crease_front)

    side_top_all = np.vstack([side_top3[0]] + [x[1:] for x in side_top3[1:]])
    info['side_top'] = side_top_all

    # ------------------------------------------------------------ top region
    # outer strip TO: from the nose to the A-pillar foot along the shoulder
    to_outer = np.vstack([side_top3[0], side_top3[1][1:], side_top3[2][1:], side_top3[3][1:]])
    n_to = len(to_outer)
    s_out = to_outer[:, 0]
    S_WS_C, S_WS_O, W_WS_O = 1318.0, 1405.0, float(P.w_sh(1405.0))

    def s_ws(w):
        return S_WS_C + (S_WS_O - S_WS_C) * (np.asarray(w, float) / W_WS_O) ** 2

    s_in = s_out.copy()
    s_in[-1] = S_WS_O
    to_inner2 = np.column_stack([s_in, P.w_sh(s_in)])
    to_inner2[-1, 1] = W_WS_O
    nv_to = 3
    left2 = lin([sF, P.w_sh(sF)], [sF, to_outer[0, 1]], nv_to)
    right2 = lin(to_inner2[-1], to_outer[-1, :2], nv_to)
    G = patch2d(to_inner2, to_outer[:, :2], left2, right2, lift_top,
                targets={'t': to_outer})
    mb.grid(G, M_PAINT, tag='top', flip=True)
    mb.mark_chain([mb.v(p) for p in to_outer])
    to_inner3 = G[:, 0]
    apillar_foot = G[-1, :]                 # inner -> outer
    to_front = G[0, :]

    # lid hole: s from sF to sL between the hood edge (w=372) and w_sh
    W_HOOD = 372.0
    k_lid = int(np.argmin(np.abs(s_out - sL)))
    assert abs(s_out[k_lid] - sL) < 1e-6
    lid_outer3 = to_inner3[:k_lid + 1]
    # TF: fender flat behind the lid
    tf_outer = to_inner3[k_lid:]
    m = len(tf_outer)
    s_hood_end = float(s_ws(W_HOOD))
    tf_s_in = sL + (tf_outer[:, 0] - sL) * (s_hood_end - sL) / (tf_outer[-1, 0] - sL)
    tf_inner2 = np.column_stack([tf_s_in, np.full(m, W_HOOD)])
    nv_tf = 6
    ws_w = np.linspace(W_HOOD, W_WS_O, nv_tf)
    tf_rear2 = np.column_stack([s_ws(ws_w), ws_w])
    tf_front2 = lin([sL, W_HOOD], [sL, P.w_sh(sL)], nv_tf)
    G = patch2d(tf_inner2, tf_outer[:, :2], tf_front2, tf_rear2, lift_top,
                targets={'t': tf_outer})
    mb.grid(G, M_PAINT, tag='top', flip=True)
    tf_inner3 = G[:, 0]
    ws_base_outer = G[-1, :]                # w 372 -> 666
    lid_rear3 = G[0, :]

    # lid inner edge (hood side) shares s-values with the lid outer edge
    lid_s = lid_outer3[:, 0]
    lid_inner3 = lift_top(np.column_stack([lid_s, np.full(len(lid_s), W_HOOD)]))
    hood_outer3 = np.vstack([lid_inner3, tf_inner3[1:]])
    n_h = len(hood_outer3)
    s_c = sF + (hood_outer3[:, 0] - sF) * (S_WS_C - sF) / (hood_outer3[-1, 0] - sF)
    hood_c2 = np.column_stack([s_c, np.zeros(n_h)])
    nv_h = 7
    hw = np.linspace(0, W_HOOD, nv_h)
    hood_rear2 = np.column_stack([s_ws(hw), hw])
    hood_front2 = np.column_stack([np.full(nv_h, sF), hw])
    G = patch2d(hood_c2, hood_outer3[:, :2], hood_front2, hood_rear2, lift_top,
                targets={'t': hood_outer3})
    mb.grid(G, M_PAINT, tag='top', flip=True)
    ws_base_inner = G[-1, :]                # w 0 -> 372
    hood_front3 = G[0, :]
    ws_base = np.vstack([ws_base_inner, ws_base_outer[1:]])
    info['ws_base'] = ws_base
    info['lid'] = dict(inner=lid_inner3, outer=lid_outer3, rear=lid_rear3)

    # ------------------------------------------------------------ greenhouse
    # roof edge: intersection of the roof crown and the glass tumble-home
    def roof_edge_at(s):
        w = 525.0
        for _ in range(20):
            z = float(P.Z_roof(s, w))
            w = float(P.W_gh(s, z))
        return np.array([s, w, z])

    S_RF, S_RR = 2030.0, 2985.0
    RFo = roof_edge_at(S_RF)
    WSt = np.array([1988.0, 505.0, 1300.0])
    WSb = ws_base[-1]
    APo = apillar_foot[-1]
    # A-pillar strip
    n_ap = 9
    ap_in = curve([WSb, (WSb + WSt) / 2 + np.array([0, 4.0, 6.0]), WSt], n_ap)
    sz0, sz1 = np.array([APo[0], APo[2]]), np.array([RFo[0], RFo[2]])
    ap_out2 = lin(sz0, sz1, n_ap)
    ap_out = lift_gh(ap_out2)
    ap_out[0] = APo
    ap_top = lin(WSt, RFo, 3)
    ap_top[1] += np.array([-4.0, 0, 8.0])
    G = coons(ap_in, ap_out, apillar_foot, ap_top)
    mb.grid(G, M_PAINT, tag='gh')
    mb.mark_chain([mb.v(p) for p in ap_in])
    info['ap_in'] = ap_in

    # roof
    n_re = 14
    roof_edge = np.array([roof_edge_at(s) for s in np.linspace(S_RF, S_RR, n_re)])
    HG_TO = np.array([3112.0, 476.0, 1288.0])
    roof_outer = np.vstack([roof_edge, curve([roof_edge[-1], (roof_edge[-1] + HG_TO) / 2 +
                                              np.array([0, 4, 6]), HG_TO], 4)[1:]])
    nr = len(roof_outer)
    nv_r = 8
    ws_top = np.vstack([lin([1975.0, 0, 1318.0], WSt, nv_r - 2), ap_top[1:]])
    ws_top[:nv_r - 2, 2] = P.Z_roof(ws_top[:nv_r - 2, 0], ws_top[:nv_r - 2, 1]) - 2
    ws_top[:nv_r - 2, 0] = 1975.0 + 13.0 * (ws_top[:nv_r - 2, 1] / 505.0) ** 2
    hg_top = lin([3112.0, 0, 1300.0], HG_TO, nv_r)
    hg_top[:, 2] = P.Z_roof(hg_top[:, 0], hg_top[:, 1])
    roof_c2 = np.column_stack([np.linspace(1975.0, 3112.0, nr), np.zeros(nr)])
    G = patch2d(roof_c2, roof_outer[:, :2], ws_top[:, :2], hg_top[:, :2], lift_roof,
                targets={'t': roof_outer, 'l': ws_top, 'r': hg_top})
    mb.grid(G, M_PAINT, tag='roof', flip=True)
    info['ws_top'] = ws_top
    info['hg_top'] = hg_top
    mb.mark_chain([mb.v(p) for p in roof_edge])

    # windows (side view outlines) ----------------------------------------
    door_glass2 = np.array([
        [1735, 866], [2200, 868], [2604, 871], [2598, 1000], [2588, 1150], [2580, 1262],
        [2400, 1266], [2200, 1262], [2120, 1250], [2050, 1210], [1950, 1145], [1850, 1080],
        [1735, 1005]])
    q_glass2 = np.array([
        [2788, 895], [3100, 902], [3400, 909], [3630, 916], [3680, 925], [3694, 940],
        [3600, 1010], [3450, 1120], [3300, 1200], [3150, 1252], [3000, 1268], [2850, 1272],
        [2720, 1270], [2706, 1255], [2745, 1070]])
    door_glass3 = _densify(lift_gh, door_glass2, 85.0)
    q_glass3 = _densify(lift_gh, q_glass2, 85.0)
    info['door_glass'] = door_glass3
    info['door_glass_2d'] = door_glass2
    info['q_glass_2d'] = q_glass2
    info['q_glass'] = q_glass3

    # C-pillar boundary on the greenhouse surface (quarter frame outer edge)
    cp2 = np.array([[S_RR, roof_edge[-1][2]], [3150, 1278], [3320, 1225], [3480, 1135],
                    [3620, 1035], [3700, 975], [sQ, float(P.side_top(sQ))]])
    cp_line = lift_gh(_densify2(cp2, 70.0))
    cp_line[0] = roof_edge[-1]
    st = side_top_all
    k_ap = int(np.argmin(np.abs(st[:, 0] - sAP)))
    k_q = int(np.argmin(np.abs(st[:, 0] - sQ)))
    cp_line[-1] = st[k_q]
    belt = st[k_ap:k_q + 1]
    outer_loop = np.vstack([ap_out, roof_edge[1:], cp_line[1:], belt[::-1][1:-1]])
    gh_proj = lambda p: np.array([p[0], p[2]])
    stn = [(s, z) for s in np.arange(1500, 3800, 90) for z in np.arange(880, 1300, 70)]
    fill_region(mb, [outer_loop, door_glass3, q_glass3], gh_proj, lift_gh, M_BLACK,
                tag='gh', steiner=stn)
    # B-pillar / frame shading split at the beltline
    mb.mark_chain([mb.v(p) for p in belt])

    # C-pillar ---------------------------------------------------------------
    HG_BO = np.array([3856.0, 588.0, 968.0])
    LIP_RO = np.array([4052.0, 640.0, 940.0])
    tail_top_side = st[-1]
    cp_outer = np.vstack([cp_line, st[k_q + 1:]])
    mb.mark_chain([mb.v(p) for p in st[k_q:]])
    n_cp = len(cp_outer)
    hg_edge = curve([HG_TO, HG_TO + (HG_BO - HG_TO) * 0.5 + np.array([0, 6, 0]), HG_BO], n_cp - 2)
    cp_inner = np.vstack([hg_edge, lin(HG_BO, LIP_RO, 3)[1:]])
    cp_top = roof_outer[n_re - 1:][::1]
    nv_cp = len(cp_top)
    cp_bottom = curve([tail_top_side, (tail_top_side + LIP_RO) / 2 + np.array([0, 6, 8]), LIP_RO], nv_cp)
    G = coons(cp_outer, cp_inner, cp_top, cp_bottom)
    mb.grid(G, M_PAINT, tag='cp', flip=True)
    info['hg_side'] = hg_edge

    # hatch lip -------------------------------------------------------------
    nv_lip = 5
    hg_bot = lin([3856.0, 0, 975.0], HG_BO, nv_r)
    lip_rear = lin([4052.0, 0, 945.0], LIP_RO, nv_r)
    lip_c = curve([[3856.0, 0, 975.0], [3955, 0, 966.0], [4052.0, 0, 945.0]], nv_lip)
    lip_o = curve([HG_BO, (HG_BO + LIP_RO) / 2 + np.array([0, 3, 2]), LIP_RO], nv_lip)
    G = coons(hg_bot, lip_rear, lip_c, lip_o)
    mb.grid(G, M_PAINT, tag='lip')
    info['hg_bot'] = hg_bot
    info['hg_c'] = (np.array([3112.0, 0, 1300.0]), np.array([3856.0, 0, 975.0]))

    # tail: white hatch skirt above z=812, black lamp band below -------------
    tail_top = np.vstack([lip_rear, cp_bottom[::-1][1:]])        # centre -> side corner
    ZB = 812.0

    def s_rear(w, z):
        return P.S_TAIL + 12 - (z - 545.0) * (105.0 / 400.0) - 0.00003 * w * w

    def lift_rear(G2):
        w, z = G2[..., 0], G2[..., 1]
        return np.stack([s_rear(w, z), w, z], axis=-1)
    rear_proj = lambda p: np.array([p[1], p[2]])
    k_b = 3                                           # index of z=812 on the corner
    corner_hi = tail_edge_side[::-1][:len(tail_edge_side) - k_b]   # top -> 812
    w_c = corner_hi[-1][1]
    band_line = lift_rear(np.column_stack([np.linspace(w_c, 0, 9), np.full(9, ZB)]))
    band_line[0] = corner_hi[-1]
    cl_hi = lift_rear(np.column_stack([np.zeros(4), np.linspace(ZB, 945.0, 4)]))[1:-1]
    upper = np.vstack([tail_top, corner_hi[1:], band_line[1:], cl_hi])
    stn = [(w, z) for w in np.arange(50, 720, 95) for z in np.arange(840, 940, 55)]
    fill_region(mb, [upper], rear_proj, lift_rear, M_PAINT, tag='tail', steiner=stn)
    mb.mark_chain([mb.v(p) for p in band_line])

    corner_lo = np.vstack([tail_edge_side[k_b::-1], tail_edge_low[::-1][1:]])   # 812 -> 545
    bot_w = np.linspace(corner_lo[-1][1], 0, 9)[1:]
    bot = np.column_stack([np.full(len(bot_w), P.S_TAIL + 12), bot_w, np.full(len(bot_w), 545.0)])
    info['tail_bottom'] = bot
    PW, PZ0, PZ1, PD = 270.0, 562.0, 738.0, 14.0
    rec2 = np.array([[0, PZ0], [PW * 0.5, PZ0], [PW, PZ0], [PW, (PZ0 + PZ1) / 2], [PW, PZ1],
                     [PW * 0.5, PZ1], [0, PZ1]])
    rec3 = lift_rear(rec2)
    cl_lo = lift_rear(np.column_stack([np.zeros(3), [PZ1, (PZ1 + ZB) / 2, ZB]]))
    # outer loop: centre(812) -> corner -> down to 545 -> along the bottom to
    # the centre -> up the centreline, around the plate recess, up to 812
    loop = np.vstack([band_line[::-1][:-1], corner_lo, bot, rec3, cl_lo[1:-1]])
    lamp2 = np.array([[292, 618], [700, 618], [704, 752], [296, 752]])
    lamp3 = _densify(lift_rear, lamp2, 50.0, closed=True)
    info['taillamp'] = lamp3
    stn = [(w, z) for w in np.arange(40, 720, 80) for z in np.arange(575, 810, 60)]
    fill_region(mb, [loop, lamp3], rear_proj, lift_rear, M_BLACK, tag='tail', steiner=stn)
    # plate recess (inset panel + walls)
    rec_in = rec3.copy()
    rec_in[:, 0] -= PD
    mb.grid(np.stack([rec3, rec_in], axis=1), M_BLACK, tag='tail')
    pan = np.stack([rec_in[[0, 1, 2]], rec_in[[6, 5, 4]]], axis=1)
    mb.grid(pan, M_BLACK, tag='tail')
    mb.mark_chain([mb.v(p) for p in rec3])
    info['tail_loop'] = loop
    info['plate'] = rec_in

    # nose ------------------------------------------------------------------
    # black recessed band under the hood front edge (centre) and under the
    # fender corner; the pop-up visors fill the part in between.
    for top_edge in (hood_front3, to_front):
        under = top_edge.copy()
        under[:, 0] = 168.0
        under[:, 2] = 648.0
        mb.grid(np.stack([top_edge, under], axis=1), M_BLACK, tag='nose', flip=True)
        low = under.copy()
        low[:, 2] = 585.0
        mb.grid(np.stack([under, low], axis=1), M_BLACK, tag='nose', flip=True)
    nose_top = np.vstack([hood_front3, to_front])
    info['nose_top'] = nose_top

    info['rocker'] = rocker3
    info['archF_top'] = archF_top3
    # full arch edges (front leg bottom -> over the top -> rear leg bottom);
    # body vertices where the body owns the edge, arch curve where a bumper does
    thf = np.pi - theta_at(AF, CZ)
    fr_lead = arch_pts(AF, np.pi, thf, 5)
    fr_lead = np.vstack([[[AF['s'] - AF['r'], AF['leg_z']]], fr_lead])
    fr_lead3 = lift_side(fr_lead)
    fr_lead3[:, 1] -= 2.0
    info['archF_edge'] = np.vstack([fr_lead3[:-1], archF_top3, archF_rear3[::-1][1:]])
    thr = theta_at(AR, 545.0)
    rr_tail = arch_pts(AR, thr, 0.0, 4)
    rr_tail = np.vstack([rr_tail, [[AR['s'] + AR['r'], AR['leg_z']]]])
    rr_tail3 = lift_side(rr_tail)
    rr_tail3[:, 1] -= 2.0
    info['archR_edge'] = np.vstack([archR_front3, archR_top3[1:], archR_low3[::-1][1:], rr_tail3[1:]])
    info['archR_top'] = archR_top3
    info['archF_rear'] = archF_rear3
    info['archR_front'] = archR_front3
    info['crease_front'] = crease_front
    info['rear_bumper_top'] = rear_bumper_top3

    # ---------------------------------------------------------- seal flanges
    # Short strips turned inward from every opening edge, so the gaps around
    # inset glass and between body and bumpers show black rubber instead of
    # the (culled) inside of the shell.
    def strip(poly, dirs, mat, depth=10.0):
        poly = np.asarray(poly, float)
        off = poly + np.asarray(dirs, float) * depth
        mb.grid(np.stack([poly, off], axis=1), mat, tag='flange')

    def unit(v):
        v = np.asarray(v, float)
        return v / np.linalg.norm(v)
    ws_poly = np.vstack([ws_base, info['ap_in'][1:], ws_top[:-2][::-1][1:]])
    strip(ws_poly, [unit([0.55, 0, -0.84])] * len(ws_poly), M_RUBBER)
    hg_poly = np.vstack([info['hg_top'], info['hg_side'][1:], info['hg_bot'][::-1][1:]])
    strip(hg_poly, [unit([-0.40, 0, -0.92])] * len(hg_poly), M_RUBBER)
    for key in ('door_glass', 'q_glass'):
        loop = np.vstack([info[key], info[key][:1]])
        t = loop[:, 2] - P.z_belt(loop[:, 0])
        dirs = [-unit([0.0, 1.0, 0.336 + 0.000866 * tt]) for tt in t]
        strip(loop, dirs, M_RUBBER)
    # body bottom edges above the bumpers: turn in and down
    cf = info['crease_front']
    strip(cf, [unit([0, -1.0, -0.45])] * len(cf), M_LOWER, depth=24.0)
    rb = np.vstack([info['rear_bumper_top'], info['tail_bottom']])
    dirs = []
    for k in range(len(rb)):
        a, b = rb[max(k - 1, 0)], rb[min(k + 1, len(rb) - 1)]
        tng = unit(b[:2] - a[:2])
        nin = np.array([tng[1], -tng[0]])          # inward in plan for this path
        dirs.append(unit([nin[0], nin[1], -0.45]))
    strip(rb, dirs, M_BLACK, depth=24.0)

    return mb, info


def _densify2(poly2, step):
    out = [poly2[0]]
    for a, b in zip(poly2[:-1], poly2[1:]):
        n = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        for k in range(1, n + 1):
            out.append(a + (b - a) * k / n)
    return np.array(out)


def _densify(lift, poly2, step, closed=True):
    poly2 = np.asarray(poly2, float)
    pts = np.vstack([poly2, poly2[:1]]) if closed else poly2
    d = _densify2(pts, step)
    if closed:
        d = d[:-1]
    return lift(d)
