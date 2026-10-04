"""Small geometry toolkit used to build the AE86 from scratch.

Everything here is pure numpy: curves are sampled from control points,
surfaces are Coons patches between boundary curves, and a MeshBuilder welds
the patches into one mesh (with sharp-edge tags and per-face materials)
before it is handed to Blender.

Car coordinates used while modelling (millimetres):
    s = distance from the front bumper tip (front -> rear)
    w = lateral offset from the centreline (left side positive)
    z = height above the ground
`to_blender` converts to Blender metres with the nose pointing to -Y.
"""
import math
import numpy as np

S_FRONT_AXLE = 863.0
S_ORIGIN = 2063.0          # s that maps to Blender Y = 0 (wheelbase centre)


def to_blender(p):
    p = np.asarray(p, dtype=float)
    out = np.empty_like(p)
    out[..., 0] = p[..., 1] / 1000.0
    out[..., 1] = (p[..., 0] - S_ORIGIN) / 1000.0
    out[..., 2] = p[..., 2] / 1000.0
    return out


# ---------------------------------------------------------------- curves
def _catmull(pts, dense=24):
    """Centripetal Catmull-Rom through pts; returns a dense polyline."""
    pts = np.asarray(pts, dtype=float)
    if len(pts) < 3:
        t = np.linspace(0, 1, dense * max(1, len(pts) - 1) + 1)[:, None]
        return pts[0] * (1 - t) + pts[-1] * t
    ext = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]

        def tj(ti, a, b):
            return ti + max(np.linalg.norm(b - a), 1e-9) ** 0.5
        t0 = 0.0
        t1 = tj(t0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)
        ts = np.linspace(t1, t2, dense, endpoint=False)[:, None]
        a1 = (t1 - ts) / (t1 - t0) * p0 + (ts - t0) / (t1 - t0) * p1
        a2 = (t2 - ts) / (t2 - t1) * p1 + (ts - t1) / (t2 - t1) * p2
        a3 = (t3 - ts) / (t3 - t2) * p2 + (ts - t2) / (t3 - t2) * p3
        b1 = (t2 - ts) / (t2 - t0) * a1 + (ts - t0) / (t2 - t0) * a2
        b2 = (t3 - ts) / (t3 - t1) * a2 + (ts - t1) / (t3 - t1) * a3
        out.append((t2 - ts) / (t2 - t1) * b1 + (ts - t1) / (t2 - t1) * b2)
    out.append(pts[-1][None, :])
    return np.vstack(out)


def resample(poly, n, bias=None):
    """Arc-length resample a dense polyline to n points.

    bias: None (uniform) or a callable mapping [0,1]->[0,1] for clustering."""
    poly = np.asarray(poly, dtype=float)
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    L = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, 1, n)
    if bias is not None:
        t = np.array([bias(x) for x in t])
    target = t * L[-1]
    out = np.empty((n, poly.shape[1]))
    for k in range(poly.shape[1]):
        out[:, k] = np.interp(target, L, poly[:, k])
    out[0], out[-1] = poly[0], poly[-1]
    return out


def curve(pts, n, smooth=True, bias=None):
    pts = np.asarray(pts, dtype=float)
    dense = _catmull(pts) if smooth and len(pts) > 2 else _linear_dense(pts)
    return resample(dense, n, bias)


def _linear_dense(pts, per=40):
    pts = np.asarray(pts, dtype=float)
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        t = np.linspace(0, 1, per, endpoint=False)[:, None]
        out.append(a * (1 - t) + b * t)
    out.append(pts[-1][None])
    return np.vstack(out)


def ease_both(k=0.5):
    """Cluster samples toward both ends (k in 0..1, 0 = uniform)."""
    def f(t):
        return (1 - k) * t + k * (0.5 - 0.5 * math.cos(math.pi * t))
    return f


def ease_end(k=0.5):
    def f(t):
        return (1 - k) * t + k * math.sin(0.5 * math.pi * t)
    return f


def ease_start(k=0.5):
    def f(t):
        return (1 - k) * t + k * (1 - math.cos(0.5 * math.pi * t))
    return f


def spline1d(xs, ys):
    """Monotone-ish smooth 1D interpolator (Catmull-Rom on (x,y))."""
    pts = np.column_stack([xs, ys])
    dense = _catmull(pts, dense=64)
    order = np.argsort(dense[:, 0])
    dx, dy = dense[order, 0], dense[order, 1]

    def f(x):
        return np.interp(x, dx, dy)
    return f


