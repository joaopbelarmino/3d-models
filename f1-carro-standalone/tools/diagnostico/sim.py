"""Pitch-plane (2D) model of the F1 car's vertical dynamics, built from the values in the .rbxl.

Not Roblox's solver: rigid-body + sequential-impulse contacts at 240 Hz, same masses,
geometry, springs, slider limits, collision clearances and elasticities as the file.
Goal: find which mechanism turns small track irregularities into vertical impulses.
"""
import math, random

G = 196.2
DT = 1 / 240

# ---------------- car data (from the file) ----------------
R_W = 1.4959                     # wheel radius
Z_F, Z_R = 6.097, -9.724         # axle positions along the car (chassis frame)
Y_WC = 0.748                     # wheel centre height in chassis frame at slider pos 0
GROUND_L = Y_WC - R_W            # wheel contact plane in chassis frame (-0.7476)
M_WF, M_WR = 2 * 6.870, 2 * 7.851            # unsprung, per axle (2 wheels)
# sprung parts: (mass, z, y) in chassis frame
SPRUNG = [(8.157, 0.0, 0.0), (0.595, -1.0, 0.6), (2 * 0.694, Z_F, 0.75),
          (1.5, 10.0, -0.2), (1.5, 10.0, -0.2), (0.529, -11.5, 3.0), (0.15, 1.5, 1.5)]
M_B = sum(m for m, _, _ in SPRUNG)
ZC = sum(m * z for m, z, _ in SPRUNG) / M_B
YC = sum(m * y for m, _, y in SPRUNG) / M_B
I_B = sum(m * ((z - ZC) ** 2 + (y - YC) ** 2) for m, z, y in SPRUNG) + 8.157 * 23.435 ** 2 / 12
M_TOT = M_B + M_WF + M_WR
# springs: lateral offset dx, vertical length at pos 0, k, c (per wheel), 2 per axle
K, FREE = 25000.0, 1.5                       # garage spawn tuning (applied by ScriptCar)
SPR_F = dict(dx=0.4987, dy0=1.4955, k=K, c=99.312, free=FREE)
SPR_R = dict(dx=0.0, dy0=1.4959, k=K, c=198.624, free=FREE)
LIM = 0.4986                                 # slider travel limit (|pos|)
# floor collision profile from the decoded Corpo hulls: (z, clearance at slider pos 0)
FLOOR = [(-12, .36), (-11, .34), (-10, .29), (-9, .31), (-8, .31), (-7, .30), (-6, .32), (-4, .31), (-3, .33),
         (-2, .33), (-1, .32), (0, .33), (1, .33), (2, .33), (3, .95), (11, 1.06)]
WING = [(8.1, .903), (9.5, .903), (11.0, .91), (11.8, .91)]   # AsaFrontal hull bottom
E_FLOOR = 0.5   # Corpo elasticity 0.5 weight 1 vs track elasticity 0 weight 0
E_WING = 0.5    # Plastic default


class Terrain:
    """Polyline y(x) with optional vertical micro-steps (vertical segments)."""
    def __init__(self, pts):
        self.p = pts  # list of (x, y), x non-decreasing (equal x = vertical step)

    def segs_near(self, x0, x1):
        p = self.p
        lo, hi = 0, len(p) - 1
        while lo < hi:  # first index with x >= x0 - 1
            mid = (lo + hi) // 2
            if p[mid][0] < x0 - 1: lo = mid + 1
            else: hi = mid
        i = max(0, lo - 1)
        while i < len(p) - 1 and p[i][0] <= x1 + 1:
            yield p[i], p[i + 1]
            i += 1

    def height(self, x):
        best = None
        for (a, b) in self.segs_near(x, x):
            if a[0] <= x <= b[0] and b[0] > a[0]:
                return a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])
        return self.p[-1][1]


