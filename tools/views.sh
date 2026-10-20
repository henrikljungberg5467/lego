#!/bin/sh
# Standard review renders: tools/views.sh model.mpd outprefix
node tools/render.mjs "$1" "$2" '[{"name":"ref","az":-62,"el":18,"fov":30,"zoom":0.72,"w":1200,"h":900},{"name":"side","az":-90,"el":0,"ortho":true,"w":1100,"h":700},{"name":"front","az":-20,"el":22,"w":1000,"h":750},{"name":"rear","az":140,"el":25,"w":1000,"h":750},{"name":"top","az":0,"el":89.9,"ortho":true,"w":1000,"h":1000}]'
