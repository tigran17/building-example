#!/bin/zsh
# Side-by-side: official render (left) vs new 3D model render (right), same height.
# usage: compare.sh <reference.png> <render.png> <out.jpg>
FONT=/System/Library/Fonts/Supplemental/Arial.ttf
[ -f "$FONT" ] || FONT=/System/Library/Fonts/Helvetica.ttc
F=$(mktemp -t nkcmp)
cat > "$F" <<FILTER
[0:v]scale=-2:1100,drawtext=fontfile=${FONT}:text=Official render:x=24:y=24:fontsize=34:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=10[a];
[1:v]scale=-2:1100,drawtext=fontfile=${FONT}:text=New 3D model (Blender Cycles):x=24:y=24:fontsize=34:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=10[b];
[a]pad=iw+16:ih:0:0:white[a2];
[a2][b]hstack
FILTER
ffmpeg -v error -y -i "$1" -i "$2" -filter_complex_script "$F" -q:v 3 "$3"
rm -f "$F"
