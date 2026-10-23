# Changelog

All the releases of Frontier, newest first.
Each release is on the [Releases page](https://github.com/ElFDA/FrontierMr/releases); the text of
a release is its entry here.

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
