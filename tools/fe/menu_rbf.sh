#!/bin/bash
# Builds the menu.rbf of Frontier (local fork of Menu_MiSTer, branch frontier)
# with Quartus 17.0 in Docker and, with --deploy, installs it on the MiSTer
# (the previous menu.rbf stays in /media/fat/menu.rbf.bak-nightly if not there yet).
# Usage: tools/fe/menu_rbf.sh [--deploy]
set -e
cd "$(dirname "$0")/../.."
. tools/fe/env.sh
MENU=${MENU_DIR:?set MENU_DIR (Menu_MiSTer checkout with the Frontier patch)}

docker run --rm -v "$MENU":/build -w /build --entrypoint "" raetro/quartus:17.0 \
	bash -c 'quartus_sh --flow compile menu.qpf > build.log 2>&1' || { tail -20 "$MENU/build.log"; exit 1; }
git -C "$MENU" checkout -q menu.qsf   # Quartus writes its own version in it
grep "Worst-case setup slack" "$MENU/build.log" | tail -1
ls -la "$MENU/output_files/menu.rbf"

if [ "$1" == "--deploy" ]; then
	mssh "[ -f /media/fat/menu.rbf.bak-nightly ] || cp /media/fat/menu.rbf /media/fat/menu.rbf.bak-nightly"
	mscp "$MENU/output_files/menu.rbf" root@$MISTER_IP:/media/fat/menu.rbf
	mssh "mkdir -p /media/fat/frontier/bin && cp /media/fat/menu.rbf /media/fat/frontier/bin/menu.rbf"
	mssh "sync; echo load_core /media/fat/menu.rbf > /dev/MiSTer_cmd"
	echo "menu.rbf installed."
fi
