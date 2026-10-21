"""Build plan for the viewer: step order, sub-assemblies and a collision-free direction for every part.

The model's main file holds parts built directly on the model (in-place sections, marked with
"0 // section: <id> - <title>") and references to submodels. A referenced submodel is a sub-assembly:
its steps are shown on their own, and the main step that references it mounts it in one piece.

For every part, and for every sub-assembly as it is mounted, the parts already built in the same
context are voxelised and the part is swept in from each of the six axis directions. The first
direction (up, down, then the horizontal ones facing away from the model's centre) whose path is
clear is used for the animation.

Usage: python3 tools/buildplan.py model.mpd   (prints the plan and any part that has no clear path)
"""
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402
import ldraw as L  # noqa: E402

DIRS = [(0, -1, 0), (0, 1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]  # LDraw: -Y is up
PART_TRAVEL = 100        # how far a part flies in (LDU)
MOUNT_MARGIN = 60        # a sub-assembly flies in from its own size plus this
TOLERANCE = 8            # voxels a sweep may touch beyond what the part touches in its final position


def read_files(path):
    files, order, cur = {}, [], None
    for ln in open(path, encoding="utf-8").read().splitlines():
        s = ln.strip()
        if s.startswith("0 FILE "):
            cur = L.norm(s[7:])
            files[cur] = []
            order.append(cur)
        elif s.startswith("0 NOFILE"):
            cur = None
        elif cur is not None:
            files[cur].append(s)
    return files, order


def plan(path):
    """Return (placements, steps). Each step: dict(ctx, section, parts=[placement indices], mounts=[sub])."""
    files, order = read_files(path)
    placements = L.load_model(path)
    info = []                       # per placement, in load_model order: (ctx, step within ctx)
    mounts = defaultdict(list)      # main step -> submodels mounted in it
    sections = {}                   # main step -> section id
    sub_steps = defaultdict(set)

    def walk_sub(name):
        st = 0
        for s in files[name]:
            t = s.split()
            if t[:2] == ["0", "STEP"]:
                st += 1
            elif t and t[0] == "1":
                assert L.norm(" ".join(t[14:])) not in files, "nested submodels are not supported"
                info.append((name, st))
                sub_steps[name].add(st)

    st = 0
    for s in files[order[0]]:
        t = s.split()
        if t[:2] == ["0", "STEP"]:
            st += 1
        elif s.startswith("0 // section:"):
            sid = s[len("0 // section:"):].strip().split(" - ")[0]
            sections[st] = sid
        elif t and t[0] == "1":
            ref = L.norm(" ".join(t[14:]))
            if ref in files:
                mounts[st].append(ref)
                walk_sub(ref)
            else:
                info.append(("main", st))
    last = st
    assert len(info) == len(placements)

    steps, sec = [], None
    by = defaultdict(list)
    for i, key in enumerate(info):
        by[key].append(i)
    for st in range(last + 1):
        for sub in mounts.get(st, []):
            for k in sorted(sub_steps[sub]):
                if by[(sub, k)]:
                    steps.append(dict(ctx=sub, section=sub[:-4], parts=by[(sub, k)], mounts=[]))
        sec = sections.get(st, sec)
        if by[("main", st)] or mounts.get(st):
            sid = sec if not sec.startswith("mount ") else sec[6:-4]
            steps.append(dict(ctx="main", section=sid, parts=by[("main", st)], mounts=list(mounts.get(st, []))))
    return placements, steps


class Space:
    """Voxel occupancy (1 LDU) labelled by build context."""

    def __init__(self, placements):
        self.vox = []
        for p in placements:
            pts = check.solid_points(p.part)
            w = pts @ p.M[:3, :3].T + p.M[:3, 3]
            self.vox.append(np.unique(np.floor(w).astype(np.int32), axis=0))
        allv = np.concatenate([v for v in self.vox if len(v)])
        self.lo = allv.min(0) - 2
        self.shape = tuple(allv.max(0) - self.lo + 3)
        self.grid = np.zeros(self.shape, dtype=np.int8)
        self.labels = {"main": 1}

    def label(self, ctx):
        if ctx not in self.labels:
            self.labels[ctx] = len(self.labels) + 1
        return self.labels[ctx]

    def add(self, idx, ctx):
        v = self.vox[idx] - self.lo
        self.grid[v[:, 0], v[:, 1], v[:, 2]] = self.label(ctx)

    def relabel(self, ctx_from, ctx_to):
        self.grid[self.grid == self.label(ctx_from)] = self.label(ctx_to)

    def hits(self, v, ctx, offset):
        w = v + np.round(offset).astype(np.int32)
        ok = np.all((w >= 0) & (w < np.array(self.shape)), axis=1)
        w = w[ok]
        return int(np.count_nonzero(self.grid[w[:, 0], w[:, 1], w[:, 2]] == self.label(ctx)))

    def sweep(self, v, ctx, d, travel):
        """Largest number of voxels in the way along the path, minus those touched at the final position."""
        d = np.array(d)
        base = self.hits(v, ctx, 0)
        worst = 0
        for k in range(1, travel + 1):
            worst = max(worst, self.hits(v, ctx, d * k))
            if worst > base + TOLERANCE:
                break
        return worst - base

    def clear(self, v, ctx, dirs, travels):
        """First (direction, travel) with a clear path, trying long travels in every direction first."""
        for t in travels:
            for d in dirs:
                if self.sweep(v, ctx, d, t) <= TOLERANCE:
                    return d, t
        return None


def own_axes(p):
    """The part's own axes, when they are not along the world axes (parts on tilted assemblies)."""
    out = []
    for k in range(3):
        a = p.M[:3, k] / np.linalg.norm(p.M[:3, k])
        if np.max(np.abs(a)) < 0.999:
            out += [tuple(a), tuple(-a)]
    return out


def preferred(outward):
    """Up, down, then the horizontal directions facing away from the model's centre first."""
    return DIRS[:2] + sorted(DIRS[2:], key=lambda d: -float(np.dot(d, outward)))


def place_step(sp, placements, parts, ctx, centre, rim_of, strategy):
    """Place one step's parts into the space. Returns ([(index, dir, travel)], [blocked indices])."""
    out = lambda i: placements[i].M[:3, 3] - centre  # noqa: E731

    def try_part(i, dirs, travels):
        v = sp.vox[i] - sp.lo
        if len(v) == 0:
            return (0, -1, 0), PART_TRAVEL
        rim = rim_of.get(i)
        if rim is not None:   # a tyre is stretched over its rim: ignore the rim on the way in
            rv = sp.vox[rim] - sp.lo
            sp.grid[rv[:, 0], rv[:, 1], rv[:, 2]] = 0
        r = sp.clear(v, ctx, dirs, travels)
        if rim is not None:
            sp.add(rim, ctx)
        return r

    tyres = [i for i in parts if rim_of.get(i) in parts]
    todo, order, bad = [i for i in parts if i not in tyres], [], []
    y = {i: placements[i].M[1, 3] for i in todo}
    if strategy == "vertical":
        passes = ((lambda: sorted(todo, key=lambda i: -y[i]), lambda i: [DIRS[0]], (PART_TRAVEL,)),
                  (lambda: sorted(todo, key=lambda i: y[i]), lambda i: [DIRS[1]], (PART_TRAVEL,)),
                  (lambda: todo, lambda i: preferred(out(i))[2:], (PART_TRAVEL,)),
                  (lambda: todo, lambda i: own_axes(placements[i]), (PART_TRAVEL,)),
                  (lambda: todo, lambda i: preferred(out(i)) + own_axes(placements[i]), (60, 40, 24)))
    else:
        passes = ((lambda: todo, lambda i: preferred(out(i)) + own_axes(placements[i]), (PART_TRAVEL, 60, 40, 24)),)
    while todo:
        pick = None
        for cands, dirs_of, travels in passes:
            for i in cands():
                r = try_part(i, dirs_of(i), travels)
                if r:
                    pick = (i, r[0], r[1])
                    break
            if pick:
                break
        if pick is None:
            i = todo[0]
            pick = (i, (0, -1, 0), PART_TRAVEL)
            bad.append(i)
        todo.remove(pick[0])
        order.append(pick)
        sp.add(pick[0], ctx)
        for t in tyres:            # a tyre goes on with its rim, as one wheel
            if rim_of[t] == pick[0]:
                order.append((t, pick[1], pick[2]))
                sp.add(t, ctx)
    return order, bad


def debug(sp, placements, i, ctx):
    v = sp.vox[i] - sp.lo
    p = placements[i]
    lbl = sp.label(ctx)
    sp.grid[v[:, 0], v[:, 1], v[:, 2]] = 0
    print(f"    {p.part} @{np.round(p.M[:3, 3]).astype(int).tolist()} base {sp.hits(v, ctx, 0)}")
    for d in DIRS + own_axes(p):
        print(f"      {np.round(d, 2).tolist()}: travel 100 -> {sp.sweep(v, ctx, d, 100)}, 24 -> {sp.sweep(v, ctx, d, 24)}")
    sp.grid[v[:, 0], v[:, 1], v[:, 2]] = lbl


def directions(placements, steps, verbose=False):
    """Order the parts of every step so each has a clear path, and give each part and each mounted
    sub-assembly a direction and travel. Sets step["order"] = [(index, dir, travel)], step["mount_paths"]."""
    sp = Space(placements)
    centre = np.mean([p.M[:3, 3] for p in placements], axis=0)
    rim_of = {}
    for a, b in check.tyre_pairs(placements):
        t, r = (a, b) if (L.part_header(placements[a].part) or "").startswith("Tyre") else (b, a)
        rim_of[t] = r
    subs = defaultdict(list)
    problems = []
    for si, st in enumerate(steps):
        ctx = st["ctx"]
        # two strategies: (a) vertical moves first, parts from above bottom-up and parts from below
        # top-down; (b) the step's own order, deferring parts that are blocked. Keep the better one.
        snap, best = sp.grid.copy(), None
        for strategy in ("vertical", "listed"):
            sp.grid = snap.copy()
            order, bad = place_step(sp, placements, st["parts"], ctx, centre, rim_of, strategy)
            if best is None or len(bad) < len(best[1]):
                best = (order, bad, sp.grid)
            if not bad:
                break
        order, bad, sp.grid = best
        del snap
        for i in bad:
            problems.append((si, i))
            if os.environ.get("BP_DEBUG"):
                debug(sp, placements, i, ctx)
        for i, _, _ in order:
            subs[ctx].append(i)
        st["order"] = order
        st["mount_paths"] = []
        for sub in st["mounts"]:
            idx = subs[sub]
            v = np.concatenate([sp.vox[i] for i in idx]) - sp.lo
            outward = np.mean([placements[i].M[:3, 3] for i in idx], axis=0) - centre
            travel = int((v.max(0) - v.min(0)).max() + MOUNT_MARGIN)
            r = sp.clear(v, "main", preferred(outward), (travel,))
            if r is None:
                problems.append((si, sub))
                r = ((0, -1, 0), travel)
            st["mount_paths"].append((sub, r[0], r[1]))
            sp.relabel(sub, "main")
    for si, what in problems:
        name = what if isinstance(what, str) else f"{placements[what].part} @{np.round(placements[what].M[:3, 3]).astype(int).tolist()}"
        print(f"  step {si + 1}: no clear path for {name}")
    return problems


NAMES = {(0, -1, 0): "uppifrån", (0, 1, 0): "nedifrån", (1, 0, 0): "+x", (-1, 0, 0): "-x", (0, 0, 1): "bakifrån", (0, 0, -1): "framifrån"}


def main():
    placements, steps = plan(sys.argv[1])
    directions(placements, steps)
    for si, st in enumerate(steps):
        ds = defaultdict(int)
        for i, d, t in st["order"]:
            ds[NAMES.get(tuple(int(c) for c in d) if max(map(abs, d)) > 0.999 else None, "snett") + ("" if t == PART_TRAVEL else f"/{t}")] += 1
        m = ", ".join(f"montera {s} {NAMES[d]}" for s, d, t in st["mount_paths"])
        print(f"{si + 1:3d} {st['ctx']:16s} {st['section']:14s} {len(st['parts']):3d} delar {dict(ds)} {m}")


if __name__ == "__main__":
    main()
