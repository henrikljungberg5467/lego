"""Buildability checks for an LDraw model.

1. Connections: LDCad shadow-library snaps (pins, axles, holes, studs) are matched
   between parts; parts form a graph. Reports floating parts / separate clusters and
   impossible fits (e.g. a pin collar sitting inside a hole).
2. Collisions: each part is voxelised (solid, eroded by one voxel) and overlapping
   solids between parts are reported.
3. Colours: every part/colour combination is looked up in the Rebrickable inventory
   database (has it appeared in an official set?).

Usage: python3 tools/check.py model.mpd [--no-collide] [--verbose]
"""
import os
import sys
import hashlib
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldraw as L  # noqa: E402

CACHE = os.path.join(L.ROOT, "tmp", "voxcache")
H = 1.0  # voxel size (LDU)


# ----------------------------------------------------------------- connections
def world_snaps(placements):
    out = []
    for i, p in enumerate(placements):
        for s in L.snaps(p.part):
            out.append((i, s.transformed(p.M)))
    return out


def _intervals(s):
    t, res = 0.0, []
    for shape, r, ln in s.secs:
        res.append((t, t + ln, shape, r))
        t += ln
    return res


def match(m, f):
    """Return (overlap_ok, conflicts) for male snap m and female snap f, or None if not coaxial."""
    if abs(float(np.dot(m.u, f.u))) < 0.999:
        return None
    d = f.p0 - m.p0
    perp = d - np.dot(d, m.u) * m.u
    if np.linalg.norm(perp) > 0.6:
        return None
    t0 = float(np.dot(d, m.u))
    sgn = 1.0 if np.dot(m.u, f.u) > 0 else -1.0
    fi = []
    for a, b, shape, r in _intervals(f):
        x, y = t0 + sgn * a, t0 + sgn * b
        fi.append((min(x, y), max(x, y), shape, r))
    ok, bad = 0.0, []
    for a, b, ms, mr in _intervals(m):
        for c, d2, fs, fr in fi:
            ov = min(b, d2) - max(a, c)
            if ov <= 0.3:
                continue
            ms_, fs_ = ms[0], fs[0]
            mr_ = 6.0 if ms_ == "L" and abs(mr - 6.25) < 0.3 else mr
            if ms_ == "A" and fs_ == "A":
                good = abs(mr_ - fr) < 0.6
            elif ms_ == "A" and fs_ in "RL":
                good = fr >= mr_ - 0.6
            elif ms_ in "RL" and fs_ == "A":
                good = mr_ <= 4.6  # bar/stud-3 into an axle hole is fine, a pin is not
            else:
                good = fr >= mr_ - 0.6
            if good:
                ok += ov if f.id != "axleHole2" else 10.0
            elif mr_ > fr + 0.6:
                bad.append((ms, mr, fs, fr, round(ov, 1)))
    return ok, bad


def connections(placements, snaps_w):
    def key(p, u):
        uu = u if (u[0], u[1], u[2]) > (0, 0, 0) else -u
        perp = p - np.dot(p, uu) * uu
        return (tuple(np.round(uu, 2)), tuple(np.round(perp).astype(int)))

    buckets = defaultdict(list)
    for idx, (i, s) in enumerate(snaps_w):
        if s.gender == "F":
            uu = s.u if (s.u[0], s.u[1], s.u[2]) > (0, 0, 0) else -s.u
            perp = s.p0 - np.dot(s.p0, uu) * uu
            base = np.floor(perp).astype(int)
            for dx in (0, 1):
                for dy in (0, 1):
                    for dz in (0, 1):
                        buckets[(tuple(np.round(uu, 2)), (base[0] + dx, base[1] + dy, base[2] + dz))].append(idx)
    edges = defaultdict(float)
    conflicts = []
    for idx, (i, s) in enumerate(snaps_w):
        if s.gender != "M":
            continue
        seen = set()
        for fidx in buckets.get(key(s.p0, s.u), []):
            j, f = snaps_w[fidx]
            if j == i or fidx in seen:
                continue
            seen.add(fidx)
            r = match(s, f)
            if r is None:
                continue
            ok, bad = r
            if ok > 0:
                edges[(min(i, j), max(i, j))] += ok
            if bad:
                conflicts.append((i, j, bad))
    return edges, conflicts


def stud_edges(placements, snaps_w, boxes):
    """Heuristic System connection: an upward stud covered by the bottom of another part."""
    edges = defaultdict(float)
    up = np.array([0.0, -1.0, 0.0])
    centers = np.array([(b[0] + b[1]) / 2 for b in boxes])
    for i, s in snaps_w:
        if s.gender != "M" or s.id not in ("studC", "studO") and not (len(s.secs) == 1 and s.secs[0][1] == 6 and s.secs[0][2] == 4):
            continue
        tip = s.p0 + s.u * 2.0
        for j, (lo, hi) in enumerate(boxes):
            if j == i:
                continue
            if np.all(tip >= lo - 0.5) and np.all(tip <= hi + 0.5):
                # base plane of j must sit at the stud base
                if abs(float(np.dot(s.u, up))) > 0.99:
                    edges[(min(i, j), max(i, j))] += 1
                else:
                    edges[(min(i, j), max(i, j))] += 1
    return edges


