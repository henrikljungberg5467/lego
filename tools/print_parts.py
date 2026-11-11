"""Printable STL files for the model's parts, all of them or a chosen subset.

Each kind of part becomes one closed solid (tools/print_stl.py) in print/delar/<subset>/, with a list
of how many are needed and in which colours (counted within the subset). Wheels, tyres, gears,
bushes and axle connectors lie with their axis vertical; everything else stands as in the model
(studs up, beams flat, axles and pins lying down).

Studs, tubes and posts use LEGO's real diameters (see print_stl.print_triangles); --clutch MM adds to
all three to tune the fit to a printer (default 0).

Usage: python3 tools/print_parts.py [filters] [--name NAME] [--clutch MM] [--zip]
       python3 tools/print_parts.py --list          what the filters can choose from
Filters (combine freely; a part must match all of them):
  --section deck,body      build sections (see --list)
  --color grön,svart       colours, Swedish names or LDraw codes
  --kind technic|system|wheels
  --parts 3023,61332       part numbers
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildplan  # noqa: E402
import ldraw as L  # noqa: E402
import partlist  # noqa: E402
import print_stl  # noqa: E402
from instructions import SECTIONS  # noqa: E402

OUT = os.path.join(L.ROOT, "print", "delar")
AXIS_UP = ("Technic Gear", "Tyre", "Wheel", "Technic Bush", "Technic Connector (Axle/Bush)", "Technic Axle Joiner")


def slug(text):
    s = re.sub(r"[^a-z0-9åäö]+", "-", text.lower()).strip("-")
    return re.sub(r"-+", "-", s)[:48].strip("-")


def kind(header):
    return "wheels" if header.startswith(("Tyre", "Wheel")) else "technic" if header.startswith("Technic") else "system"


def placements(model):
    """[(part, colour code, section)] for every part in the model."""
    pl, steps = buildplan.plan(model)
    sec = {}
    for st in steps:
        for i in st["parts"]:
            sec[i] = st["section"]
    return [(p.part[:-4], p.color, sec[i]) for i, p in enumerate(pl)]


def colour_code(name):
    for code, (_, _, sv) in partlist.COLORS.items():
        if name.lower() in (code, sv.lower()):
            return code
    sys.exit(f"unknown colour: {name} (choose from {', '.join(c[2].lower() for c in partlist.COLORS.values())})")


def arg(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None


def overview(items):
    print("Sektioner (--section):")
    for sid, title in SECTIONS.items():
        sel = [x for x in items if x[2] == sid]
        print(f"  {sid:13s} {title:30s} {len(sel):3d} delar, {len({x[0] for x in sel}):2d} sorter")
    print("Färger (--color):")
    for code, n in Counter(x[1] for x in items).most_common():
        print(f"  {partlist.COLORS[code][2].lower():12s} {n:3d} delar, {len({x[0] for x in items if x[1] == code}):2d} sorter")
    print("Typer (--kind):")
    for k in ("system", "technic", "wheels"):
        sel = [x for x in items if kind(L.part_header(x[0] + '.dat')) == k]
        print(f"  {k:12s} {len(sel):3d} delar, {len({x[0] for x in sel}):2d} sorter")


def main():
    model = os.path.join(L.ROOT, "model", "z315e.mpd")
    items = placements(model)
    if "--list" in sys.argv:
        overview(items)
        return
    filters = []
    if arg("--section"):
        secs = arg("--section").split(",")
        unknown = [s for s in secs if s not in SECTIONS]
        if unknown:
            sys.exit(f"unknown section: {unknown} (see --list)")
        filters.append(lambda x: x[2] in secs)
    if arg("--color"):
        codes = [colour_code(c) for c in arg("--color").split(",")]
        filters.append(lambda x: x[1] in codes)
    if arg("--kind"):
        kinds = arg("--kind").split(",")
        filters.append(lambda x: kind(L.part_header(x[0] + ".dat")) in kinds)
    if arg("--parts"):
        wanted = arg("--parts").split(",")
        filters.append(lambda x: x[0] in wanted)
    chosen = [x for x in items if all(f(x) for f in filters)]
    if not chosen:
        sys.exit("no parts match the filters")
    clutch = float(arg("--clutch") or 0)
    name = arg("--name") or "-".join(slug(arg(f)) for f in ("--section", "--color", "--kind", "--parts") if arg(f)) or "alla"
    out = os.path.join(OUT, name)
    os.makedirs(out, exist_ok=True)
    cols = defaultdict(Counter)
    for part, colour, _ in chosen:
        cols[part][colour] += 1
    rows = []
    for part in sorted(cols, key=lambda k: (L.part_header(k + ".dat"), k)):
        header = L.part_header(part + ".dat")
        lo, hi = L.bbox(part + ".dat")
        size = max(hi - lo) * print_stl.MM
        faces = 8_000 if size < 20 else 16_000 if size < 50 else 30_000
        m = print_stl.mesh(part, 0.1, faces, up="z" if header.startswith(AXIS_UP) else "y", clutch=clutch)
        fname = f"{part}-{slug(header)}.stl"
        m.export(os.path.join(out, fname))
        colours = ", ".join(f"{c}× {partlist.COLORS[k][2].lower()}" for k, c in cols[part].most_common())
        rows.append((fname, header, sum(cols[part].values()), colours, m))
        print(f"{fname:60s} {print_stl.report(m)}", flush=True)
    with open(os.path.join(out, "LISTA.md"), "w") as fh:
        fh.write(f"# Delar för 3D-utskrift: {name}\n\n{len(chosen)} delar, {len(rows)} sorter. Varje fil är en sluten solid "
                 "i millimeter, lagd för utskrift. Antal och färger gäller den här delmängden. Knoppar "
                 f"{print_stl.STUD_MM + clutch:.2f} mm, rör {print_stl.TUBE_MM + clutch:.2f} mm, stolpar "
                 f"{print_stl.POST_MM + clutch:.2f} mm (grepp {clutch:+.2f} mm).\n\n"
                 "| Fil | Del | Antal | Färger | Storlek (mm) |\n|---|---|---:|---|---|\n")
        for fname, header, n, colours, m in rows:
            fh.write(f"| `{fname}` | {header} | {n} | {colours} | {' × '.join(f'{e:.1f}' for e in m.extents)} |\n")
    if "--zip" in sys.argv:
        import zipfile
        with zipfile.ZipFile(out + ".zip", "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(os.listdir(out)):
                z.write(os.path.join(out, f), os.path.join(name, f))
    bad = [r[0] for r in rows if not r[4].is_watertight]
    total = sum(os.path.getsize(os.path.join(out, r[0])) for r in rows)
    print(f"{name}: {len(rows)} sorter, {len(chosen)} delar, {total / 1e6:.1f} MB, {len(bad)} inte slutna {bad}")


if __name__ == "__main__":
    main()
