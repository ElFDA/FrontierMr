#!/bin/bash
# Copies a theme to the MiSTer and reloads it in Frontier (F5 key).
# Usage: tools/fe/theme_push.sh <theme folder> [out.png width height]
#      with out.png it also saves the screenshots of the two pages (out_p1.png, out_p2.png).
set -e
cd "$(dirname "$0")/../.."
. tools/fe/env.sh
DIR=${1%/}
[ -f "$DIR/theme.ini" ] || { echo "$DIR/theme.ini missing"; exit 1; }
NAME=$(basename "$DIR")
tar -C "$(dirname "$DIR")" -cf - "$NAME" | mssh "mkdir -p /media/fat/frontier/themes && tar -C /media/fat/frontier/themes -xf -"
mssh "python3 /tmp/sendkeys.py f5"
echo "Theme $NAME copied and reloaded (the active theme is the one in frontier.ini)."
if [ -n "$2" ]; then
	# F5 redraws on the hidden page and shows it: which one is not known, both are saved
	sleep 1
	tools/fe/shot.sh 1 "${2%.png}_p1.png" ${3:-640} ${4:-240}
	tools/fe/shot.sh 2 "${2%.png}_p2.png" ${3:-640} ${4:-240}
fi
