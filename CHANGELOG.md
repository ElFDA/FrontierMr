# Changelog

All the releases of Frontier, newest first.
Each release is on the [Releases page](https://github.com/ElFDA/FrontierMr/releases); the text of
a release is its entry here.

## Unreleased
* **Theme editor program for macOS: the menus are back** (version 0.3.2): File, Edit, View, Variant and Help
  were missing on macOS; they are now in the system menu bar, with the Cmd shortcuts (on Windows and Linux
  they are buttons with a menu in the top bar).
  The guides explain how to open the unsigned app on a recent macOS (Privacy & Security → Open Anyway).

## v2026.10.30
* **The theme editor as a program for Windows, macOS and Linux**: Frontier MRTE (`tools/fe/theme_editor.py`)
  is attached to every release as `FrontierThemeEditor-windows.exe`, `FrontierThemeEditor-macos.zip` (Apple
  Silicon) and `FrontierThemeEditor-linux.tar.gz`, with nothing to install: made by PyInstaller on GitHub
  (`.github/workflows/theme_editor.yml`). See `docs/THEME_EDITOR.md`. Version 0.3.1 adds **Make 4:3** to the
  top bar and **Make 4:3**, **Make detail**, **Make screensaver** to the Variant menu, as in the web editor;
  the theme guides say which menu has each button of the web page.
* **Pictures without ScreenScraper for TOSEC names and hacks**: libretro pictures are found by the name of the
  file as before, or else by the title of the game (the list of the pictures of the system is read once and kept
  30 days), choosing the one of the same year and publisher or of the preferred region: TOSEC computer games
  (Amiga, C64, Spectrum, CPC, Atari ST, MSX...) and console hacks get box art, screenshots and title screens
  without a ScreenScraper account. 20 more systems have their libretro pictures (Nintendo DS, PC/DOS cores, C16,
  ZX81, PET, Thomson, CD-i...).
* **TOSEC names are one game per title**: `Predator 2 (1991)(ImageWorks)(Disk 1 of 2)[cr CPY]`, its disk 2 and
  the other dumps are one game, `Predator 2`, which starts the first disk of the cleanest copy (in the lists by
  title and in the scraper, which asks ScreenScraper once per game instead of once per file).
* **The scraper reads the zip files with free names inside** (TOSEC collections like `VIC20 Games [TAP]
  (TOSEC...).zip`), whose games are seen in the folders view, up to 3000 per system (a bigger collection is
  left out, with a line in the log).
* **The scraper knows 74 more systems**: many computers (C16, BBC Micro, Oric, MSX variants, TI-99/4A, ZX81,
  SAM Coupé, PC/DOS cores, Macintosh...), handhelds and consoles (Nintendo DS, Game & Watch, Mega Duck, CD-i,
  Super Cassette Vision...) and the 2P/HD variants of cores were skipped, as they had no ScreenScraper system:
  only the systems with No-Intro sets got data and pictures. 139 of the 195 folders of `systems.ini` now have
  one; the others are not on ScreenScraper.
* **Computers open in their folders**: C64, Amiga, Spectrum, MSX and the other systems of the Computer
  category open straight in their real folders, as the MiSTer shows them (a zip opens as a folder), instead
  of one list of all their files: their collections have free names and folders that mean something. Consoles
  and handhelds stay by title. **Frontier Settings → Systems view** switches each system between Titles and
  Folders (`view_folders=` / `view_titles=` in `frontier.ini`, `view=` in `systems.ini` for the default).
* **MiSTer-DB9: no more unstable cores from update_all**: the filter Frontier writes in `downloader.ini`
  (`[MiSTer] !misterfirmware`) took the place of the default filter of MiSTer-DB9's database
  (`!unstable !jtbeta !dualsdram`), so update_all also downloaded the `_Unstable` cores. The filter now keeps
  that default; on a MiSTer which has the older filter it is completed at the next start, and the next
  update_all removes the unstable cores it had added. The official database has no default filter: nothing
  changes there.
* **Games on USB disks without a `games` folder**: the system folders right on a USB disk
  (`/media/usb0/SNES`) and on the SD card (`/media/fat/SNES`) are read too, as the MiSTer's own file
  browser does; before, only `/media/usbN/games/SNES` was. The scraper reads the same places.
* **Storage: USB** in the MiSTer's OSD: Frontier keeps using its folder on the SD card
  (`/media/fat/frontier`, where the installer puts it) and also lists the games of `/media/fat/games`;
  before, it looked for its themes and settings on the USB disk and found nothing.

## v2026.10.27
* **F12 -> Cores inside a game lists all the cores again**: it opened the folder of the launcher MGL that
  Frontier makes in `frontier/launch/`, which holds only the game just started, so only that core was
  there (arcade games were fine). It now opens the folder of the core's `.rbf`, as in the original MiSTer.
  Alt+F12 still goes back to Frontier. Thanks to HerrBerzerk for the report.
* **Pictures for the categories and for 46 systems in the themes** (City Pop, simple): the big picture of
  Computer, Console, Handheld and Arcade on the main screen, and one for each system (PlayStation, SNES, Mega Drive,
  C64, Amiga...) in its list, named by the id of `systems.ini` (`media/systems/psx.png`...). **Many thanks to
  Dedaloso for the pictures!**
* **Games on more disks and network shares are one list**: PSX on the SD card and more PSX on a second USB disk
  (or on `/media/network`, `/media/fat/cifs`...) appear together, by title and in the folders view; a system found
  only on a second disk appears too. `merge_games=0` in `frontier.ini` reads only `/media/fat/games`. The
  scraper reads the same places. See `docs/STORAGE.md`.
* **Games on several discs are one game**: a folder with only the discs of one game (PlayStation, Saturn,
  Mega CD...: `Xenogears/Xenogears (Disc 1).chd` and `(Disc 2).chd`) is shown with the name of the folder and
  **A** starts the first disc, instead of opening the folder. The details list all the discs, to start
  another one. A folder with a single cue/chd/iso is a game too.
* **Every file is a game, whatever its name** (no more region needed): `Crash Bandicoot.chd`, hacks, translations
  and collections appear in the list of the system, with the file name as title, cleaned (`_` as spaces, no `[!]`,
  no disc number: `Spyro (Disc 1)` + `Spyro (Disc 2)` are one game); GoodTools codes `(U)`, `(E)`, `(J)` count as
  regions; No-Intro names still group the versions of a title. The scraper lists the same games. The **Folders** entry at the top of every system
  is gone by default (`folders=1` brings it back: it is the way to the `Extra` folders and to zip files with
  free names inside, which the lists still leave out). BIOS files named `[BIOS] ...` are not listed.

## v2026.10.25b
* **Pictures, videos and descriptions for the launchers of a system** (the MGL files listed with `launchers=`,
  e.g. the X68000 games): they were looked up under `mgl` and never found; they now use the media of the
  system, by the name of the MGL.
* **Back from an MGL launcher, Frontier reopens the same list** (the X68000 games), not the MiSTer folder
  `_Computer/_X68000 Games`.
* **Commodore 64 disks start by themselves**: after the disk image the MGL loads a small PRG
  (`frontier/autorun/c64.prg`) which types `LOAD"*",8,1` and `RUN`, as MeGaLoSorTer does. Before, a `.d64`
  left the C64 at the `READY.` prompt.
* **Coleco Adam and Apple III disks now start**: the MGL adds a reset after the disk is mounted
  (`reset=` in `systems.ini`), so the machine boots from it. Tested with `tools/fe/launch_test.py`, which
  launches one file per slot on the MiSTer and takes screenshots.
* **Launch indexes of 22 systems corrected** (VIC-20 disks, MacPlus floppies, TRS-80 disks, MSX, Aquarius, Apogee,
  ColecoAdam, Galaksija, Orao...): the MGL finds the OSD entry of the core by its number and a wrong number
  made it load the first entry. `tools/fe/systems/check_conf.py` compares every slot with the real core.

## v2026.10.25
* **Fix: Amiga with a hard disk did not boot.** `MiSTer` is now built on the stable release 20261010
  of Main_MiSTer (the one `update_all` installs), not on a later commit of `master`: that build needed a
  newer Minimig core than the stable one, so an Amiga configuration with a hard disk (e.g. MegaAGS)
  stayed on black and grey screens. From now on Frontier follows the stable releases only
  (`tools/fe/upstream_check.sh` checks it). The Minimig options added after that release (68030,
  drive sounds) come back with the next one.
* **Amiga configurations**: Amiga, Amiga 500, Amiga 500HD and Amiga 600HD are all in the Computer
  category, each with its own folder in `games/`; the MGL of `_Computer` which starts the
  configuration (e.g. the one which boots from a `.hdf`) is the first entry of the folder
  (`launchers=` in `systems.ini`, usable for any core with several MGLs). Before, only "Amiga" was
  there and it started nothing without `.adf` files.
* **X68000 games**: the MGLs of `_Computer/_X68000 Games` (the games of the classic menu) are now in
  Computer → Sharp X68000, alphabetical, as the first entries of its folder.
* **VIC-20**: `.rom` cartridges (Ultimate Cartridge, Megacart) now start (file index 2 of the core).
* **`fe_scrape.py --dedupe-media`** (with `--dry-run` to only see): the arcade versions scraped one by
  one by older runs have copies of the pictures and videos of their main game; they now use the files
  of the main game and the identical copies are deleted (7067 files, 8.2 GB on the test MiSTer).
  No network; different pictures stay.
* Only `MiSTer`, `systems.ini` and the scraper script change; `menu.rbf` and `fe_av.so` are the same as in `v2026.10.24b`.

## v2026.10.24b
* **"#Newest" groups the versions of a game.** The new `.mra` which use the same romset (the
  regions and revisions of a core, or the same game from two cores) are one entry, as in the Arcade
  folder, and the others are the versions of the detail view: 219 new files were 189 games on the
  test MiSTer. Clones with another title (Space Invaders / Balloon Bomber, Pac-Man / Ms. Pac-Man)
  stay separate games.
* **Faster arcade scraper**: the `.mra` outside `_alternatives` which are versions of one game (the
  regions of a core, such as Heavy Unit World / Japan / US) are scraped once, the others take its data
  and pictures like the alternatives do (443 of 2784 games on the test MiSTer, no BIOS or other-title
  clone joins).
* Only `MiSTer` changes (and the scraper script); `menu.rbf` and `fe_av.so` are the same as in `v2026.10.24`.

## v2026.10.24
* **Fix: "#Newest" (Arcade folder) was empty just after the power on.** The MiSTer has no clock of its
  own: until the network sets it (20-30 seconds after the start) the date is 1970, and Frontier gave up
  before reading the games it already knew, so the list showed nothing. Now it shows the known ones
  at once; the new games get their day as soon as the clock is right (open "#Newest" again or press F5).
* Only `MiSTer` changes; `menu.rbf` and `fe_av.so` are the same as in `v2026.10.23c`.

## v2026.10.23c
* **Fix: `frontier_install` stopped with "Custom base_system_path"** on older `downloader.ini` files
  (the example of Downloader up to 1.5, still found on many SD cards: `base_system_path = '/media/fat/'`,
  with the slash at the end): Frontier was not installed and the MiSTer stayed on the official menu. The path is now read as `/media/fat`;
  a really different path is still refused. `frontier_uninstall` stopped with the same error.
* The program (`MiSTer`, `menu.rbf`, `fe_av.so`) is the same as in `v2026.10.23b`.

## v2026.10.23b
* **Faster scraper**, above all for arcade games: the `.mra` files are read once and kept in a
  cache, ArcadeDB is asked only for the games to do (in a few batches), the gamelist is written in
  one go (seconds instead of a minute on the SD card) and not written at all when nothing changed,
  the index of the lists keeps the systems not scraped.
* **Games not found are remembered**: a game that no source has (hacks, bootlegs, homebrew) is
  skipped for 30 days, so the counter shows only the games to do; network errors do not count.
  Frontier Settings -> Scraper -> Games already scraped -> "retry not found" (`--retry-missing`)
  tries them at once.
* **Arcade alternatives** (`_Arcade/_alternatives`) take the data and the pictures of their main game,
  keeping their own name, without requests or copies; only those without a main game are scraped.
* The scraper finds the pictures already there whatever the case of the letters, as Frontier does
  ("Revision 1" and "revision 1" are the same file on the SD card): they are no longer downloaded
  again at every run.
* At the end Frontier says what the run brought: "finished: 3 updated" or "finished: nothing new", and
  the message also counts the games not found.
* The scraper started from Frontier runs on the core of the processor that Frontier leaves free: before it
  shared the busy one and was about 9 times slower (an arcade run with nothing to do: 5 minutes, now about one).
* **Scrape this game**: in the details of a game, under "Add to list...", the scraper for that game only
  (asked again to the sources, data and pictures downloaded again; `--game` from a terminal).
* While the scraper gets ready Frontier shows what it is doing ("checking what is missing",
  "asking ArcadeDB") instead of "0/…".

## v2026.10.23
* **Theme editor as a download of its own.** `theme_editor.html` is now a file of every release (on the
  Releases page, next to the ZIP): it is a tool for the PC, so it is not in the ZIP for the SD card.
  Latest version: <https://github.com/ElFDA/FrontierMr/releases/latest/download/theme_editor.html>.
  The theme guides and the README point there.
* Theme editor: the sample data now has `${game.cpu}`, `${game.memory}`, `${game.graphics}`,
  `${game.sound}`, `${game.media}` and `${game.units}` (the data of the systems), so the themes that
  use them can be previewed.
* New step by step guide: [Theme editor](docs/THEME_EDITOR.md) (English and Italian).
* README: beta note at the top, screenshots and credits.
* New: this changelog. The program (`MiSTer`, `menu.rbf`, `fe_av.so`) is the same as in `v2026.10.22c`.

## v2026.10.22c
* New step by step guides: [Coin-Op mode](docs/COINOP.md) and
  [getting the MiSTer back from a game with a black screen](docs/BLACK_SCREEN.md) (English and Italian).

## v2026.10.22b
First release kept online (the earlier `v2026.10.22` was withdrawn).
* Installation through `update_all` first (`downloader_frontiermr.ini`), the ZIP as an alternative;
  the database of `update_all` takes every file from the ZIP of the release.
* Step by step guides: [scraper](docs/SCRAPER.md), [lists](docs/LISTS.md),
  [which version of a game starts](docs/VERSIONS.md) (English and Italian).
* CRT output without editing files: Frontier Settings -> CRT output and `Scripts/frontier_crt`.
* Frontier Settings: folders first, then the single entries, in alphabetical order.
* In the OSD of a game, "Core" opens the browser of the cores as in the original; Alt+F12 goes back to Frontier.
* Fix: the empty `filter =` left by `protect_updates --disable` made `downloader.ini` unreadable
  when Frontier was installed again.
* The `frontier_scrape` script is gone: the scraper starts from Frontier Settings.
* README of the repository with the `MiSTer.ini` settings for CRT, HDMI and CRT + HDMI.
