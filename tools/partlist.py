"""Parts list from an LDraw model.

Writes:
  <out>/parts.csv              Rebrickable import format (Part,Color,Quantity)
  <out>/bricklink_wanted.xml   BrickLink wanted list (upload via Want > Upload)
  <out>/parts.md               human readable table
Usage: python3 tools/partlist.py model.mpd outdir
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldraw as L  # noqa: E402
import partsdb  # noqa: E402

# LDraw colour -> (Rebrickable id, BrickLink id, Swedish name)
COLORS = {
    "0": (0, 11, "Svart"), "1": (1, 7, "Blå"), "2": (2, 6, "Grön"), "4": (4, 5, "Röd"),
    "14": (14, 3, "Gul"), "15": (15, 1, "Vit"), "25": (25, 4, "Orange"),
    "71": (71, 86, "Ljus blågrå"), "72": (72, 85, "Mörk blågrå"),
}
# LDraw part number -> BrickLink item number where they differ
BRICKLINK_PART = {"32123b": "4265c", "6141": "4073", "3040b": "3040", "32064a": "32064a"}


def main():
    model, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    pl = L.load_model(model)
    cnt = Counter((p.part[:-4], p.color) for p in pl)
    rows = []
    for (part, col), n in cnt.items():
        rb_col, bl_col, cname = COLORS[col]
        name = partsdb.name(part) or L.part_header(part + ".dat")
        rows.append(dict(part=part, color=col, rb_color=rb_col, bl_color=bl_col, cname=cname, n=n, name=name,
                         bl_part=BRICKLINK_PART.get(part, part), sets=partsdb.sets_with(part, rb_col)))
    rows.sort(key=lambda r: (r["cname"], r["name"]))
    with open(os.path.join(out, "parts.csv"), "w") as fh:
        fh.write("Part,Color,Quantity\n")
        for r in rows:
            fh.write(f"{r['part']},{r['rb_color']},{r['n']}\n")
    with open(os.path.join(out, "bricklink_wanted.xml"), "w") as fh:
        fh.write("<INVENTORY>\n")
        for r in rows:
            fh.write(f"  <ITEM><ITEMTYPE>P</ITEMTYPE><ITEMID>{r['bl_part']}</ITEMID><COLOR>{r['bl_color']}</COLOR>"
                     f"<MINQTY>{r['n']}</MINQTY></ITEM>\n")
        fh.write("</INVENTORY>\n")
    total = sum(r["n"] for r in rows)
    with open(os.path.join(out, "parts.md"), "w") as fh:
        fh.write(f"# Dellista – {total} delar, {len(rows)} unika del/färg-kombinationer\n\n")
        fh.write("| Antal | Del | Färg | Benämning | Finns i antal officiella set |\n|---:|---|---|---|---:|\n")
        for r in rows:
            fh.write(f"| {r['n']} | {r['part']} | {r['cname']} | {r['name']} | {r['sets']} |\n")
    print(f"{total} parts, {len(rows)} lots -> {out}")


if __name__ == "__main__":
    main()
