#!/bin/bash
# Installs Frontier. Its firmware stays in frontier/bin: frontier/guard.sh puts
# MiSTer back after any update, menu.rbf is loaded from there, and update_all
# also updates Frontier through its database. Works from a package
# (frontier_setup/) or with the files update_all has already put in frontier/.
set -e
F=${FRONTIER_SD_ROOT:-/media/fat}
S="$F/frontier_setup"
cd "$F"
if [ -d "$S" ]; then
	if [ ! -s "$S/frontier/bin/MiSTer" ] || [ ! -f "$S/frontier/protect_updates.py" ] || [ ! -f "$S/frontier/guard.sh" ]; then
		echo "Installation stopped: the Frontier package is incomplete."
		echo "Copy the complete SD folder from the new package, then run frontier_install again."
		exit 1
	fi
elif [ ! -s frontier/bin/MiSTer ] || [ ! -f frontier/protect_updates.py ] || [ ! -f frontier/guard.sh ]; then
	echo "Installation stopped: Frontier's files are missing."
	echo "Copy the SD folder of a Frontier package, or run update_all with Frontier's database."
	exit 1
fi
if ! command -v python3 >/dev/null; then
	echo "Installation stopped: Python 3 is missing. Update MiSTer Linux first."
	exit 1
fi
if [ ! -f MiSTer.orig ] && ! cmp -s MiSTer "${S}/frontier/bin/MiSTer" && ! cmp -s MiSTer frontier/bin/MiSTer; then
	cp MiSTer MiSTer.orig
	echo "Original MiSTer saved."
fi
if [ -d "$S" ]; then
	KEEP=$(mktemp)
	KEEP_SETTINGS=0
	trap 'rm -f "$KEEP"' EXIT
	if [ -f frontier/frontier.ini ]; then
		cp frontier/frontier.ini "$KEEP"
		KEEP_SETTINGS=1
	fi
	mkdir -p frontier
	cp -r "$S/frontier/." frontier/
	if [ "$KEEP_SETTINGS" = 1 ]; then
		cp "$KEEP" frontier/frontier.ini
		echo "Your settings have been kept."
	fi
fi
if ! python3 frontier/protect_updates.py --root "$F" >frontier/update_protection.log 2>&1; then
	echo "Installation stopped: update protection could not be configured."
	cat frontier/update_protection.log
	echo "The MiSTer binary has not been replaced. Send the error above to the package maintainer."
	exit 1
fi
# older versions: Frontier's menu replaced the official one in the root
if [ -s menu.rbf.orig ]; then
	cp menu.rbf.orig menu.rbf.new
	mv menu.rbf.new menu.rbf
	rm -f menu.rbf.orig
	echo "Official menu restored: Frontier's menu is loaded from frontier/bin."
fi
# scripts of older versions: the CRT menu is always installed, the scraper runs from Frontier
rm -f Scripts/frontier_crt_menu.sh Scripts/frontier_scrape.sh frontier.off
# the theme "default" is now "simple": the old folder goes out of the theme list
if [ -d frontier/themes/default ] && [ -d frontier/themes/simple ]; then
	mkdir -p frontier/old
	rm -rf frontier/old/default
	mv frontier/themes/default frontier/old/default
fi
# the guard copies and checks MiSTer (the running executable is replaced, not overwritten)
if ! sh frontier/guard.sh install || ! cmp -s MiSTer frontier/bin/MiSTer; then
	echo "Installation stopped: MiSTer could not be copied from frontier/bin."
	exit 1
fi
sync
echo
echo "Frontier installed. MiSTer is protected from updates, update_all also updates Frontier."
echo "The MiSTer reboots in 5 seconds..."
sleep 5
reboot
