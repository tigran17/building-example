#!/bin/zsh
# Double-click to run the New Komitas photoreal 3D site on this Mac: http://localhost:8770
cd "$(dirname "$0")"
( sleep 1.5 && open "http://localhost:8770" ) &
exec /usr/bin/python3 Scripts/serve.py 8770 Website