def lin1d(xs, ys):
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)

    def f(x):
        return np.interp(x, xs, ys)
    return f


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- patches
def coons(bottom, top, left, right):
    """Coons patch. bottom/top: (nu,3) along u; left/right: (nv,3) along v.
    Corner order: bottom[0]=left[0], bottom[-1]=right[0], top[0]=left[-1],
    top[-1]=right[-1].  Returns grid (nu, nv, 3)."""
    bottom, top = np.asarray(bottom, float), np.asarray(top, float)
    left, right = np.asarray(left, float), np.asarray(right, float)
    nu, nv = len(bottom), len(left)
    assert len(top) == nu and len(right) == nv, (len(bottom), len(top), len(left), len(right))
    # use the arc-length fraction of each boundary as its parameter so that
    # uneven spacing on a boundary is carried into the interior smoothly
    def frac(c):
        d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))])
        return d / max(d[-1], 1e-9)
    ub, ut = frac(bottom), frac(top)
    vl, vr = frac(left), frac(right)
    P00, P10, P01, P11 = bottom[0], bottom[-1], top[0], top[-1]
    G = np.zeros((nu, nv, 3))
    for i in range(nu):
        for j in range(nv):
            v = (1 - ub[i]) * vl[j] + ub[i] * vr[j]
            u = (1 - vl[j]) * ub[i] + vl[j] * ut[i]
            Sc = (1 - v) * bottom[i] + v * top[i]
            Sd = (1 - u) * left[j] + u * right[j]
            B = ((1 - u) * (1 - v) * P00 + u * (1 - v) * P10 +
                 (1 - u) * v * P01 + u * v * P11)
            G[i, j] = Sc + Sd - B
    G[:, 0], G[:, -1], G[0, :], G[-1, :] = bottom, top, left, right
    return G


def loft(rows):
    """Grid from a list of equally sized curves (each a row along v)."""
    return np.stack([np.asarray(r, float) for r in rows], axis=0)


# ---------------------------------------------------------------- mesh
class MeshBuilder:
    """Accumulates quad grids / polygons with vertex welding."""

    def __init__(self, weld=0.05):
        self.verts = []
        self.vindex = {}
        self.faces = []
        self.fmat = []
        self.ftag = []
        self.sharp = set()
        self.weld = weld
        self.vtag = []

    def _key(self, p):
        q = self.weld
        return (round(p[0] / q), round(p[1] / q), round(p[2] / q))

    def v(self, p, tag=None):
        k = self._key(p)
        idx = self.vindex.get(k)
        if idx is None:
            idx = len(self.verts)
            self.vindex[k] = idx
            self.verts.append(np.array(p, float))
            self.vtag.append(set())
        if tag:
            self.vtag[idx].add(tag)
        return idx

    def grid(self, G, mat=0, flip=False, tag=None, sharp_u0=False, sharp_u1=False,
             sharp_v0=False, sharp_v1=False):
        nu, nv = G.shape[0], G.shape[1]
        ids = [[self.v(G[i, j], tag) for j in range(nv)] for i in range(nu)]
        for i in range(nu - 1):
            for j in range(nv - 1):
                q = [ids[i][j], ids[i + 1][j], ids[i + 1][j + 1], ids[i][j + 1]]
                if flip:
                    q = q[::-1]
                self.poly(q, mat, tag)
        if sharp_v0:
            self.mark_chain([ids[i][0] for i in range(nu)])
        if sharp_v1:
            self.mark_chain([ids[i][nv - 1] for i in range(nu)])
        if sharp_u0:
            self.mark_chain([ids[0][j] for j in range(nv)])
        if sharp_u1:
            self.mark_chain([ids[nu - 1][j] for j in range(nv)])
        return ids

    def poly(self, ids, mat=0, tag=None):
        # drop consecutive duplicates (degenerate corners)
        clean = []
        for i in ids:
            if not clean or clean[-1] != i:
                clean.append(i)
        if len(clean) > 1 and clean[0] == clean[-1]:
            clean.pop()
        if len(set(clean)) < 3:
            return
        self.faces.append(clean)
        self.fmat.append(mat)
        self.ftag.append(tag)

    def mark_chain(self, ids):
        for a, b in zip(ids[:-1], ids[1:]):
            if a != b:
                self.sharp.add((min(a, b), max(a, b)))

    def mark_points_sharp(self, pts):
        ids = [self.vindex.get(self._key(p)) for p in pts]
        ids = [i for i in ids if i is not None]
        self.mark_chain(ids)


def mirror_builder(mb, axis=1, center_tol=0.5):
    """Return a new MeshBuilder containing mb plus its mirror (w -> -w)."""
    out = MeshBuilder(mb.weld)
    remap_a, remap_b = {}, {}
    for i, p in enumerate(mb.verts):
        q = p.copy()
        if abs(q[axis]) < center_tol:
            q[axis] = 0.0
        remap_a[i] = out.v(q)
        out.vtag[remap_a[i]] |= mb.vtag[i]
        r = q.copy()
        r[axis] = -r[axis]
        remap_b[i] = out.v(r)
        out.vtag[remap_b[i]] |= mb.vtag[i]
    for f, m, t in zip(mb.faces, mb.fmat, mb.ftag):
        out.poly([remap_a[i] for i in f], m, t)
        out.poly([remap_b[i] for i in f][::-1], m, t)
    for a, b in mb.sharp:
        out.sharp.add(tuple(sorted((remap_a[a], remap_a[b]))))
        out.sharp.add(tuple(sorted((remap_b[a], remap_b[b]))))
    return out


def merge(dst, src, matmap=None, tag=None):
    """Append MeshBuilder src into dst (welding shared positions)."""
    idm = {}
    for i, p in enumerate(src.verts):
        idm[i] = dst.v(p, tag)
    for f, m, t in zip(src.faces, src.fmat, src.ftag):
        dst.poly([idm[i] for i in f], matmap.get(m, m) if matmap else m, tag or t)
    for a, b in src.sharp:
        dst.sharp.add(tuple(sorted((idm[a], idm[b]))))
    return dst
