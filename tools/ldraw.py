"""Minimal LDraw toolkit: library lookup, geometry flattening, LDCad snap extraction.

Coordinates are LDraw units (LDU): 1 stud = 20 LDU, plate = 8 LDU, -Y is up.
"""
import os
import re
from functools import lru_cache

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.environ.get("LDRAW_LIB", os.path.join(ROOT, "ldraw"))
SHADOW = os.environ.get("LDCAD_SHADOW", "/home/user/RolandMelkert/LDCadShadowLibrary")


def _index(base, subdirs):
    idx = {}
    for sub in subdirs:
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            continue
        for dirpath, _, files in os.walk(d):
            rel = os.path.relpath(dirpath, d)
            for f in files:
                key = f.lower() if rel == "." else (rel.replace(os.sep, "/") + "/" + f).lower()
                idx.setdefault(key, os.path.join(dirpath, f))
    return idx


_lib_index = None
_shadow_index = None


def lib_index():
    global _lib_index
    if _lib_index is None:
        _lib_index = _index(LIB, ["parts", "p", "models"])
    return _lib_index


def shadow_index():
    global _shadow_index
    if _shadow_index is None:
        _shadow_index = _index(SHADOW, ["parts", "p"])
    return _shadow_index


def norm(name):
    return name.strip().replace("\\", "/").lower()


def find(name):
    return lib_index().get(norm(name))


def mat(vals):
    """12 LDraw numbers (x y z a b c d e f g h i) -> 4x4 matrix."""
    x, y, z, a, b, c, d, e, f, g, h, i = vals
    return np.array([[a, b, c, x], [d, e, f, y], [g, h, i, z], [0, 0, 0, 1]], dtype=float)


@lru_cache(maxsize=None)
def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


@lru_cache(maxsize=None)
def part_header(name):
    p = find(name)
    if not p:
        return None
    for line in read_lines(p):
        s = line.strip()
        if s.startswith("0 "):
            return s[2:].strip()
    return None


@lru_cache(maxsize=None)
def parsed(name):
    """Return (refs, tris, quads) for a library file. refs: [(color, M, subname)]."""
    p = find(name)
    if not p:
        raise FileNotFoundError(name)
    refs, tris, quads = [], [], []
    for line in read_lines(p):
        t = line.split()
        if not t:
            continue
        if t[0] == "1" and len(t) >= 15:
            refs.append((t[1], mat([float(v) for v in t[2:14]]), norm(" ".join(t[14:]))))
        elif t[0] == "3" and len(t) >= 11:
            tris.append([float(v) for v in t[2:11]])
        elif t[0] == "4" and len(t) >= 14:
            quads.append([float(v) for v in t[2:14]])
    return refs, np.array(tris).reshape(-1, 3, 3), np.array(quads).reshape(-1, 4, 3)


@lru_cache(maxsize=None)
def triangles(name):
    """All triangles of a part in part-local coords, shape (n,3,3)."""
    refs, tris, quads = parsed(name)
    out = [tris]
    if len(quads):
        out.append(quads[:, [0, 1, 2]])
        out.append(quads[:, [0, 2, 3]])
    for _, M, sub in refs:
        if not find(sub):
            continue
        st = triangles(sub)
        if len(st):
            pts = st.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
            out.append(pts.reshape(-1, 3, 3))
    out = [o for o in out if len(o)]
    return np.concatenate(out) if out else np.zeros((0, 3, 3))


@lru_cache(maxsize=None)
def bbox(name):
    t = triangles(name).reshape(-1, 3)
    return t.min(0), t.max(0)


# ---------------------------------------------------------------- snaps
_meta_re = re.compile(r"\[(\w+)=([^\]]*)\]")


class Snap:
    """A cylindrical connector. Axis u (unit), runs from p0 along u for sum(len)."""

    __slots__ = ("gender", "secs", "p0", "u", "id", "caps", "src")

    def __init__(self, gender, secs, p0, u, sid=None, caps=None, src=None):
        self.gender, self.secs, self.p0, self.u, self.id, self.caps, self.src = gender, secs, p0, u, sid, caps, src

    @property
    def length(self):
        return sum(s[2] for s in self.secs)

    def transformed(self, M):
        p0 = M[:3, :3] @ self.p0 + M[:3, 3]
        u = M[:3, :3] @ self.u
        n = np.linalg.norm(u)
        return Snap(self.gender, self.secs, p0, u / n, self.id, self.caps, self.src)


def _parse_secs(s):
    toks = s.split()
    out = []
    i = 0
    while i + 2 < len(toks) + 0:
        shape, r, ln = toks[i], float(toks[i + 1]), float(toks[i + 2])
        out.append((shape.strip("_").replace("L_", "L"), r, ln))
        i += 3
    return out


def _parse_grid(g):
    toks = g.split()
    # forms: "C 3 1 20 20", "3 C 1 20 20", "C 3 C 2 20 20", "2 2 20 20"
    vals, centered = [], []
    c = False
    for t in toks:
        if t.upper() == "C":
            c = True
            continue
        vals.append(float(t))
        centered.append(c)
        c = False
    nx, nz, sx, sz = vals[:4]
    cx, cz = centered[0], centered[1]
    xs = [(i - (nx - 1) / 2) * sx if cx else i * sx for i in range(int(nx))]
    zs = [(j - (nz - 1) / 2) * sz if cz else j * sz for j in range(int(nz))]
    return [(x, z) for x in xs for z in zs]


