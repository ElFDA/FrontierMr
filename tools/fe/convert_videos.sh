#!/bin/bash
# Optional (Frontier also plays the mp4 files, with lib/fe_av.so): converts to .mjv,
# lighter to play, on a PC (ffmpeg needed) the .mp4 videos the scraper downloaded on the
# MiSTer (which has no ffmpeg): takes them in blocks, converts them with
# fe_scrape.py --convert-videos, sends back the .mjv files and deletes the converted .mp4 files.
# Usage: tools/fe/convert_videos.sh [system ...]   (default: all the folders of media/)
# Variables: FE_VIDEO_TMP (work folder, default $HOME/.frontier/videos), FE_VIDEO_BLOCK (files per block, 300)
# Then run the scraper again with the same options (without network it takes a few seconds):
# it writes the .mjv files in the gamelists, also for the other versions of the titles.
set -e
cd "$(dirname "$0")/../.."
. tools/fe/env.sh
command -v ffmpeg >/dev/null || { echo "ffmpeg not found"; exit 1; }

WORK=${FE_VIDEO_TMP:-$HOME/.frontier/videos}
BLOCK=${FE_VIDEO_BLOCK:-300}
rm -rf "$WORK"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

if [ $# -gt 0 ]; then
	DIRS=""
	for s in "$@"; do DIRS="$DIRS media/$(echo "$s" | tr 'A-Z' 'a-z')/video"; done
else
	DIRS="media/*/video"
fi

mssh "cd /media/fat/frontier && find $DIRS -name '*.mp4' 2>/dev/null | sort" > "$WORK/all"
total=$(wc -l < "$WORK/all")
echo "videos to convert: $total"
[ "$total" -gt 0 ] || exit 0

split -l "$BLOCK" "$WORK/all" "$WORK/block."
n=0
for list in "$WORK"/block.*; do
	rm -rf "$WORK/frontier"
	mkdir -p "$WORK/frontier"
	mssh "cd /media/fat/frontier && tar -cf - -T -" < "$list" | tar -C "$WORK/frontier" -xf -
	python3 tools/fe/sd/frontier/scraper/fe_scrape.py --root "$WORK" --frontier "$WORK/frontier" --convert-videos | grep -v "^Pillow\|credenziali" || true
	(cd "$WORK/frontier" && find media -name '*.mjv' | sort) > "$WORK/done"
	if [ -s "$WORK/done" ]; then
		tar -C "$WORK/frontier" -cf - -T "$WORK/done" | mssh "tar -C /media/fat/frontier -xf -"
		sed 's/\.mjv$/.mp4/' "$WORK/done" | mssh "cd /media/fat/frontier && while IFS= read -r f; do rm -f \"\$f\"; done"
	fi
	n=$((n + $(wc -l < "$list")))
	echo "converted $n/$total"
done
