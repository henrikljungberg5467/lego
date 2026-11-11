"""Printable STL of single LDraw parts (millimetres, closed solid).

LDraw parts are visual models: their surfaces are built from primitives and often have cracks where
those meet (up to a few tenths of a millimetre where a 16-sided circle meets a 48-sided one), so
they are not closed solids. Here the surface is voxelised, the voxels are grown until the cracks
close, everything not reachable from outside is filled, and the solid is shrunk back by the same
amount (a morphological closing). Marching cubes turns it back into a surface, which is simplified
without letting it open. The part lies with its local Z axis vertical (a wheel or tyre lies flat).

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

# Connection geometry for printing. LDraw draws circles as 16-gons (a stud measures 4.71-4.80 mm across,
# a tube 6.28-6.40 mm) and its tubes 6.40 mm wide, where LEGO's are 6.51 mm: studs then miss the tubes by
# about 0.1 mm and are held by the walls alone. For printing, circles use the 48-gon primitives and studs,
# tubes and the solid posts of 1 x N parts get LEGO's diameters. `clutch` (mm) adds to all three, to tune
# the fit to a printer: the grip against tubes grows by `clutch`, against walls by half of it.
STUD_MM, TUBE_MM, POST_MM = 4.8, 6.51, 3.2
STUDS = ("stud.dat", "stud2.dat", "stud2a.dat")          # outer radius 6 LDU (stud2: hollow stud)
TUBES = ("stud4.dat", "stud4a.dat", "stud4h.dat", "stud4s.dat")
POSTS = ("stud3.dat", "stud3a.dat")


def print_triangles(name, clutch=0.0):
    """Like ldraw.triangles, with the connection geometry above."""
    from functools import lru_cache
    idx = L.lib_index()

    @lru_cache(maxsize=None)
    def tris(name):
        refs, t, quads = L.parsed(name)
        out = [t]
        if len(quads):
            out += [quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]]
        for _, M, sub in refs:
            if "/" not in sub and "48/" + sub in idx:
                sub = "48/" + sub
            if not L.find(sub):
                continue
            M = M.copy()
            radial = abs(M[0, 0])
            if name in STUDS and abs(radial - 6) < 1e-6:          # the stud's outside (radius 6 LDU)
                M[[0, 2], :3] *= (STUD_MM + clutch) / 2 / MM / 6
            elif name in TUBES and abs(radial - 8) < 1e-6:        # outer wall of the tube (radius 8 LDU)
                M[[0, 2], :3] *= (TUBE_MM + clutch) / 2 / MM / 8
            elif name in POSTS and abs(radial - 4) < 1e-6:        # the solid post (radius 4 LDU)
                M[[0, 2], :3] *= (POST_MM + clutch) / 2 / MM / 4
            st = tris(sub)
            if len(st):
                out.append((st.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]).reshape(-1, 3, 3))
        out = [o for o in out if len(o)]
        return np.concatenate(out) if out else np.zeros((0, 3, 3))

    return tris(name)


def solid(part, res_mm, close_mm=0.2, clutch=None):
    """Boolean voxel grid of the part's interior, and the position of voxel (0,0,0) in LDU.
    clutch=None: LDraw's geometry as it is; a number: printing geometry (see print_triangles)."""
    import trimesh
    from scipy import ndimage
    check.H = res_mm / MM                                  # voxel size in LDU (used by mesh() for the cut)
    raw = L.triangles(part + ".dat") if clutch is None else print_triangles(part + ".dat", clutch)
    tris = np.asarray(raw, dtype=float).reshape(-1, 3, 3)
    surf = trimesh.Trimesh(tris.reshape(-1, 3), np.arange(len(tris) * 3).reshape(-1, 3), process=True)
    pad = int(np.ceil(close_mm / res_mm)) + 2
    h = check.H
    lo = tris.reshape(-1, 3).min(0) - pad * h
    shape = np.ceil((tris.reshape(-1, 3).max(0) + pad * h - lo) / h).astype(int) + 1
    # surface voxels: points on every triangle at most half a voxel apart
    shell = np.zeros(shape, dtype=bool)
    tri = surf.triangles
    n_of = np.ceil(np.max(np.linalg.norm(tri - np.roll(tri, 1, axis=1), axis=2), axis=1) / (h / 2)).astype(int)
    for n in np.unique(n_of):
        a, b = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        keep = a + b <= n
        w = np.stack([a[keep], b[keep], n - a[keep] - b[keep]], axis=1) / max(n, 1)      # barycentric
        sel = tri[n_of == n]
        for chunk in np.array_split(sel, max(1, len(sel) * len(w) // 2_000_000)):
            pts = np.einsum("pk,tkd->tpd", w, chunk).reshape(-1, 3)
            idx = np.floor((pts - lo) / h).astype(int)
            shell[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    def closed(k):
        """Grow the surface by k voxels so cracks close, fill what the outside cannot reach, then let the
        outside flow back up to the surface voxels (6-connected, so it cannot cross them). Shrinking back
        by erosion instead would round every inner corner, such as the foot of a stud."""
        grown = ndimage.binary_dilation(shell, iterations=k) if k else shell
        outside = ~ndimage.binary_fill_holes(grown)
        for _ in range(k + 1):
            outside = ndimage.binary_dilation(outside) & ~shell
        return ~outside

    # the smallest closing that fills the part as well as the full one: none at all for most parts, whose
    # surfaces only have hairline cracks, so their inner corners stay sharp
    kmax = int(np.ceil(close_mm / res_mm))
    full = closed(kmax)
    for k in range(kmax):
        vol = closed(k)
        if vol.sum() >= 0.995 * full.sum():
            return vol, lo
    return full, lo


def engrave(vol, lo, text, height_mm=2.6, depth_mm=0.4):
    """Engrave `text` into the part's +Z side (LDraw), below the studs (y > 0), readable from outside."""
    from PIL import Image, ImageDraw, ImageFont
    h = check.H
    z = lo[2] + (np.arange(vol.shape[2]) + 0.5) * h
    y = lo[1] + (np.arange(vol.shape[1]) + 0.5) * h
    x = lo[0] + (np.arange(vol.shape[0]) + 0.5) * h
    filled_z = z[vol.any(axis=(0, 1))]
    face = filled_z.max()                                           # the outside of the +Z wall
    body = y[(y > 0) & vol.any(axis=(0, 2))]                        # side below the studs
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 200)
    box = font.getbbox(text)
    img = Image.new("L", (box[2] - box[0] + 20, box[3] - box[1] + 20), 0)
    ImageDraw.Draw(img).text((10 - box[0], 10 - box[1]), text, fill=255, font=font)
    rows = int(round(height_mm / MM / h))
    cols = int(round(rows * img.width / img.height))
    mask = np.array(img.resize((cols, rows), Image.LANCZOS)) > 110  # [row, col], row 0 at the top
    yc = (body.min() + body.max()) / 2                              # centre of the side, vertically
    xc = (x[vol.any(axis=(1, 2))].min() + x[vol.any(axis=(1, 2))].max()) / 2
    iy0 = int(np.argmin(np.abs(y - (yc - rows * h / 2))))           # LDraw -Y is up: row 0 = smallest y
    ix0 = int(np.argmin(np.abs(x - (xc + cols * h / 2))))           # seen from +Z, text runs towards -X
    k = (z > face - depth_mm / MM) & (z <= face + h)
    for r in range(rows):
        for c in np.nonzero(mask[r])[0]:
            vol[ix0 - c, iy0 + r, k] = False
    return vol


SIDE_GAP_MM = 0.04   # per side, as in Mecabricks' parts (LEGO's own are about 0.1)


def side_clearance(verts, part, gap=SIDE_GAP_MM, band=0.3):
    """Move the outer faces of the part's sides inwards, so that its outside measures a whole number of
    studs minus 2 * gap, on the axes where LDraw draws it exactly a whole number of studs long. Only
    points within `band` mm of an outer face move (studs, holes and the underside stay where they are)."""
    lo, hi = L.bbox(part + ".dat")
    for ax in (0, 2):                                         # LDraw X and Z: the horizontal axes
        n = (hi[ax] - lo[ax]) / 20
        if abs(n - round(n)) > 1e-3 or round(n) < 1:
            continue
        a, b = verts[:, ax].min(), verts[:, ax].max()
        target_a, target_b = lo[ax] * MM + gap, hi[ax] * MM - gap
        wa = np.clip(1 - (verts[:, ax] - a) / band, 0, 1)    # 1 on the outer face, 0 at band mm inside
        wb = np.clip(1 - (b - verts[:, ax]) / band, 0, 1)
        verts[:, ax] += wa * (target_a - a) - wb * (b - target_b)
    return verts


def mesh(part, res_mm=0.1, faces=150_000, half=None, up="z", clutch=None, label=None):
    """half=None: the whole part; 0 or 1: the half below or above the middle of its local Z extent.
    up="z": the part's local Z axis is vertical (wheels, tyres, gears, bushes lie flat);
    up="y": its LDraw up (-Y) is up (bricks and plates studs up, beams flat, axles and pins lying)."""
    import fast_simplification
    import trimesh
    from skimage import measure
    vol, lo = solid(part, res_mm, clutch=clutch)
    if label:
        vol = engrave(vol.copy(), lo, label)
    if half is not None:
        zc = lo[2] + (np.arange(vol.shape[2]) + 0.5) * check.H
        zmid = (zc[vol.any(axis=(0, 1))].min() + zc[vol.any(axis=(0, 1))].max()) / 2
        vol = vol.copy()
        vol[:, :, (zc > zmid) if half == 0 else (zc < zmid)] = False
    from scipy import ndimage
    # a light blur of the voxels gives a smoother surface, which simplifies without opening up
    v = ndimage.gaussian_filter(np.pad(vol, 2).astype(np.float32), 0.7)
    # surface voxels are solid all the way through, so the solid reaches about half a voxel past the
    # true surface; the level 0.75 of the blurred step (sigma 0.7 voxel) moves it back by that much
    verts, tri, _, _ = measure.marching_cubes(v, 0.75, spacing=(res_mm,) * 3)
    verts -= res_mm                                       # the extra padding voxel
    verts += (lo * MM) - res_mm * 0.5                     # voxel centres -> part coordinates (mm)
    if clutch is not None:
        verts = side_clearance(verts, part)
    # simplify without changing the topology (MeshLab's quadric edge collapse), so the surface stays one
    # closed solid; fast_simplification can pinch thin places into edges shared by four faces
    m = None
    if len(tri) > faces:
        try:
            import pymeshlab
            ms = pymeshlab.MeshSet()
            ms.add_mesh(pymeshlab.Mesh(np.asarray(verts, float), np.asarray(tri, np.int32)))
            ms.meshing_decimation_quadric_edge_collapse(targetfacenum=faces, preservetopology=True,
                                                        preservenormal=True, qualitythr=0.3, planarquadric=True)
            cur = ms.current_mesh()
            m = trimesh.Trimesh(cur.vertex_matrix(), cur.face_matrix(), process=True)
            if not m.is_watertight:
                m = None
        except ImportError:
            pass
    target = faces
    while m is None:                  # fallback: allow more triangles until the surface stays closed
        if len(tri) > target:
            v2, t2 = fast_simplification.simplify(verts.astype(np.float32), tri.astype(np.int32), 1 - target / len(tri))
        else:
            v2, t2 = verts, tri
        m = trimesh.Trimesh(v2, t2, process=True)
        if not m.is_watertight and len(tri) > target:
            m, target = None, int(target * 1.5)
    # rotate about X (never mirror): by 180° local Z stays vertical, by -90° LDraw -Y becomes up;
    # then put it on the bed at the origin
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi if up == "z" else -np.pi / 2, [1, 0, 0]))
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
