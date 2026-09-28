#!/bin/zsh
# Full web rebuild for the realism pass (denser trees, ground, roofs, grade, black-texel refill).
set -e
cd "$(dirname "$0")/.."
B=/Applications/Blender.app/Contents/MacOS/Blender
NK_DETAIL=web $B -b --factory-startup -P Scripts/nk_build.py -- --web --out "$PWD/Blender/NewKomitas-Web.blend" > Web-Build/realism_build.log 2>&1
$B -b Blender/NewKomitas-Web.blend -P Scripts/nk_web.py -- prep > Web-Build/realism_prep.log 2>&1
$B -b Blender/NewKomitas-Web-baked.blend -P Scripts/nk_web.py -- bake > Web-Build/realism_bake.log 2>&1
$B -b Blender/NewKomitas-Web-baked.blend -P Scripts/nk_web.py -- env,trees,export > Web-Build/realism_export.log 2>&1
/usr/bin/python3 Scripts/nk_webdata.py > Web-Build/realism_webdata.log 2>&1
$B -b Blender/NewKomitas-Web.blend -P Scripts/nk_trafficshade.py > Web-Build/realism_shade.log 2>&1
echo REALISM_PIPELINE_DONE