def circle_contacts(ter, cx, cy, r):
    out = []
    for a, b in ter.segs_near(cx - r, cx + r):
        ax, ay = a; bx, by = b
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((cx - ax) * vx + (cy - ay) * vy) / L2))
        px, py = ax + t * vx, ay + t * vy
        dx, dy = cx - px, cy - py
        d = math.hypot(dx, dy)
        if d < r + 0.02:
            if d < 1e-9:
                nx, ny = -vy, vx; n = math.hypot(nx, ny); nx, ny = nx / n, ny / n
            else:
                nx, ny = dx / d, dy / d
            out.append((r - d, nx, ny))
    # keep the deepest contact per distinct normal
    out.sort(key=lambda c: -c[0])
    res = []
    for c in out:
        if all(abs(c[1] - o[1]) + abs(c[2] - o[2]) > 1e-3 for o in res):
            res.append(c)
        if len(res) == 2: break
    return res


def run(ter, v, *, downforce=True, e_wheel=0.15, limits='stops', throttle=0.0, brake=0.0,
        x0=-120.0, x_end=60.0, log=False, floor=True, mods=None):
    mods = mods or {}
    mwf, mwr = M_WF * mods.get('wheel_mass', 1), M_WR * mods.get('wheel_mass', 1)
    cmul = mods.get('damping', 1.0)
    e_floor = mods.get('e_floor', E_FLOOR)
    e_w = mods.get('e_wheel', e_wheel)
    clear_add = mods.get('ride', 0.0)
    # state: body CoM X,Y, pitch th; velocities; wheel vertical y, vy
    X = x0; vx = v
    # settle start: put car on terrain at x0
    gy = ter.height(X)
    Y = gy - GROUND_L + YC - 0.02          # slider pos ~0 start, slightly loaded
    th = 0.0; vY = 0.0; w = 0.0
    wh = {'F': dict(z=Z_F, m=mwf, s=SPR_F), 'R': dict(z=Z_R, m=mwr, s=SPR_R)}
    for k_, W in wh.items():
        W['y'] = Y - YC + Y_WC; W['vy'] = 0.0
    t = 0.0
    stats = dict(maxVyBody=0, maxRise=0, airborne=0.0, maxAir=0.0, floorHits=0, wingHits=0,
                 stopHits=0, maxWheelVy=0, minPos=9, maxPos=-9, firstJumpT=None)
    rows = []
    cur_air = 0.0
    base_h = None
    prev_floor = prev_wing = prev_stop = False
    while X < x_end:
        speed = vx
        # ---------- forces ----------
        FY = -M_B * G; TQ = 0.0
        if downforce:
            Fd = -2000.0 * min(1.0, speed / 400.0)
            FY += Fd * math.cos(th)
        else:
            Fd = 0.0
        # longitudinal: throttle / brake -> pitch torque on the body
        # drive: rear motor torque reacts on the body (nose up); inertia transfer
        if throttle:
            Tq = 2 * 5000 * throttle
            TQ += Tq                      # reaction torque on body (nose up)
            ax = Tq / R_W / M_TOT
            TQ += M_TOT * ax * (YC - GROUND_L)
        if brake:
            Tq = 2 * 2500 * brake + 2 * 2684 * brake
            TQ -= Tq
            ax = -Tq / R_W / M_TOT
            TQ += M_TOT * ax * (YC - GROUND_L)
        for k_, W in wh.items():
            s = W['s']; z = W['z']
            yb = Y + (Y_WC - YC) + th * (z - ZC)            # slider pos-0 point, world
            vb = vY + w * (z - ZC)
            pos = yb - W['y']                                # + = wheel below (droop)
            # spring top is above the wheel: vertical length = dy0 + pos (pos positive = wheel lower)
            dy = s['dy0'] + pos
            L = math.hypot(s['dx'], dy)
            dL = (vb - W['vy']) * dy / L
            T = 2 * (s['k'] * (L - s['free']) + s['c'] * cmul * dL)   # tension, 2 springs per axle
            Fv = T * dy / L                                  # pulls wheel up, body down
            W['F'] = Fv
            FY -= Fv
            TQ -= Fv * (z - ZC)
            W['pos'] = pos
        # integrate velocities
        vY += FY / M_B * DT
        w += TQ / I_B * DT
        for W in wh.values():
            W['vy'] += (W['F'] / W['m'] - G) * DT
        # ---------- constraints (sequential impulses) ----------
        contacts_w = {}
        for k_, W in wh.items():
            cx = X + (W['z'] - ZC)
            contacts_w[k_] = circle_contacts(ter, cx, W['y'], R_W)
        body_pts = []
        if floor:
            for z, c in FLOOR:
                body_pts.append((z, GROUND_L + c + clear_add, e_floor, 'floor'))
            for z, c in WING:
                body_pts.append((z, GROUND_L + c + clear_add, E_WING, 'wing'))
        floor_hit = wing_hit = stop_hit = False
        pre_vn = {}
        for it in range(10):
            # wheel-ground
            for k_, W in wh.items():
                for idx, (pen, nx, ny) in enumerate(contacts_w[k_]):
                    vn = vx * nx + W['vy'] * ny
                    key = (k_, idx)
                    if it == 0: pre_vn[key] = vn
                    target = -e_w * pre_vn[key] if pre_vn[key] < -1.0 else 0.0
                    target += max(0.0, pen - 0.005) * 0.2 / DT    # position recovery
                    if vn < target:
                        inv = nx * nx / M_TOT + ny * ny / W['m']
                        J = (target - vn) / inv
                        W['vy'] += J * ny / W['m']
                        vx += J * nx / M_TOT
            # slider limits / lock
            for k_, W in wh.items():
                z = W['z']
                yb = Y + (Y_WC - YC) + th * (z - ZC)
                vb = vY + w * (z - ZC)
                pos = yb - W['y']; vrel = vb - W['vy']        # d(pos)/dt
                arm = z - ZC
                invm = 1 / M_B + arm * arm / I_B + 1 / W['m']
                if limits == 'locked':
                    target = -(pos - W.get('lockpos', pos)) * 0.2 / DT
                    W.setdefault('lockpos', pos)
                    J = (target - vrel) / invm
                elif limits == 'stops':
                    J = 0.0
                    if pos < -LIM and vrel < 0:              # full compression (bump stop)
                        J = (0 - vrel + (-LIM - pos) * 0.2 / DT) / invm; stop_hit = True
                    elif pos > LIM and vrel > 0:             # full droop
                        J = (0 - vrel - (pos - LIM) * 0.2 / DT) / invm
                else:
                    J = 0.0
                if J:
                    vY += J / M_B; w += J * arm / I_B; W['vy'] -= J / W['m']
            # body points vs ground (floor / wing)
            for z, yl, e, kind in body_pts:
                py = Y + (yl - YC) + th * (z - ZC)
                px = X + (z - ZC)
                gyp = ter.height(px)
                pen = gyp - py
                if pen > -0.01:
                    vp = vY + w * (z - ZC)
                    key = ('b', z)
                    if it == 0: pre_vn[key] = vp
                    target = -e * pre_vn[key] if pre_vn[key] < -1.0 else 0.0
                    target += max(0.0, pen) * 0.2 / DT
                    if vp < target:
                        arm = z - ZC
                        J = (target - vp) / (1 / M_B + arm * arm / I_B)
                        vY += J / M_B; w += J * arm / I_B
                        if kind == 'floor': floor_hit = True
                        else: wing_hit = True
        # speed keeping (the driver holds speed unless braking/accelerating test)
        vx += (v - vx) * min(1.0, 5 * DT)
        # ---------- integrate positions ----------
        X += vx * DT; Y += vY * DT; th += w * DT
        for W in wh.values():
            W['y'] += W['vy'] * DT
        t += DT
        # ---------- stats ----------
        grounded = sum(1 for k_ in wh if contacts_w[k_] and min(c[0] for c in contacts_w[k_]) > -0.03)
        if X - (Z_F - ZC) > -40 and base_h is None:
            base_h = Y - ter.height(X)
        if floor_hit and not prev_floor: stats['floorHits'] += 1
        if wing_hit and not prev_wing: stats['wingHits'] += 1
        if stop_hit and not prev_stop: stats['stopHits'] += 1
        prev_floor, prev_wing, prev_stop = floor_hit, wing_hit, stop_hit
        if X > -30:
            stats['maxVyBody'] = max(stats['maxVyBody'], vY - vx * slope_at(ter, X))
            for W in wh.values():
                stats['maxWheelVy'] = max(stats['maxWheelVy'], W['vy'] - vx * slope_at(ter, X))
                stats['minPos'] = min(stats['minPos'], W['pos']); stats['maxPos'] = max(stats['maxPos'], W['pos'])
            if base_h is not None:
                rise = (Y - ter.height(X)) - base_h
                stats['maxRise'] = max(stats['maxRise'], rise)
            if grounded == 0:
                cur_air += DT; stats['airborne'] += DT
                stats['maxAir'] = max(stats['maxAir'], cur_air)
                if stats['firstJumpT'] is None and cur_air > 0.03: stats['firstJumpT'] = (round(t, 3), round(X, 1))
            else:
                cur_air = 0.0
        if log:
            rows.append(dict(t=round(t, 4), x=round(X, 3), speed=round(vx, 2), vyBody=round(vY, 3),
                             vyWheelF=round(wh['F']['vy'], 3), vyWheelR=round(wh['R']['vy'], 3),
                             posF=round(wh['F']['pos'], 4), posR=round(wh['R']['pos'], 4),
                             springF=round(math.hypot(SPR_F['dx'], SPR_F['dy0'] + wh['F']['pos']), 4),
                             springR=round(SPR_R['dy0'] + wh['R']['pos'], 4),
                             wheelAngVel=round(vx / R_W, 2), downforce=round(Fd, 1), steer=0,
                             pitchDeg=round(math.degrees(th), 3), grounded=grounded,
                             floor=int(floor_hit), wing=int(wing_hit), stop=int(stop_hit)))
    return stats, rows


