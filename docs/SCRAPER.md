# Scraper: game data, pictures and videos

Frontier shows box art, screenshots, title screens, marquees, videos and the
data of the games (description, year, developer, publisher, genre, players).
They are downloaded by the scraper, which runs from Frontier itself:
**Frontier Settings -> Scraper**.

## 1. A ScreenScraper account (recommended)

[ScreenScraper](https://www.screenscraper.fr) has data, pictures and videos
for all the systems. It needs a free account:

1. Register on https://www.screenscraper.fr.
2. Connect a USB keyboard to the MiSTer.
3. In Frontier: Frontier Settings -> Scraper -> **ScreenScraper user**, press
   A, type the user name, Enter. Then **ScreenScraper password** the same way.
   Esc (or B) cancels; an empty value removes it.

The two values are saved in `/media/fat/frontier/scraper/scraper.ini`
(or `/media/fat/frontier/scraper.ini` if that is the one you have). Without a
keyboard, write them there from a PC, starting from
`scraper/scraper.ini.example`:

```ini
[screenscraper]
user = your_name
password = your_password
```

Leave `devid` and `devpassword` empty: Frontier's developer key is in the
package.

## 2. Without an account

ScreenScraper is skipped and the other sources are used:

| | Arcade and Neo Geo | Consoles, computers, handhelds |
|---|---|---|
| Source | ArcadeDB | libretro thumbnails |
| Data (description, genre...) | yes | no |
| Box art, screenshots, title screens | yes | yes, only for files with exact No-Intro names |
| Marquees, videos | yes | no |

The data of the systems (description, maker, year, hardware) always come from
Wikipedia. Without the data of the console games, the filters of My Lists
(publisher, genre, series...) only work for the arcade games, and the
consoles have no videos.

## 3. What to download

Frontier Settings -> Scraper:

| Entry | What it does |
|---|---|
| Start scraping | A starts the scraper in the background; A again stops it. The progress is on the right ("SNES 120/840 (2/5)", then finished / stopped / error; "finished: 3 updated" = 3 games got new data or pictures, "finished: nothing new" = nothing to add). You can go on using Frontier and play meanwhile: the scraper works on the other core of the processor. |
| Get systems data only | only the data of the systems, from Wikipedia: a few minutes, no games |
| Systems | Arcade and the categories; inside a category "All" or one system at a time, ON/OFF |
| Language | English (default), Italian, French, German, Spanish, Portuguese, Japanese: descriptions and genres (English when a text is missing in that language) |
| Texts | names, descriptions, genres, publishers... ON/OFF |
| Box art, Screenshots, Title screens, Marquees and logos, Fanart, Videos | each ON/OFF; all ON except Fanart at the start |
| Games already scraped | skip (only what is missing, the default), texts again (data in the language chosen, pictures kept), all again, retry not found (also the games that no source had in the last 30 days) |

Your choices are kept in `frontier.ini`. Stopping is safe: what was downloaded
stays and the next run goes on from there. Errors of ScreenScraper (its daily
quota, the network) are tried again in the next run.

**Games not found.** When no source has a game, or not everything you asked
(for example no box art anywhere), the scraper remembers it and skips it for
30 days: the counter shows only the games really to do, and hacks, bootlegs
and homebrew are not asked again at every run. They are tried again after 30
days, when you ask for more pictures or add a source (e.g. your ScreenScraper
account), or at once with "Games already scraped" -> retry not found.

**Arcade alternatives.** The games in `_Arcade/_alternatives` take the data and
the pictures of their main game (the `.mra` outside `_alternatives` of the same
MAME set: "Street Fighter II (USA 910522)" from "Street Fighter II (World
910522)"), keeping their own name. Nothing is downloaded or copied for them;
only an alternative without a main game is scraped on its own.

The new pictures of a system appear when that system is finished; to see
them at once on a system already open, hold X on it (or press F5).

**One game only.** Open the details of a game (X) and choose **Scrape this
game**, under "Add to list...": the scraper asks the sources again for that
game and downloads again its data and pictures, with the content chosen in
Frontier Settings -> Scraper (the arcade alternatives that take from it are
updated too). It runs in the background, about a minute; the new pictures
appear when it is finished. Useful for a game with a wrong or missing picture.

## 4. Which region the pictures come from

Each title is scraped once, with the version that starts from the list (see
[VERSIONS.md](VERSIONS.md)), and its data and pictures are used for all the
versions of the title. Names and pictures are taken in this order of regions:

1. the regions of that file, e.g. `(USA, Europe)`;
2. the order of `regions=` in `frontier.ini` (default USA, World, Europe,
   Japan);
3. then ScreenScraper's own, Europe, World, USA, Japan.

For the **box art** only, another region can come first, e.g. the Japanese
covers, in `scraper/scraper.ini`:

```ini
[scraper]
box_regions = jp
```

(more than one: `box_regions = jp,us`). Then "Games already scraped" -> all
again, for the systems you want.

## 5. Space and time

Pictures take a few hundred KB per game; **videos** take a few MB each (a
full scraping of the consoles with videos can take tens of GB and a long
time: it can be stopped and resumed). Fanart is large and off at the start.

Everything goes in `/media/fat/frontier`:

| Folder | What |
|---|---|
| `gamelists/<system>/gamelist.xml` | the data of the games (EmulationStation format) |
| `media/<system>/<type>/` | pictures and videos (`box`, `snap`, `title`, `marquee`, `fanart`, `video`) |
| `.scrape_cache/` | the answers of the sources, so a new run does not ask again; the games not found (`notfound_<system>.tsv`) and what the scraper read of the `.mra` files (`mra_info.tsv`) |
| `.cache/scrape.log` | the output of the last run |

## 6. From a terminal

The same scraper runs from SSH, with more options (`--help`):

```sh
python3 /media/fat/frontier/scraper/fe_scrape.py --arcade
python3 /media/fat/frontier/scraper/fe_scrape.py --system NES --system SNES --video
python3 /media/fat/frontier/scraper/fe_scrape.py --all-systems --lang it
python3 /media/fat/frontier/scraper/fe_scrape.py --arcade --game "Bomb Jack"
```

On a PC with the SD card mounted: add `--root /path/of/the/sd`.
The full list of options is in the user guide, `frontier/README.txt`
(section SCRAPER).
