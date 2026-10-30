# Frontier and update_all

Frontier replaces `/media/fat/MiSTer`, a file the official distribution also
updates. Goals:

1. no update may put the official MiSTer back in place of Frontier's;
2. update_all also updates Frontier;
3. nothing to do by hand after installation;
4. one script brings the official firmware back.

## Why a filter alone is not enough

Downloader can skip a file with a filter (`!misterfirmware` in
`[distribution_mister]` of `downloader.ini`), but:

* a file it has installed before and that the filter now hides is **deleted**
  at the next update (it is no longer in the filtered list);
* update_all rewrites `downloader.ini`: turning the main distribution off and
  on, or choosing a fork, recreates the section without the filter; a new
  `downloader.ini` has none;
* other tools can copy a MiSTer binary without Downloader;
* Main starts `/media/fat/MiSTer` from the SD card again at every core load,
  so a replaced file is used at once.

Other ideas that do not work: a database of Frontier declaring `MiSTer` or
`menu.rbf` in the root (Downloader refuses those paths from any database but
the official one, and two databases declaring a file are resolved in an order
that is not guaranteed); read-only attributes (FAT/exFAT have no immutable
flag); changing the Linux image (replaced by Linux updates).

## How it works

Frontier owns no official path: its firmware lives in `frontier/bin/`
(`MiSTer`, `menu.rbf`).

* **Menu core**: the official `menu.rbf` stays in the root and keeps
  updating. U-Boot loads it at power on; at its first start Frontier loads its
  own from `frontier/bin/menu.rbf` once, and every later `menu.rbf` load uses
  it (`fe_update.cpp`, hook in `fpga_io.cpp`). `frontier/bin/.menu_try` counts
  the attempts: after two power ons where Frontier's menu core did not start
  (a damaged file), `.menu_bad` makes Frontier use the official one until the
  file changes.
* **Guard** (`frontier/guard.sh`, one line in `linux/user-startup.sh`): at
  shutdown (`stop`, also the reboot after an update) and at boot (`start`,
  after a power cut) it copies `frontier/bin/MiSTer` to `/media/fat/MiSTer`
  if something else has replaced it. It copies only a non-empty ELF file,
  through a temporary file checked before the rename; at boot it also
  restarts Main. The reset from the OSD and the restart of Main at each core
  do not run the shutdown scripts: Main runs the guard itself before them when
  the file on the SD card is no longer the running one.
* **Self repair**: once per power on Frontier runs
  `frontier/protect_updates.py --repair` in the background. It puts back what
  an updater or another tool removed (the guard line, the filter, Frontier's
  database) and writes nothing when everything is in place.
* **Filter**: `!misterfirmware` in `[distribution_mister]`, with the official
  MiSTer forgotten in Downloader's index (so that it is not deleted), only
  avoids downloading the official binary for nothing. If it is lost, the guard
  undoes the update at the next reboot. A database can have a default filter
  of its own, which Downloader uses only while its section has no `filter`:
  MiSTer-DB9's leaves out its unstable cores (`!unstable !jtbeta !dualsdram`).
  For it the filter written is `[MiSTer] !unstable !jtbeta !dualsdram
  !misterfirmware`, unless `[MiSTer]` has a filter (that one replaces the
  default); the self repair completes the `[MiSTer] !misterfirmware` of older
  versions, and Downloader then removes the unstable cores it had added.
* **Frontier's updates**: `/media/fat/downloader_frontiermr.ini` (a Downloader
  drop-in, copied from `frontier/downloader_frontiermr.ini`) adds the database
  `frontiermr` (`tools/fe/make_db.py`). Its only archive is the ZIP of the
  release: Downloader downloads it once and extracts, checking each file, what
  goes into `frontier/` and the `Scripts/frontier_*.sh` scripts; `frontier.ini` is never replaced (and
  favorites, lists, game data and media are not in it). A new
  `frontier/bin/MiSTer` asks update_all to reboot; the guard installs it at
  shutdown.

## Back to the official firmware

F12 -> Scripts -> `frontier_uninstall` runs `protect_updates.py --disable`
(first `frontier/uninstalled`, which stops the guard at once, then the guard
line, Frontier's database and the filter are removed) and puts back
`MiSTer.orig`, saved by `frontier_install`. Without it the next update_all
installs the official MiSTer. Frontier's files stay on the SD card (Downloader
deletes nothing of a database that is no longer configured);
`frontier_install` brings Frontier back.

## Limits

* A new SD card (or a formatted one) is a new installation.
* A power cut right after an official update: at the next boot the official
  Main runs for a few seconds, then the guard restores Frontier.
* If another tool rewrites `user-startup.sh` **and** an official update
  arrives before Frontier starts again, run `frontier_install` once.

## Tests

* `tools/fe/protect_updates_test.py`, `tools/fe/guard_test.py`,
  `tools/fe/package_test.py`: the scripts on a simulated SD card.
* `tools/fe/protect_updates_downloader_test.py <Downloader zip or src>`: the
  real Downloader code on a temporary SD card with test databases (only the
  HTTP answers are replaced): the filter alone deletes MiSTer; with the
  protection MiSTer is kept, the official menu and the cores update and
  Frontier's update arrives in `frontier/bin`; with the filter lost the
  official MiSTer is installed, the guard puts Frontier back and the repair
  makes the next update keep it; removing Frontier's database deletes nothing;
  after the uninstall the official MiSTer comes back.
* On a MiSTer: replacing MiSTer and rebooting, the same with `reboot -f`, the
  official `menu.rbf` in the root, replacing MiSTer while Frontier runs and
  loading a core, a new Main in `frontier/bin`.
