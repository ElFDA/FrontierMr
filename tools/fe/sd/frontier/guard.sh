#!/bin/sh
# Frontier guard: keeps /media/fat/MiSTer equal to frontier/bin/MiSTer.
# Called by linux/user-startup.sh with "stop" at shutdown (also the reboot that
# follows an update) and "start" at boot (after a power cut). Any updater can
# replace MiSTer with the official one: here Frontier's comes back. Frontier's
# own updates arrive in frontier/bin and are installed here the same way.
# Does nothing after frontier_uninstall (frontier/uninstalled).
F=${FRONTIER_SD_ROOT:-/media/fat}
SRC="$F/frontier/bin/MiSTer"
DST="$F/MiSTer"
LOG="$F/frontier/guard.log"

[ -f "$F/frontier/uninstalled" ] && exit 0
[ -s "$SRC" ] || exit 0
# only an executable: a partial or wrong file must never replace MiSTer
[ "$(head -c 4 "$SRC" | tail -c 3)" = "ELF" ] || exit 0
cmp -s "$SRC" "$DST" && exit 0

if ! cp "$SRC" "$DST.frontier-new" || ! cmp -s "$SRC" "$DST.frontier-new"; then
	rm -f "$DST.frontier-new"
	echo "$(date '+%F %T') $1: copy failed" >>"$LOG"
	exit 1
fi
chmod +x "$DST.frontier-new"
sync
mv -f "$DST.frontier-new" "$DST"
sync
# keep the log short
[ -f "$LOG" ] && [ "$(wc -l <"$LOG")" -gt 50 ] && tail -n 20 "$LOG" >"$LOG.tmp" && mv -f "$LOG.tmp" "$LOG"
echo "$(date '+%F %T') $1: MiSTer restored from frontier/bin" >>"$LOG"
sync

# at boot the replaced MiSTer is already running: start Frontier's
if [ "$1" = "start" ]; then
	killall MiSTer 2>/dev/null
	n=0
	while pidof MiSTer >/dev/null && [ $n -lt 50 ]; do
		sleep 0.1
		n=$((n + 1))
	done
	cd "$F" || exit 1
	# a simple command: the shell does not stay as its parent
	setsid "$DST" </dev/null >/dev/null 2>&1 &
fi
exit 0
