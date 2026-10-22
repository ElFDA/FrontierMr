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

## Files that are not in the list by title

Hacks, translations, pirate copies, files with other text after the tags and
collections without No-Intro names are only in **Folders**, at the top of the
list of the system, where the real folders of `games/` are shown as they are
(a zip opens as a folder). The folders named `Extra` (unlicensed games,
prototypes, hacks...) are skipped by the list and by the scraper; other names
can be added with `exclude_dirs=` in `frontier.ini`.

## Arcade and Neo Geo

* **Arcade**: every `.mra` of `_Arcade` is an entry, as in the original
  browser; the versions in `_Arcade/_alternatives` are in the details (X).
* **Neo Geo**: the romsets are used as the core does (`.neo` files with the
  setname, the zip files of `games/NEOGEO/romsets.xml`); the same title is one
  entry, the `.neo` starts, the others are in the details.
