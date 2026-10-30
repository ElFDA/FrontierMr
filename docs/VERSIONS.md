# Which version of a game starts

In the systems (Computer, Console, Handheld, Other) Frontier shows **one entry
per title**: "Altered Beast" once, even when the folder has the USA, Europe
and Japan files, revisions and prototypes. A starts one of them, the
**default version**; the others are in the details.

## The default version

Frontier reads the [No-Intro](https://no-intro.org) style names of the files,
e.g. `Altered Beast (USA, Europe) (Rev 1).md`, and chooses in this order:

1. **Released before unreleased**: betas, prototypes, samples and demos come
   after the released versions, even of another region.
2. **The preferred region**: the first one of `regions=` in
   `/media/fat/frontier/frontier.ini` that the file has. Default:
   `regions=USA,World,Europe,Japan`. A file with more regions,
   `(USA, Europe)`, counts as the better of them; regions not in the list
   come after all those in it.
3. **Originals before re-releases**: Virtual Console, Switch Online, mini
   consoles, collections, Evercade... come after.
4. **The latest revision**: `(Rev 2)` before `(Rev 1)` before none; `(v1.1)`
   before `(v1.0)`.
5. A version without `(Alt)` before an alternative dump.

For example, with the default `regions=`:

| Files in the folder | Starts |
|---|---|
| `Sonic (Japan)`, `Sonic (USA, Europe)` | `Sonic (USA, Europe)` |
| `Game (USA) (Beta)`, `Game (Japan)` | `Game (Japan)`: released before beta |
| `Game (USA)`, `Game (USA) (Rev 1)` | `Game (USA) (Rev 1)` |
| `Game (Europe)`, `Game (USA) (Virtual Console)` | `Game (Europe)`: the original first |

## Another region first

Change the order in `frontier.ini`, e.g. Europe first:

```ini
regions=Europe,World,USA,Japan
```

or the Japanese versions first: `regions=Japan,World,USA,Europe`. Any region
of the No-Intro names can be used (France, Germany, Italy, Spain, Korea,
Brazil, Asia...). Then press F5 in Frontier (or restart it).

The same order also tells the scraper from which region to take names and
pictures (see [SCRAPER.md](SCRAPER.md)).

## The other versions

On a game press **X**: the details list all its versions (regions, revisions,
prototypes) and also the other titles of the same game, e.g. *Thunder Force
IV* and *Lightening Force*, linked by the MAME lists. A on a version starts
that one.

To link the different titles of the same game, once per system, from SSH:

```sh
python3 /media/fat/frontier/scraper/fe_scrape.py --groups --system MegaDrive
```

then F5.

Favorites and Recent hold the title: they start its default version too.

## Games on several discs

On a system with disc images (PlayStation, Saturn, Mega CD...) a folder with only
the discs of one game, e.g. `games/PSX/Xenogears/Xenogears (Disc 1).chd` and
`(Disc 2).chd`, is **one game** with the name of the folder, even if the names have no
region: it is in the list of the system (a cue/chd/iso alone in its own folder as well). **A** starts the first disc; **X** lists all the discs in the details, to
start another one. The scraper gives the game the pictures of its first disc. The files must differ only by the
number of the disc (`(Disc 1)`, `(Disc 2 of 3)`, `- CD2`...); a folder with subfolders or
with other games stays a folder.

## Files without a region in the name

Every file with an extension of the system is a game, whatever its name. Without a
No-Intro style region (hacks, translations, `Crash Bandicoot.chd`...) the file name is the
title, cleaned: `_` as spaces, no `[!]`, no disc number (`Spyro (Disc 1)` and `Spyro (Disc 2)`
are one game, `Spyro`, and the discs are its versions in the details). The GoodTools country
codes `(U)`, `(E)`, `(J)`, `(UE)`... count as regions, so `Sonic (U)` and `Sonic (E)` are one
title with two versions. A [TOSEC](https://www.tosecdev.org) name counts only for its title:
`Predator 2 (1991)(ImageWorks)(Disk 1 of 2)[cr CPY]`, `(Disk 2 of 2)` and the other dumps are one game,
`Predator 2`, which starts the first disk of the copy with the fewest `[...]` tags (cracks, trainers,
alternatives). BIOS files named `[BIOS] ...` are not listed.

Two things are left out of the lists: a zip with free names inside (a zip of C64 games
named `Spy vs Spy.crt`: only the roms with a region are read from zip files) and the
folders named `Extra` (unlicensed games, prototypes, hacks...; other names can be added
with `exclude_dirs=` in `frontier.ini`). `folders=1` in `frontier.ini` adds **Folders**
at the top of each system: the real folders of `games/` as they are, where a zip opens as
a folder. The folders are also in **MiSTer** from the main screen.

The computers (category Computer: C64, Amiga, Spectrum, MSX...) open straight in their real
folders, not by title: their collections have free names and folders which mean something.
Each system can be switched between the two in *Frontier Settings → Systems view*
(`view_folders=` and `view_titles=` in `frontier.ini`; `view=folders|titles` in `systems.ini`
changes the default).

## Cores with several configurations (Amiga)

Amiga, Amiga 500, Amiga 500HD and Amiga 600HD are each a system of the Computer
category, with its own `games/` folder (`games/Amiga500HD`...). The MGL of
`_Computer` which starts the configuration is the first entry of the folder
(`launchers=` in `systems.ini`), so a configuration which boots by itself, for
example from a hard disk (`.hdf`), starts from Frontier too. The `.adf` files
of the folder start with the same configuration. A `launchers=` path ending with `/` takes
all the MGLs of that folder: the games of `_Computer/_X68000 Games` are in Sharp X68000. A launcher shows the pictures, video and data
of the game with the same name (for names without a region the scraper needs
`--all-files`: `fe_scrape.py --system X68000 --all-files`), and after the game Frontier reopens the same
list. VIC-20: the `.rom` cartridges (Megacart, Ultimate...) start too.

Commodore 64 disks (`.d64 .g64 .t64 .d81`) start by themselves: after the disk the MGL loads
`frontier/autorun/c64.prg`, which types `LOAD"*",8,1` and `RUN` (the way MeGaLoSorTer makes its
launchers). Coleco Adam and Apple III disks are followed by a reset (`reset=` in `systems.ini`). The
disks and tapes of other computers which need typed commands (Amstrad, Spectrum, C128...) start with
the machine at its prompt, because an MGL cannot press keys.

## Arcade and Neo Geo

* **Arcade**: every `.mra` of `_Arcade` is an entry, as in the original
  browser; the versions in `_Arcade/_alternatives` are in the details (X).
* **Neo Geo**: the romsets are used as the core does (`.neo` files with the
  setname, the zip files of `games/NEOGEO/romsets.xml`); the same title is one
  entry, the `.neo` starts, the others are in the details.
