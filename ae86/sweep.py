"""Plan-view sweep used for bumpers and skirts."""
import numpy as np
from geom import curve


def plan_normals(path):
    """Outward normals (in s,w) for a plan path running centre -> side."""
    path = np.asarray(path, float)
    T = np.gradient(path, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    return np.column_stack([-T[:, 1], T[:, 0]])


def sweep(path, profiles, normals=None):
    """path: (n,2) plan points (s,w); profiles: (n, m, 2) per-station lists of
    (outward offset, z).  Returns grid (n, m, 3)."""
    path = np.asarray(path, float)
    N = plan_normals(path) if normals is None else normals
    n, m = len(path), len(profiles[0])
    G = np.zeros((n, m, 3))
    for i in range(n):
        for j in range(m):
            o, z = profiles[i][j]
            G[i, j, 0] = path[i, 0] + N[i, 0] * o
            G[i, j, 1] = path[i, 1] + N[i, 1] * o
            G[i, j, 2] = z
    return G
