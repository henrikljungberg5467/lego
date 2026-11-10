"""Printable STL for every kind of part in the model: print/delar/<part>-<name>.stl plus a list.

Each part is made a closed solid by tools/print_stl.py. Wheels, tyres, gears, bushes and axle
connectors lie with their axis vertical; everything else stands as in the model (studs up, beams
flat, axles and pins lying down). The list gives how many of each part are needed, in which colours.

Usage: python3 tools/print_parts.py [model.mpd]
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldraw as L  # noqa: E402
import partlist  # noqa: E402
import print_stl  # noqa: E402

OUT = os.path.join(L.ROOT, "print", "delar")
AXIS_UP = ("Technic Gear", "Tyre", "Wheel", "Technic Bush", "Technic Connector (Axle/Bush)", "Technic Axle Joiner")


def slug(header):
    s = re.sub(r"[^a-z0-9]+", "-", header.lower()).strip("-")
    return re.sub(r"-+", "-", s)[:48].strip("-")


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else os.path.join(L.ROOT, "model", "z315e.mpd")
    pl = L.load_model(model)
    cols = defaultdict(Counter)
    for p in pl:
        cols[p.part[:-4]][p.color] += 1
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for part in sorted(cols, key=lambda k: (L.part_header(k + ".dat"), k)):
        header = L.part_header(part + ".dat")
        lo, hi = L.bbox(part + ".dat")
        size = max(hi - lo) * print_stl.MM
        faces = 20_000 if size < 20 else 40_000 if size < 50 else 80_000
        up = "z" if header.startswith(AXIS_UP) else "y"
        name = f"{part}-{slug(header)}.stl"
        m = print_stl.mesh(part, 0.1, faces, up=up)
        m.export(os.path.join(OUT, name))
        n = sum(cols[part].values())
        colours = ", ".join(f"{c}× {partlist.COLORS[k][2].lower()}" for k, c in cols[part].most_common())
        rows.append((name, header, n, colours, m))
        print(f"{name:60s} {print_stl.report(m)}", flush=True)
    with open(os.path.join(OUT, "LISTA.md"), "w") as fh:
        fh.write(f"# Delar för 3D-utskrift – {len(pl)} delar, {len(rows)} sorter\n\n"
                 "Varje fil är en sluten solid i millimeter, lagd för utskrift. Antal och färger är vad modellen behöver.\n"
                 "Däcken finns också delade i halvor i `print/` (bäst för TPU).\n\n"
                 "| Fil | Del | Antal | Färger | Storlek (mm) |\n|---|---|---:|---|---|\n")
        for name, header, n, colours, m in rows:
            fh.write(f"| `{name}` | {header} | {n} | {colours} | {' × '.join(f'{e:.1f}' for e in m.extents)} |\n")
    bad = [r[0] for r in rows if not r[4].is_watertight]
    print(f"{len(rows)} parts, {len(bad)} not closed: {bad}")


if __name__ == "__main__":
    main()