def tyre_pairs(placements):
    """A tyre is connected to the rim sitting at the same centre with the same axis."""
    out = set()
    tyres = [i for i, p in enumerate(placements) if (L.part_header(p.part) or "").startswith("Tyre")]
    rims = [i for i, p in enumerate(placements) if (L.part_header(p.part) or "").startswith("Wheel")]
    for t in tyres:
        for r in rims:
            a, b = placements[t].M, placements[r].M
            if np.linalg.norm(a[:3, 3] - b[:3, 3]) < 1.0 and abs(abs(np.dot(a[:3, 2], b[:3, 2])) - 1) < 1e-3:
                out.add((min(t, r), max(t, r)))
    return out


def world_box(p):
    lo, hi = L.bbox(p.part)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    w = corners @ p.M[:3, :3].T + p.M[:3, 3]
    return w.min(0), w.max(0)


# ----------------------------------------------------------------- collisions
def _ray_fill(tris, lo, hi, axis):
    """Parity fill along `axis`. Returns boolean grid (nx,ny,nz) over [lo,hi) with cell H."""
    n = np.maximum(np.ceil((hi - lo) / H).astype(int), 1)
    grid = np.zeros(n, dtype=bool)
    a1, a2 = [k for k in range(3) if k != axis]
    hits = defaultdict(list)
    c1 = lo[a1] + (np.arange(n[a1]) + 0.5) * H
    c2 = lo[a2] + (np.arange(n[a2]) + 0.5) * H
    for t in tris:
        p = t[:, [a1, a2]]
        mn, mx = p.min(0), p.max(0)
        i0, i1 = np.searchsorted(c1, mn[0]), np.searchsorted(c1, mx[0], side="right")
        j0, j1 = np.searchsorted(c2, mn[1]), np.searchsorted(c2, mx[1], side="right")
        if i0 >= i1 or j0 >= j1:
            continue
        X, Y = np.meshgrid(c1[i0:i1], c2[j0:j1], indexing="ij")
        v0, v1, v2 = p[0], p[1], p[2]
        den = (v1[1] - v2[1]) * (v0[0] - v2[0]) + (v2[0] - v1[0]) * (v0[1] - v2[1])
        if abs(den) < 1e-9:
            continue
        w0 = ((v1[1] - v2[1]) * (X - v2[0]) + (v2[0] - v1[0]) * (Y - v2[1])) / den
        w1 = ((v2[1] - v0[1]) * (X - v2[0]) + (v0[0] - v2[0]) * (Y - v2[1])) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        z = w0 * t[0, axis] + w1 * t[1, axis] + w2 * t[2, axis]
        ii, jj = np.nonzero(inside)
        for a, b, zz in zip(ii + i0, jj + j0, z[inside]):
            hits[(a, b)].append(zz)
    cz = lo[axis] + (np.arange(n[axis]) + 0.5) * H
    for (a, b), zs in hits.items():
        zs = np.unique(np.round(np.array(zs), 3))
        if len(zs) < 2:
            continue
        inside = np.zeros(n[axis], dtype=bool)
        cnt = np.searchsorted(zs, cz)  # number of crossings below each cell centre
        inside = (cnt % 2) == 1
        idx = [slice(None)] * 3
        idx[a1], idx[a2] = a, b
        grid[tuple(idx)] |= inside
    return grid


def solid_points(part):
    """Eroded interior sample points of a part in local coords (cached)."""
    os.makedirs(CACHE, exist_ok=True)
    fn = os.path.join(CACHE, hashlib.md5(part.encode()).hexdigest() + ".npy")
    if os.path.exists(fn):
        return np.load(fn)
    tris = L.triangles(part)
    if len(tris) == 0:
        pts = np.zeros((0, 3))
        np.save(fn, pts)
        return pts
    lo, hi = tris.reshape(-1, 3).min(0) - H, tris.reshape(-1, 3).max(0) + H
    votes = sum(_ray_fill(tris, lo, hi, ax).astype(int) for ax in range(3))
    g = votes >= 2
    e = g.copy()
    e[1:] &= g[:-1]; e[:-1] &= g[1:]
    e[:, 1:] &= g[:, :-1]; e[:, :-1] &= g[:, 1:]
    e[:, :, 1:] &= g[:, :, :-1]; e[:, :, :-1] &= g[:, :, 1:]
    idx = np.argwhere(e)
    pts = lo + (idx + 0.5) * H
    np.save(fn, pts)
    return pts


