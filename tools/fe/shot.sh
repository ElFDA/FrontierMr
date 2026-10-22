#!/bin/bash
# Downloads a framebuffer page of Frontier as PNG.
# Usage: tools/fe/shot.sh <page 1|2|c0|c1> <out.png> [width height]
set -e
cd "$(dirname "$0")/../.."
. tools/fe/env.sh
W=${3:-1920}; H=${4:-1080}
mscp tools/fe/fbdump.py root@$MISTER_IP:/tmp/fbdump.py
mssh "python3 /tmp/fbdump.py $1 $W $H /tmp/fe_shot.ppm"
mscp root@$MISTER_IP:/tmp/fe_shot.ppm /tmp/fe_shot.$$.ppm
python3 -I -c "import sys; from PIL import Image; Image.open(sys.argv[1]).save(sys.argv[2])" /tmp/fe_shot.$$.ppm "$2"
rm -f /tmp/fe_shot.$$.ppm
echo "$2"
