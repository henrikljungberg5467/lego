"""Building instructions as a PDF: docs/bygginstruktioner.pdf.

Uses the same build plan as the viewer (tools/buildplan.py): sub-assemblies built on their own pages
in a green frame, then mounted; every part's direction comes from the collision-free sweep.
Pictures are rendered headless by tools/instructions.mjs + tools/instructions.html.

Usage: python3 tools/instructions.py [model.mpd] [out.pdf]
"""
import html
import json
import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildplan  # noqa: E402
import ldraw as L  # noqa: E402
import partlist  # noqa: E402

ROOT = L.ROOT
WORK = os.path.join(ROOT, "tmp", "instructions")
SECTIONS = {"rear_frame": "Bakram med hjullager", "rear_wheels": "Drivhjul", "floor": "Golv, fotstöd och lyftpedal",
            "front_frame": "Främre ram och tvärbalk", "casters": "Länkhjul", "deck": "Klippaggregat med knivar",
            "deck_hangers": "Upphängning och knopp", "body": "Kaross och stänkskärmar", "seat": "Förarstol",
            "lap_bars": "Styrspakar"}
FONTS = os.path.join(ROOT, "node_modules", "@fontsource")
esc = html.escape


def lot_key(p):
    return f"{p.part[:-4]}-{p.color}"


def write_plan(model):
    pl, steps = buildplan.plan(model)
    buildplan.directions(pl, steps)
    where = {}
    for si, st in enumerate(steps):
        for i, d, t in st["order"]:
            where[i] = (si, [float(c) for c in d], int(t))
    first = {}
    for i, p in enumerate(pl):
        first.setdefault(lot_key(p), i)
    plan = {"parts": [{"part": p.part[:-4], "color": p.color, "step": where[i][0], "dir": where[i][1], "travel": where[i][2],
                       "ctx": steps[where[i][0]]["ctx"]} for i, p in enumerate(pl)],
            "steps": [{"ctx": st["ctx"], "section": st["section"],
                       "mounts": [{"sub": s, "dir": [int(c) for c in d], "travel": int(t)} for s, d, t in st["mount_paths"]],
                       "order": [i for i, _, _ in st["order"]]} for st in steps],
            "lots": [{"key": k, "index": i} for k, i in first.items()]}
    os.makedirs(WORK, exist_ok=True)
    with open(os.path.join(WORK, "plan.json"), "w") as fh:
        json.dump(plan, fh)
    return pl, plan


def element_of(part, color, rejected):
    rb = partlist.COLORS[color][0]
    els = [e for e in (partlist.element_ids(part, rb) or []) if e not in rejected]
    return els[0] if els else None


def thumbs(lots_counts, size_mm):
    out = []
    for key, n in lots_counts:
        out.append(f'<div class="t" style="width:{size_mm}mm"><img src="img/part-{key}.png"><b>{n}×</b></div>')
    return "".join(out)


def page(body, cls=""):
    return f'<section class="page {cls}">{body}</section>'


