#!/bin/bash
# Frontier on the CRT of the VGA output (crt=1 in frontier.ini) on or off.
# With a CRT alone the OSD (F12) is seen, Frontier is not: this script turns it
# on from there. Also in Frontier Settings -> CRT output. MiSTer.ini is not changed.
set -e
F=${FRONTIER_SD_ROOT:-/media/fat}
INI="$F/frontier/frontier.ini"
if [ ! -f "$INI" ]; then
	echo "Install Frontier with frontier_install first."
	exit 1
fi
if grep -q '^[[:space:]]*crt[[:space:]]*=[[:space:]]*1' "$INI"; then NEW=0; else NEW=1; fi
if grep -q '^[[:space:]]*crt[[:space:]]*=' "$INI"; then
	sed -i "s/^[[:space:]]*crt[[:space:]]*=.*/crt=$NEW/" "$INI"
else
	[ -z "$(tail -c 1 "$INI")" ] || echo >>"$INI"
	echo "crt=$NEW" >>"$INI"
fi
sync
if [ "$NEW" = 1 ]; then
	echo "Frontier on the CRT: ON (VGA of the I/O board, 15 kHz)."
	echo "MiSTer.ini must send the menu to the CRT: see VIDEO OUTPUTS in frontier/README.txt."
else
	echo "Frontier on the CRT: OFF."
fi
echo "The MiSTer reboots in 5 seconds..."
sleep 5
reboot
