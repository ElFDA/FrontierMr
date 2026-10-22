# How Frontier hooks into Main_MiSTer

Frontier replaces only the game selection screen of the menu core. It lives in
`frontier.cpp/.h` and `fe_*.cpp/.h`; the upstream files get small hooks marked
`// FRONTIER`, so a rebase on a new upstream version stays easy:

| File | Hooks |
|---|---|
| `menu.cpp` | states `MENU_FRONTIER1/2`; `MENU_NONE2` goes to Frontier instead of the core browser; Alt+F12 in a game comes back to it (the "Core" entry opens the core browser as upstream); key autorepeat |
| `video.cpp/.h` | access to the menu framebuffer pages, the CRT mode and the dual HDMI + CRT mode (functions `video_fe_*` at the end of the file) |
| `input.cpp` | the panic combo L+R+Select+Start (back to the menu from a game) |
| `fpga_io.cpp` | `menu.rbf` loaded from `frontier/bin`; the update guard before MiSTer restarts or resets (see [UPDATE_PROTECTION.md](UPDATE_PROTECTION.md)) |
| `Makefile` | FreeType headers in `lib/freetype2` |

## Interface with the menu

```cpp
enum fe_action { FE_NONE, FE_LAUNCH, FE_OPEN_OSD, FE_OPEN_BROWSER };
int  frontier_enabled();                         // 0 if /media/fat/frontier.off exists
void frontier_start();                           // entering the state (full redraw)
fe_action frontier_poll(uint32_t key, int menu); // non blocking, every tick of HandleUI
const char *frontier_selected_path();            // after FE_LAUNCH, relative to the root
const char *frontier_selected_label();
```

* `MENU_FRONTIER1` hides the OSD (`OsdMenuCtl(0)`: the input stays with the
  menu) and calls `frontier_start()`.
* `MENU_FRONTIER2` calls `frontier_poll()`:
  * `FE_LAUNCH`: sets `selPath`, `SelectedDir`, `SelectedLabel` and goes to
    `MENU_CORE_FILE_SELECTED1`, **the same code as the original browser**:
    Frontier never loads cores or games by itself. Games of the systems are
    started with an MGL written in `frontier/launch/`, like the official ones.
  * `FE_OPEN_OSD` (F12, OSD key; B/Esc on the main screen): `MENU_SYSTEM1`.
  * `FE_OPEN_BROWSER` (Tab): the original core browser.
* Folders of cores are read with the same `ScanDirectory(..., SCANO_CORES)`
  as the original browser: same filters, sorting and names.

## Drawing

Frontier draws in memory and copies to page 1 or 2 of the menu framebuffer
(the memory of the menu wallpaper); only the changed lines are copied, with a
full redraw when the wallpaper code has drawn over the pages
(`video_fe_bg_gen()`). Themes are `.ini` files read by `fe_theme.cpp` and drawn
by `fe_render.cpp` (Imlib2 for pictures, FreeType for text). Pictures and
game data are loaded by worker threads (`fe_media.cpp`); mp4 videos are decoded
on the ARM core 0 by `lib/fe_av.so` (FFmpeg, `tools/fe/fe_av/`).

## CRT and HDMI together

With the official `menu.rbf` the VGA output of the analog I/O board shows the
menu framebuffer only with `direct_video`, and HDMI and VGA share one picture.
Frontier's menu core (`tools/fe/menu_frontier.patch` on Menu_MiSTer) adds a
second framebuffer for the VGA: Main keeps HD pages for HDMI and two 640x240
(288 PAL) pages at `0x23800000` for the CRT (`status[9]` on, page in
`status[10]`, base in `status[31:16]`, horizontal position in
`status[15:12]`). Frontier draws `theme.ini` on HDMI and `theme_43.ini` on the
CRT. Main recognises Frontier's menu core by "fe" at the end of its version.
Games are not affected: their core replaces `menu.rbf`.

## Files on the SD card

`/media/fat/frontier/` holds the settings (`frontier.ini`), the table of the
systems (`systems.ini`), themes, scraper, the game data (`gamelists/`,
`media/`), the lists (`favorites.txt`, `recent.txt`, `mylists.ini`), the
caches (`.cache/`) and Frontier's firmware (`bin/`). Creating
`/media/fat/frontier.off` brings the original browser back without changing
the binary.
