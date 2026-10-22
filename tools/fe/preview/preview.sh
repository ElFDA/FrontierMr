#!/bin/bash
# Preview of a theme on a PC with the same renderer as the MiSTer.
# Usage: tools/fe/preview/preview.sh <theme folder> <out.png> [width height] [selection] [detail|screensaver|loading]
# Media and gamelists are those of the Frontier folder which contains the theme
# (<frontier>/themes/<name>): gamelists/arcade, media/arcade.
# Examples: 1920 1080 (HDMI), 640 240 (CRT 240p: the lines are doubled in the PNG)
# FE_LAYOUT=text: the text layout of the theme (elements with layout=text, not layout=media)
# Needs g++ and libImlib2.so.1 (libimlib2 package) on the PC.
set -e
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BIN="$ROOT/tools/fe/preview/fe_preview"
SRC="$ROOT/tools/fe/preview/fe_preview.cpp $ROOT/fe_render.cpp $ROOT/fe_theme.cpp $ROOT/fe_media.cpp $ROOT/sxmlc.c"
LIB=$(ls /usr/lib/*/libImlib2.so.1 /usr/lib/libImlib2.so.1 2>/dev/null | head -1)
if [ ! -x "$BIN" ] || [ -n "$(find $SRC -newer "$BIN")" ]; then
	gcc -O2 -c -o "$BIN.sxmlc.o" "$ROOT/sxmlc.c"
	g++ -O2 -std=gnu++14 -DFE_PREVIEW -I"$ROOT" -I/usr/include/freetype2 -o "$BIN" ${SRC% *} "$BIN.sxmlc.o" "$LIB" -lfreetype -lpthread
	rm -f "$BIN.sxmlc.o"
fi
"$BIN" "$@"
