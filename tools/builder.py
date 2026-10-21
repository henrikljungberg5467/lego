"""Tiny DSL for writing LDraw multi-part models from Python.

Coordinates: LDU, -Y up. Rotations are given by where the part's local axes point,
e.g. rot(x='+Z', y='-Y') -> local x along world +Z, local y along world -Y.
"""
import numpy as np

AX = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Y": (0, 1, 0), "-Y": (0, -1, 0), "+Z": (0, 0, 1), "-Z": (0, 0, -1)}

# colours (LDraw codes)
BLACK, BLUE, GREEN, RED, LBG, DBG, YELLOW, WHITE, ORANGE, TAN, TRANS_CLEAR = 0, 1, 2, 4, 71, 72, 14, 15, 25, 19, 47


def _v(a):
    if isinstance(a, str):
        return np.array(AX[a.upper()], dtype=float)
    return np.array(a, dtype=float)


def rot(x=None, y=None, z=None):
    """Rotation matrix whose columns are the world directions of local x, y, z."""
    x, y, z = (None if a is None else _v(a) for a in (x, y, z))
    if x is None:
        x = np.cross(y, z)
    if y is None:
        y = np.cross(z, x)
    if z is None:
        z = np.cross(x, y)
    R = np.column_stack([x, y, z])
    assert abs(np.linalg.det(R) - 1) < 1e-6, f"not a rotation: {R}"
    return R


I = np.eye(3)


def rot_axis(axis, deg):
    """Rotation about a world axis ('X','Y','Z' or vector) by deg (right hand)."""
    a = _v(axis if not isinstance(axis, str) or axis[0] in "+-" else "+" + axis)
    a = a / np.linalg.norm(a)
    t = np.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * K @ K


