"""Build the web viewer: viewer/index.html (+ packed model, LDConfig, part names)."""
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildplan  # noqa: E402
import ldraw as L  # noqa: E402
import partsdb  # noqa: E402

ROOT = L.ROOT
DOWNLOADS = ("bygginstruktioner.pdf", "pick_a_brick.csv", "bricklink_inte_pa_pab.xml")   # linked from the page
SECTIONS = {"rear_frame": "Bakram med hjullager", "rear_wheels": "Drivhjul", "floor": "Golv, fotstöd och lyftpedal",
            "front_frame": "Främre ram och tvärbalk", "casters": "Länkhjul", "deck": "Klippaggregat med knivar",
            "deck_hangers": "Upphängning och knopp", "body": "Kaross och stänkskärmar", "seat": "Förarstol",
            "lap_bars": "Styrspakar"}
SV = {"0": "Svart", "1": "Blå", "2": "Grön", "4": "Röd", "14": "Gul", "15": "Vit", "25": "Orange",
      "71": "Ljus blågrå", "72": "Mörk blågrå"}


def main():
    model = os.path.join(ROOT, "model", "z315e.mpd")
    vdir = os.path.join(ROOT, "viewer")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "pack.py"), model, os.path.join(vdir, "z315e_packed.mpd")], check=True)
    shutil.copy(os.path.join(L.LIB, "LDConfig.ldr"), os.path.join(vdir, "LDConfig.ldr"))
    pl, steps = buildplan.plan(model)
    buildplan.directions(pl, steps)
    # per part (in file order): step, position in the step's sequence, direction it comes from, travel
    where = [None] * len(pl)
    for si, st in enumerate(steps):
        for k, (i, d, t) in enumerate(st["order"]):
            where[i] = [si, k, *[round(float(c), 3) for c in d], int(t)]
    plan = {"parts": [[p.part[:-4]] + where[i] for i, p in enumerate(pl)],
            "steps": [{"ctx": st["ctx"], "section": st["section"],
                       "mounts": [[sub, *[int(c) for c in d], int(t)] for sub, d, t in st["mount_paths"]]} for st in steps],
            "sections": SECTIONS}
    names = {p.part[:-4]: partsdb.name(p.part[:-4]) or L.part_header(p.part) for p in pl}
    cfg = open(os.path.join(L.LIB, "LDConfig.ldr")).read()
    cols = {}
    for c in sorted({p.color for p in pl}, key=int):
        mm = re.search(r"0 !COLOUR \S+\s+CODE\s+%s\s+VALUE\s+(#[0-9A-Fa-f]{6})" % c, cfg)
        cols[c] = [SV.get(c, c), mm.group(1)]
    data = json.dumps({"names": names, "colors": cols, "plan": plan}, ensure_ascii=False, separators=(",", ":"))
    tpl = open(os.path.join(vdir, "index.template.html"), encoding="utf-8").read()
    pdf = os.path.join(ROOT, "docs", "bygginstruktioner.pdf")
    html = tpl.replace("__PARTDATA__", data).replace("__PDFSIZE__", f"{os.path.getsize(pdf) / 1e6:.0f} MB")
    open(os.path.join(vdir, "index.html"), "w", encoding="utf-8").write(html)
    # local test copy that loads three.js from node_modules instead of the CDN
    tdir = os.path.join(ROOT, "tmp", "viewer_test")
    os.makedirs(tdir, exist_ok=True)
    local = html.replace("https://cdn.jsdelivr.net/npm/three@0.169.0/", "/node_modules/three/")
    open(os.path.join(tdir, "index.html"), "w", encoding="utf-8").write("<!doctype html><meta charset=utf-8>" + local)
    for f in ("z315e_packed.mpd", "LDConfig.ldr"):
        shutil.copy(os.path.join(vdir, f), os.path.join(tdir, f))
    for f in DOWNLOADS:   # served next to the page on GitHub Pages and in the artifact
        shutil.copy(os.path.join(ROOT, "docs", f), os.path.join(tdir, f))
    print("viewer built:", os.path.getsize(os.path.join(vdir, "index.html")), "bytes html")


if __name__ == "__main__":
    main()
