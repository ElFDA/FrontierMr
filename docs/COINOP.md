# Coin-Op mode

As in an arcade cabinet: when the MiSTer is switched on, the last game
launched from Frontier starts again by itself.

## Turn it on

Frontier Settings -> **Coin-Op mode**, A: ON/OFF. It writes `coinop=1` (or
`0`) in `/media/fat/frontier/frontier.ini`, which can also be changed on a PC.

The game that starts is the last one launched **from Frontier**: arcade,
console, computer or handheld, also from Favorites, Recent or My Lists. A ROM
loaded from the OSD inside a core does not count.

## When it starts

* At every **power on** and every **reboot** (also the one after update_all
  or from the OSD).
* **Not** when you come back to Frontier from a game (Alt+F12 or the panic
  combo): there you stay in Frontier.

## A countdown before the start

With `coinop_delay=N` in `frontier.ini`, for N seconds the bottom of the
screen shows *Coin-Op: <game> - any button: menu*: any button cancels the
start (*Coin-Op: cancelled*) and you stay in Frontier. With `coinop_delay=0`
(the default) the game starts at once.

If `games/` is on a USB disk that is mounted late, Frontier waits for the
game up to `games_wait` seconds (`games_wait=30`, for example).

## If the game does not show or hangs the MiSTer

Coin-Op protects itself (see also [BLACK_SCREEN.md](BLACK_SCREEN.md)):

1. **Switch off and on again within a minute.** An automatic start counts
   only if the game stayed on for `coinop_safe` seconds (60 by default);
   otherwise at the next power on nothing starts, Frontier shows *Coin-Op:
   last start did not complete, skipped* and you can choose another game.
2. **L+R+Select+Start held for 2 seconds** on the joypad: back to Frontier.
3. With a countdown (`coinop_delay`), any button during it.
4. On a PC with the SD card: `coinop=0` in `frontier/frontier.ini`, or an
   empty file `frontier/coinop.off` (Coin-Op stays off whatever
   `frontier.ini` says, until you delete the file).

## The files

| File | What |
|---|---|
| `frontier/frontier.ini` | `coinop=`, `coinop_delay=`, `coinop_safe=`, `games_wait=` |
| `frontier/coinop_last.txt` | the last game: path, name, file to wait for |
| `frontier/coinop.pending` | there only during the first minute of an automatic start |
| `frontier/coinop.off` | if present, Coin-Op is off |
