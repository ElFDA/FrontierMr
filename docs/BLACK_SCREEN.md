# A game shows a black screen: getting the MiSTer back

A game can show nothing: a video mode the screen does not take, a core that
waits for a missing BIOS, a game that hangs. The MiSTer itself (Linux and
Main, on the ARM processor) keeps running, so it can be brought back without
touching the SD card. In order, from the easiest:

## 1. The panic combo: L+R+Select+Start

Hold **L + R + Select + Start for 2 seconds** on the joypad: Frontier comes
back. It works even when the game has hung, because it is read by Main, not by
the core. A quick press stays for the game (in many SNES games it is the
reset). They are the buttons of the joypad as mapped for the menu.
`panic_combo=0` in `frontier/frontier.ini` turns it off.

## 2. With a keyboard: Alt+F12

**Alt+F12** goes back to Frontier, as from the OSD. If the OSD does not show
(no picture at all), use the combo above.

## 3. Coin-Op starts the game again at every power on

If Coin-Op mode is on ([COINOP.md](COINOP.md)) and the last game is the one
that does not show, the MiSTer seems stuck at every power on:

* **Switch off and on again within a minute**: an automatic start counts only
  if the game stayed on for 60 seconds (`coinop_safe`), so the next power on
  stays in Frontier (*Coin-Op: last start did not complete, skipped*).
* Or, with the SD card on a PC: an empty file `frontier/coinop.off`, or
  `coinop=0` in `frontier/frontier.ini`.

## 4. Nothing answers

Switch the MiSTer off and on. With Coin-Op on, see point 3.

From another computer on the same network, SSH works even when the screen is
black: user `root`, password `1` unless you changed it.

```sh
touch /media/fat/frontier/coinop.off   # Coin-Op off
reboot
```

## 5. Frontier itself does not show

* **CRT only**, the menu shows noise: F12 (the OSD is seen on the CRT too) ->
  Scripts -> `frontier_crt`, or `direct_video=1` in the `[Menu]` section of
  `MiSTer.ini` (see the [README](../README.md#misterini)).
* Any other case: F12 -> Scripts -> `frontier_on_off` brings back the
  original core browser; or, on a PC, an empty file `/media/fat/frontier.off`.

## Usual causes

| What you see | Usually |
|---|---|
| The loading screen of the games loses the sync | `vscale_mode` other than 0 or 1 in `[MiSTer]` of `MiSTer.ini` |
| Nothing on a 15 kHz CRT | `vga_scaler=1`: the VGA gets the scaler output (31 kHz or more) |
| Nothing on an HDMI TV | `direct_video=1` in `[MiSTer]`: it is only for HDMI to VGA adapters |
| Only one game or one core | that core's own settings or a missing BIOS: check it from the original browser or the core's OSD |

Keep a copy of `MiSTer.ini` before changing it. More `MiSTer.ini` files
(e.g. `MiSTer.ini` and `MiSTer_TV.ini`) can be chosen from the OSD.
