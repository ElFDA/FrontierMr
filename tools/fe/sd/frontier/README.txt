FRONTIER for MiSTer - quick guide
=================================

Frontier replaces the core selection screen of the menu. Everything else
in MiSTer works as before.
Step by step guides (scraper and ScreenScraper account, lists, which version
of a game starts, Coin-Op mode, a game with a black screen):
https://github.com/ElFDA/FrontierMr/tree/master/docs
Earlier versions were called "frontend": at the first start the folder
/media/fat/frontend becomes /media/fat/frontier (frontend.ini becomes
frontier.ini, frontend.off frontier.off), with themes, favorites, media and
settings.

MAIN SCREEN
  Favorites   all your favorite games in a single list (system on the right)
              and, above it, one folder per system with its favorites
              (Arcade, Mega Drive, SNES..., MiSTer for cores and MGLs)
  Recent      the games you played last, the last one first (see RECENT)
  My Lists    your own lists of games (see MY LISTS)
  Arcade      the games in _Arcade (.mra) and its subfolders; the
              _alternatives are in the game details (X)
              "#Newest", first in the folder: the arcade games which appeared
              on the SD card in the last 30 days (new ones, not updated ones),
              the newest first; see NEWEST ARCADE GAMES
  Computer, Console, Handheld, Other
              the systems with games in /media/fat/games (see below); a
              category is shown only if it has some
  MiSTer      the folders and cores of the original browser (Utility, Other...)
  Frontier Settings
              the settings of Frontier, last entry (see FRONTIER SETTINGS)

  Frontier always starts on this screen after power on or a cold reboot; after
  a game or a core it reopens the folder of the last game.

  In a game: OSD (F12) -> Core opens the list of the cores as in the original
  MiSTer (to start another core); Alt+F12, or L+R+Select+Start held for 2
  seconds on the joypad, goes back to Frontier.

