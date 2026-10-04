"""Measured AE86 Sprinter Trueno (3-door, zenki) profiles.

All numbers are millimetres in car coordinates (s from the front bumper tip,
w lateral half width, z height).  They come from digitising the supplied
blueprint (length 4205, width 1625, height 1335, wheelbase 2400) and were
cross-checked against the reference photos.
"""
import numpy as np
from geom import spline1d, lin1d, smoothstep

LENGTH, WIDTH, HEIGHT, WHEELBASE = 4205.0, 1625.0, 1335.0, 2400.0
S_FA, S_RA = 863.0, 3263.0              # axle stations
TRACK_F, TRACK_R = 1355.0, 1345.0
TIRE_R = 296.0                          # 185/60R14-ish on 14" rim
CREASE_Z = 590.0                        # waist crease (white/black split)
ROCKER_Z = 250.0                        # bottom of the painted body side
SKIRT_Z = 172.0                         # bottom of the side skirt

ARCH_F = dict(s=873.0, z=350.0, r=342.0, leg_z=238.0)
ARCH_R = dict(s=3255.0, z=350.0, r=328.0, leg_z=238.0)

S_NOSE = 143.0                          # hood / fender leading edge
S_TAIL = 4148.0                         # rear face of the body (above bumper)

# ---------------------------------------------------------------- top
# hood / fender-top height along the car (includes the rolled nose)
z_hood = spline1d(
    [143, 150, 160, 175, 195, 240, 311, 450, 603, 750, 896, 1090, 1236, 1300, 1420, 1470],
    [655, 672, 688, 703, 714, 732, 752, 783, 816, 846, 875, 905, 930, 937, 942, 943])

# plan width of the body side at crease height (no arch flares)
W_base = spline1d(
    [143, 150, 175, 220, 330, 430, 530, 700, 900, 1100, 1300, 2000, 2600, 2900, 3200,
     3450, 3550, 3700, 3850, 4000, 4100, 4148],
    [682, 700, 714, 726, 742, 755, 767, 780, 787, 791, 794, 795, 795, 794, 790,
     783, 776, 768, 759, 745, 731, 720])

W_SH0 = 633.0      # pop-up lid outer edge / fender-top flat boundary at nose


def w_sh(s):
    return W_SH0 + (np.asarray(s, float) - 143.0) * 0.026


def nose_fade(s):
    return smoothstep(146.0, 330.0, s)


def fender_drop(s):
    """Height the fender top falls from the flat part to the shoulder edge."""
    return 4.0 + 22.0 * nose_fade(s)


def crown(s, w):
    w = np.minimum(np.asarray(w, float), 650.0)
    return -12.0 * (w / 650.0) ** 2 * smoothstep(150.0, 300.0, s)


def w_edge(s):
    """Plan position of the fender shoulder edge."""
    return W_base(s) - (8.0 + 22.0 * nose_fade(s))


def Z_top(s, w):
    """Hood + fender-top surface height."""
    s = np.asarray(s, float)
    w = np.asarray(w, float)
    z = z_hood(s) + crown(s, w)
    ws, we = w_sh(s), w_edge(s)
    t = np.clip((w - ws) / np.maximum(we - ws, 1.0), 0.0, 1.0)
    return z - fender_drop(s) * t ** 2.4


def z_edge(s):
    return Z_top(s, w_edge(s))


# ---------------------------------------------------------------- greenhouse
# beltline (bottom of the side glass) and the body shoulder below it
z_belt = spline1d([1440, 1514, 1723, 2100, 2610, 2780, 3200, 3650, 3720],
                  [905, 868, 862, 864, 867, 880, 893, 906, 912])
w_belt = spline1d([1440, 1600, 2600, 3000, 3400, 3720],
                  [744, 745, 745, 742, 735, 724])


def W_gh(s, z):
    """Greenhouse side surface (tumble-home of the glass)."""
    t = np.asarray(z, float) - z_belt(s)
    return w_belt(s) - 0.336 * t - 0.000433 * t * t


Z_ROOF_C = 1335.0


def Z_roof(s, w):
    s = np.asarray(s, float)
    w = np.asarray(w, float)
    long = lin1d([1975, 2150, 2400, 2700, 2900, 3040, 3120],
                 [1318, 1328, 1334, 1335, 1330, 1318, 1306])(s)
    return long - 0.000125 * w * w


# ---------------------------------------------------------------- side
def side_profile(t, roll_start=0.82, lean=0.62):
    """Normalised inward offset above the crease, t in [0,1]."""
    t = np.clip(np.asarray(t, float), 0, 1)
    r = np.clip((t - roll_start) / (1 - roll_start), 0, 1)
    return lean * t + (1 - lean) * r ** 1.8


def side_top(s):
    """z of the top boundary of the body side (shoulder edge / beltline)."""
    s = np.asarray(s, float)
    zf = z_edge(s)
    zb = z_belt(np.clip(s, 1514, 3720))
    # fender shoulder until the door, then the beltline
    k = smoothstep(1380.0, 1530.0, s)
    z = zf * (1 - k) + zb * k
    # behind the quarter glass the shoulder rises toward the tail top
    kr = smoothstep(3650.0, 4050.0, s)
    return z * (1 - kr) + 925.0 * kr


def side_top_w(s):
    s = np.asarray(s, float)
    wf = w_edge(s)
    wb = w_belt(np.clip(s, 1440, 3720))
    k = smoothstep(1380.0, 1530.0, s)
    w = wf * (1 - k) + wb * k
    kr = smoothstep(3650.0, 4050.0, s)
    return w * (1 - kr) + (W_base(s) - 40.0) * kr


def W_side(s, z):
    s = np.asarray(s, float)
    z = np.asarray(z, float)
    base = W_base(s)
    zt = side_top(s)
    wt = side_top_w(s)
    d_top = base - wt
    t = (z - CREASE_Z) / np.maximum(zt - CREASE_Z, 1.0)
    above = base - d_top * side_profile(t)
    dz = np.maximum(CREASE_Z - z, 0.0)
    below = base - 0.115 * dz - 0.00009 * dz * dz
    w = np.where(z >= CREASE_Z, above, below)
    return w + flare(s, z)


def flare(s, z):
    out = np.zeros(np.broadcast(s, z).shape)
    for a, amp in ((ARCH_F, 22.0), (ARCH_R, 26.0)):
        d = np.hypot(np.asarray(s, float) - a['s'], np.asarray(z, float) - a['z']) - a['r']
        f = amp * (1.0 - smoothstep(0.0, 120.0, d)) * (d > -40)
        f *= smoothstep(300.0, 470.0, z)
        out = out + f
    return out


def arch_curve(a, n, z_from=None, start='front'):
    """Points (s,z) along a wheel arch opening, front leg -> top -> rear leg."""
    zc, r, sc = a['z'], a['r'], a['s']
    legz = a['leg_z'] if z_from is None else z_from
    pts = [(sc - r, legz)]
    for k in range(0, 33):
        ang = np.pi - np.pi * k / 32
        pts.append((sc + r * np.cos(ang), zc + r * np.sin(ang)))
    pts.append((sc + r, legz))
    return np.array(pts)


def arch_z(a, s):
    """z of the arch opening at station s (upper half)."""
    ds = np.clip(np.asarray(s, float) - a['s'], -a['r'], a['r'])
    return a['z'] + np.sqrt(np.maximum(a['r'] ** 2 - ds ** 2, 0))


def arch_s_at(a, z, side):
    dz = z - a['z']
    ds = np.sqrt(max(a['r'] ** 2 - dz ** 2, 0.0))
    return a['s'] - ds if side == 'front' else a['s'] + ds
