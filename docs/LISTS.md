# Favorites, Recent and My Lists

The main screen of Frontier has three lists of games that mix all the
systems, each game with its system on the right.

| List | What it is | How it fills |
|---|---|---|
| **Favorites** | your favorite games | X held for a second on a game (or F on a keyboard); again to remove it |
| **Recent** | the games you played last, the last one first | by itself, every time a game starts |
| **My Lists** | lists made by you, as many as you want | by hand or from a filter on the data of the games |

## Favorites

On any game (in a system, in Arcade, in My Lists...) hold **X** for a second:
a star appears and the game is in Favorites. Do it again to remove it; it
works in the details too. X pressed and released at once opens the details.

In Favorites there is a single list with all your favorites and, above it, a
folder per system with only its favorites. They are saved in
`/media/fat/frontier/favorites.txt`.

## Recent

The last games started from Frontier, the newest first. How many:
Frontier Settings -> **Recent games** (OFF, 10 ... 200, 50 at the start).
Saved in `/media/fat/frontier/recent.txt`: delete it to empty the list.

## My Lists

### A list by hand

1. On a game press **X** for its details.
2. Go down to **Add to list...** (under the versions) and press A: your lists
   are shown, with "in list" next to those that already have the game.
3. A on a list adds the game (or removes it, if it is there). A on
   **+ New list** makes a new list with the game ("List 1", "List 2"...).
   B goes back.

To remove a game, open its details from inside the list and press A on
**Remove from this list**.

### A list from a filter

In My Lists, **+ New list from filter...** shows one line per data of the
games, with what is chosen on the right:

| Line | Values |
|---|---|
| System | Arcade, Mega Drive, SNES... |
| Core | the arcade boards: CPS1, CPS2, Neo Geo MVS, Sega System 16B... |
| Publisher | Capcom, Konami, Sega... |
| Developer | who made the game (arcade: the manufacturer) |
| Genre | Shoot'em up, Platform, Fighting, Beat'em up, Run and gun, RPG, Sports... |
| Subgenre | Shoot'em up / Vertical, Sports / Soccer... |
| Decade, Year | 1980s, 1990s... / 1991... |
| Series | Street Fighter, Castlevania, Thunder Force... |
| Players | 1 player ... 5+ players (how many at once) |

A on a line shows its values with the number of games; A ticks or unticks a
value, **Any** unticks them all, B goes back. More values in one line = any
of them; more lines = all of them. For example the platform games of Capcom
and Konami on the SNES:

```
System = SNES
Publisher = Capcom + Konami
Genre = Platform
```

Then, at the end of the lines:

| Entry | What it does |
|---|---|
| Show the N games | the games of the filter, to start them or open their details |
| Create a list with the N games... | a new list: **Name it "..."** uses a name made from the filter ("SNES - Capcom, Konami - Platform"), **Type a name on the keyboard...** your own name (USB keyboard; Enter creates, Esc or B cancel) |
| Add the N games to a list... | adds them to one of your lists (games already there stay once): different filters can go in the same list |
| Clear the filter | starts again from nothing |

A list made from a filter is a list like the others: add or remove games by
hand as above.

**The filters need the data of the games**, which come from the scraper
([SCRAPER.md](SCRAPER.md), with Texts ON). Arcade games always have at least
core, manufacturer and year (from their `.mra`); the console games only have
data once they are scraped with a ScreenScraper account.

### Rename or delete a list

At the end of every list:

* **Rename this list (keyboard)**: type the new name on a USB keyboard
  (Enter saves; Esc or B cancel).
* **Delete this list**: A deletes it; a list with games asks for A a second
  time.

### The file

The lists are in `/media/fat/frontier/mylists.ini`: a section per list, its
name in brackets, then one line per game (path, a tab, the name shown). It
can be edited on a PC; then press F5 in Frontier.

```ini
[Shoot'em ups]
@sys/MegaDrive/Thunder Force IV	Thunder Force IV
_Arcade/1943 The Battle of Midway (Euro).mra	1943 The Battle of Midway (Euro)
```
