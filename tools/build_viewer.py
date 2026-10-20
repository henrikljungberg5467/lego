"""Build the web viewer: viewer/index.html (+ packed model, LDConfig, part names)."""
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldraw as L  # noqa: E402
import partsdb  # noqa: E402

ROOT = L.ROOT
SV = {"0": "Svart", "1": "Blå", "2": "Grön", "4": "Röd", "14": "Gul", "15": "Vit", "25": "Orange",
      "71": "Ljus blågrå", "72": "Mörk blågrå"}


def main():
    model = os.path.join(ROOT, "model", "z315e.mpd")
    vdir = os.path.join(ROOT, "viewer")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "pack.py"), model, os.path.join(vdir, "z315e_packed.mpd")], check=True)
    shutil.copy(os.path.join(L.LIB, "LDConfig.ldr"), os.path.join(vdir, "LDConfig.ldr"))
    pl = L.load_model(model)
    names = {p.part[:-4]: partsdb.name(p.part[:-4]) or L.part_header(p.part) for p in pl}
    cfg = open(os.path.join(L.LIB, "LDConfig.ldr")).read()
    cols = {}
    for c in sorted({p.color for p in pl}, key=int):
        mm = re.search(r"0 !COLOUR \S+\s+CODE\s+%s\s+VALUE\s+(#[0-9A-Fa-f]{6})" % c, cfg)
        cols[c] = [SV.get(c, c), mm.group(1)]
    data = json.dumps({"names": names, "colors": cols}, ensure_ascii=False)
    tpl = open(os.path.join(vdir, "index.template.html"), encoding="utf-8").read()
    html = tpl.replace("__PARTDATA__", data)
    open(os.path.join(vdir, "index.html"), "w", encoding="utf-8").write(html)
    # local test copy that loads three.js from node_modules instead of the CDN
    tdir = os.path.join(ROOT, "tmp", "viewer_test")
    os.makedirs(tdir, exist_ok=True)
    local = html.replace("https://cdn.jsdelivr.net/npm/three@0.169.0/", "/node_modules/three/")
    open(os.path.join(tdir, "index.html"), "w", encoding="utf-8").write("<!doctype html><meta charset=utf-8>" + local)
    for f in ("z315e_packed.mpd", "LDConfig.ldr"):
        shutil.copy(os.path.join(vdir, f), os.path.join(tdir, f))
    print("viewer built:", os.path.getsize(os.path.join(vdir, "index.html")), "bytes html")


if __name__ == "__main__":
    main()
