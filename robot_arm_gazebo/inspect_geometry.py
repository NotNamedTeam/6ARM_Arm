from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
FREECAD = ROOT.parents[1] / 'tools/freecad/squashfs-root/usr/lib'
sys.path.insert(0, str(FREECAD))
import FreeCAD
import Mesh
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

out = ROOT / 'inspection'
out.mkdir(exist_ok=True)
for prefix in ('BASE', 'AXIS1', 'AXIS2', 'AXIS3', 'WRIST', 'GRIPPER'):
    paths = sorted((ROOT / 'meshes').glob(prefix + '_*.stl'))
    fig, axs = plt.subplots(len(paths), 3, figsize=(15, 3.5 * len(paths)), squeeze=False)
    for row, path in enumerate(paths):
        mesh = Mesh.Mesh(str(path))
        points, faces = mesh.Topology
        v = np.asarray([[p.x, p.y, p.z] for p in points])
        f = np.asarray(faces)
        n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        edges = {}
        for i, triangle in enumerate(f):
            for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
                edges.setdefault(tuple(sorted((a, b))), []).append(i)
        crease = [edge for edge, fs in edges.items() if len(fs) != 2 or np.dot(n[fs[0]], n[fs[1]]) < .995]
        for col, (a, b) in enumerate(((0, 1), (0, 2), (2, 1))):
            ax = axs[row, col]
            ax.add_collection(LineCollection([v[list(e)][:, [a, b]] for e in crease], linewidths=.35, colors='#174663'))
            ax.autoscale()
            ax.set_aspect('equal')
            ax.grid(alpha=.2)
            ax.set_xlabel('XYZ'[a] + ' (mm)')
            ax.set_ylabel('XYZ'[b] + ' (mm)')
            ax.set_title(path.stem.replace('_-_', ' / '), fontsize=9)
    fig.tight_layout()
    fig.savefig(out / (prefix + '.png'), dpi=120)
    plt.close(fig)
