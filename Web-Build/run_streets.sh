#!/bin/zsh
# Towers -> park, the new street west of block A, street markings / kerbs / lamps (2026-09-27):
# full web rebuild (every lightmap: the towers' shadows and the tree layout change everywhere), then the stills.
set -e
cd "$(dirname "$0")/.."
B=/Applications/Blender.app/Contents/MacOS/Blender
NK_DETAIL=web $B -b --factory-startup -P Scripts/nk_build.py -- --web --out "$PWD/Blender/NewKomitas-Web.blend" > Web-Build/streets_build.log 2>&1
$B -b Blender/NewKomitas-Web.blend -P Scripts/nk_web.py -- prep > Web-Build/streets_prep.log 2>&1
$B -b Blender/NewKomitas-Web-baked.blend -P Scripts/nk_web.py -- bake > Web-Build/streets_bake.log 2>&1
$B -b Blender/NewKomitas-Web-baked.blend -P Scripts/nk_web.py -- env,trees,export > Web-Build/streets_export.log 2>&1
/usr/bin/python3 Scripts/nk_webdata.py > Web-Build/streets_webdata.log 2>&1
$B -b Blender/NewKomitas-Web.blend -P Scripts/nk_trafficshade.py > Web-Build/streets_shade.log 2>&1
echo WEB_DONE
./Web-Build/run_stills.sh
echo STREETS_PIPELINE_DONE
