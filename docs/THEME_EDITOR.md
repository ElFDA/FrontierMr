# Theme editor

The theme editor is a single web page, `theme_editor.html`, to make and change
Frontier themes on a PC: you drag the elements, change their properties and
save the `.ini` files. It needs no installation and no internet.
Italian: [THEME_EDITOR_ita.md](THEME_EDITOR_ita.md).

## Get it

* Download [theme_editor.html](https://github.com/ElFDA/FrontierMr/releases/latest/download/theme_editor.html)
  (it is a file of every release; it is **not** in the ZIP for the SD card,
  because it runs on the PC).
* Open it with Chrome or Edge (double click). They save straight into the
  theme folder; other browsers can only download the `.ini` files with
  **Download .ini**.

### As a program (Windows, macOS, Linux)

The editor is also a program which needs no browser and nothing installed
(Frontier MRTE, made from `tools/fe/theme_editor.py`); it always saves straight
into the theme folder and shows the first frame of the videos. Each release has it:

| System | File | First start |
|---|---|---|
| Windows | [FrontierThemeEditor-windows.exe](https://github.com/ElFDA/FrontierMr/releases/latest/download/FrontierThemeEditor-windows.exe) | Windows SmartScreen may say "unknown publisher": **More info → Run anyway** |
| macOS (Apple Silicon) | [FrontierThemeEditor-macos.zip](https://github.com/ElFDA/FrontierMr/releases/latest/download/FrontierThemeEditor-macos.zip) | unzip it and move the app out of Downloads; it is not signed, so the first time macOS blocks it with only "Move to Trash": open **System Settings → Privacy & Security**, scroll down and press **Open Anyway**; if it says the app is damaged: `xattr -cr FrontierThemeEditor.app` |
| Linux (x86_64) | [FrontierThemeEditor-linux.tar.gz](https://github.com/ElFDA/FrontierMr/releases/latest/download/FrontierThemeEditor-linux.tar.gz) | `tar xzf` it and start `./FrontierThemeEditor`; if it says that the Qt "xcb" plugin can not be loaded, install `libxcb-cursor0` |

On an Intel Mac, or anywhere else: `pip install PySide6`, then
`python theme_editor.py` (the file is in `tools/fe/` of the repository).

The steps below name the buttons of the web page; in the program **Open folder** and
**Save** (Ctrl+S) are in the File menu, **Import .ini** is File → **Load .ini**, the
**Variant** is chosen with **16:9 | 4:3** and the screen menu of the top bar, **Make 4:3**
is in the top bar, and **Make 4:3**, **Make detail** and **Make screensaver** are also in
the Variant menu. Help → *How to use it and shortcuts* explains the rest.

## What you need

A theme is a folder with `theme.ini` and the pictures and fonts it uses. The
easiest start is a copy of a theme from the SD card
(`/media/fat/frontier/themes/simple`, or `citypop`) on the PC, renamed, for
instance `mytheme`.

## Step by step

1. **Open folder**: choose your copy and allow the editor to change it. A folder
   without `theme.ini` starts from an empty theme (**New** does the same).
2. **Variant** chooses the file you are editing:

   | File | Screen |
   |---|---|
   | `theme.ini` / `theme_43.ini` | game list, 16:9 and 4:3 (CRT) |
   | `detail.ini` / `detail_43.ini` | detail of a game (X on the pad) |
   | `screensaver.ini` / `screensaver_43.ini` | screensaver |

   The missing ones are made from the current one: **Make 4:3** (x and widths
   × 0.75), **Make detail** (a copy of `theme.ini`) and **Make screensaver**
   (a copy of `detail.ini` without the versions). `loading.ini` /
   `loading_43.ini` (loading screen) are edited the same way; if a theme has
   none, Frontier uses the ones of the simple theme.
3. Click an element in the canvas or in the list on the right. **Drag** it to
   move it, use the handles to resize it; arrows move 1 px, Shift + arrows 10 px,
   Shift while dragging turns the grid off. **Add** a rectangle, picture, text,
   list, video or bar; **Duplicate**, **Delete** and ▲ ▼ (the order matters
   where elements overlap). Ctrl+Z undoes.
4. In the panel you change the properties: colors, font and `size` (height in
   base px, as in CSS), `src` of a picture, `if` / `ifnot` (show the element
   only if a variable is not empty / is empty), `layout=media` or `layout=text`
   (only without / with *Text layout*). Keys the editor does not know stay in
   "Other keys" and are saved as they are. **Add pictures...** copies pictures
   into the `img/` folder of the theme.
5. **Sample data** (below the panel) are the values of the `${variables}` in the
   preview: change them to see a long title, no picture, many players... The
   `${game.cpu}`, `${game.memory}`, `${game.graphics}`, `${game.sound}`,
   `${game.media}` and `${game.units}` of the systems are there too.
6. The preview helps you with **Zoom**, **grid 8**, **240p preview** (as on a
   240p CRT: lines halved and doubled) and **text layout** (the theme as with
   *Text layout* ON). **Import .ini** loads `.ini` files of another theme into
   the editor, keeping the pictures and fonts of the open folder; it asks before
   replacing and can be undone.
7. **Save to folder** writes the `.ini` files in the open folder (or
   **Download .ini** in other browsers). The files are rewritten with the keys in
   a fixed order and comments only at the top.

## Try it on the MiSTer

1. Copy the theme folder to `/media/fat/frontier/themes/` on the SD card.
2. Choose it in Frontier Settings -> Themes, or write `theme=mytheme` in
   `frontier.ini`.
3. Press F5 in Frontier to reload it. Edit, save, copy again, F5.

## Limits

* The preview is approximate and the animations (fades, scrolling, frames,
  video) are not animated.
* Fonts outside the open folder (for instance `../simple/fonts/`) show as
  sans-serif in the editor: copy them into a `fonts/` folder of your theme and
  point `font` there; it works on the MiSTer too.

## More

* [THEME_GUIDE.txt](../tools/fe/sd/frontier/THEME_GUIDE.txt) rebuilds the City
  Pop theme step by step with the editor (also on the SD card, in
  `/media/fat/frontier/`).
* The keys of the themes are described at the top of
  `themes/simple/theme.ini`.
