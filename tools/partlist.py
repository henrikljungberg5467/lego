"""Parts list from an LDraw model.

Writes:
  <out>/parts.csv              Rebrickable import format (Part,Color,Quantity)
  <out>/bricklink_wanted.xml   BrickLink wanted list (upload via Want > Upload)
  <out>/pick_a_brick.csv       LEGO Pick a Brick upload (elementId,quantity), needs REBRICKABLE_ELEMENTS
  <out>/parts.md               human readable table
If <out>/pick_a_brick_avvisade.txt lists element IDs that Pick a Brick rejected, those IDs are skipped and
  <out>/pick_a_brick_forsok2.csv    new attempt for the affected parts (other IDs or newer replacement parts)
  <out>/inte_pa_pick_a_brick.md     what Pick a Brick did not have, and what to do instead
  <out>/bricklink_inte_pa_pab.xml   BrickLink wanted list for those parts
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
    hit = [r for r in rows if r["rejected"]]
    if hit:
        retry = [r for r in hit if r["elements"]]
        with open(os.path.join(out, "pick_a_brick_forsok2.csv"), "w") as fh:
            fh.write("elementId,quantity\n")
            for r in retry:
                fh.write(f"{r['elements'][0]},{r['n']}\n")
        with open(os.path.join(out, "bricklink_inte_pa_pab.xml"), "w") as fh:
            fh.write("<INVENTORY>\n")
            for r in hit:
                fh.write(f"  <ITEM><ITEMTYPE>P</ITEMTYPE><ITEMID>{r['bl_part']}</ITEMID><COLOR>{r['bl_color']}</COLOR>"
                         f"<MINQTY>{r['n']}</MINQTY></ITEM>\n")
            fh.write("</INVENTORY>\n")
        with open(os.path.join(out, "inte_pa_pick_a_brick.md"), "w") as fh:
            n_parts = sum(r["n"] for r in hit)
            fh.write(f"# Delar som Pick a Brick inte hade\n\n"
                     f"{len(hit)} av {len(rows)} rader ({n_parts} av {sum(r['n'] for r in rows)} delar) avvisades med "
                     f"\"Detta element-ID är för närvarande inte tillgängligt på Pick a Brick\".\n\n"
                     f"- **Försök igen:** ladda upp `pick_a_brick_forsok2.csv`. Den har andra element-ID för samma del, "
                     f"eller den nuvarande versionen av delen.\n"
                     f"- **Det som inte går att få där:** köp på BrickLink med `bricklink_inte_pa_pab.xml` "
                     f"(den innehåller alla rader nedan, så den fungerar även om försök 2 misslyckas).\n\n")
            fh.write("| Antal | Del | Färg | Benämning | Avvisat ID | Gör så här |\n|---:|---|---|---|---|---|\n")
            for r in hit:
                eid, oldpart = r["rejected"]
                if not r["elements"]:
                    todo = f"Finns inte på Pick a Brick. Köp på BrickLink (del {r['bl_part']})."
                elif oldpart != r["part"]:
                    todo = (f"Ersatt av nyare versionen {r['part']} (samma form och funktion). "
                            f"Prova element {r['elements'][0]}.")
                else:
                    todo = "Prova element " + " eller ".join(str(i) for i in r["elements"][:2]) + ", annars BrickLink."
                part = oldpart if oldpart == r["part"] else f"{oldpart} → {r['part']}"
                fh.write(f"| {r['n']} | {part} | {r['cname']} | {r['name']} | {eid} | {todo} |\n")
        print(f"{len(hit)} rejected lots, {len(retry)} with something new to try")
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
