#!/bin/zsh
# Photoreal stills with the realism pass (full-detail scene), then the site's still images.
set -e
cd "$(dirname "$0")/.."
B=/Applications/Blender.app/Contents/MacOS/Blender
TAG=${TAG:-v6-final}
$B -b --factory-startup -P Scripts/nk_build.py > Web-Build/stills_build.log 2>&1
$B -b Blender/NewKomitas-Exterior.blend -P Scripts/nk_render.py -- --cams CAM_Aerial,CAM_Street,CAM_Corner,CAM_Courtyard --scale 1.0 --samples 160 --tag $TAG > Web-Build/stills_render.log 2>&1
for c in Aerial Street Corner Courtyard; do /opt/homebrew/bin/ffmpeg -v error -y -i Renders/$TAG/CAM_$c.png -q:v 2 Renders/$TAG/CAM_$c.jpg; done
/opt/homebrew/bin/ffmpeg -v error -y -i Renders/$TAG/CAM_Aerial.png -vf "scale=1600:-2:flags=lanczos" -q:v 3 Website/assets/model-aerial.jpg
/opt/homebrew/bin/ffmpeg -v error -y -i Renders/$TAG/CAM_Corner.png -vf "scale=1600:-2:flags=lanczos" -q:v 3 Website/assets/model-street.jpg
/opt/homebrew/bin/ffmpeg -v error -y -i Renders/$TAG/CAM_Courtyard.png -vf "scale=-2:1600:flags=lanczos" -q:v 3 Website/assets/model-courtyard.jpg
/opt/homebrew/bin/ffmpeg -v error -y -i Renders/$TAG/CAM_Aerial.png -vf "scale=960:-2:flags=lanczos" -q:v 9 Website/assets/loading-still.jpg
echo STILLS_DONE
