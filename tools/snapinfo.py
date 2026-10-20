"""Print connection points of parts: tools/snapinfo.py part [part...]"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldraw as L

for p in sys.argv[1:]:
    f = p if p.endswith('.dat') else p + '.dat'
    lo, hi = L.bbox(f)
    print(f'== {p}: {L.part_header(f)}  bbox {lo.round(1).tolist()} .. {hi.round(1).tolist()}')
    seen = set()
    for s in L.snaps(f):
        c = s.p0 + s.u * s.length / 2
        key = (s.gender, tuple(np.round(c, 1)), tuple(np.round(np.abs(s.u), 2)), tuple(x[0] for x in s.secs))
        if key in seen:
            continue
        seen.add(key)
        sh = ''.join(sorted({x[0] for x in s.secs}))
        print(f'   {s.gender} {sh:3s} center {np.round(c,1).tolist()} axis {np.round(s.u,2).tolist()} len {s.length:.0f} id={s.id}')
