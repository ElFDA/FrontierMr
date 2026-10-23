# Changelog

All the releases of Frontier, newest first.
Each release is on the [Releases page](https://github.com/ElFDA/FrontierMr/releases); the text of
a release is its entry here.

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
