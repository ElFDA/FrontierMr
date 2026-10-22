#!/bin/bash
# Back to the official firmware: the guard stops, Frontier's database and the
# update filter are removed, the original MiSTer comes back (or, without a
# backup, with the next update_all). Frontier's media, settings and lists stay
# for a later installation.
set -e
F=${FRONTIER_SD_ROOT:-/media/fat}
cd "$F"
if [ ! -f frontier/protect_updates.py ]; then
	echo "Uninstall stopped: frontier/protect_updates.py is missing."
	echo "Copy the complete SD folder of a Frontier package, then run frontier_uninstall again."
	exit 1
fi
if ! python3 frontier/protect_updates.py --root "$F" --disable >frontier/update_protection.log 2>&1; then
	echo "Uninstall stopped: update settings could not be restored. Nothing was changed."
	cat frontier/update_protection.log
	echo "Send the error above to the package maintainer."
	exit 1
fi
if [ -s menu.rbf.orig ]; then
	cp menu.rbf.orig menu.rbf.new
	mv menu.rbf.new menu.rbf
fi
if [ -s MiSTer.orig ]; then
	cp MiSTer.orig MiSTer.new
	chmod +x MiSTer.new
	mv MiSTer.new MiSTer
	rm -f MiSTer.orig menu.rbf.orig frontier.off
	echo "Frontier uninstalled. Original firmware and update settings restored."
else
	# Frontier's MiSTer shows the original menu until update_all installs the official one
	touch frontier.off
	rm -f menu.rbf.orig
	echo "Frontier uninstalled. Run update_all to get the official MiSTer back."
fi
sync
echo "The MiSTer reboots in 5 seconds..."
sleep 5
reboot
