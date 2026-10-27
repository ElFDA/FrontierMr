# Games on more disks and network shares

The games of a system can be on more storages: PlayStation on the SD card and more
PlayStation on a second USB disk, a NAS, a CIFS share... Frontier reads all of them
and shows **one list per system** (`merge_games=1` in `frontier.ini`, the default).

## Where it looks

In this order; for the same file in two places the first one wins:

| Place | What it is |
|---|---|
| `/media/fat/games` | the SD card, or the disk it links to |
| `/media/usb0/games` ... `/media/usb7/games` | the USB disks, each with a `games` folder |
| `/media/network/games` and `/media/network` | network shares |
| `/media/fat/cifs/games` and `/media/fat/cifs` | CIFS shares mounted by the `cifs_mount.sh` script (its shares can hold the system folders directly: `Amiga`, `C64`, `NES`...) |

A disk which `games` already links to is not read twice. In each place the system
folder is the usual one (`games/PSX`, `games/SNES`...); the case doesn't matter
(`PSX` and `psx` are the same). A system found only on a second disk appears too.

## What is joined

* The games of a system are one list (by title, or the folders view).
* A folder with the same name on two disks shows the files of both: with `games/PSX`
  on the first USB disk and `games/PSX/Xenogears` on the second one, the PlayStation list
  has all the games, and `Xenogears` is one game that starts disc 1 (see
  [Which version of a game starts](VERSIONS.md), *Games on several discs*).
* Favorites, Recent and My Lists remember a game by its path inside `games/` and find it
  again on whichever disk it is.
* The scraper (`fe_scrape.py`) reads the same places.

## Good to know

* The MiSTer's own file browser inside a core does **not** join: it uses the first place
  which has the folder (USB disks, then the network, then the SD card).
* The disk or the share has to be there when the list is read. After plugging in a disk
  or mounting a share, read the lists again: hold **X** on the category or on the system
  (see *Updating the lists* in `README.txt`).
* A network share which is slow or switched off makes the lists slow: unmount it
  (`cifs_umount.sh`) or set `merge_games=0`, which reads only `/media/fat/games`.
* System folders right in `/media/usbN` (without a `games` folder) are not read.