def build_html(pl, plan):
    rejected = partlist.rejected_ids(os.path.join(ROOT, "docs"))
    steps = plan["steps"]
    n_steps = len(steps)
    lots = Counter(lot_key(p) for p in pl)
    pages = []
    # cover
    pages.append(page(f'''
      <div class="cover">
        <div class="kicker">LEGO-modell · skala 1:8 · bygginstruktion</div>
        <h1>John Deere <span>Z315E</span> ZTrak</h1>
        <img class="hero" src="{ROOT}/renders/z315e-hero.png">
        <div class="specs"><span><b>{len(pl)}</b> delar</span><span><b>{n_steps}</b> byggsteg</span>
          <span><b>23 × 18 × 14</b> cm</span><span>Nollsvängsklippare med 42-tums klippaggregat</span></div>
      </div>''', "plain"))
    # how to read
    pages.append(page(f'''
      <h2>Så läser du instruktionen</h2>
      <div class="howto">
        <div><h3>Steg</h3><p>Rutan överst på varje sida visar delarna som behövs i steget. Delar från tidigare steg är ljusare
          i bilden, så det som är nytt syns tydligt.</p></div>
        <div><h3>Röda pilar</h3><p>Delar som inte sätts på ovanifrån har en röd pil som visar varifrån de kommer:
          underifrån, från sidan eller längs en axel. När delarna i ett steg sätts underifrån visas modellen underifrån.</p></div>
        <div><h3>Delmonteringar</h3><p>Sidor med <span class="g">grön ram</span> är en delmontering: främre ramen,
          klippaggregatet, karossen och sätet byggs för sig. Därefter kommer ett steg där den färdiga delmonteringen sätts på plats.</p></div>
        <div><h3>Knivarna</h3><p>När modellen är klar snurrar de tre knivarna under klippaggregatet när du vrider på den gula
          knoppen ovanpå vänster sidobalk.</p></div>
        <div><h3>Dekaler</h3><p>Dekalarket <i>stickers/z315e_stickers.svg</i> skrivs ut i skala 1:1 på klisteretikettpapper.</p></div>
        <div><h3>Delarna</h3><p>Nästa sidor visar alla delar. Elementnumret är det som LEGO Pick a Brick använder; listan finns
          även som <i>docs/pick_a_brick.csv</i>. Bakdäcken (55976) finns inte på Pick a Brick, köp dem på BrickLink.</p></div>
      </div>'''))
    # inventory
    inv = sorted(lots.items(), key=lambda kv: (partlist.COLORS[kv[0].rsplit("-", 1)[1]][2], kv[0]))
    per = 40
    for k in range(0, len(inv), per):
        cells = []
        for key, n in inv[k:k + per]:
            part, color = key.rsplit("-", 1)
            el = element_of(part, color, rejected)
            cells.append(f'''<div class="inv"><img src="img/part-{key}.png"><div><b>{n}×</b><br>{esc(part)}
              <br><span>{esc(partlist.COLORS[color][2])}</span><br><span class="el">{el or "BrickLink"}</span></div></div>''')
        pages.append(page(f'<h2>Alla delar <small>{len(pl)} st, {len(inv)} sorter'
                          f'{" (forts.)" if k else ""}</small></h2><div class="invgrid">{"".join(cells)}</div>'))
    # steps
    for si, st in enumerate(steps):
        sec = SECTIONS.get(st["section"], st["section"])
        sub = st["ctx"] != "main"
        img = f"img/step-{si + 1:03d}.jpg"
        if st["mounts"]:
            m = st["mounts"][0]["sub"].replace(".ldr", "")
            call = (f'<div class="callout mount"><img src="img/sub-{m}.jpg"><span>Färdig delmontering</span></div>')
            label = f"Montera: {esc(sec)}"
        else:
            cnt = Counter(lot_key(pl[i]) for i in st["order"])
            order = []
            for i in st["order"]:
                k = lot_key(pl[i])
                if k not in order:
                    order.append(k)
            size = 22 if len(order) <= 8 else 18
            call = f'<div class="callout">{thumbs([(k, cnt[k]) for k in order], size)}</div>'
            label = f"Delmontering: {esc(sec)}" if sub else esc(sec)
        body = f'''<div class="hdr"><span>{label}</span><span>Steg {si + 1} av {n_steps}</span></div>
          <div class="top"><div class="num">{si + 1}</div>{call}</div>
          <div class="pic"><img src="{img}"></div>'''
        pages.append(page(body, "sub" if sub else ""))
    # finished
    pages.append(page(f'''<h2>Klar!</h2>
      <div class="done"><img src="{ROOT}/renders/z315e-front-left.png"><img src="{ROOT}/renders/z315e-under.png"></div>
      <ul class="feat"><li>Vrid på den gula knoppen: de tre knivarna snurrar.</li>
        <li>Framhjulen är länkhjul som svänger fritt. Bakhjulen rullar var för sig, så modellen kan snurra på stället.</li>
        <li>Styrspakarna kan fällas ut i parkeringsläge eller in i körläge.</li></ul>'''))
    for i, p in enumerate(pages):
        pages[i] = p.replace("</section>", f'<div class="foot"><span>John Deere Z315E ZTrak · LEGO</span><span>{i + 1}</span></div></section>')
    css = CSS.replace("FONTS", FONTS)
    return f'<!doctype html><html lang="sv"><head><meta charset="utf-8"><title>Bygginstruktion</title><style>{css}</style></head><body>{"".join(pages)}</body></html>'


