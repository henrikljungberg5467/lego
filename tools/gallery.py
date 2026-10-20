"""Write a grid of parts to an .ldr for visual comparison. Usage: gallery.py out.ldr color part [part...]"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldraw as L

out, color, parts = sys.argv[1], sys.argv[2], sys.argv[3:]
lines = ['0 gallery']
k = 0
for p in parts:
    f = p if p.endswith('.dat') else p + '.dat'
    if not L.find(f):
        print('missing', p); continue
    lo, hi = L.bbox(f); c = (lo + hi) / 2
    print(f'{k:2d} {p:8s} {L.part_header(f)}  bbox {lo.round(1).tolist()} {hi.round(1).tolist()}')
    x = (k % 6) * 320; z = (k // 6) * 320
    lines.append(f'1 {color} {x-c[0]:.2f} {-c[1]:.2f} {z-c[2]:.2f} 1 0 0 0 1 0 0 0 1 {f}')
    k += 1
open(out, 'w').write('\n'.join(lines) + '\n')
