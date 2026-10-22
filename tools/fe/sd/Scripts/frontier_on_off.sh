#!/bin/bash
# Switch the Frontier interface on or off; MiSTer and its update protection stay.
set -e
cd "${FRONTIER_SD_ROOT:-/media/fat}"
if [ -f frontier.off ]; then
	rm -f frontier.off
	echo "Frontier is ON."
else
	touch frontier.off
	echo "Frontier is OFF: the MiSTer shows its original menu."
	echo "Run this script again to turn it on."
fi
sync
echo "The MiSTer reboots in 5 seconds..."
sleep 5
reboot