def collisions(placements, min_shared=40):
    keys, owners = [], []
    for i, p in enumerate(placements):
        pts = solid_points(p.part)
        if len(pts) == 0:
            continue
        w = pts @ p.M[:3, :3].T + p.M[:3, 3]
        k = np.floor(w / H).astype(np.int64) + 100000
        kk = (k[:, 0] * 200003 + k[:, 1]) * 200003 + k[:, 2]
        kk = np.unique(kk)
        keys.append(kk)
        owners.append(np.full(len(kk), i))
    if not keys:
        return {}
    K = np.concatenate(keys)
    O = np.concatenate(owners)
    order = np.argsort(K, kind="stable")
    K, O = K[order], O[order]
    dup = np.nonzero(K[1:] == K[:-1])[0]
    pairs = defaultdict(int)
    for d in dup:
        a, b = O[d], O[d + 1]
        if a != b:
            pairs[(min(a, b), max(a, b))] += 1
    return {k: v for k, v in pairs.items() if v >= min_shared}


# ----------------------------------------------------------------- colours
DB = os.environ.get("REBRICKABLE_DB", "/home/user/data-dl/lego-oracle/package/dist/data/lego.sqlite")
LDRAW_TO_RB_COLOR = {"0": 0, "1": 1, "2": 2, "4": 4, "14": 14, "15": 15, "19": 19, "25": 25, "28": 28, "70": 70,
                     "71": 71, "72": 72, "191": 191, "288": 288, "326": 326, "320": 320, "308": 308, "484": 484,
                     "27": 27, "10": 10, "47": 47, "36": 36, "46": 46, "34": 34, "182": 182, "379": 379}
PART_ALIASES = {"3069b": ["3069b", "3069"], "4265c": ["4265c", "3713"], "32123": ["32123b", "4265c"],
                "2780": ["2780"], "6558": ["6558"], "3673": ["3673"]}


def color_check(placements):
    import sqlite3
    if not os.path.exists(DB):
        return None
    c = sqlite3.connect(DB)
    res = {}
    for p in placements:
        base = p.part[:-4] if p.part.endswith(".dat") else p.part
        key = (base, p.color)
        if key in res:
            continue
        cid = LDRAW_TO_RB_COLOR.get(p.color, int(p.color) if p.color.isdigit() else -1)
        cands = PART_ALIASES.get(base, [base])
        rel = [r[0] for r in c.execute("select child_part_num from part_relationships where parent_part_num=? and rel_type in ('M','A','T')", (base,))]
        rel += [r[0] for r in c.execute("select parent_part_num from part_relationships where child_part_num=? and rel_type in ('M','A','T')", (base,))]
        best = (0, None)
        for pn in cands + rel:
            n = c.execute("""select count(distinct i.set_num) from inventory_parts ip join inventories i on i.id=ip.inventory_id
                             where ip.part_num=? and ip.color_id=?""", (pn, cid)).fetchone()[0]
            if n > best[0]:
                best = (n, pn)
        res[key] = best
    return res


# ----------------------------------------------------------------- main
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    verbose = "--verbose" in sys.argv
    placements = L.load_model(args[0])
    print(f"parts: {len(placements)}")
    missing = sorted({p.part for p in placements if not L.find(p.part)})
    if missing:
        print("MISSING PARTS:", missing)
        placements = [p for p in placements if L.find(p.part)]

    def label(i):
        p = placements[i]
        return f"#{i} {p.part}({p.color}) @{np.round(p.M[:3, 3], 1).tolist()} [{p.path}:{p.line}]"

    sw = world_snaps(placements)
    edges, conflicts = connections(placements, sw)
    boxes = [world_box(p) for p in placements]
    for k, v in stud_edges(placements, sw, boxes).items():
        edges[k] += v
    for k in tyre_pairs(placements):
        edges[k] += 100
    # union-find
    parent = list(range(len(placements)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for (a, b), w in edges.items():
        if w >= 2.0:
            parent[find(a)] = find(b)
    groups = defaultdict(list)
    for i in range(len(placements)):
        groups[find(i)].append(i)
    comps = sorted(groups.values(), key=len, reverse=True)
    print(f"connected clusters: {len(comps)} (largest {len(comps[0]) if comps else 0})")
    for comp in comps[1:]:
        print("  FLOATING cluster:", [label(i) for i in comp[:6]], "..." if len(comp) > 6 else "")
    for i, j, bad in conflicts:
        print("  FIT CONFLICT:", label(i), "<->", label(j), bad[:3])

    if "--no-collide" not in sys.argv:
        col = collisions(placements)
        for k in tyre_pairs(placements):
            col.pop(k, None)
        print(f"colliding pairs: {len(col)}")
        for (a, b), n in sorted(col.items(), key=lambda kv: -kv[1]):
            print(f"  COLLISION {n:5d} voxels:", label(a), "<->", label(b))

    cc = color_check(placements)
    if cc is not None:
        bad = {k: v for k, v in cc.items() if v[0] == 0}
        print(f"part/colour combos: {len(cc)}, never produced: {len(bad)}")
        for (part, col), v in sorted(bad.items()):
            print(f"  NO SET HAS {part} in colour {col}")
        if verbose:
            for (part, col), v in sorted(cc.items()):
                print(f"  {part:10s} col {col:4s} in {v[0]} sets (as {v[1]})")


if __name__ == "__main__":
    main()