CSS = """
@font-face { font-family: Saira; font-weight: 600; src: url(file://FONTS/saira-condensed/files/saira-condensed-latin-600-normal.woff2); }
@font-face { font-family: Saira; font-weight: 800; src: url(file://FONTS/saira-condensed/files/saira-condensed-latin-800-normal.woff2); }
@font-face { font-family: Barlow; font-weight: 400; src: url(file://FONTS/barlow/files/barlow-latin-400-normal.woff2); }
@font-face { font-family: Barlow; font-weight: 600; src: url(file://FONTS/barlow/files/barlow-latin-600-normal.woff2); }
@font-face { font-family: Mono; font-weight: 400; src: url(file://FONTS/ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2); }
@page { size: A4 landscape; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Barlow, sans-serif; color: #18211a; font-size: 11pt; }
.page { width: 297mm; height: 210mm; padding: 9mm 12mm 12mm; position: relative; overflow: hidden; break-after: page;
  display: flex; flex-direction: column; }
.page.sub { border: 2.2mm solid #367c2b; padding: 7mm 10mm 10mm; }
.foot { position: absolute; left: 12mm; right: 12mm; bottom: 5mm; display: flex; justify-content: space-between;
  font-size: 8pt; color: #5b6a5d; }
.hdr { display: flex; justify-content: space-between; font-family: Saira; font-weight: 600; font-size: 12pt; color: #5b6a5d;
  border-bottom: 0.3mm solid #c9d3c6; padding-bottom: 1.5mm; }
.page.sub .hdr span:first-child { color: #367c2b; }
.top { display: flex; align-items: flex-start; gap: 6mm; margin-top: 3mm; }
.num { font-family: Saira; font-weight: 800; font-size: 46pt; line-height: 0.9; min-width: 22mm; }
.callout { display: flex; flex-wrap: wrap; gap: 2mm 4mm; background: #eef3ec; border: 0.3mm solid #c9d3c6;
  border-radius: 2.5mm; padding: 2.5mm 4mm; max-width: 235mm; }
.callout .t { display: flex; flex-direction: column; align-items: center; }
.callout .t img { width: 100%; aspect-ratio: 1; object-fit: contain; }
.callout .t b { font-family: Saira; font-weight: 800; font-size: 12pt; margin-top: -1mm; }
.callout.mount { flex-direction: column; align-items: center; padding: 2mm; }
.callout.mount img { height: 38mm; }
.callout.mount span { font-size: 9pt; color: #5b6a5d; }
.pic { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; margin-top: 2mm; }
.pic img { max-width: 100%; max-height: 100%; object-fit: contain; }
h2 { font-family: Saira; font-weight: 800; font-size: 26pt; margin: 0 0 4mm; }
h2 small { font-family: Barlow; font-weight: 400; font-size: 12pt; color: #5b6a5d; margin-left: 3mm; }
h3 { font-family: Saira; font-weight: 600; font-size: 15pt; margin: 0 0 1.5mm; color: #367c2b; }
.howto { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8mm 10mm; }
.howto p { margin: 0; line-height: 1.4; }
.g { color: #367c2b; font-weight: 600; }
.invgrid { display: grid; grid-template-columns: repeat(5, 1fr); grid-auto-rows: 20.5mm; gap: 1.6mm 3mm; }
.inv { display: flex; gap: 2mm; align-items: center; font-size: 8pt; line-height: 1.25; }
.inv img { width: 18mm; height: 18mm; object-fit: contain; }
.inv b { font-family: Saira; font-weight: 800; font-size: 12pt; }
.inv span { color: #5b6a5d; }
.inv .el { font-family: Mono; font-size: 7.5pt; color: #18211a; }
.plain { justify-content: center; }
.cover { text-align: center; }
.cover .kicker { font-family: Saira; font-weight: 600; font-size: 14pt; color: #5b6a5d; letter-spacing: 0.04em; }
.cover h1 { font-family: Saira; font-weight: 800; font-size: 44pt; margin: 1mm 0 3mm; }
.cover h1 span { color: #367c2b; }
.cover .hero { height: 125mm; }
.cover .specs { display: flex; justify-content: center; gap: 9mm; font-size: 12pt; margin-top: 3mm; color: #5b6a5d; }
.cover .specs b { color: #18211a; font-family: Saira; font-weight: 800; font-size: 15pt; }
.done { display: flex; gap: 8mm; justify-content: center; height: 120mm; }
.done img { height: 100%; object-fit: contain; }
.feat { font-size: 13pt; line-height: 1.6; }
"""


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "model", "z315e.mpd")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "docs", "bygginstruktioner.pdf")
    pl, plan = write_plan(model)
    subprocess.run(["node", os.path.join(ROOT, "tools", "instructions.mjs"), "render", WORK], check=True)
    book = os.path.join(WORK, "book.html")
    with open(book, "w", encoding="utf-8") as fh:
        fh.write(build_html(pl, plan))
    subprocess.run(["node", os.path.join(ROOT, "tools", "instructions.mjs"), "pdf", book, out], check=True)
    print(f"{out}: {os.path.getsize(out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