def _local_snaps_from_meta(params, scale_mat):
    """Build snaps from one SNAP_CYL meta. scale_mat is applied later by caller."""
    pos = np.array([float(v) for v in params.get("pos", "0 0 0").split()])
    ori = np.array([float(v) for v in params.get("ori", "1 0 0 0 1 0 0 0 1").split()]).reshape(3, 3)
    secs = _parse_secs(params.get("secs", ""))
    center = params.get("center", "false").lower() == "true"
    gender = params.get("gender", "M").upper()
    total = sum(s[2] for s in secs)
    offsets = [(0.0, 0.0)]
    if "grid" in params:
        offsets = _parse_grid(params["grid"])
    out = []
    for gx, gz in offsets:
        base = pos + ori @ np.array([gx, 0.0, gz])
        # cylinder runs along local -Y from pos
        u = ori @ np.array([0.0, -1.0, 0.0])
        p0 = base - u * (total / 2 if center else 0.0)
        out.append(dict(gender=gender, secs=secs, p0=p0, u=u, id=params.get("id") or params.get("ID"),
                        caps=params.get("caps"), scale=params.get("scale", "none").lower()))
    return out


def _metas(path):
    res = []
    for line in read_lines(path):
        s = line.strip()
        if not s.startswith("0 !LDCAD"):
            continue
        m = re.match(r"0 !LDCAD (\w+)(.*)", s)
        kind, rest = m.group(1), m.group(2)
        params = {k.lower(): v for k, v in _meta_re.findall(rest)}
        res.append((kind, params))
    return res


def _apply(sd, M):
    """Transform snap dict by 4x4 M respecting scale mode; returns Snap."""
    A = M[:3, :3]
    p0 = A @ sd["p0"] + M[:3, 3]
    u = A @ sd["u"]
    n = np.linalg.norm(u)
    secs = sd["secs"]
    if sd.get("scale") in ("yonly", "yandr") and abs(n - 1) > 1e-6:
        secs = [(s, r, ln * n) for s, r, ln in secs]
    return Snap(sd["gender"], secs, p0, u / n, sd.get("id"), sd.get("caps"))


@lru_cache(maxsize=None)
def snaps(name, depth=0):
    """Snaps of a library file in its local coords (list of Snap)."""
    name = norm(name)
    inherited = []
    if find(name):
        refs, _, _ = parsed(name)
        for _, M, sub in refs:
            if not find(sub) or depth > 12:
                continue
            for s in snaps(sub, depth + 1):
                # a nested scale (e.g. axle.dat scaled) arrives here with unit u; lengths already scaled
                inherited.append(_scale_snap(s, M))
    own = []
    sp = shadow_index().get(name)
    if sp:
        for kind, params in _metas(sp):
            if kind == "SNAP_CLEAR":
                sid = params.get("id")
                inherited = [s for s in inherited if sid and s.id != sid] if sid else []
            elif kind == "SNAP_CYL":
                for sd in _local_snaps_from_meta(params, None):
                    own.append(_apply(sd, np.eye(4)) if sd["scale"] == "none" else _RawSnap(sd))
            elif kind == "SNAP_INCL":
                ref = norm(params.get("ref", ""))
                pos = np.array([float(v) for v in params.get("pos", "0 0 0").split()])
                ori = np.array([float(v) for v in params.get("ori", "1 0 0 0 1 0 0 0 1").split()]).reshape(3, 3)
                offsets = _parse_grid(params["grid"]) if "grid" in params else [(0.0, 0.0)]
                for gx, gz in offsets:
                    M = np.eye(4)
                    M[:3, :3] = ori
                    M[:3, 3] = pos + ori @ np.array([gx, 0.0, gz])
                    for s in snaps(ref, depth + 1):
                        own.append(_scale_snap(s, M))
    return tuple(inherited + own)


class _RawSnap(Snap):
    """Snap whose lengths scale with the referencing matrix (scale=YOnly)."""

    __slots__ = ("sd",)

    def __init__(self, sd):
        super().__init__(sd["gender"], sd["secs"], sd["p0"], sd["u"], sd.get("id"), sd.get("caps"))
        self.sd = sd


def _scale_snap(s, M):
    if isinstance(s, _RawSnap):
        return _apply(s.sd, M)
    return s.transformed(M)


# ---------------------------------------------------------------- model files
class Placement:
    __slots__ = ("part", "color", "M", "step", "path", "line")

    def __init__(self, part, color, M, step=0, path="", line=0):
        self.part, self.color, self.M, self.step, self.path, self.line = part, color, M, step, path, line


def load_model(path):
    """Flatten an .ldr/.mpd model into part placements (world matrices)."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    files = {}
    order = []
    cur = None
    for ln in lines:
        s = ln.strip()
        if s.startswith("0 FILE "):
            cur = norm(s[7:])
            files[cur] = []
            order.append(cur)
            continue
        if s.startswith("0 NOFILE"):
            cur = None
            continue
        if cur is None:
            if not files:
                cur = norm(os.path.basename(path))
                files[cur] = []
                order.append(cur)
            else:
                continue
        files[cur].append(s)

    out = []

    def walk(fname, M, color, prefix):
        step = 0
        for i, s in enumerate(files[fname]):
            t = s.split()
            if not t:
                continue
            if t[0] == "0" and len(t) > 1 and t[1] == "STEP":
                step += 1
            if t[0] != "1":
                continue
            c = t[1]
            if c == "16":
                c = color
            Ml = mat([float(v) for v in t[2:14]])
            sub = norm(" ".join(t[14:]))
            W = M @ Ml
            if sub in files:
                walk(sub, W, c, f"{prefix}{fname}#{i}/")
            else:
                out.append(Placement(sub, c, W, step, prefix + fname, i))

    walk(order[0], np.eye(4), "16", "")
    return out