def fmt(v):
    v = float(v)
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def _bottom_up_key(line, hanging):
    """Sort key for a part line: lowest part first (by the bottom of its bounding box), or the
    highest part first (by its top) when the assembly is built hanging."""
    import ldraw as L
    t = line.split()
    pos = np.array([float(v) for v in t[2:5]])
    R = np.array([float(v) for v in t[5:14]]).reshape(3, 3)
    try:
        lo, hi = L.bbox(" ".join(t[14:]))
    except Exception:
        return -pos[1] if not hanging else pos[1]
    ys = [(R @ np.array([x, y, z]))[1] + pos[1] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    return min(ys) if hanging else -max(ys)


class Sub:
    def __init__(self, model, name, title):
        self.model, self.name, self.title = model, name, title
        self.lines = []
        self.count = 0
        self.hanging = False   # True: built upside down, so big steps are split top-down instead of bottom-up

    def add(self, part, color, pos, R=I, note=None):
        part = part if part.endswith((".dat", ".ldr")) else part + ".dat"
        R = np.asarray(R, dtype=float)
        p = [fmt(c) for c in pos]
        m = [fmt(R[i, j]) for i in range(3) for j in range(3)]
        if note:
            self.lines.append(f"0 // {note}")
        self.lines.append(f"1 {color} {' '.join(p)} {' '.join(m)} {part}")
        self.count += 1
        return self

    def step(self):
        if self.lines and not self.lines[-1].startswith("0 STEP"):
            self.lines.append("0 STEP")
        return self

    def comment(self, text):
        self.lines.append(f"0 // {text}")
        return self

    def place(self, sub, pos=(0, 0, 0), R=I, color=16):
        """Place another submodel inside this one."""
        return self.add(sub.name, color, pos, R)

    MAX_STEP = 10

    def _chunked(self):
        """Split steps with many parts into several, bottom-up (largest y first; top-down if hanging).
        "0 // section:" comments stay at the start of their step; other comments stay with their part."""
        steps, cur, note, head = [], [], [], []
        for ln in self.lines:
            if ln.startswith("0 STEP"):
                steps.append((head, cur))
                cur, head = [], []
            elif ln.startswith("0 // section:"):
                head.append(ln)
            elif ln.startswith("0 //"):
                note.append(ln)
            else:
                cur.append((note, ln))
                note = []
        steps.append((head, cur))
        out = []
        for head, st in steps:
            if not st:
                continue
            out += head
            if len(st) > self.MAX_STEP:
                st = sorted(st, key=lambda it: _bottom_up_key(it[1], self.hanging))
            for i in range(0, len(st), self.MAX_STEP):
                for nt, ln in st[i:i + self.MAX_STEP]:
                    out += nt
                    out.append(ln)
                out.append("0 STEP")
        return out

    def text(self):
        out = [f"0 FILE {self.name}", f"0 {self.title}", f"0 Name: {self.name}", "0 Author: Claude (for henrikljungberg5467)", "0 !LDRAW_ORG Unofficial_Model", ""]
        out += self._chunked()
        out.append("0 NOFILE")
        return "\n".join(out)


class Model:
    def __init__(self, name, title):
        self.main = Sub(self, name, title)
        self.subs = []

    def sub(self, name, title):
        s = Sub(self, name if name.endswith(".ldr") else name + ".ldr", title)
        self.subs.append(s)
        return s

    def write(self, path):
        parts = [self.main.text()] + [s.text() for s in self.subs]
        with open(path, "w", newline="\r\n") as fh:
            fh.write("\n\n".join(parts) + "\n")


# ---------------------------------------------------------------- System grid helpers
PLATES = {(1, 1): "3024", (1, 2): "3023", (1, 3): "3623", (1, 4): "3710", (1, 6): "3666", (1, 8): "3460",
          (1, 10): "4477", (1, 12): "60479", (2, 2): "3022", (2, 3): "3021", (2, 4): "3020", (2, 6): "3795",
          (2, 8): "3034", (2, 10): "3832", (2, 12): "2445", (2, 16): "4282", (4, 4): "3031",
          (4, 6): "3032", (4, 8): "3035", (4, 10): "3030", (4, 12): "3029", (6, 6): "3958", (6, 8): "3036",
          (6, 10): "3033", (6, 12): "3028", (8, 8): "41539", (8, 16): "92438"}
TILES = {(1, 1): "3070b", (1, 2): "3069b", (1, 3): "63864", (1, 4): "2431", (1, 6): "6636", (1, 8): "4162",
         (2, 2): "3068b", (2, 3): "26603", (2, 4): "87079"}
BRICKS = {(1, 1): "3005", (1, 2): "3004", (1, 3): "3622", (1, 4): "3010", (1, 6): "3009", (1, 8): "3008",
          (1, 10): "6111", (1, 12): "6112", (2, 2): "3003", (2, 3): "3002", (2, 4): "3001", (2, 6): "2456",
          (2, 8): "3007"}
KIND = {"plate": PLATES, "tile": TILES, "brick": BRICKS}


_avail = {}
MIN_SETS = 3  # only use part/colour combinations that appeared in at least this many sets


def exists(part, color):
    """Has this part appeared in this colour in an official set? (True if no database.)"""
    key = (part, color)
    if key not in _avail:
        try:
            import partsdb
            _avail[key] = partsdb.sets_with(part, color) >= MIN_SETS
        except Exception:
            _avail[key] = True
    return _avail[key]


def box(sub, kind, color, x0, x1, z0, z1, ytop, note=None):
    """Place one plate/tile/brick exactly covering [x0,x1]x[z0,z1] (LDU), top surface at ytop."""
    w, d = round((x1 - x0) / 20), round((z1 - z0) / 20)
    key = (min(w, d), max(w, d))
    part = KIND[kind][key]
    R = I if w >= d else rot(x="+Z", y="+Y")
    sub.add(part, color, ((x0 + x1) / 2, ytop, (z0 + z1) / 2), R, note)


def fill(sub, kind, color, x0, x1, z0, z1, ytop, avoid=(), sizes=None, prefer="x"):
    """Greedy cover of a rectangle with plates/tiles/bricks, skipping cells whose centre is in `avoid`.
    prefer: 'x' tries long side along X first, 'z' along Z."""
    nx, nz = round((x1 - x0) / 20), round((z1 - z0) / 20)
    free = [[True] * nx for _ in range(nz)]
    for (ax, az) in avoid:
        i, j = int((ax - x0) // 20), int((az - z0) // 20)
        if 0 <= i < nx and 0 <= j < nz:
            free[j][i] = False
    table = KIND[kind] if sizes is None else {k: v for k, v in KIND[kind].items() if k in sizes}
    table = {k: v for k, v in table.items() if exists(v, color)}
    shapes = []
    for (a, b) in table:
        shapes.append((b, a) if prefer == "x" else (a, b))
        if a != b:
            shapes.append((a, b) if prefer == "x" else (b, a))
    shapes.sort(key=lambda s: -s[0] * s[1])
    for j in range(nz):
        for i in range(nx):
            if not free[j][i]:
                continue
            for (w, d) in shapes:
                if i + w > nx or j + d > nz:
                    continue
                if all(free[jj][ii] for jj in range(j, j + d) for ii in range(i, i + w)):
                    for jj in range(j, j + d):
                        for ii in range(i, i + w):
                            free[jj][ii] = False
                    box(sub, kind, color, x0 + i * 20, x0 + (i + w) * 20, z0 + j * 20, z0 + (j + d) * 20, ytop)
                    break
