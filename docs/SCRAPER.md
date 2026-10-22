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
| Start scraping | A starts the scraper in the background; A again stops it. The progress is on the right ("SNES 120/840 (2/5)", then finished / stopped / error). You can go on using Frontier and play meanwhile. |
| Get systems data only | only the data of the systems, from Wikipedia: a few minutes, no games |
| Systems | Arcade and the categories; inside a category "All" or one system at a time, ON/OFF |
| Language | English (default), Italian, French, German, Spanish, Portuguese, Japanese: descriptions and genres (English when a text is missing in that language) |
| Texts | names, descriptions, genres, publishers... ON/OFF |
| Box art, Screenshots, Title screens, Marquees and logos, Fanart, Videos | each ON/OFF; all ON except Fanart at the start |
| Games already scraped | skip (only what is missing, the default), texts again (data in the language chosen, pictures kept), all again |

Your choices are kept in `frontier.ini`. Stopping is safe: what was downloaded
stays and the next run goes on from there. Errors of ScreenScraper (its daily
quota, the network) are tried again in the next run.

The new pictures of a system appear when that system is finished; to see
them at once on a system already open, hold X on it (or press F5).

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
| `.scrape_cache/` | the answers of the sources, so a new run does not ask again |
| `.cache/scrape.log` | the output of the last run |

## 6. From a terminal

The same scraper runs from SSH, with more options (`--help`):

```sh
python3 /media/fat/frontier/scraper/fe_scrape.py --arcade
python3 /media/fat/frontier/scraper/fe_scrape.py --system NES --system SNES --video
python3 /media/fat/frontier/scraper/fe_scrape.py --all-systems --lang it
```

On a PC with the SD card mounted: add `--root /path/of/the/sd`.
The full list of options is in the user guide, `frontier/README.txt`
(section SCRAPER).
