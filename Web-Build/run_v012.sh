#!/bin/zsh
# v0.12 street life: courtyards, plaza/street details, roof equipment, shadow lift (people routes: nk_people.py after this)
set -e
cd "$(dirname "$0")/.."
B=/Applications/Blender.app/Contents/MacOS/Blender
NK_DETAIL=web $B -b --factory-startup -P Scripts/nk_build.py -- --web --out "$PWD/Blender/NewKomitas-Web.blend" > Web-Build/v012_build.log 2>&1
$B -b Blender/NewKomitas-Web.blend -P Scripts/nk_web.py -- prep > Web-Build/v012_prep.log 2>&1
$B -b Blender/NewKomitas-Web-baked.blend -P Scripts/nk_web.py -- bake > Web-Build/v012_bake.log 2>&1
$B -b Blender/NewKomitas-Web-baked.blend -P Scripts/nk_web.py -- env,trees,export > Web-Build/v012_export.log 2>&1
/usr/bin/python3 Scripts/nk_webdata.py > Web-Build/v012_webdata.log 2>&1
$B -b Blender/NewKomitas-Web.blend -P Scripts/nk_trafficshade.py > Web-Build/v012_shade.log 2>&1
echo WEB_DONE
TAG=v7-final ./Web-Build/run_stills.sh
echo V012_PIPELINE_DONE
