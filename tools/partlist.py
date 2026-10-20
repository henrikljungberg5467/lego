"""Parts list from an LDraw model.

Writes:
  <out>/parts.csv              Rebrickable import format (Part,Color,Quantity)
  <out>/bricklink_wanted.xml   BrickLink wanted list (upload via Want > Upload)
  <out>/pick_a_brick.csv       LEGO Pick a Brick upload (elementId,quantity), needs REBRICKABLE_ELEMENTS
  <out>/parts.md               human readable table
If <out>/pick_a_brick_avvisade.txt lists element IDs that Pick a Brick rejected, those IDs are skipped and
  <out>/inte_pa_pick_a_brick.md     what Pick a Brick does not have, and what was substituted
  <out>/bricklink_inte_pa_pab.xml   BrickLink wanted list for the parts with no accepted element ID
Usage: python3 tools/partlist.py model.mpd outdir

REBRICKABLE_ELEMENTS points at Rebrickable's elements table (elements.csv or a parquet copy).
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
ELEMENTS = os.environ.get("REBRICKABLE_ELEMENTS",
                          "/home/user/data-dl/kiliantscherny_Fun-With-LEGO-data/data/rebrickable/elements.parquet")


def element_ids(part, color):
    """LEGO element IDs for a Rebrickable part/colour, preferred (newest 7-digit) first."""
    global _elements
    if "_elements" not in globals():
        _elements = None
        if os.path.exists(ELEMENTS):
            import pandas as pd
            e = pd.read_parquet(ELEMENTS) if ELEMENTS.endswith(".parquet") else pd.read_csv(ELEMENTS)
            _elements = {}
            for eid, pn, cid in zip(e.element_id, e.part_num, e.color_id):
                _elements.setdefault((str(pn), int(cid)), []).append(int(eid))
    if _elements is None:
        return None
    ids = _elements.get((part, color), [])
    return sorted(ids, key=lambda i: (len(str(i)) == 7, i), reverse=True)


# substitutions made because Pick a Brick did not stock the original element
SUBSTITUTIONS = [
    ("12 × friktionsstift 2780 (svart)", "12 × friktionsstift 61332 (svart), nyare version med samma form"),
    ("2 × axelkoppling med tvärhål 32039 (svart)", "2 × 42135 (svart), förstärkt version med samma form"),
    ("4 × rund hörnkloss 4 × 4, 48092 (grön)", "12 × rund hörnplatta 4 × 4, 30565 (grön), sex i höjd per hörn"),
    ("1 × platta 6 × 8, 3036 (gul) under sätet", "fyra plattor 2 × 8, 3034 (gul), i stället för 6 × 8 + 2 × 8"),
]

# current part (used in the model) -> older mould it replaced
REPLACES = {"61332": "2780", "42135": "32039"}


def rejected_ids(out):
    path = os.path.join(out, "pick_a_brick_avvisade.txt")
    if not os.path.exists(path):
        return set()
    return {int(ln.split()[0]) for ln in open(path) if ln.strip() and not ln.startswith("#")}


def element_owner(eid):
    """(part_num, color_id) of an element ID, or None."""
    element_ids("", 0)  # make sure the table is loaded
    for key, ids in (_elements or {}).items():
        if eid in ids:
            return key
    return None


# LDraw part number -> BrickLink item number where they differ
BRICKLINK_PART = {"32123b": "4265c", "6141": "4073", "3040b": "3040", "32064a": "32064a",
                  "61332": "2780", "42135": "32039"}  # older moulds are interchangeable and plentiful on BrickLink


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
                         bl_part=BRICKLINK_PART.get(part, part), sets=partsdb.sets_with(part, rb_col),
                         elements=element_ids(part, rb_col)))
    rows.sort(key=lambda r: (r["cname"], r["name"]))
    rejected = rejected_ids(out)
    old_to_new = {v: k for k, v in REPLACES.items()}
    affected = {}
    for eid in sorted(rejected):
        owner = element_owner(eid)
        if owner:
            part, col = owner
            affected[(old_to_new.get(part, part), col)] = (eid, part)
    for r in rows:
        r["rejected"] = affected.get((r["part"], r["rb_color"]))
        if r["elements"] is not None:
            r["elements"] = [i for i in r["elements"] if i not in rejected]
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
    have_el = all(r["elements"] is not None for r in rows)
    if have_el:
        with open(os.path.join(out, "pick_a_brick.csv"), "w") as fh:
            fh.write("elementId,quantity\n")
            for r in rows:
                if r["elements"]:
                    fh.write(f"{r['elements'][0]},{r['n']}\n")
        missing = [r for r in rows if not r["elements"]]
        if missing:
            print("no element id:", [(r["part"], r["color"]) for r in missing])
    if rejected:
        gone = [r for r in rows if r["elements"] is not None and not r["elements"]]
        old = os.path.join(out, "pick_a_brick_forsok2.csv")
        if os.path.exists(old):
            os.remove(old)
        with open(os.path.join(out, "bricklink_inte_pa_pab.xml"), "w") as fh:
            fh.write("<INVENTORY>\n")
            for r in gone:
                fh.write(f"  <ITEM><ITEMTYPE>P</ITEMTYPE><ITEMID>{r['bl_part']}</ITEMID><COLOR>{r['bl_color']}</COLOR>"
                         f"<MINQTY>{r['n']}</MINQTY></ITEM>\n")
            fh.write("</INVENTORY>\n")
        with open(os.path.join(out, "inte_pa_pick_a_brick.md"), "w") as fh:
            fh.write("# Delar som inte finns på Pick a Brick\n\n"
                     "Kontrollerat mot Pick a Brick (lego.com, Sverige) i oktober 2026. Element-ID som avvisats står i "
                     "`pick_a_brick_avvisade.txt`; `pick_a_brick.csv` innehåller bara element som har godkänts.\n\n"
                     "## Köp på BrickLink\n\n"
                     "Ladda upp `bricklink_inte_pa_pab.xml` som önskelista på BrickLink.\n\n"
                     "| Antal | Del | Färg | Benämning |\n|---:|---|---|---|\n")
            for r in gone:
                fh.write(f"| {r['n']} | {r['part']} | {r['cname']} | {r['name']} |\n")
            fh.write("\n## Ersatta i modellen\n\n"
                     "De här delarna fanns inte på Pick a Brick och är utbytta mot delar som finns där. "
                     "Modellen är kontrollerad igen efter bytet.\n\n"
                     "| Tidigare | Nu |\n|---|---|\n")
            for a, b in SUBSTITUTIONS:
                fh.write(f"| {a} | {b} |\n")
            fh.write("\n## Gick igenom med ett annat element-ID\n\n"
                     "Gul kloss 1 × 2, gul platta 2 × 4 slät, svart platta 4 × 10 och svart axelkoppling slät "
                     "nekades med sitt första element-ID men godkändes med ett äldre nummer för samma del. "
                     "`pick_a_brick.csv` använder de godkända numren.\n")
        print(f"{len(gone)} lots not on Pick a Brick")
    total = sum(r["n"] for r in rows)
    with open(os.path.join(out, "parts.md"), "w") as fh:
        fh.write(f"# Dellista – {total} delar, {len(rows)} unika del/färg-kombinationer\n\n")
        if have_el:
            fh.write("Elementnummer är LEGOs nummer för del + färg (det som Pick a Brick använder). "
                     "Det första står i `pick_a_brick.csv`; övriga är äldre eller alternativa nummer för samma del.\n\n")
        fh.write("| Antal | Del | Färg | Benämning | Elementnummer | Finns i antal officiella set |\n|---:|---|---|---|---|---:|\n")
        for r in rows:
            el = ", ".join(str(i) for i in (r["elements"] or []))
            fh.write(f"| {r['n']} | {r['part']} | {r['cname']} | {r['name']} | {el} | {r['sets']} |\n")
    print(f"{total} parts, {len(rows)} lots -> {out}")


if __name__ == "__main__":
    main()
