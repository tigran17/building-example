#!/bin/zsh
# Serves the site to this Mac AND to phones/tablets on the same Wi-Fi (scan the QR code it prints).
cd "$(dirname "$0")"
( sleep 1.5 && open "http://localhost:8770" ) &
exec /usr/bin/python3 Scripts/serve.py 8770 Website --lan
