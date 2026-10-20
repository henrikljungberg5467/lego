#!/bin/sh
# Render single parts from three angles: tools/inspect.sh color part [part...]
col=$1; shift
for p in "$@"; do
  printf '0 inspect\n1 %s 0 0 0 1 0 0 0 1 0 0 0 1 %s.dat\n' "$col" "$p" > tmp/inspect_$p.ldr
  node tools/render.mjs tmp/inspect_$p.ldr tmp/inspect_$p '[{"name":"a","az":35,"el":30,"zoom":0.9,"w":600,"h":450},{"name":"b","az":90,"el":0,"zoom":0.9,"w":600,"h":450,"ortho":true},{"name":"c","az":0,"el":0,"zoom":0.9,"w":600,"h":450,"ortho":true}]' > /dev/null
  python3 -c "
from PIL import Image
ims=[Image.open('tmp/inspect_$p-'+k+'.png') for k in 'abc']
W=sum(i.width for i in ims); out=Image.new('RGB',(W,450),'white'); x=0
for i in ims: out.paste(i,(x,0)); x+=i.width
out.save('tmp/inspect_$p.png')"
done