CONTROLS
  Up/Down, Left/Right (page)          move in the list (holding Up/Down speeds
                                      up after 1.5 and 3 seconds)
  L / R  (keyboard - and =)           previous / next letter
  A / Enter                           open a folder or start a game
  B / Esc                             parent folder (in the main screen: OSD menu)
  X / Tab / Backspace / I             game details (Backspace on a folder:
                                      parent folder; on the gamepad A+B = Backspace)
  X held for a second / F             add or remove the game from Favorites
                                      (also in the details); X pressed and
                                      released at once opens the details
  X held on a folder                  update the lists (see below)
  F12 / OSD button                    original menu (System)
  R2 / ` (backtick)                   original core browser
  F5                                  reload theme, games and media (for theme authors)
  While Up/Down is held only the list moves: pictures and game data are
  updated when you stop.

GAME DETAILS (X)
  Large picture or video, game card (year, developer, publisher, genre,
  players, rating), description and the versions of the game: for arcade
  games the main .mra and its _alternatives (same romset). Up/Down picks a
  version, A starts it, B or X go back to the list, X held adds or removes
  the game from Favorites.
  The index of the alternatives is built the first time in the background
  (up to a minute with a cold SD card) and kept in .cache/alternatives.txt.

FRONTIER SETTINGS (last entry of the main screen)
  CRT Geometry        folder with the picture on the CRT:
    Width, Height     size of the picture on the CRT, 50-100% of the screen
    Left/right, Up/down
                      position of the picture on the CRT: pixels to the right
                      and lines down (negative = left, up)
    Reset             A: back to 100%, 100%, +0, +0
  Scraper             game data, pictures and videos from Frontier (see
                      SCRAPER FROM FRONTIER)
  Screensaver         folder with the screensaver settings (see SCREENSAVER):
    Start after       after how long without keys it starts: OFF, 30 s ... 60 min
    Time per game     how long each game is shown: 10 s ... 5 min (default 30 s)
    Transition        effect between two games: fade, slide, wipe, none
  Themes              folder:
    Theme             A or Right: next theme, Left: previous one (see THEMES)
    Text layout       ON: the descriptions in place of the pictures of the
                      games, for those who scrape only the texts (see TEXT
                      LAYOUT); OFF (default): the pictures
  Visible systems     the systems shown in Frontier: Arcade and the
                      categories; in a category A (or Left/Right) on a system
                      = shown/HIDDEN. A hidden system is not in the lists nor
                      in the screensaver (favorites and recent games stay); a
                      category with all its systems hidden disappears.
                      Written in frontier.ini: hidden=NES,_Arcade...
  Coin-Op mode        A or Left/Right: ON/OFF (see COIN-OP MODE)
  CRT output          A or Left/Right: ON/OFF, Frontier also on the CRT of the
                      VGA output (crt=1, see VIDEO OUTPUTS); also F12 ->
                      Scripts -> frontier_crt
  Recent games        how many games Recent shows: OFF, 10, 20, 30, 50, 100,
                      200 (default 50, see RECENT)
  Left/Right (or L/R) change the selected value and the CRT shows it at once.
  While an entry of CRT Geometry is selected a yellow frame marks the edges of the
  picture: make it smaller and move it until the frame is all on the screen
  (CRTs hide the borders of the picture). The values are written in
  frontier.ini (crt_width, crt_height, crt_hpos, crt_vpos) a second after the
  last change. CRT Geometry is there only when Frontier is on a CRT
  (CRT output ON, or direct_video=1 in MiSTer.ini).
  With Frontier's menu.rbf left/right moves the sync of the CRT in steps
  of 4 pixels (nothing is cut); everything else is done by drawing the
  picture smaller in its 640x240 page, so at 100% a picture moved up or down
  loses some lines at the edge.
  These settings are only for the screens of Frontier: a game shows the
  picture of its own core, which they don't change. Set up the CRT (its own
  controls) for the games first, then fit Frontier with these entries.

FAVORITES
  Hold X on a game (or press F on the keyboard) to add it to Favorites; do it
  again to remove it (also from the Favorites list). A star on the picture
  marks the games which are already there. It works for console games by
  title (the default version starts, the others are in the details), files
  in the folders of games/, arcade games and cores.
  They are stored in /media/fat/frontier/favorites.txt, one line per game:
  <key><TAB><name>, key = @sys/<folder>/<title> or the path
  (games/..., _Arcade/....mra). It can be edited by hand, then press F5.

RECENT
  Every game started from Frontier (from the lists, the details, Favorites,
  Recent or the screensaver; not the cores) goes on top of Recent, with its system on the
  right; a game played again moves up. A starts it, X shows the details, X
  held adds it to Favorites; L/R move by a page (the list isn't in name
  order). Games by title start with their default version, as in Favorites.
  In frontier.ini (or in Frontier Settings, see above):
    recent=50                       how many games (0 = no Recent, nothing
                                    is written)
  They are stored in /media/fat/frontier/recent.txt, one line per game, the
  last one first, as favorites.txt. Delete it to empty Recent (then F5).

MY LISTS
  Lists of games made by you, e.g. "Capcom arcade", "Shoot'em ups", "Party
  games": each one is like Favorites (games of all systems together, the
  system on the right).
  Adding a game: open its details (X), go down to "Add to list..." under the
  versions and press A: your lists are shown, "in list" on the right of
  those which have the game already. A on a list adds the game (or removes
  it, if it is there); A on "+ New list" makes a new list with the game
  ("List 1", "List 2"...). B goes back to the versions.
  Removing a game: open its details inside the list, then A on "Remove from
  this list" (there it takes the place of "Add to list..."). From the other
  lists "Add to list..." removes it too (A on a list marked "in list").
  A list from a filter: in My Lists, "+ New list from filter..." shows a
  line for each data of the games, with what is chosen on the right:
    System      Arcade, Mega Drive, SNES...
    Core        the arcade boards: CPS1, CPS2, Neo Geo MVS, Sega System 16B...
    Publisher   Capcom, Konami, Sega...
    Developer   who made the game (arcade: the manufacturer)
    Genre       Shoot'em up, Platform, Fighting, Beat'em up, Run and gun,
                RPG, Sports... (the same genres for arcade and consoles)
    Subgenre    Shoot'em up / Vertical, Sports / Soccer...
    Decade      1980s, 1990s...     Year   1991...
    Series      Street Fighter, Castlevania, Thunder Force...
    Players     1 player ... 5+ players (how many can play at once)
  A on a line shows its values with the number of games (counting the
  other choices): A ticks [x] or unticks a value, "Any" unticks all, B goes
  back. More values of a line: one of them; more lines: all of them. E.g.
  the platform games of Capcom and Konami on the SNES:
    System = SNES, Publisher = Capcom + Konami, Genre = Platform
  Then, at the end of the lines:
    Show the N games              the games of the filter (they start, show
                                  their details... as in the other lists)
    Create a list with the N games...  a new list, then its name:
                                  Name it "..." = the name made from the
                                  filter ("SNES - Capcom, Konami - Platform");
                                  Type a name on the keyboard... = your own
                                  name, typed on a USB keyboard (Enter:
                                  create, Esc or B: cancel)
    Add the N games to a list...  adds them to one of your lists (the games
                                  already there stay once): so different
                                  filters go in the same list
    Clear the filter              nothing chosen
  The filter stays as it is (also after a game) until a list is made or
  games are added to a list with it: then it starts again from nothing. A
  list made this way is a list like the others: add or remove games as above.
  The data come from the scraper: at the end of every run it writes
  .cache/meta.tsv; to make it again without downloading anything:
    python3 /media/fat/frontier/scraper/fe_scrape.py --index
  (the first time it reads all the answers saved by the scraper: a few
  minutes; then less than a minute). Only the games scraped have data;
  arcade games always have at least core, manufacturer and year (from the
  .mra). The genres of the sources are made the same by scraper/genres.ini,
  the names of the same company ("Capcom U.S.A.", "Mitchell (Capcom
  license)") by scraper/publishers.ini, the names of the arcade cores by
  scraper/arcade_cores.ini: they can be edited, then run --index again.
  At the end of every list:
    Rename this list (keyboard)   type the new name on a USB keyboard: the
                                  name is there to change, Backspace deletes,
                                  Enter saves; Esc or B on the joypad cancel
                                  (e.g. if no keyboard is connected)
    Delete this list              A deletes it; a list with games asks for
                                  A a second time
  The names can also be changed in /media/fat/frontier/mylists.ini, then F5.
  mylists.ini has a section per list, its name in brackets, then one line
  per game as in favorites.txt:
    [Shoot'em ups]
    @sys/MegaDrive/Thunder Force IV<TAB>Thunder Force IV
    _Arcade/1943 The Battle of Midway (Euro).mra<TAB>1943 The Battle of Midway (Euro)

SCREENSAVER
  After some time without keys (5 minutes by default) Frontier shows random
  games, one after the other: their video (or picture, if there is no video),
  game card and description, with the look of the theme. Only games with a
  video or a picture are shown: arcade games of _Arcade and the games by
  title of the systems. Start on the gamepad (Space on the keyboard) plays
  the game shown; any other button goes back to the screen of before.
  In frontier.ini (or in Frontier Settings -> Screensaver, see above):
    screensaver=300                 seconds without keys (0 = off)
    screensaver_time=30             seconds for each game
    screensaver_transition=fade     fade, slide, wipe or none
    screensaver_transition_ms=700   length of the transition
  Themes draw it with screensaver.ini / screensaver_43.ini (without them the
  ones of the simple theme are used). With the built-in look (theme=none)
  there is no screensaver.

LOADING SCREEN
  While a core loads the game (the bar at the top left of the OSD, slow with
  the big Neo Geo games) HDMI shows the loading screen of the theme: the
  game, its box, an animation and the progress, then the game. The analog
  output of a core shows only the core's own picture and the OSD: the CRT gets
  a loading screen in the OSD (white on the darkened picture of the core: a
  turning record, NOW LOADING, the game, the bar); loading_crt=0 in
  frontier.ini keeps the bar of the OSD. With direct_video=1 for the games
  (MiSTer.ini, [MiSTer] or the section of the core, not [Menu]: CRT only
  setups, HDMI at 15 kHz) the CRT shows the loading screen of the theme too.
  Themes draw it with loading.ini / loading_43.ini (without them the one of
  the simple theme is used); loading_screen=0 in frontier.ini turns it off.

GAMES ON A USB DISK
  If /media/fat/games is a link to a USB disk, the disk is mounted some
  seconds after the MiSTer starts. Set games_wait=N in frontier.ini: the
  longest wait in seconds, e.g. 30. It is not a delay: games/ is checked at
  once and, while it is empty, every 2 seconds; as soon as the disk is there
  the systems appear and Coin-Op starts the game. After N seconds it stops
  trying (Coin-Op: "game not found, skipped"). games_wait=0 (default): games
  on the SD card, no wait.

COIN-OP MODE (the last game starts at power on)
  As in a cabinet: switching the MiSTer on, the last game launched from
  Frontier starts again by itself (arcade, console, computer, handheld, from
  Favorites too; a ROM loaded from the OSD inside a core doesn't count).
  Turn it on and off from Frontier Settings -> "Coin-Op mode"
  (A: ON/OFF), which writes
  coinop=1/0 in frontier.ini (it can be changed on the PC too).
  At power on the game starts at once. With coinop_delay=N in frontier.ini
  "Coin-Op: <game> - any button: menu" appears at the bottom for N seconds
  first, and any button cancels the start ("Coin-Op: cancelled"). If games/ is
  on a USB disk mounted late, it waits for the game up to games_wait seconds
  (see GAMES ON A USB DISK).
  Coming back to the menu from a game nothing starts: only at power on.
  Anti-panic, if the last game doesn't show on the CRT or hangs the MiSTer:
  - switch off and on within a minute: the automatic start counts only if the
    game stayed on for coinop_safe seconds (60); otherwise at the next power on
    nothing starts ("Coin-Op: last start did not complete, skipped") and you
    are in Frontier;
  - in the game, L+R+Select+Start held for 2 seconds go back to the menu (a
    quick press stays for the game: in many SNES games it is the reset). They
    are the joypad's buttons as mapped for the menu. panic_combo=0 in
    frontier.ini turns them off;
  - with coinop_delay, a button during the countdown;
  - on the PC: coinop=0 in frontier.ini, or an empty file frontier/coinop.off
    on the SD card.
  The last game is in frontier/coinop_last.txt (path, name, file to wait
  for); frontier/coinop.pending is there in the first minute of an automatic
  start.

UPDATING THE LISTS (after adding or removing games or cores)
  The lists of the games of each system, of the systems with games and cores
  and of the arcade versions are made the first time and kept in
  /media/fat/frontier/.cache: coming back from a game Frontier doesn't
  read the disk again. To read them again, hold X (F on the keyboard):
    on a system (Console -> Mega Drive) or on "Folders" inside the system
                                      the games of that system
    on Computer, Console, Handheld, Other in the main screen
                                      all the systems of the category, new
                                      ones too (folders or cores added)
    on Arcade in the main screen      the alternative versions (_alternatives)
  "Updating: ..." and then "List updated: ..." appear at the bottom; the list
  can be used in the meantime. F5 reads again everything you open until the
  next start. With rescan=auto in frontier.ini the lists are checked
  automatically at every start. Deleting the .cache folder = everything is
  made again on first use.

GAMES BY SYSTEM
  Computer, Console, Handheld and Other list the folders of /media/fat/games
  which have files and an installed core.
  Inside a system there is a single list with all the games of its
  subfolders (1 US, 2 Europe, 2 Japan...), one entry per title: it takes the
  files with a No-Intro style region in the name, e.g.
  "Altered Beast (USA, Europe).md"; hacks, translations, pirate copies and
  files with other text after the tags are only in "Folders". A release date
  in front of the name (collections sorted by date) doesn't count.
  Collections without No-Intro names (e.g. a zip of C64 games named "Spy vs
  Spy.crt") are only in "Folders", where a zip opens as a folder. Files and
  folders whose name starts with @ ("@C64 2023-4-28.zip") work as the others.
  "Extra" folders (games/NES/Extra with unlicensed games, prototypes, hacks,
  compilations...) are skipped by the list and by the scraper: they are only
  in "Folders". To use other names or more folders: exclude_dirs= in
  frontier.ini (e.g. exclude_dirs=Extra,Unsupported).
  A starts the released version (before betas and prototypes, even of
  another region) of the preferred region (regions= in frontier.ini, default
  USA, World, Europe, Japan; then the latest revision). X shows all the
  versions: regions, revisions and also the other titles of the same game
  (Thunder Force IV and Lightening Force are both in the list, each one with
  the versions of the other in the details). For these, once per system:
    python3 /media/fat/frontier/scraper/fe_scrape.py --groups --system MegaDrive
  (MAME software lists, matched by name or CRC; a few minutes the first time,
  then seconds) -> gamelists/<system>/groups.txt. Then F5.
  Zip files are listed like plain files: the roms inside them with the region
  in the name, one game per zip ("Altered Beast (USA, Europe).zip") or a whole
  collection in one zip ("SNES.zip", also with folders inside).
  "Folders" at the top of the list leads to the real folders (hacks,
  translations, compilations...). The list is read once and kept in
  .cache/games_*.txt: from then on it appears at once and is not read again
  (see UPDATING THE LISTS).
  The game starts with an MGL (like the official .mgl files) made in launch/.
  Neo Geo (romsets=1 in systems.ini): the names have no region, the romsets
  are used as the core does: .neo files with the setname at the end of the
  name ("3 Count Bout (3countb).neo") and the zip files listed in
  games/NEOGEO/romsets.xml (3countb.zip -> "3 Count Bout"). Same title = one
  entry, with .neo, zip, "set 2" and AES version in the details (the .neo
  starts); different titles of the same romset are linked. In "Folders" zip
  and .neo files are shown with the names of romsets.xml, as in the core's
  browser.
  .neo files without the setname ("Burning Fight.neo") are games too, with
  the name of the file as title; so are the .neo files inside a zip which
  isn't a romset of romsets.xml (e.g. NEOGEO.zip with BeatEmUp/Burning
  Fight.neo...): they start from inside the zip. The scraper gives them the
  setname of the game with the same name in romsets.xml ("The Super Spy" =
  "Super Spy, The" -> superspy), so ArcadeDB and ScreenScraper find them.
  When a version has no data of its own, Frontier shows those of another
  version of the same game.

SYSTEM DATA
  On a system (in Computer, Console, Handheld, Other, in Favorites and in My
  Lists) Frontier shows what it is: description, maker, year, type and the
  hardware (CPU, memory, graphics, sound, media, units sold...). With the
  text layout the description takes the place of the picture; the themes
  show maker and year where they show those of the games.
  The data come from Wikipedia, with the texts of the games (Texts ON in the
  scraper): the English article written in wiki= of systems.ini, the
  description in the language of the scraper (from the English one if that
  language has no article), the hardware from the table of the English
  article. Saved in frontier/gamelists/systems/gamelist.xml, once per
  system; again with "Games already scraped" = texts again (or --refresh-data).
  Only the data of the systems: Frontier Settings -> Scraper -> "Get systems
  data only", or from SSH:
    python3 /media/fat/frontier/scraper/fe_scrape.py --systems-info --all-systems --lang it
  Themes: ${game.desc} (description and hardware), ${game.developer},
  ${game.year}, ${game.genre} and one variable per data: ${game.cpu},
  ${game.memory}, ${game.graphics}, ${game.sound}, ${game.display},
  ${game.media}, ${game.units}, ${game.generation}, ${game.released}...

SCRAPER FROM FRONTIER (Frontier Settings -> Scraper)
  Start scraping      A: starts the scraper in the background with the choices
                      below (A again: Stop scraping). On the right the progress,
                      e.g. "SNES 120/840 (2/5)", then finished/stopped/error;
                      "finished: 3 updated" = 3 games got new data or
                      pictures, "finished: nothing new" = nothing to add (the
                      message at the end also says how many were not found).
                      You can go on using Frontier and play: the scraper keeps
                      working on the other core of the processor; the new
                      pictures of a system appear when that system is
                      finished. Its output: frontier/.cache/scrape.log
  Scrape this game    in the details of a game (X), under "Add to list...":
                      the scraper for that game only (and the arcade
                      alternatives that take from it), in the background. It
                      asks the sources again and downloads again its data and
                      pictures, with the content chosen here (Texts, Box
                      art...). About a minute; the new pictures appear when it
                      is finished.
  Get systems data only
                      A: only the data of the systems chosen (description,
                      maker, year, hardware from Wikipedia, see SYSTEM DATA),
                      in the language chosen: a few minutes, no games. Those
                      already there are skipped, unless "Games already
                      scraped" is texts again or all again.
  Systems             Arcade and the categories; in a category "All" or one
                      system at a time: ON/OFF
  Language            English (default), Italian, French, German, Spanish,
                      Portuguese, Japanese: descriptions and genres
  Texts               names, descriptions, genres, publishers... ON/OFF;
                      also the data of the systems (see SYSTEM DATA)
  Box art, Screenshots, Title screens, Marquees and logos, Fanart, Videos
                      what to download, ON/OFF each (default all but fanart)
  Games already scraped
                      skip (only what is missing, default), texts again (the
                      data in the language chosen, pictures kept), all again,
                      retry not found (also the games no source had in the
                      last 30 days, see SCRAPER)
  ScreenScraper user, ScreenScraper password
                      A, then type them on a keyboard connected to the MiSTer
                      (Enter: save, Esc: cancel; empty = removed). Saved in
                      scraper.ini. Without an account only ArcadeDB and
                      libretro are used (arcade, pictures).
  The choices are kept in frontier.ini (scrape_systems, scrape_lang,
  scrape_text, scrape_media, scrape_redo). Stopping is safe: what was
  downloaded stays and the next run goes on from there.

SCRAPER (game data and pictures)
  On the MiSTer (via SSH or terminal):
    python3 /media/fat/frontier/scraper/fe_scrape.py --arcade
    python3 /media/fat/frontier/scraper/fe_scrape.py --system NES --system SNES
    python3 /media/fat/frontier/scraper/fe_scrape.py --all-systems
  Useful options: --limit 20 (test), --force (do it again), --lang en, --help.
  --game "Bomb Jack": only that game (file name without extension, with
  --arcade or one --system), asked again and downloaded again.
  --media box,snap,video: only these pictures/videos (box, snap, title,
  marquee, fanart, video; none = no media); --no-text: no data, only media.
  --groups (with --system or --all-systems): only the different titles of
  the same game from the MAME lists, no data or pictures.
  --category Console (or Handheld, Computer, Other; repeatable): all the
  systems of a category of systems.ini.
  --systems-info: only the data of the systems (Wikipedia, see SYSTEM DATA)
  of --system, --category or --all-systems; also done with the games, unless
  --no-text.
  --index: only the data for "+ New list from filter..." (see MY LISTS), no
  network; it is also done at the end of every run.
  --refresh-data: write again names, descriptions, genres... in the language
  of --lang (e.g. after scraping in another language), without downloading
  again the pictures already there (--force downloads everything again).
  The answers of ArcadeDB are kept per language (.scrape_cache/adb_en...).
  For systems the scraper works like the list: only files with a region, one
  request per title (the version which starts), data and pictures copied to
  the other versions of the title too. --all-files = all the files, hacks
  included.
  Neo Geo: like the list (romsets), data and pictures from ArcadeDB and
  ScreenScraper by setname, as for arcade games.
  Box art of another region: --box-regions jp, or in scraper.ini
    [scraper]
    box_regions = jp
  Example, all the consoles with videos (ScreenScraper; it takes time, it
  can be stopped and resumed):
    python3 /media/fat/frontier/scraper/fe_scrape.py --groups --category Console
    nohup python3 /media/fat/frontier/scraper/fe_scrape.py --category Console --video > /media/fat/frontier/scrape.log 2>&1 &
  Fanart and videos are downloaded only on request: --fanart, --video (see
  below). Fanart already downloaded stays and the gamelist keeps using it; to
  free space delete media/<system>/fanart/ by hand.
  Sources, in this order: ScreenScraper (all systems, arcade too, so they
  all have the same genres, descriptions and videos: it needs a free account
  on screenscraper.fr, see scraper/scraper.ini.example -> copy it to
  /media/fat/frontier/scraper.ini or next to the example and write user and
  password; the "developer" credentials of Frontier are in the scraper), ArcadeDB (arcade
  and Neo Geo: what ScreenScraper hasn't, or everything without its
  account), libretro-thumbnails (pictures). Another order: --sources adb,ss,libretro.
  On a PC with the SD card mounted: add --root <SD card path>; with Pillow
  the pictures are also scaled down.
  Stopping the scraper (Ctrl+C) is safe: run it again and it resumes.
  Games not found: when no source has a game (or not all that was asked:
  e.g. no box art anywhere), the scraper remembers it in
  .scrape_cache/notfound_<system>.tsv and skips it for 30 days, so the
  counter only shows the games to do (hacks, bootlegs and homebrew are not
  asked again at every run). After 30 days, or asking more pictures or
  another source, it tries them again; at once with --retry-missing (or
  "Games already scraped" = retry not found), --force or --refresh-data.
  Network or server errors do not count: those games are tried again.
  Arcade alternatives (_Arcade/_alternatives): an alternative takes the data
  and the pictures of its main game (the .mra outside _alternatives of the
  same MAME set, e.g. "Street Fighter II (USA 910522)" from "Street Fighter
  II (World 910522)"), keeping its own name: no request and no file copied.
  Only an alternative without a main game (or whose main game has nothing)
  is scraped on its own. The .mra files are read once and kept in
  .scrape_cache/mra_info.tsv (read again when they change).

VIDEOS
  Frontier plays the mp4 videos the scraper downloads with --video
  (ScreenScraper, ArcadeDB), with their sound, where the theme has a video
  element (in the City Pop themes: the details view). They are decoded by the
  MiSTer's ARM with lib/fe_av.so (FFmpeg, licence in lib/FFMPEG_LICENSE.txt)
  on the processor core the menu leaves free: a 640x480 ScreenScraper video
  takes about half of that core, the menu stays as fast as before. Without
  lib/fe_av.so only .mjv videos play (they have no sound).
  Sound: video_volume=40 in frontier.ini (0-100, 0 = no sound; the default is
  lower than the games). It stops when the details close, a game starts or
  the OSD opens. With the TV and the CRT together (dual mode) the video is
  shown on both.
  .mjv videos (a sequence of JPEG pictures, lighter to play, ~7 MB per 30 s)
  still play and are used before an mp4 of the same game. They are made on a
  PC with ffmpeg: python3 fe_scrape.py --root <SD> --video --mjv downloads
  and converts, --convert-videos converts the mp4 files already downloaded;
  from the repository tools/fe/convert_videos.sh [system ...] takes the mp4
  files from the MiSTer and sends back the .mjv files (then run the scraper
  again with the same options to write them in the gamelists).

UPDATES (update_all / downloader)
  Install once with F12 -> Scripts -> frontier_install, then use update_all
  as usual: no terminal commands, INI edits or reinstallation after updates.
  Two ways to install:
  - through update_all: copy downloader_frontiermr.ini (from
    https://github.com/ElFDA/FrontierMr/releases/latest/download/downloader_frontiermr.ini)
    to /media/fat, run update_all, then frontier_install;
  - the ZIP of a release (https://github.com/ElFDA/FrontierMr/releases):
    copy the contents of its SD folder to the SD card, then frontier_install.
  Official cores, the official menu.rbf and everything else keep updating.
  How MiSTer stays Frontier's:
  - Frontier's firmware lives in frontier/bin (MiSTer and menu.rbf). The
    MiSTer in the root is a copy; menu.rbf in the root stays the official one
    and Frontier loads its own from frontier/bin (for a moment at power on
    you may see the official menu: Frontier switches to its own).
  - frontier/guard.sh, started by linux/user-startup.sh at shutdown and at
    boot, copies frontier/bin/MiSTer to the root whenever something else
    (an update, another tool) has replaced it. Frontier does the same before
    starting a core and before a reboot from the OSD.
  - '!misterfirmware' in the filter of [distribution_mister] in
    downloader.ini avoids downloading the official MiSTer for nothing. If an
    update rewrites downloader.ini or user-startup.sh, Frontier puts its lines
    back at the next start (log: frontier/update_protection.log).
  - Frontier's own updates: /media/fat/downloader_frontiermr.ini (put there
    by frontier_install) lets update_all download each new release and take
    from it the files of frontier/ and the frontier_* scripts (your
    frontier.ini, favorites, lists, gamelists and media are never replaced).
    After the update the MiSTer reboots and the guard installs the new MiSTer.
  If you installed an older Frontier package, copy the new package's SD
  folder to your card and run frontier_install again once: the official
  menu.rbf comes back in the root (at the latest with the next update_all;
  Frontier's is in frontier/bin) and
  frontier_crt_menu is no longer needed. Settings and data are kept.
  frontier_on_off only switches the interface; MiSTer stays Frontier's.
  BACK TO THE OFFICIAL FIRMWARE: F12 -> Scripts -> frontier_uninstall. It
  stops the guard, removes Frontier's lines and database from the update
  setup and puts back MiSTer.orig (saved by frontier_install); without
  MiSTer.orig the next update_all brings the official MiSTer. Frontier's
  files, settings and media stay on the SD: frontier_install brings it back.
  Do not run another updater during installation. If the protection cannot
  be configured, installation stops before replacing MiSTer; send the error
  to the package maintainer. Details: frontier/update_protection.log, what
  the guard did: frontier/guard.log.

SPEED ON THE TV
  Frontier draws at the resolution of the menu framebuffer: at 1080p
  each step in the list takes ~70 ms. With fb_size=2 in the [Menu] section of
  MiSTer.ini (or of the TV's ini) the menu works at 960x540 scaled up by the
  scaler: ~20 ms per step, slightly softer picture.

VIDEO OUTPUTS (MiSTer.ini)
  The main settings of /media/fat/MiSTer.ini for each setup; the other
  options can keep their default values. Keep a copy of the ini before
  changing it. Two setups can live in two ini files (e.g. MiSTer.ini and
  MiSTer_TV.ini), chosen from the OSD.

  CRT only (VGA of the analog I/O board -> TV/PVM, RGB SCART)
    [MiSTer]
    vga_scaler=0           ; VGA = original video of the core (15 kHz)
    forced_scandoubler=0   ; 1 only for a 31 kHz VGA monitor
    composite_sync=1       ; composite sync for TV/PVM over SCART
                           ; (vga_sog=1 if the cable uses sync on green)
    vga_mode=rgb           ; ypbpr for component
    direct_video=0
    [Menu]
    direct_video=1         ; Frontier at 640x240 on the VGA too
    menu_pal=0             ; 1 if the CRT does not take NTSC
  Without direct_video=1 in [Menu] (and with the official menu.rbf) the VGA
  shows only noise in the menu: Frontier draws in the framebuffer. Without
  changing MiSTer.ini, F12 -> Scripts -> frontier_crt (crt=1) sends Frontier
  to the CRT as well: the OSD is seen there even when the menu is noise.
  With an HDMI->VGA DAC instead of the I/O board: direct_video=1 in
  [MiSTer] (2 for DACs that report 1024x768) and composite_sync=1.

  HDMI only
    [MiSTer]
    video_mode=8           ; 1920x1080@60 (0 = 720p, 14 = 1440p)
    vsync_adjust=2         ; low latency (1 if the TV loses the signal)
    vscale_mode=0          ; 1 = integer scale only
    direct_video=0         ; with 1 the TV gets raw 240p
    hdmi_limited=0
    [Menu]
    fb_size=2              ; faster Frontier (see SPEED ON THE TV)
  and crt=0 in frontier.ini.

  CRT + HDMI together
    [MiSTer]
    video_mode=8
    vsync_adjust=2
    direct_video=0         ; scaled HDMI on the TV
    vga_scaler=0           ; native 15 kHz on the CRT
    composite_sync=1
    forced_scandoubler=0
    [Menu]
    video_mode=8
    direct_video=0
    fb_size=2
  and CRT output ON (Frontier Settings -> CRT output, or F12 -> Scripts ->
  frontier_crt: crt=1 in frontier.ini). Games always come out on both.
  Frontier loads its own menu.rbf (frontier/bin): the menu is in HD on the
  TV and 240p on the CRT (theme_43.ini). With the official menu.rbf (if
  Frontier's could not start) both show the same 4:3 picture.

  To avoid: direct_video=1 in [MiSTer] with an HDMI TV (it is only for
  DACs); vga_scaler=1 with a 15 kHz CRT (the VGA gets the scaler output,
  31 kHz or more).
  vscale_mode=4 (or any value other than 0 and 1) in [MiSTer]: the loading
  screen of the games loses the sync, on the HDMI and on the CRT. Use 0 or 1.

DISABLING FRONTIER
  F12 -> Scripts -> frontier_on_off (or create the file /media/fat/frontier.off)
  -> the original browser is back; the same script turns Frontier on again.

SCRIPTS (F12 -> Scripts)
  frontier_install    installs Frontier, or a new version from a package;
                      keeps settings, lists and media (see UPDATES)
  frontier_uninstall  back to the official firmware (see UPDATES)
  frontier_on_off     Frontier's screen off (original browser) or on again
  frontier_crt        Frontier also on the CRT of the VGA output, on or off
                      (the same as Frontier Settings -> CRT output)
  The scraper runs from Frontier Settings -> Scraper (see SCRAPER FROM
  FRONTIER); the frontier_scrape script of older versions is removed.

THIS FOLDER (/media/fat/frontier)
  favorites.txt     Favorites (see above)
  recent.txt        Recent (see above)
  mylists.ini       My Lists (see above)
  frontier.ini      theme=<theme name> (see THEMES; none = plain look)
                    fps=30 (animations)   debug=1 (drawing times on stderr)
                    regions=, exclude_dirs=, rescan=, crt=, crt_width=, crt_height=,
                    crt_hpos=, crt_vpos=, recent=, screensaver=... (see the comments)
  systems.ini       systems: folder in games/ -> core and MGL parameters
  themes/<name>/    themes: theme.ini (16:9), theme_43.ini (4:3/CRT),
                    detail.ini and detail_43.ini (details), screensaver.ini
                    and screensaver_43.ini (screensaver), loading.ini and
                    loading_43.ini (loading screen; if missing the default
                    ones are used), pictures, fonts
  themes/<name>/media/systems/<key>.png|.jpg
                    picture of the theme in the large box for the main screen
                    (key favorites, recent, mylists, arcade, computer, console,
                    handheld, other, mister, settings; without settings the
                    picture of mister) and for the systems, in Favorites too
                    (key = folder of games/ in lowercase, e.g. 3do, nes,
                    gameboy, or the section name in systems.ini, e.g.
                    gameboycolor).
                    JPG for full pictures, PNG only if transparency is needed;
                    suggested size 660x495 (4:3). After copying them: F5.
  gamelists/<system>/gamelist.xml   game data (EmulationStation format)
  media/<system>/<type>/<game>.png|.jpg|.mp4|.mjv
                    type: box snap title marquee fanart video
                    system: arcade, nes, snes, ... (folder of games/ in lowercase)
  launch/           MGLs made to start the games (can be deleted)
  bin/              Frontier's MiSTer and menu.rbf (see UPDATES)
  guard.sh, protect_updates.py, guard.log, update_protection.log
                    keep MiSTer through updates (see UPDATES)
  downloader_frontiermr.ini
                    Frontier's database for update_all, copied to /media/fat
  old/              folders of older versions (the theme "default", now "simple")
  scraper/          fe_scrape.py: downloads game data and pictures;
                    genres.ini, publishers.ini, arcade_cores.ini (see MY LISTS)
  .cache/           saved lists (see UPDATING THE LISTS), meta.tsv (data of
                    the games for the lists from a filter)

NEWEST ARCADE GAMES
  Arcade -> "#Newest" lists the new .mra files (also in the subfolders of
  _Arcade, not _alternatives) with the day Frontier saw them. The date of the
  files can't tell new from updated (update_all rewrites them), so Frontier
  keeps its own list in frontier/arcade_seen.txt: the first time everything
  already on the card counts as known and "#Newest" is empty; from then on a
  game which was not there at the previous start of Frontier (or the previous
  visit to "#Newest", or F5) is new. It stays for newest=30 days in
  frontier.ini (0 = no "#Newest"). Delete arcade_seen.txt to start again from
  now. Needs the clock of the MiSTer to be set (internet at least once): the
  MiSTer has no clock of its own, so for the first seconds after the power on
  "#Newest" shows what is already known and new games get their day later
  (open "#Newest" again or press F5).

THEMES
  Change the theme from Frontier Settings -> Themes -> "Theme" (A), or with
  theme= in frontier.ini.
  citypop_blue  Japanese pop of the bubble era on the blue of the titles,
              light panels, a pink bubble, offset shadows, cards for the main
              screen. The theme used when frontier.ini has no theme=
  citypop     the same on pale pink with a dashed grid, mint and blue
  citypop_dark  the same on the dark background of the site at night
  simple      dark blue, the original look of Frontier. It is also the theme
              the screens missing from another theme are taken from

TEXT LAYOUT
  Frontier Settings -> Themes -> "Text layout" ON (text_layout=1 in
  frontier.ini): in the list and in the details the description of the game
  scrolls where its picture (or video) was; name, year, maker, genre and the
  rest stay. For those who scrape only the texts, without pictures. On the
  main screen and on the categories the pictures of the theme stay; on a
  system its description (see SYSTEM DATA).
  All the themes of Frontier have it. In a theme: layout=media on the
  elements of the pictures (shown only with the text layout OFF),
  layout=text on those which replace them (only with it ON); elements
  without layout are always there.

MAKING A THEME
  The editor is for the PC, not for the MiSTer: it is one file, theme_editor.html,
  which works offline. Download it from the Releases page of FrontierMr
  (https://github.com/ElFDA/FrontierMr/releases/latest/download/theme_editor.html)
  and open it with Chrome or Edge, "Open folder" on a copy of themes/simple, edit, "Save to folder", copy
  the folder to /media/fat/frontier/themes/, set theme=<name> in
  frontier.ini and press F5.
  The editor edits theme.ini, theme_43.ini, detail.ini, detail_43.ini,
  screensaver.ini and screensaver_43.ini ("Variant"; "Make 4:3", "Make
  detail" and "Make screensaver" make the missing ones) and
  loads .ini files of other themes with "Import .ini". "text layout" in the
  toolbar shows the theme as with Text layout ON (key layout=, see TEXT
  LAYOUT).
  THEME_GUIDE.txt (in this folder) rebuilds the City Pop theme step by step.
  The theme keys are described at the top of themes/simple/theme.ini.

  Text on the CRT (theme_43.ini, 240 lines): the text is drawn on the real
  lines of the screen, with the horizontal strokes on whole lines
  (font_hinting=light, the default). The CRT has 640 columns but only 240
  lines, so narrower glyphs keep the text readable and fit longer names:
    [theme]
    font_width=85        width of the glyphs in percent (any text element too)
    font_hinting=light   light | mono (sharp, jagged) | full | none
  Sizes that read well at 240p with base=960x720: lists 28 (row_height=42),
  small texts 26, titles 34 and more. Below 26 the letters lose details.
  Look at the result on the PC with tools/fe/preview/preview.sh <theme>
  out.png 640 240, then on the CRT with F5.