def slope_at(ter, x):
    return (ter.height(x + 0.5) - ter.height(x - 0.5))


# ---------------- terrain library ----------------
def flat():
    return Terrain([(-1000, 0.0), (1000, 0.0)])

def kink(deg, smooth=0.0):
    """slope changes from 0 to `deg` at x=0 (positive = uphill / sag, negative = crest)."""
    s = math.tan(math.radians(deg))
    pts = [(-1000, 0.0)]
    if smooth > 0:
        n = 40
        for i in range(n + 1):
            x = smooth * i / n
            pts.append((x, s * x * x / (2 * smooth)))
        x1, y1 = pts[-1]
        pts.append((x1 + 1000, y1 + s * 1000))
    else:
        pts += [(0.0, 0.0), (1000, s * 1000)]
    return Terrain(pts)

def ramp(deg, length=30.0, smooth=0.0):
    """flat -> slope `deg` for `length` -> flat (up if deg>0, down if deg<0)."""
    s = math.tan(math.radians(deg))
    if smooth <= 0:
        return Terrain([(-1000, 0.0), (0.0, 0.0), (length, s * length), (1000, s * length)])
    pts = [(-1000, 0.0)]
    n = 30
    for i in range(n + 1):
        x = smooth * i / n; pts.append((x, s * x * x / (2 * smooth)))
    xa, ya = pts[-1]
    xb = xa + length; yb = ya + s * length
    for i in range(1, n + 1):
        x = smooth * i / n; pts.append((xb + x, yb + s * x - s * x * x / (2 * smooth)))
    xe, ye = pts[-1]; pts.append((1000, ye))
    return Terrain(pts)

def step(h):
    """vertical lip of height h at x=0 (h>0 up)."""
    return Terrain([(-1000, 0.0), (0.0, 0.0), (0.0, h), (1000, h)])

def facets(seg_len, kink_sd_deg, lip_sd, seed=1, length=200.0):
    rnd = random.Random(seed)
    pts = [(-1000, 0.0), (-20.0, 0.0)]
    x, y, sl = -20.0, 0.0, 0.0
    while x < length:
        sl += math.radians(rnd.gauss(0, kink_sd_deg))
        sl = max(-0.05, min(0.05, sl)) * 0.9
        nx = x + seg_len; ny = y + math.tan(sl) * seg_len
        lip = rnd.gauss(0, lip_sd) if lip_sd else 0.0
        pts.append((nx, ny)); pts.append((nx, ny + lip))
        x, y = nx, ny + lip
    pts.append((x + 1000, y))
    return Terrain(pts)
