"""Pack an MPD together with every LDraw library file it needs (for three.js LDrawLoader).

Usage: python3 tools/pack.py model.mpd out.mpd
Embedded file names follow LDrawLoader's lookup rules ("s\\x" -> "parts/s/x", "48\\x" -> "p/48/x").
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldraw as L  # noqa: E402


def loader_name(ref):
    n = ref.strip().replace("\\", "/").lower()
    if n.startswith("s/"):
        return "parts/" + n
    if n.startswith("48/"):
        return "p/" + n
    return n


def main():
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, encoding="utf-8").read().replace("\r\n", "\n")
    model_files = {m.lower() for m in re.findall(r"^0 FILE (.+)$", text, re.M)}
    needed, order = set(), []

    def visit(ref):
        name = L.norm(ref)
        if name in needed or name in model_files:
            return
        path = L.find(name)
        if not path:
            print("missing", name)
            return
        needed.add(name)
        order.append(name)
        for line in L.read_lines(path):
            t = line.split()
            if len(t) >= 15 and t[0] == "1":
                visit(" ".join(t[14:]))

    colours = set()
    for line in text.splitlines():
        t = line.split()
        if len(t) >= 15 and t[0] == "1":
            colours.add(t[1])
            visit(" ".join(t[14:]))
    # colour definitions (plus the edge colours LDraw parts refer to)
    cfg = open(os.path.join(L.LIB, "LDConfig.ldr"), encoding="utf-8").read().splitlines()
    defs = [ln for ln in cfg if ln.startswith("0 !COLOUR")]
    lines = text.splitlines()
    first_type1 = next(i for i, ln in enumerate(lines) if ln.startswith("1 "))
    out = lines[:first_type1] + defs + lines[first_type1:]
    for name in order:
        body = [ln for ln in L.read_lines(L.find(name))]
        out.append(f"0 FILE {loader_name(name)}")
        out += body
        out.append("")
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"packed {len(order)} library files, {os.path.getsize(dst) / 1e6:.1f} MB -> {dst}")


if __name__ == "__main__":
    main()
