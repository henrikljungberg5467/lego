"""Printable STL of single LDraw parts (millimetres, closed solid).

LDraw parts are visual models: their surfaces are built from primitives and often have small cracks
where those meet, so they are not closed solids. Here the part is voxelised (inside/outside by ray
parity along three axes, majority vote), turned back into a surface with marching cubes and
simplified. The part lies with its local Z axis vertical (a wheel or tyre lies flat on the bed).

With --halves the part is cut in two across its local Z axis (a tyre at its middle) and both halves
are laid out on one plate, each with its outer side down: a tyre's halves then print without
support and are glued together around the rim.

Usage: python3 tools/print_stl.py PART [out.stl] [--res 0.1] [--halves]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402
import ldraw as L  # noqa: E402

MM = 0.4  # mm per LDU


def solid(part, res_mm):
    """Boolean voxel grid of the part's interior, and the position of voxel (0,0,0) in LDU."""
    check.H = res_mm / MM
    tris = np.asarray(L.triangles(part + ".dat"), dtype=float).reshape(-1, 3, 3)
    lo, hi = tris.reshape(-1, 3).min(0) - 2 * check.H, tris.reshape(-1, 3).max(0) + 2 * check.H
    votes = sum(check._ray_fill(tris, lo, hi, ax).astype(np.uint8) for ax in range(3))
    return votes >= 2, lo


def mesh(part, res_mm=0.1, faces=150_000, half=None):
    """half=None: the whole part; 0 or 1: the half below or above the middle of its local Z extent."""
    import fast_simplification
    import trimesh
    from skimage import measure
    vol, lo = solid(part, res_mm)
    if half is not None:
        zc = lo[2] + (np.arange(vol.shape[2]) + 0.5) * check.H
        zmid = (zc[vol.any(axis=(0, 1))].min() + zc[vol.any(axis=(0, 1))].max()) / 2
        vol = vol.copy()
        vol[:, :, (zc > zmid) if half == 0 else (zc < zmid)] = False
    v = np.pad(vol, 1).astype(np.float32)
    verts, tri, _, _ = measure.marching_cubes(v, 0.5, spacing=(res_mm,) * 3)
    verts += (lo * MM) - res_mm * 0.5                     # voxel centres -> part coordinates (mm)
    # simplify, but never into an open or non-manifold surface: allow more triangles until it stays closed
    target = faces
    while True:
        if len(tri) > target:
            v2, t2 = fast_simplification.simplify(verts.astype(np.float32), tri.astype(np.int32), 1 - target / len(tri))
        else:
            v2, t2 = verts, tri
        m = trimesh.Trimesh(v2, t2, process=True)
        if m.is_watertight or len(tri) <= target:
            break
        target = int(target * 1.5)
    # turn over about X (LDraw -Y up -> +Y, Z -> -Z: no mirroring); local Z stays vertical, so a
    # wheel or tyre lies flat; then put it on the bed at the origin
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    if half is not None:
        # outer side down: the cut face (the flat ring with the largest area at one end) goes on top
        top = m.triangles_center[:, 2] > m.bounds[1][2] - 0.05
        bottom = m.triangles_center[:, 2] < m.bounds[0][2] + 0.05
        if m.area_faces[bottom].sum() > m.area_faces[top].sum():
            m.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    m.apply_translation(-m.bounds[0] * [0, 0, 1] - m.centroid * [1, 1, 0])
    m.fix_normals()
    return m


def report(m):
    n = m.face_normals
    a = m.area_faces
    bottom = m.triangles_center[:, 2] < m.bounds[0][2] + 0.3
    steep = (n[:, 2] < -np.cos(np.radians(45))) & ~bottom
    return (f"{len(m.faces)} triangles, closed solid: {m.is_watertight}, volume {m.volume / 1000:.1f} cm³, "
            f"size {' × '.join(f'{e:.1f}' for e in m.extents)} mm, "
            f"overhang over 45°: {100 * a[steep].sum() / a.sum():.0f} % of the surface")


def main():
    import trimesh
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    res = float(sys.argv[sys.argv.index("--res") + 1]) if "--res" in sys.argv else 0.1
    if "--res" in sys.argv:
        args.remove(str(sys.argv[sys.argv.index("--res") + 1]))
    part = args[0]
    out = args[1] if len(args) > 1 else f"{part}.stl"
    if "--halves" in sys.argv:
        halves = [mesh(part, res, 100_000, half=h) for h in (0, 1)]
        for h in halves:
            print("  half -", report(h))
        halves[1].apply_translation([halves[0].extents[0] + 6, 0, 0])
        m = trimesh.util.concatenate(halves)
        m.apply_translation([-m.bounds.mean(0)[0], -m.bounds.mean(0)[1], 0])
        m.export(out)
        print(out, f"- plate {' × '.join(f'{e:.1f}' for e in m.extents)} mm")
    else:
        m = mesh(part, res)
        m.export(out)
        print(out, "-", report(m))


if __name__ == "__main__":
    main()
