#!/bin/bash
# Installs bin/MiSTer on the MiSTer keeping a backup of the original one and restarts
# it in the menu core. Also copies tools/fe/sd/frontier to /media/fat/frontier.
# Log of the process in /tmp/MiSTer.log on the MiSTer.
# Usage: tools/fe/deploy.sh [--restore]
set -e
cd "$(dirname "$0")/../.."
. tools/fe/env.sh

if [ "$1" == "--restore" ]; then
	SRC=/media/fat/MiSTer.orig
else
	[ -f tools/fe/sd/frontier/lib/fe_av.so ] || echo "warning: lib/fe_av.so missing (tools/fe/fe_av/build.sh): no mp4 videos"
	mscp tools/fe/sendkeys.py tools/fe/fbdump.py root@$MISTER_IP:/tmp/
	mscp bin/MiSTer root@$MISTER_IP:/media/fat/MiSTer.new
	# the old folder (before the name Frontier) is moved, with its ini
	mssh 'cd /media/fat; if [ -d frontend ] && [ ! -d frontier ]; then mv frontend frontier; [ -f frontier/frontend.ini ] && mv frontier/frontend.ini frontier/frontier.ini; [ -f config/frontend_last.txt ] && mv config/frontend_last.txt config/frontier_last.txt; [ -f frontend.off ] && mv frontend.off frontier.off; sync; echo "moved frontend -> frontier"; fi; true'
	# Frontier's files on the SD card: themes always updated, frontier.ini only if missing
	tar -C tools/fe/sd -cf - --exclude=frontier/frontier.ini --exclude=__pycache__ --exclude=.gitignore frontier | mssh 'tar -C /media/fat -xf -'
	# the theme "default" is now "simple" (as frontier_install does)
	mssh 'cd /media/fat/frontier && if [ -d themes/default ] && [ -d themes/simple ]; then mkdir -p old; rm -rf old/default; mv themes/default old/default; fi; true'
	mscp tools/fe/sd/frontier/frontier.ini root@$MISTER_IP:/tmp/frontier.ini
	mssh '[ -f /media/fat/frontier/frontier.ini ] || cp /tmp/frontier.ini /media/fat/frontier/frontier.ini' 
	SRC=/media/fat/MiSTer.new
fi

mssh "set -e
cd /media/fat
[ -f MiSTer.orig ] || cp MiSTer MiSTer.orig
killall MiSTer 2>/dev/null || true
sleep 1
if [ $SRC == /media/fat/MiSTer.new ]; then mv MiSTer.new MiSTer; mkdir -p frontier/bin; cp MiSTer frontier/bin/MiSTer; else cp MiSTer.orig MiSTer; fi
sync
md5sum MiSTer MiSTer.orig
# always restarts from the menu core
setsid stdbuf -oL -eL /media/fat/MiSTer >/tmp/MiSTer.log 2>&1 </dev/null &
sleep 1
echo load_core /media/fat/menu.rbf > /dev/MiSTer_cmd
"
echo "Deploy done."
