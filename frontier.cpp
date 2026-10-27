// Frontier: graphical game selection frontend for the menu core.
//
// Root: Favorites, Recent, My Lists, Arcade, the categories of the games by system
// (Computer, Console, Handheld, Other) and MiSTer, which browses the same
// folders as the original core browser using ScanDirectory(), so filtering,
// sorting and display names are identical. Draws a full screen
// list on the menu framebuffer page, with the theme set in
// frontier/frontier.ini (see fe_render.cpp) or with the built-in look.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include <dirent.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/wait.h>
#include <linux/input.h>

#include <string>
#include <vector>
#include <map>
#include <set>
#include <algorithm>

#include "frontier.h"
#include "fe_theme.h"
#include "fe_render.h"
#include "fe_media.h"
#include "fe_games.h"
#include "fe_alt.h"
#include "fe_group.h"
#include "fe_fav.h"
#include "fe_lists.h"
#include "fe_newest.h"
#include "fe_loading.h"
#include "fe_scrape.h"
#include "fe_update.h"
#include "file_io.h"
#include "video.h"
#include "charrom.h"
#include "cfg.h"
#include "input.h"
#include "user_io.h"
#include "fpga_io.h"

#define FE_DISABLE_FILE "frontier.off"
#define FE_LAST_FILE    "config/frontier_last.txt"
#define FE_DIR          "frontier"
#define FE_FAV_FILE     "favorites.txt"   // in FE_DIR
#define FE_RECENT_FILE  "recent.txt"      // in FE_DIR: the games played last
#define FE_MYLISTS_FILE "mylists.ini"     // in FE_DIR: the lists made by the user
// Coin-Op mode: the last game launched from Frontier starts at power on
#define FE_COINOP       "@coinop"            // settings: Coin-Op mode on/off
#define FE_THEME        "@theme"             // settings: next theme
#define FE_TEXT_LAYOUT  "@text_layout"       // settings: the text layout of the themes on/off
#define FE_CRT_OUT      "@crtout"            // settings: Frontier also on the CRT (crt=1) on/off
#define FE_SETTINGS     "@settings"          // last entry of the main screen: Coin-Op, theme, screensaver, CRT picture
#define FE_SAVER        "@saver"             // settings: seconds without keys before the screensaver
#define FE_SAVER_TIME   "@saver_time"        // settings: seconds for each game of the screensaver
#define FE_SAVER_FX     "@saver_fx"          // settings: transition between two games
#define FE_RECENT_MAX   "@recent_max"        // settings: games in "Recent"
#define FE_CRT_W        "@crt_w"             // settings: size and position of the picture on the CRT
#define FE_CRT_H        "@crt_h"
#define FE_CRT_X        "@crt_x"
#define FE_CRT_Y        "@crt_y"
#define FE_CRT_RESET    "@crt_reset"
#define FE_SET_VISIBLE  FE_SETTINGS "/visible"   // settings folder: the systems shown or hidden
#define FE_SET_SCRAPER  FE_SETTINGS "/scraper"   // settings folder: the scraper
#define FE_SET_SCR_SYS  FE_SET_SCRAPER "/systems" // the systems to scrape
#define FE_SET_THEMES   FE_SETTINGS "/themes"    // settings folder: theme and text layout
#define FE_SET_SAVER    FE_SETTINGS "/saver"     // settings folder: the screensaver
#define FE_SET_CRT      FE_SETTINGS "/crt"       // settings folder: the picture on the CRT
#define FE_HIDE         "@hide/"             // + games/ folder or _Arcade: shown or hidden
#define FE_SCR_SYS      "@scrsys/"           // + games/ folder or _Arcade: scraped or not
#define FE_SCR_ALL      "@scrall/"           // + category: all its systems scraped or not
#define FE_SCR_RUN      "@scr_run"           // start or stop the scraper
#define FE_SCR_SYSINFO  "@scr_sysinfo"       // the scraper for the data of the systems only (Wikipedia)
#define FE_SCR_LANG     "@scr_lang"
#define FE_SCR_TEXT     "@scr_text"
#define FE_SCR_MEDIA    "@scr_media/"        // + box, snap, title, marquee, fanart, video
#define FE_SCR_REDO     "@scr_redo"
#define FE_SCR_USER     "@scr_user"          // ScreenScraper account, typed on a keyboard
#define FE_SCR_PASS     "@scr_pass"
#define FE_COINOP_LAST  "coinop_last.txt"    // in FE_DIR: path, label, file to wait for
#define FE_COINOP_PEND  "coinop.pending"     // in FE_DIR: automatic start not confirmed yet
#define FE_COINOP_OFF   "coinop.off"         // in FE_DIR: Coin-Op off whatever frontier.ini says
#define FE_COINOP_BOOT  "/tmp/fe_coinop_boot" // tmpfs: gone at every power on
#define FE_PANIC_MS     2000                 // L+R+Select+Start held: back to the menu

static std::vector<fe_entry> entries;
static std::string cur_dir;      // relative to root dir, "" = root
static std::string launch_path;
static std::string launch_label;
static int sel = 0;
static int top = 0;
static int started = 0;
static int dirty = 1;
static int list_gen = 0;
static int hide_date = -1;
static int debug = 0;
static int max_fps = 30;          // animations
static uint64_t last_frame = 0;

static uint64_t now_ms()
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

// rendering
static uint32_t *back = 0;
static uint32_t *shadow = 0;
static int fb_w = 0, fb_h = 0;
static int fe_page = 0;
static int bg_gen = -1;
static int rows = 1;
static uint32_t *crt_back = 0;    // CRT pages (Frontier's menu.rbf)
static uint32_t *crt_out = 0;     // crt_back after the flicker filter (interlaced CRT)
static int crt_flicker = 0;       // crt_flicker=1: flicker filter on the CRT pages
static int crt_w = 0, crt_h = 0, crt_top = 0;
static int crt_shown = -1;        // page shown on the CRT, -1 = redraw all
// picture on the CRT: crt_width/crt_height = percent of the page, crt_hpos = pixels to
// the right, crt_vpos = lines down (frontier.ini, "Frontier Settings"); Frontier's
// menu.rbf moves the sync for crt_hpos in steps of 4 pixels (crt_hw_x), the rest is
// done by drawing the picture smaller and moved in its page
static int crt_wpct = 100, crt_hpct = 100, crt_hpos = 0, crt_vpos = 0, crt_hw_x = 0;
static uint64_t crt_save_ms = 0;  // settings changed: written in frontier.ini a while later
static int crt_guide = 0;         // a CRT setting is selected: a frame shows the edges of the picture
// game panel (images, texts): while a key is held the selection runs and the
// panel follows only when it stops for FE_SETTLE_MS
#define FE_SETTLE_MS 200
static int info_sel = -1, info_gen = -1;
static uint64_t sel_ms = 0;       // last change of the selection

// detail view (Y / Backspace on a file): info of the game and its versions
// (the file itself and, for an .mra, its _alternatives)
static int detail = 0;
static fe_entry detail_entry;              // entry of the list
static std::string detail_path;            // its path, relative to the root
static std::vector<fe_entry> versions;     // list of the detail view
static std::vector<std::string> version_paths;
static std::string detail_key;             // the game, for the favorites and frontier_last.txt
static int picking = 0;                    // "Add to list...": the list of the detail view shows My Lists
static int vsel = 0, vtop = 0, crt_vtop = 0, versions_gen = 0;
static int versions_pending = 0;           // the index of the alternatives is being built

#define COL_BG      0x0E1420
#define COL_HEADER  0x1C2A44
#define COL_SEL     0x2F5FB3
#define COL_TEXT    0xF0F0F0
#define COL_DIM     0x8CA0C0
#define COL_TITLE   0xFFC040
#define COL_DIR     0xFFD878
#define COL_SCROLL  0x3A4A66

/////////////////////////////////////////////////////////////////////////////
// folders
//
// cur_dir is a folder relative to the root ("_Arcade", "_Console", "games/NES/..."),
// "" = Frontier's root (Favorites, Recent, Arcade, the categories of the games by
// system and MiSTer), "@games/<category>" = the systems with files in games/,
// "@mister" = the root of the original browser, "@sys/<folder>" = the games of
// a games/ folder grouped by title (fe_group), "games/<folder>/..." = its real
// folders, "@fav" = all the favorites and their systems, "@fav/<system>" = the
// favorites of a system (a games/ folder, "@arcade" or "@mister"), "@recent" =
// the games played last, "@my" = the lists made by the user, "@my/<name>" = a list,
// "@lists..." = the games by their data, to make a list from them (fe_lists.h).
// In the favorites, the recent games and the lists the name of an entry is its key (fe_fav.h).

#define FE_GAMES  "@games"
#define FE_MISTER "@mister"
#define FE_SYS    "@sys/"
#define FE_FOLDERS "@folders"   // entry of a @sys list: the real folders
#define FE_MGL    "@mgl:"       // entry of the folder of a system: an MGL of the root (systems.ini launchers=)
#define FE_ARCADE "_Arcade"
#define FE_FAV    "@fav"
#define FE_RECENT "@recent"
#define FE_NEWEST "@newest"             // "#Newest" in the Arcade folder: the arcade games which are new
#define FE_NEWEST_FILE  "arcade_seen.txt" // in FE_DIR: the .mra met (fe_newest.h)
#define FE_MY     "@my"
#define FE_ADD_LIST "@addlist"  // entry of the detail view: "Add to list..."
#define FE_NEW_LIST "@newlist"  // entry of "Add to list...": a new list with the game
#define FE_DEL_LIST "@dellist"  // entry of a list: it is removed (A twice if it has games)
#define FE_REN_LIST "@renlist"  // entry of a list: a new name typed on a keyboard
#define FE_REM_LIST "@remlist"  // entry of the detail view of a game of a list: out of it
#define FE_SCR_GAME "@scrapegame" // entry of the detail view: the scraper for this game only
#define FE_TYPED_LIST "@typedlist" // entry of "@lists/new": the name typed on a keyboard
#define FE_MAKE_LIST "@makelist" // entry of the filter: a new list with its games
#define FE_CLEAR_FILTER "@clearfilter" // entry of the filter: nothing chosen
#define FE_LISTS_GAMES FE_LISTS "/games" // the games of the filter
#define FE_LISTS_ADD FE_LISTS "/add"     // the lists to add the games of the filter to
#define FE_LISTS_NEW FE_LISTS "/new"     // the name of a new list with the games of the filter

static const char *categories[][2] = {
	{ "Computer", "Computer" }, { "Console", "Console" }, { "Handheld", "Handheld" }, { "Other", "Other" }
};

static int in_mister = 0; // the real folders were opened from "MiSTer" (up goes back there)
static std::string scan_want; // entry to select when the games of the @sys folder are read
static int root_has_games = 0; // the root was loaded with the categories of games/
static std::string message;      // "Added to favorites"..., shown by the theme (${message}) for FE_MSG_MS
static uint64_t message_ms = 0;
#define FE_MSG_MS 1500
#define FE_HOLD_MS 800          // X held: favorite
static std::string theme_name;    // theme= in frontier.ini
static int coinop = 0;            // coinop=1 in frontier.ini
static int coinop_delay = 0;      // s of countdown before the automatic start (0: at once)
static int show_folders = 0;      // folders=1: "Folders" (the real folders) in the lists of the systems
static int games_wait = 0;        // games_wait: s to wait for the games disk (USB mounted late)
static int coinop_safe = 60;      // s of game after which the automatic start is confirmed
static int coinop_state = 0;      // 0 nothing, 1 waiting for the file, 2 countdown
static uint64_t coinop_t0 = 0;
static std::string coinop_path, coinop_label, coinop_need;
static uint64_t notice_until = 0; // ${message} kept until then
// screensaver (see "Screensaver" below)
static int newest_days = 30;      // newest=N in frontier.ini: days "#Newest" keeps a new arcade game (0 = no "#Newest")
static int recent_max = 50;       // recent=N in frontier.ini: games in "Recent" (0 = no "Recent")
static int text_layout = 0;       // text_layout=1 in frontier.ini: descriptions in place of the pictures
static int crt_enabled = 0;       // crt=1 in frontier.ini: Frontier also on the CRT of the VGA output
static int saver_after = 0;       // screensaver=N in frontier.ini: seconds without keys (0 = off)
static int saver_time = 30;       // screensaver_time=N: seconds for each game
static int saver_fx = 1;          // screensaver_transition=: 0 none, 1 fade, 2 slide, 3 wipe
static const char *saver_fx_names[] = { "none", "fade", "slide", "wipe" };
static int saver_fx_ms = 700;     // screensaver_transition_ms=N: length of the transition
static int saver = 0;             // 0 off, 1 looking for the first game, 2 a game is shown
static std::vector<fe_entry> saver_entries; // the game shown, for a list in screensaver.ini
static std::map<std::string, std::string> saver_vars; // its ${variables}
static int saver_gen = 0;
// transition to a new game: the picture before (fx_old, crt_fx_old) and the new
// one (back, crt_back) mixed on the hidden page, then shown, for saver_fx_ms
static int fx_req = 0;            // asked by the screensaver: 1 HDMI pages, 2 CRT pages
static int fx_hdmi = 0, fx_crt = 0; // 1 the new picture is drawn until its images are loaded, 2 running
static uint64_t fx_t0 = 0, crt_fx_t0 = 0; // waiting or running since
#define FE_FX_WAIT_MS 1500        // at most this long for the images of the new game
static std::vector<uint32_t> fx_old, crt_fx_old;
static int rescan_auto = 0;      // rescan=auto in frontier.ini: the games are read again at every start
static std::vector<std::string> rescanning; // games/ folders being read again (X held on a system)
static int rescanning_alt = 0;   // the arcade alternatives are being read again
static char jump_letter = 0;    // L/R: letter jumped to, shown by the theme (${jump}) for FE_JUMP_MS
// "Frontier Settings" > "Visible systems" and "Scraper" (frontier.ini)
static std::vector<std::string> hidden;     // hidden=: games/ folders (and _Arcade) not shown
static std::vector<std::string> scr_systems; // scrape_systems=: games/ folders (and _Arcade) to scrape
static std::string scr_lang = "en";         // scrape_lang=
static int scr_text = 1;                    // scrape_text=0: no data, only pictures and videos
static std::vector<std::string> scr_media;  // scrape_media=box,snap,...
static int scr_redo = 0;                    // scrape_redo=: 0 only what is missing, 1 the texts again, 2 everything again, 3 also the games not found lately
static const char *scr_langs[][2] = {
	{ "en", "English" }, { "it", "Italian" }, { "fr", "French" }, { "de", "German" },
	{ "es", "Spanish" }, { "pt", "Portuguese" }, { "ja", "Japanese" }
};
static const char *scr_media_names[][2] = {
	{ "box", "Box art" }, { "snap", "Screenshots" }, { "title", "Title screens" },
	{ "marquee", "Marquees and logos" }, { "fanart", "Fanart (large backgrounds)" }, { "video", "Videos" }
};
static const char *scr_redo_names[] = { "skip", "texts again", "all again", "retry not found" };
// typed on a keyboard: 1 ScreenScraper user, 2 its password, 3 a new name of a list,
// 4 the name of a new list with the games of the filter
static int editing = 0;
static std::string edit_buf;
static std::string del_armed;    // "Delete this list" pressed once: the list, until del_ms
static uint64_t del_ms = 0;
static uint64_t jump_ms = 0;
#define FE_JUMP_MS 1000

static int starts_with(const std::string &s, const char *prefix)
{
	return !s.compare(0, strlen(prefix), prefix);
}

static const char *category_label(const std::string &id)
{
	for (auto &c : categories) if (id == c[0]) return c[1];
	return id.c_str();
}

static int is_games_path(const std::string &path)
{
	return !strncasecmp(path.c_str(), "games/", 6);
}

// "@sys/NES" -> "NES"
static std::string sys_folder(const std::string &dir)
{
	return dir.substr(strlen(FE_SYS));
}

static int is_sys_path(const std::string &dir)
{
	return starts_with(dir, FE_SYS);
}

static int is_fav_path(const std::string &dir)
{
	return dir == FE_FAV || starts_with(dir, FE_FAV "/");
}

// "@my/List 1": a list of My Lists (its name can have a '/')
static int is_my_list(const std::string &dir)
{
	return starts_with(dir, FE_MY "/");
}

static int my_list_index(const std::string &dir)
{
	return is_my_list(dir) ? fe_mylists_find(dir.substr(strlen(FE_MY "/"))) : -1;
}

static int is_lists_path(const std::string &dir)
{
	return dir == FE_LISTS || starts_with(dir, FE_LISTS "/");
}

// entries which are not games nor folders: A does something (a value of the
// filter is chosen, the games go in a list...)
static int is_list_action(const std::string &name)
{
	return name == FE_DEL_LIST || name == FE_REN_LIST || name == FE_MAKE_LIST || name == FE_TYPED_LIST ||
		name == FE_CLEAR_FILTER ||
		(starts_with(name, FE_LISTS "/v/") && name.find('/', strlen(FE_LISTS "/v/")) != std::string::npos) ||
		starts_with(name, FE_LISTS_ADD "/");
}

// entries of the detail view that are not versions of the game
static int is_detail_action(const std::string &name)
{
	return name == FE_ADD_LIST || name == FE_REM_LIST || name == FE_SCR_GAME;
}

// lists whose entries are named by their key: the favorites, the recent games, My Lists,
// the games by their data
static int is_key_list(const std::string &dir)
{
	return is_fav_path(dir) || dir == FE_RECENT || dir == FE_NEWEST || is_my_list(dir) || is_lists_path(dir);
}

// folder and name of an entry as in its own list: a favorite's key
// "@sys/SNES/Super Mario World" -> "@sys/SNES", "Super Mario World"
static void entry_place(const fe_entry &e, std::string &dir, std::string &name)
{
	dir = cur_dir;
	name = e.name;
	if (!is_key_list(cur_dir) || e.dir || e.name.empty()) return;
	size_t pos = e.name.rfind('/');
	dir = (pos == std::string::npos) ? FE_MISTER : e.name.substr(0, pos);
	name = e.name.substr(pos + 1);
}

// rom launched by an entry of a @sys list (or a favorite from one)
static const fe_grom *sys_rom(const fe_entry &e)
{
	std::string dir, name;
	entry_place(e, dir, name);
	if (!is_sys_path(dir) || e.dir || name.empty()) return 0;
	const fe_gsystem *s = fe_group_get(sys_folder(dir));
	const fe_gtitle *t = fe_group_title(s, name);
	return t ? &s->roms[t->def] : 0;
}

// system of a favorite: its games/ folder, "@arcade" or "@mister"
static std::string fav_group(const std::string &key)
{
	if (is_sys_path(key) || is_games_path(key))
	{
		std::string folder = key.substr(key[0] == '@' ? strlen(FE_SYS) : 6);
		return folder.substr(0, folder.find('/'));
	}
	if (!strncasecmp(key.c_str(), FE_ARCADE "/", strlen(FE_ARCADE) + 1)) return "@arcade";
	return "@mister";
}

static std::string fav_group_label(const std::string &group)
{
	if (group == "@arcade") return "Arcade";
	if (group == "@mister") return "MiSTer";
	const fe_games_folder *f = fe_games_find(group);
	return f ? f->name : group;
}

// "@fav/SNES" -> "SNES", "@fav" -> ""
static std::string fav_dir_group(const std::string &dir)
{
	return (dir.size() > strlen(FE_FAV)) ? dir.substr(strlen(FE_FAV "/")) : std::string();
}

static int fav_count(const std::string &group)
{
	int n = 0;
	for (auto &f : fe_fav_list()) if (fav_group(f.key) == group) n++;
	return n;
}

static void add_entry(const std::string &name, const std::string &label, int dir)
{
	fe_entry e;
	e.name = name;
	e.label = label;
	e.dir = dir;
	entries.push_back(e);
}

// the launchers of a system (its configurations which start by themselves) first
static void add_launchers(const std::string &folder, size_t at)
{
	std::vector<fe_entry> list;
	for (auto &l : fe_games_launchers(folder))
	{
		fe_entry e;
		e.name = FE_MGL + l;
		size_t slash = l.rfind('/');
		e.label = l.substr(slash == std::string::npos ? 0 : slash + 1);
		if (e.label.size() > 4 && !strcasecmp(e.label.c_str() + e.label.size() - 4, ".mgl")) e.label.erase(e.label.size() - 4);
		e.dir = 0;
		list.push_back(e);
	}
	entries.insert(entries.begin() + std::min(at, entries.size()), list.begin(), list.end());
}

static int is_dir(const std::string &path)
{
	struct stat st;
	return !stat(path.c_str(), &st) && S_ISDIR(st.st_mode);
}

// entries of "Frontier Settings" which are not games
static int is_setting(const std::string &name)
{
	return name == FE_COINOP || name == FE_CRT_OUT || name == FE_THEME || name == FE_TEXT_LAYOUT || name == FE_RECENT_MAX || starts_with(name, FE_SAVER) || starts_with(name, "@crt_") ||
		starts_with(name, FE_HIDE) || starts_with(name, FE_SCR_SYS) || starts_with(name, FE_SCR_ALL) || starts_with(name, "@scr_");
}

static int is_settings_dir(const std::string &dir)
{
	return dir == FE_SETTINGS || starts_with(dir, FE_SETTINGS "/");
}

/////////////////////////////////////////////////////////////////////////////
// lists of systems in frontier.ini (hidden=, scrape_systems=): games/ folders and
// _Arcade, case insensitive

static int in_list(const std::vector<std::string> &list, const std::string &name)
{
	for (auto &s : list) if (!strcasecmp(s.c_str(), name.c_str())) return 1;
	return 0;
}

static void list_set(std::vector<std::string> &list, const std::string &name, int on)
{
	if (on && !in_list(list, name)) list.push_back(name);
	if (!on) list.erase(std::remove_if(list.begin(), list.end(), [&](const std::string &s) { return !strcasecmp(s.c_str(), name.c_str()); }), list.end());
}

static std::vector<std::string> split_list(const std::string &text)
{
	std::vector<std::string> out;
	size_t start = 0;
	while (start <= text.size())
	{
		size_t end = text.find(',', start);
		if (end == std::string::npos) end = text.size();
		std::string s = text.substr(start, end - start);
		s.erase(0, s.find_first_not_of(" \t"));
		s.erase(s.find_last_not_of(" \t") + 1);
		if (!s.empty()) out.push_back(s);
		start = end + 1;
	}
	return out;
}

static std::string join_list(const std::vector<std::string> &list)
{
	std::string out;
	for (auto &s : list) out += (out.empty() ? "" : ",") + s;
	return out;
}

static int is_hidden(const std::string &system)
{
	return in_list(hidden, system);
}

static int arcade_there()
{
	return is_dir(std::string(getRootDir()) + "/" FE_ARCADE);
}

// systems of a category (with games and core) in the list, and how many there are
static int count_in(const std::vector<std::string> &list, const std::string &cat, int &all)
{
	int n = 0;
	all = 0;
	for (auto &f : fe_games_folders())
	{
		if (f.category != cat) continue;
		all++;
		n += in_list(list, f.dir);
	}
	return n;
}

// what the last run brought: "3 updated", "nothing new", "" (an older scraper)
static std::string scrape_result(const fe_scrape_state &s)
{
	if (s.updated < 0) return "";
	return s.updated ? std::to_string(s.updated) + " updated" : std::string("nothing new");
}

// "SNES 120/840 (2/5)" while the scraper runs, or how the last run ended
static std::string scrape_progress()
{
	const fe_scrape_state &s = fe_scrape_get();
	if (!s.running)
	{
		if (s.state == "done") return scrape_result(s).empty() ? "finished" : "finished: " + scrape_result(s);
		if (s.state == "stopped") return "stopped";
		if (s.state == "error") return "error";
		return "";
	}
	std::string name = s.system;
	if (name == "arcade") name = "Arcade";
	else if (const fe_games_folder *f = fe_games_find(s.system)) name = f->name;
	std::string text;
	if (s.step == "index") text = "making the index";
	else if (s.step == "system") text = name + ": data of the system";
	else if (s.step == "check") text = name + ": checking what is missing";
	else if (s.step == "adb") text = name + ": asking ArcadeDB";
	else if (s.step == "scrape" && s.total) text = name + " " + std::to_string(s.n) + "/" + std::to_string(s.total);
	else if (!name.empty()) text = name + ": reading the games";
	else text = "starting";
	if (s.systems > 1 && s.step != "index") text += " (" + std::to_string(std::min(s.done + 1, s.systems)) + "/" + std::to_string(s.systems) + ")";
	return text;
}

// there is a 15 kHz picture: CRT pages of Frontier's menu.rbf, or the menu
// pages themselves (direct_video, crt=1)
static int crt_present()
{
	return video_fe_crt_page(0, 0, 0) || video_fe_main_crt();
}

// "5 min", "30 s", "OFF"
static std::string saver_label(int s)
{
	if (!s) return "OFF";
	if (s % 60) return std::to_string(s) + " s";
	return std::to_string(s / 60) + " min";
}

// values of the settings, on the right of their entries
static void settings_tags()
{
	char str[32];
	for (auto &e : entries)
	{
		if (e.name == FE_COINOP) e.tag = coinop ? "ON" : "OFF";
		else if (e.name == FE_THEME || e.name == FE_SET_THEMES) e.tag = theme_name;
		else if (e.name == FE_TEXT_LAYOUT) e.tag = text_layout ? "ON" : "OFF";
		else if (e.name == FE_CRT_OUT) e.tag = crt_enabled ? "ON" : "OFF";
		else if (e.name == FE_RECENT_MAX) e.tag = recent_max ? std::to_string(recent_max) : std::string("OFF");
		else if (e.name == FE_SAVER || e.name == FE_SET_SAVER) e.tag = saver_label(saver_after);
		else if (e.name == FE_SAVER_TIME) e.tag = saver_label(saver_time);
		else if (e.name == FE_SAVER_FX) e.tag = saver_fx_names[saver_fx];
		else if (e.name == FE_CRT_W || e.name == FE_CRT_H)
		{
			snprintf(str, sizeof(str), "%d%%", e.name == FE_CRT_W ? crt_wpct : crt_hpct);
			e.tag = str;
		}
		else if (e.name == FE_CRT_X || e.name == FE_CRT_Y)
		{
			snprintf(str, sizeof(str), "%+d", e.name == FE_CRT_X ? crt_hpos : crt_vpos);
			e.tag = str;
		}
		else if (starts_with(e.name, FE_HIDE)) e.tag = is_hidden(e.name.substr(strlen(FE_HIDE))) ? "HIDDEN" : "shown";
		else if (starts_with(e.name, FE_SCR_SYS)) e.tag = in_list(scr_systems, e.name.substr(strlen(FE_SCR_SYS))) ? "ON" : "OFF";
		else if (starts_with(e.name, FE_SCR_ALL))
		{
			int all, n = count_in(scr_systems, e.name.substr(strlen(FE_SCR_ALL)), all);
			e.tag = (all && n == all) ? "ON" : "OFF";
		}
		else if (starts_with(e.name, FE_SET_VISIBLE "/") || starts_with(e.name, FE_SET_SCR_SYS "/"))
		{
			int vis = starts_with(e.name, FE_SET_VISIBLE "/");
			std::string cat = e.name.substr(e.name.rfind('/') + 1);
			int all, n = count_in(vis ? hidden : scr_systems, cat, all);
			e.tag = vis ? (n ? std::to_string(n) + " hidden" : std::string()) : std::to_string(n) + "/" + std::to_string(all);
		}
		else if (e.name == FE_SET_VISIBLE || e.name == FE_SET_SCR_SYS)
		{
			int vis = e.name == FE_SET_VISIBLE;
			const std::vector<std::string> &list = vis ? hidden : scr_systems;
			int n = arcade_there() && in_list(list, FE_ARCADE);
			for (auto &f : fe_games_folders()) n += in_list(list, f.dir);
			if (vis) e.tag = n ? std::to_string(n) + " hidden" : std::string("all shown");
			else e.tag = n ? std::to_string(n) + (n == 1 ? " system" : " systems") : std::string("none");
		}
		else if (e.name == FE_SET_SCRAPER || e.name == FE_SCR_RUN)
		{
			e.tag = scrape_progress();
			if (e.name == FE_SCR_RUN) e.label = fe_scrape_get().running ? "Stop scraping" : "Start scraping";
		}
		else if (e.name == FE_SCR_LANG)
		{
			e.tag = scr_lang;
			for (auto &l : scr_langs) if (scr_lang == l[0]) e.tag = l[1];
		}
		else if (e.name == FE_SCR_TEXT) e.tag = scr_text ? "ON" : "OFF";
		else if (starts_with(e.name, FE_SCR_MEDIA)) e.tag = in_list(scr_media, e.name.substr(strlen(FE_SCR_MEDIA))) ? "ON" : "OFF";
		else if (e.name == FE_SCR_REDO) e.tag = scr_redo_names[scr_redo];
		else if (e.name == FE_SCR_USER || e.name == FE_SCR_PASS)
		{
			int pass = e.name == FE_SCR_PASS;
			if (editing == 1 + pass) e.tag = (pass ? std::string(edit_buf.size(), '*') : edit_buf) + "_";
			else
			{
				std::string v = fe_scrape_cred(pass ? "password" : "user");
				e.tag = v.empty() ? "none" : pass ? "********" : v;
			}
		}
	}
}

// the entries of a list and of a new list which can be typed on a keyboard: what is
// typed while it is
static void list_labels()
{
	for (auto &e : entries)
	{
		if (e.name == FE_REN_LIST) e.label = (editing == 3) ? "New name: " + edit_buf + "_" : std::string("Rename this list (keyboard)");
		else if (e.name == FE_TYPED_LIST) e.label = (editing == 4) ? "Name: " + edit_buf + "_" : std::string("Type a name on the keyboard...");
	}
}

static std::string lower(std::string s);

// path for ScanDirectory (it always puts the root in front): relative to the root, as Main does
// for the other disks ("../usb1/games/PSX")
static std::string scan_path(const std::string &abs)
{
	std::string root = getRootDir();
	if (abs.compare(0, root.size() + 1, root + "/") == 0) return abs.substr(root.size() + 1);
	if (abs.compare(0, 7, "/media/") == 0) return "../" + abs.substr(7);
	return "../../" + abs.substr(1);
}

static int load_dir(std::string dir, const char *select_name)
{
	// copies: the caller may pass cur_dir or a name in entries
	std::string want = select_name ? select_name : "";
	static char path[1024];
	snprintf(path, sizeof(path), "%s", (dir == FE_MISTER) ? "" : dir.c_str());

	if (dir.empty())
	{
		entries.clear();
		add_entry(FE_FAV, "Favorites", 1);
		if (recent_max) add_entry(FE_RECENT, "Recent", 1);
		add_entry(FE_MY, "My Lists", 1);
		if (arcade_there() && !is_hidden(FE_ARCADE)) add_entry(FE_ARCADE, "Arcade", 1);
		for (auto &c : categories)
		{
			for (auto &f : fe_games_folders())
			{
				if (f.category != c[0] || is_hidden(f.dir)) continue;
				add_entry(std::string(FE_GAMES "/") + c[0], c[1], 1);
				break;
			}
		}
		add_entry(FE_MISTER, "MiSTer", 1);
		add_entry(FE_SETTINGS, "Frontier Settings", 1);
		root_has_games = !fe_games_folders().empty();
		in_mister = 0;
	}
	else if (is_sys_path(dir))
	{
		std::string folder = sys_folder(dir);
		fe_group_request(folder);
		const fe_gsystem *s = fe_group_get(folder);
		// nothing with a region: only the folders (coming up from them: the list of systems)
		if (s && s->titles.empty())
		{
			const fe_games_folder *f = fe_games_find(folder);
			if (want == FE_FOLDERS) return f ? load_dir(std::string(FE_GAMES "/") + f->category, folder.c_str()) : load_dir("", 0);
			return load_dir("games/" + folder, want.empty() ? 0 : want.c_str());
		}

		entries.clear();
		add_entry("..", "..", 1);
		if (show_folders) add_entry(FE_FOLDERS, "Folders", 1);
		add_launchers(folder, entries.size());
		if (!s)
		{
			// first time: the thread of fe_group reads the folders (see frontier_poll)
			add_entry("", "Reading the games...", 0);
			scan_want = want;
		}
		else
		{
			for (auto &t : s->titles) add_entry(t.title, t.title, 0);
		}
		in_mister = 0;
	}
	else if (is_fav_path(dir))
	{
		// all the favorites (with the system on the right) after their systems, or
		// the favorites of a system; sorted by name
		std::string group = fav_dir_group(dir);
		std::vector<fe_entry> games;
		std::vector<std::string> groups;
		for (auto &f : fe_fav_list())
		{
			std::string g = fav_group(f.key);
			if (is_sys_path(f.key)) fe_group_request(g); // the roms of the titles (cache at once)
			if (!group.empty() && g != group) continue;
			if (std::find(groups.begin(), groups.end(), g) == groups.end()) groups.push_back(g);
			fe_entry e;
			e.name = f.key;
			e.label = f.label;
			e.dir = 0;
			if (group.empty()) e.tag = fav_group_label(g).substr(0, fav_group_label(g).find(" / ")); // "Mega Drive / Genesis" -> "Mega Drive"
			games.push_back(e);
		}
		std::stable_sort(games.begin(), games.end(), [](const fe_entry &a, const fe_entry &b) {
			int c = strcasecmp(a.label.c_str(), b.label.c_str());
			return c ? c < 0 : strcasecmp(a.tag.c_str(), b.tag.c_str()) < 0;
		});
		// Arcade, the systems by name, MiSTer
		std::stable_sort(groups.begin(), groups.end(), [](const std::string &a, const std::string &b) {
			int pa = (a == "@arcade") ? 0 : (a == "@mister") ? 2 : 1;
			int pb = (b == "@arcade") ? 0 : (b == "@mister") ? 2 : 1;
			return (pa != pb) ? pa < pb : strcasecmp(fav_group_label(a).c_str(), fav_group_label(b).c_str()) < 0;
		});

		entries.clear();
		add_entry("..", "..", 1);
		if (group.empty()) for (auto &g : groups) add_entry(FE_FAV "/" + g, fav_group_label(g), 1);
		for (auto &e : games) entries.push_back(e);
		if (games.empty()) add_entry("", "No favorites yet: hold X on a game", 0);
		in_mister = 0;
	}
	else if (dir == FE_RECENT)
	{
		// the games played last, the last one first, with the system on the right
		if (!recent_max) return 0;
		entries.clear();
		add_entry("..", "..", 1);
		int n = 0;
		for (auto &f : fe_recent_list())
		{
			if (n++ >= recent_max) break;
			std::string g = fav_group(f.key);
			if (is_sys_path(f.key)) fe_group_request(g); // the roms of the titles (cache at once)
			fe_entry e;
			e.name = f.key;
			e.label = f.label;
			e.dir = 0;
			e.tag = fav_group_label(g).substr(0, fav_group_label(g).find(" / "));
			entries.push_back(e);
		}
		if (entries.size() == 1) add_entry("", "Nothing played yet", 0);
		in_mister = 0;
	}
	else if (dir == FE_NEWEST)
	{
		// the arcade games which appeared lately, the newest first, with the day Frontier saw them
		if (!newest_days) return 0;
		fe_newest_scan(getRootDir(), std::string(getRootDir()) + "/" FE_DIR "/" FE_NEWEST_FILE);
		entries.clear();
		add_entry("..", "..", 1);
		for (auto &n : fe_newest_list(newest_days))
		{
			fe_entry e;
			e.name = n.key;
			e.label = n.key.substr(n.key.rfind('/') + 1);
			if (e.label.size() > 4) e.label.erase(e.label.size() - 4); // ".mra"
			e.dir = 0;
			struct tm tm;
			localtime_r(&n.seen, &tm);
			char day[16];
			strftime(day, sizeof(day), "%d.%m", &tm);
			e.tag = day;
			entries.push_back(e);
		}
		if (entries.size() == 1) add_entry("", "Nothing new yet", 0);
		in_mister = 0;
	}
	else if (dir == FE_MY)
	{
		// the lists made by the user, with their number of games
		entries.clear();
		add_entry("..", "..", 1);
		for (auto &l : fe_mylists())
		{
			add_entry(FE_MY "/" + l.name, l.name, 1);
			entries.back().tag = std::to_string(l.games.size());
		}
		if (entries.size() == 1) add_entry("", "No lists yet: X on a game, then Add to list", 0);
		add_entry(FE_LISTS, "+ New list from filter...", 1);
		in_mister = 0;
	}
	else if (is_my_list(dir))
	{
		// a list: its games by name with the system on the right, as in Favorites
		int idx = my_list_index(dir);
		if (idx < 0) return 0; // removed or renamed (F5)
		std::vector<fe_entry> games;
		for (auto &f : fe_mylists()[idx].games)
		{
			std::string g = fav_group(f.key);
			if (is_sys_path(f.key)) fe_group_request(g); // the roms of the titles (cache at once)
			fe_entry e;
			e.name = f.key;
			e.label = f.label;
			e.dir = 0;
			e.tag = fav_group_label(g).substr(0, fav_group_label(g).find(" / "));
			games.push_back(e);
		}
		std::stable_sort(games.begin(), games.end(), [](const fe_entry &a, const fe_entry &b) {
			int c = strcasecmp(a.label.c_str(), b.label.c_str());
			return c ? c < 0 : strcasecmp(a.tag.c_str(), b.tag.c_str()) < 0;
		});
		entries.clear();
		add_entry("..", "..", 1);
		for (auto &e : games) entries.push_back(e);
		if (games.empty()) add_entry("", "Empty list: add games from their detail view", 0);
		add_entry(FE_REN_LIST, "", 0);
		add_entry(FE_DEL_LIST, "Delete this list", 0);
		list_labels();
		in_mister = 0;
	}
	else if (dir == FE_LISTS_NEW)
	{
		// the name of a new list: the one made from the filter, or one typed
		entries.clear();
		add_entry("..", "..", 1);
		add_entry(FE_MAKE_LIST, "Name it \"" + fe_lists_name() + "\"", 0);
		add_entry(FE_TYPED_LIST, "", 0);
		list_labels();
		in_mister = 0;
	}
	else if (dir == FE_LISTS_ADD)
	{
		// the lists the games of the filter can be added to
		entries.clear();
		add_entry("..", "..", 1);
		for (auto &l : fe_mylists())
		{
			add_entry(FE_LISTS_ADD "/" + l.name, l.name, 0);
			entries.back().tag = std::to_string(l.games.size());
		}
		in_mister = 0;
	}
	else if (is_lists_path(dir))
	{
		// the filter: its data, then what to do with its games; its games, with
		// "Create a list" first
		std::vector<fe_entry> list;
		if (!fe_lists_entries(dir, list)) return 0;
		entries.swap(list);
		int n = fe_lists_count();
		std::string games = std::to_string(n) + (n == 1 ? " game" : " games");
		if (dir == FE_LISTS)
		{
			add_entry(FE_LISTS_GAMES, "Show the " + games, 1);
			add_entry(FE_LISTS_NEW, "Create a list with the " + games + "...", 1);
			if (!fe_mylists().empty()) add_entry(FE_LISTS_ADD, "Add the " + games + " to a list...", 1);
			if (fe_lists_has_filter()) add_entry(FE_CLEAR_FILTER, "Clear the filter", 0);
		}
		else if (dir == FE_LISTS_GAMES && n)
		{
			fe_entry e;
			e.name = FE_LISTS_NEW;
			e.label = "Create a list with these " + games + "...";
			e.dir = 1;
			entries.insert(entries.begin() + 1, e);
		}
		in_mister = 0;
	}
	else if (starts_with(dir, FE_SETTINGS "/"))
	{
		entries.clear();
		add_entry("..", "..", 1);
		if (dir == FE_SET_SCRAPER)
		{
			add_entry(FE_SCR_RUN, "Start scraping", 0);
			add_entry(FE_SCR_SYSINFO, "Get systems data only", 0);
			add_entry(FE_SET_SCR_SYS, "Systems", 1);
			add_entry(FE_SCR_LANG, "Language", 0);
			add_entry(FE_SCR_TEXT, "Texts (descriptions, genres...)", 0);
			for (auto &m : scr_media_names) add_entry(std::string(FE_SCR_MEDIA) + m[0], m[1], 0);
			add_entry(FE_SCR_REDO, "Games already scraped", 0);
			add_entry(FE_SCR_USER, "ScreenScraper user", 0);
			add_entry(FE_SCR_PASS, "ScreenScraper password", 0);
		}
		else if (dir == FE_SET_THEMES)
		{
			add_entry(FE_THEME, "Theme", 0);
			add_entry(FE_TEXT_LAYOUT, "Text layout", 0);
		}
		else if (dir == FE_SET_SAVER)
		{
			add_entry(FE_SAVER, "Start after", 0);
			add_entry(FE_SAVER_TIME, "Time per game", 0);
			add_entry(FE_SAVER_FX, "Transition", 0);
		}
		else if (dir == FE_SET_CRT)
		{
			if (!crt_present()) return 0;
			add_entry(FE_CRT_W, "Width", 0);
			add_entry(FE_CRT_H, "Height", 0);
			add_entry(FE_CRT_X, "Left/right", 0);
			add_entry(FE_CRT_Y, "Up/down", 0);
			add_entry(FE_CRT_RESET, "Reset", 0);
		}
		else if (dir == FE_SET_VISIBLE || dir == FE_SET_SCR_SYS)
		{
			// Arcade, then the categories with systems
			if (arcade_there()) add_entry((dir == FE_SET_VISIBLE ? FE_HIDE : FE_SCR_SYS) + std::string(FE_ARCADE), "Arcade", 0);
			for (auto &c : categories)
			{
				int all;
				count_in(hidden, c[0], all);
				if (all) add_entry(dir + "/" + c[0], c[1], 1);
			}
		}
		else if (starts_with(dir, FE_SET_VISIBLE "/") || starts_with(dir, FE_SET_SCR_SYS "/"))
		{
			int vis = starts_with(dir, FE_SET_VISIBLE "/");
			std::string cat = dir.substr(dir.rfind('/') + 1);
			if (!vis) add_entry(FE_SCR_ALL + cat, "All", 0);
			for (auto &f : fe_games_folders()) if (f.category == cat) add_entry((vis ? FE_HIDE : FE_SCR_SYS) + f.dir, f.name, 0);
			if (entries.size() < 2 + !vis) return 0;
		}
		else return 0;
		settings_tags();
		in_mister = 0;
	}
	else if (dir == FE_SETTINGS)
	{
		entries.clear();
		add_entry("..", "..", 1);
		add_entry(FE_SET_VISIBLE, "Visible systems", 1);
		add_entry(FE_SET_SCRAPER, "Scraper", 1);
		add_entry(FE_COINOP, "Coin-Op mode", 0);
		add_entry(FE_SET_THEMES, "Themes", 1);
		add_entry(FE_RECENT_MAX, "Recent games", 0);
		add_entry(FE_SET_SAVER, "Screensaver", 1);
		add_entry(FE_CRT_OUT, "CRT output", 0);
		if (crt_present()) add_entry(FE_SET_CRT, "CRT Geometry", 1);
		// folders first, then the single settings, each in alphabetical order
		std::stable_sort(entries.begin() + 1, entries.end(), [](const fe_entry &a, const fe_entry &b)
		{
			if (a.dir != b.dir) return a.dir > b.dir;
			return strcasecmp(a.label.c_str(), b.label.c_str()) < 0;
		});
		settings_tags();
		in_mister = 0;
	}
	else if (starts_with(dir, FE_GAMES "/"))
	{
		std::string cat = dir.substr(strlen(FE_GAMES "/"));
		entries.clear();
		add_entry("..", "..", 1);
		for (auto &f : fe_games_folders()) if (f.category == cat && !is_hidden(f.dir)) add_entry(f.dir, f.name, 1);
		in_mister = 0;
	}
	else
	{
		// games/: the same folder can be in more storages (SD card, USB disks, network
		// shares): the folders are read one after the other and joined
		std::vector<std::string> srcs;
		std::string scan_folder;
		auto scan_games = [&]()
		{
			// files of the systems which use this folder, zip files as folders;
			// romsets (Neo Geo) as in the core's browser: zip files and folders of
			// romsets.xml are games, with its names
			if (fe_games_romsets(scan_folder)) ScanDirectory(path, SCANF_INIT, "", SCANO_DIR | SCANO_NEOGEO);
			else ScanDirectory(path, SCANF_INIT, fe_games_exts(scan_folder).c_str(), SCANO_DIR);
		};
		if (is_games_path(dir))
		{
			scan_folder = dir.substr(6);
			scan_folder = scan_folder.substr(0, scan_folder.find('/'));
			srcs = fe_games_dirs(dir);
			if (!srcs.empty()) snprintf(path, sizeof(path), "%s", scan_path(srcs[0]).c_str());
			scan_games();
		}
		else
		{
			// same scan as SelectFile(.., SCANO_CORES, ..) in menu.cpp
			ScanDirectory(path, SCANF_INIT, "RBFMRAMGL", SCANO_CORES);
		}

		int count = flist_nDirEntries();
		if (!count && dir != FE_MISTER) return 0;

		// Arcade from Frontier's root, everything else from "MiSTer"
		if (dir == FE_MISTER || (!is_games_path(dir) && strncasecmp(dir.c_str(), FE_ARCADE, strlen(FE_ARCADE))))
			in_mister = 1;

		// the alternative versions are in the detail view
		int hide_alt = !in_mister && !strcasecmp(dir.c_str(), FE_ARCADE);

		entries.clear();
		if (dir == FE_MISTER)
		{
			add_entry("..", "..", 1);
		}

		// folders with only the discs of one game are games (they start the first disc)
		std::vector<fe_entry> disc_games;
		std::vector<std::string> disc_exts;
		if (is_games_path(dir))
		{
			std::string sysdir = dir.substr(6, dir.find('/', 6) == std::string::npos ? std::string::npos : dir.find('/', 6) - 6);
			if (!fe_games_romsets(sysdir)) disc_exts = fe_games_ext_list(sysdir);
		}

		std::set<std::string> seen; // names of the first storage (a name in two is listed once)
		auto add_items = [&](int n, const std::string &abs_dir, int more)
		{
		for (int i = 0; i < n; i++)
		{
			direntext_t *de = flist_DirItem(i);
			fe_entry e;
			e.name = de->de.d_name;
			e.dir = (de->de.d_type == DT_DIR);
			if (more && (e.name == ".." || seen.count(lower(e.name)))) continue;
			if (hide_alt && e.dir && !strcasecmp(e.name.c_str(), "_alternatives")) continue;
			e.label = (e.dir && de->altname[0] == '_') ? de->altname + 1 : de->altname;
			if (e.dir && !disc_exts.empty() && !(de->flags & DT_EXT_ZIP) && e.name != "..")
			{
				std::vector<std::string> discs = fe_disc_set(abs_dir + "/" + e.name, disc_exts);
				if (!discs.empty())
				{
					for (auto &f : discs) e.discs.push_back(e.name + "/" + f);
					e.name = e.discs[0];
					e.dir = 0;
					disc_games.push_back(e);
					continue;
				}
			}
			if (is_games_path(dir) && e.label == e.name && (!e.dir || (de->flags & DT_EXT_ZIP)))
			{
				// games and zip files: name without extension
				size_t dot = e.label.rfind('.');
				if (dot != std::string::npos && dot > 0) e.label.erase(dot);
			}
			size_t len = e.name.size();
			if (!e.dir && len > 4 && !strcasecmp(e.name.c_str() + len - 4, ".rbf") && strlen(de->datecode) >= 6 && strcmp(de->datecode, "------"))
			{
				char tmp[16];
				snprintf(tmp, sizeof(tmp), "%.2s.%.2s.%.2s", de->datecode, de->datecode + 2, de->datecode + 4);
				e.date = tmp;
			}
			entries.push_back(e);
		}
		};

		add_items(count, srcs.empty() ? std::string(getRootDir()) + "/" + dir : srcs[0], 0);
		for (size_t k = 1; k < srcs.size(); k++)
		{
			for (auto &e : entries) seen.insert(lower(e.name));
			for (auto &g : disc_games) seen.insert(lower(g.label)); // the folder of a game of discs
			snprintf(path, sizeof(path), "%s", scan_path(srcs[k]).c_str());
			scan_games();
			add_items(flist_nDirEntries(), srcs[k], 1);
		}
		if (srcs.size() > 1)
		{
			// the lists of the storages one after the other: folders first, by name as ScanDirectory does
			size_t first = (!entries.empty() && entries[0].name == "..") ? 1 : 0;
			std::stable_sort(entries.begin() + first, entries.end(), [](const fe_entry &a, const fe_entry &b)
			{
				if (a.dir != b.dir) return a.dir > b.dir;
				return strcasecmp(a.label.c_str(), b.label.c_str()) < 0;
			});
		}

		// the folders of discs among the games, by name
		for (auto &g : disc_games)
		{
			size_t at = entries.size();
			for (size_t i = 0; i < entries.size(); i++)
			{
				if (entries[i].dir || entries[i].name == ".." || strcasecmp(entries[i].label.c_str(), g.label.c_str()) <= 0) continue;
				at = i;
				break;
			}
			entries.insert(entries.begin() + at, g);
		}

		// the configurations of the system which start by themselves, first in its folder
		if (is_games_path(dir) && dir.find('/', 6) == std::string::npos)
			add_launchers(dir.substr(6), (!entries.empty() && entries[0].name == "..") ? 1 : 0);

		// "#Newest" first in the Arcade folder
		if (newest_days && !in_mister && !strcasecmp(dir.c_str(), FE_ARCADE))
		{
			fe_entry e;
			e.name = FE_NEWEST;
			e.label = "#Newest";
			e.dir = 1;
			entries.insert(entries.begin() + ((!entries.empty() && entries[0].name == "..") ? 1 : 0), e);
		}
	}

	cur_dir = dir;
	list_gen++;
	sel = 0;
	top = 0;
	// entering a folder: first item after ".."
	if (want.empty() && entries.size() > 1 && entries[0].name == "..") sel = 1;
	if (want.empty() && is_sys_path(dir) && (int)entries.size() > 1 + show_folders) sel = 1 + show_folders; // the first game, not "Folders"
	if (want.empty() && is_fav_path(dir))
	{
		// the first game, not the systems
		for (size_t i = 1; i < entries.size(); i++)
		{
			if (entries[i].dir) continue;
			sel = i;
			break;
		}
	}
	if (!want.empty())
	{
		for (size_t i = 0; i < entries.size(); i++)
		{
			if (!strcasecmp(entries[i].name.c_str(), want.c_str()) ||
				std::find(entries[i].discs.begin(), entries[i].discs.end(), want) != entries[i].discs.end())
			{
				sel = i;
				break;
			}
		}
	}

	dirty = 1;
	return 1;
}

// first letter of an entry for L/R: A-Z, '#' for digits and symbols, 0 for "..",
// "Folders" and the placeholder
static char entry_letter(const fe_entry &e)
{
	if (e.name == ".." || e.name == FE_FOLDERS || e.name.empty() || e.label.empty()) return 0;
	if (e.dir && is_fav_path(cur_dir)) return 0; // the systems of the favorites: only the games
	if (e.name == FE_LISTS_NEW || e.name == FE_MAKE_LIST || e.name == FE_DEL_LIST || e.name == FE_REN_LIST) return 0;
	// the values of the filter: "[x] Capcom"
	unsigned char c = (starts_with(e.name, FE_LISTS "/v/") && e.label.size() > 4 && e.label[0] == '[') ? e.label[4] : e.label[0];
	return isalpha(c) ? toupper(c) : '#';
}

// R: start of the next letter; L: start of this letter, or of the previous one
static int letter_jump(int dir)
{
	int count = entries.size();
	if (!count) return 0;
	char cur = entry_letter(entries[sel]);
	if (dir > 0)
	{
		for (int i = sel + 1; i < count; i++) if (entry_letter(entries[i]) && entry_letter(entries[i]) != cur) return i;
		for (int i = 0; i < count; i++) if (entry_letter(entries[i])) return i; // around to the first letter
		return sel;
	}

	int i = sel;
	if (cur)
	{
		while (i > 0 && entry_letter(entries[i - 1]) == cur) i--;
		if (i < sel) return i;
	}
	int j = i - 1;
	while (j >= 0 && !entry_letter(entries[j])) j--;
	if (j < 0) j = count - 1; // around to the last letter
	char l = entry_letter(entries[j]);
	if (!l) return sel;
	while (j > 0 && entry_letter(entries[j - 1]) == l) j--;
	return j;
}

static void go_up()
{
	if (cur_dir.empty()) return;

	if (is_fav_path(cur_dir))
	{
		if (cur_dir == FE_FAV) load_dir("", FE_FAV);
		else load_dir(FE_FAV, cur_dir.c_str());
		return;
	}

	if (is_my_list(cur_dir))
	{
		load_dir(FE_MY, cur_dir.c_str());
		return;
	}

	if (is_lists_path(cur_dir))
	{
		std::string select;
		std::string parent = fe_lists_parent(cur_dir, select);
		if (parent.empty()) load_dir(FE_MY, FE_LISTS);
		else if (!load_dir(parent, select.c_str())) load_dir(FE_LISTS, 0);
		return;
	}

	if (cur_dir == FE_NEWEST)
	{
		load_dir(FE_ARCADE, FE_NEWEST);
		return;
	}

	if (cur_dir == FE_MISTER || cur_dir == FE_RECENT || cur_dir == FE_MY || cur_dir == FE_SETTINGS || starts_with(cur_dir, FE_GAMES "/"))
	{
		load_dir("", cur_dir.c_str());
		return;
	}

	if (starts_with(cur_dir, FE_SETTINGS "/"))
	{
		std::string child = cur_dir;
		load_dir(cur_dir.substr(0, cur_dir.rfind('/')), child.c_str());
		return;
	}

	if (is_sys_path(cur_dir))
	{
		// back to the list of systems
		std::string folder = sys_folder(cur_dir);
		const fe_games_folder *f = fe_games_find(folder);
		if (f) load_dir(std::string(FE_GAMES "/") + f->category, folder.c_str());
		else load_dir("", 0);
		return;
	}

	size_t pos = cur_dir.rfind('/');
	std::string parent = (pos == std::string::npos) ? "" : cur_dir.substr(0, pos);
	std::string child = (pos == std::string::npos) ? cur_dir : cur_dir.substr(pos + 1);

	if (!strcasecmp(parent.c_str(), "games"))
	{
		// back to the games by title, or to the list of systems if there are none
		const fe_gsystem *s = fe_group_get(child);
		const fe_games_folder *f = fe_games_find(child);
		if (!s || !s->titles.empty()) load_dir(FE_SYS + child, FE_FOLDERS);
		else if (f) load_dir(std::string(FE_GAMES "/") + f->category, child.c_str());
		else load_dir("", 0);
		return;
	}

	if (parent.empty() && in_mister) parent = FE_MISTER;
	load_dir(parent, child.c_str());
}

static std::string full_path(const fe_entry &e)
{
	std::string dir, name;
	entry_place(e, dir, name);
	if (name.empty()) return "";
	if (name == FE_NEWEST) return name;
	if (starts_with(name, FE_MGL)) return name.substr(strlen(FE_MGL));
	if (is_sys_path(dir))
	{
		if (name == FE_FOLDERS) return "games/" + sys_folder(dir);
		const fe_grom *r = sys_rom(e);
		return r ? r->path : std::string();
	}
	// "@..." are the virtual entries of Frontier, but only in its virtual folders: a real
	// file or folder may start with @ too (games/C64/@C64 2023-4-28.zip)
	if (name[0] == '@' && (dir.empty() || dir[0] == '@')) return name;
	if (starts_with(dir, FE_GAMES "/")) return FE_SYS + name;
	return (dir.empty() || dir == FE_MISTER) ? name : dir + "/" + name;
}

// key of a game for the favorites ("@sys/<folder>/<title>" or its path), "" for
// the folders
static std::string entry_key(const fe_entry &e)
{
	if (e.dir || e.name.empty() || e.name == ".." || is_list_action(e.name)) return "";
	if (is_key_list(cur_dir)) return e.name;
	if (is_sys_path(cur_dir)) return cur_dir + "/" + e.name;
	return full_path(e);
}

// line of frontier_last.txt: the key, or "<list>\t<key>" from the favorites
// and the recent games (that list is reopened)
static std::string remember_of(const std::string &key)
{
	return is_key_list(cur_dir) ? cur_dir + "\t" + key : key;
}

// "_Console/_Extra" -> "MiSTer / Console / Extra", "games/NES/Europe" -> "Console / NES / Europe"
static std::string breadcrumb()
{
	if (cur_dir.empty()) return "";
	if (cur_dir == FE_MISTER) return "MiSTer";
	if (cur_dir == FE_SETTINGS) return "Frontier Settings";
	if (starts_with(cur_dir, FE_SETTINGS "/"))
	{
		std::string out = "Frontier Settings";
		if (starts_with(cur_dir, FE_SET_VISIBLE)) out += " / Visible systems";
		if (starts_with(cur_dir, FE_SET_SCRAPER)) out += " / Scraper";
		if (cur_dir == FE_SET_THEMES) out += " / Themes";
		if (cur_dir == FE_SET_SAVER) out += " / Screensaver";
		if (cur_dir == FE_SET_CRT) out += " / CRT Geometry";
		if (starts_with(cur_dir, FE_SET_SCR_SYS)) out += " / Systems";
		size_t pos = cur_dir.rfind('/');
		if (starts_with(cur_dir, FE_SET_VISIBLE "/") || starts_with(cur_dir, FE_SET_SCR_SYS "/")) out += std::string(" / ") + category_label(cur_dir.substr(pos + 1));
		return out;
	}
	if (cur_dir == FE_FAV) return "Favorites";
	if (cur_dir == FE_RECENT) return "Recent";
	if (cur_dir == FE_NEWEST) return "Arcade / #Newest";
	if (cur_dir == FE_MY) return "My Lists";
	if (is_my_list(cur_dir)) return "My Lists / " + cur_dir.substr(strlen(FE_MY "/"));
	if (is_lists_path(cur_dir)) return fe_lists_title(cur_dir);
	if (is_fav_path(cur_dir)) return "Favorites / " + fav_group_label(fav_dir_group(cur_dir));
	if (starts_with(cur_dir, FE_GAMES "/")) return category_label(cur_dir.substr(strlen(FE_GAMES "/")));
	if (is_sys_path(cur_dir))
	{
		const fe_games_folder *f = fe_games_find(sys_folder(cur_dir));
		return f ? std::string(category_label(f->category)) + " / " + f->name : sys_folder(cur_dir);
	}

	std::string out = in_mister ? "MiSTer" : "";
	size_t start = 0;
	int games = is_games_path(cur_dir);
	const fe_games_folder *f = 0;
	if (games)
	{
		std::string folder = cur_dir.substr(6);
		f = fe_games_find(folder.substr(0, folder.find('/')));
	}
	for (int n = 0; start <= cur_dir.size(); n++)
	{
		size_t end = cur_dir.find('/', start);
		if (end == std::string::npos) end = cur_dir.size();
		std::string part = cur_dir.substr(start, end - start);
		if (!part.empty() && part[0] == '_') part.erase(0, 1);
		if (games && n == 0) part = f ? category_label(f->category) : "Games";
		if (games && n == 1 && f) part = f->name;
		if (!out.empty()) out += " / ";
		out += part;
		start = end + 1;
	}
	return out;
}

/////////////////////////////////////////////////////////////////////////////
// drawing

static void fill_rect(int x, int y, int w, int h, uint32_t color)
{
	if (x < 0) { w += x; x = 0; }
	if (y < 0) { h += y; y = 0; }
	if (x + w > fb_w) w = fb_w - x;
	if (y + h > fb_h) h = fb_h - y;
	if (w <= 0 || h <= 0) return;

	for (int j = 0; j < h; j++)
	{
		uint32_t *p = back + (y + j) * fb_w + x;
		for (int i = 0; i < w; i++) p[i] = color;
	}
}

// returns the x after the text
static int draw_text(int x, int y, int scale, const char *str, uint32_t color, int max_x = -1)
{
	if (max_x < 0) max_x = fb_w;
	const int cw = 8 * scale;

	for (const unsigned char *s = (const unsigned char *)str; *s; s++)
	{
		unsigned char c = *s;
		if (c >= 0x80)
		{
			if ((c & 0xC0) == 0x80) continue; // utf-8 continuation byte
			c = '?';
		}

		if (x + cw > max_x)
		{
			// mark truncation
			if (x + 3 * scale <= max_x) fill_rect(x, y + 6 * scale, scale, scale, color);
			break;
		}

		for (int col = 0; col < 8; col++)
		{
			unsigned char bits = charfont[c][col];
			for (int row = 0; bits && row < 8; row++, bits >>= 1)
			{
				if (bits & 1) fill_rect(x + col * scale, y + row * scale, scale, scale, color);
			}
		}
		x += cw;
	}
	return x;
}

static int text_w(const char *str, int scale)
{
	return (int)strlen(str) * 8 * scale;
}

static void render()
{
	const int s = (fb_h >= 360) ? fb_h / 360 : 1;
	const int lh = 11 * s;
	const int mx = fb_w / 24;
	const int header_h = 3 * lh;
	const int footer_h = 2 * lh;
	const int list_y = header_h + lh / 2;

	rows = (fb_h - list_y - footer_h - lh / 2) / lh;
	if (rows < 1) rows = 1;

	int count = entries.size();
	if (sel >= count) sel = count ? count - 1 : 0;
	if (sel < top) top = sel;
	if (sel >= top + rows) top = sel - rows + 1;
	if (top > count - rows) top = count - rows;
	if (top < 0) top = 0;

	fill_rect(0, 0, fb_w, fb_h, COL_BG);

	// header: title or current folder, position on the right
	char str[128];
	snprintf(str, sizeof(str), "%d/%d", count ? sel + 1 : 0, count);
	int pos_x = fb_w - mx - text_w(str, s);

	fill_rect(0, 0, fb_w, header_h, COL_HEADER);
	std::string title = cur_dir.empty() ? std::string("MiSTer") : breadcrumb();
	int ts = (text_w(title.c_str(), 2 * s) <= pos_x - 2 * mx) ? 2 * s : s;
	draw_text(mx, (header_h - 8 * ts) / 2, ts, title.c_str(), COL_TITLE, pos_x - 8 * s);
	draw_text(pos_x, (header_h - 8 * s) / 2, s, str, COL_DIM);

	// list
	if (!count) draw_text(mx, list_y + lh, s, "No cores or games in this folder", COL_TEXT);

	int list_w = fb_w - 2 * mx - 3 * s;
	for (int i = 0; i < rows && top + i < count; i++)
	{
		const fe_entry &e = entries[top + i];
		int y = list_y + i * lh;
		if (top + i == sel) fill_rect(mx - 2 * s, y - 2 * s, list_w + 2 * s, lh, COL_SEL);

		const char *tag = 0;
		if (e.dir) tag = (e.name == "..") ? "<SU>" : !e.tag.empty() ? e.tag.c_str() : "<DIR>"; // My Lists: number of games
		else if (!e.tag.empty()) tag = e.tag.c_str();
		else if (!cfg.rbf_hide_datecode && !e.date.empty()) tag = e.date.c_str();

		int max_x = mx + list_w - 8 * s;
		if (tag)
		{
			int tx = mx + list_w - 8 * s - text_w(tag, s);
			draw_text(tx, y, s, tag, COL_DIM);
			max_x = tx - 8 * s;
		}

		if (e.dir)
		{
			// small folder mark
			fill_rect(mx, y + 2 * s, 7 * s, 5 * s, COL_DIR);
			fill_rect(mx, y + 1 * s, 3 * s, 1 * s, COL_DIR);
			draw_text(mx + 10 * s, y, s, e.label.c_str(), COL_DIR, max_x);
		}
		else
		{
			draw_text(mx + 10 * s, y, s, e.label.c_str(), COL_TEXT, max_x);
		}
	}

	// scrollbar
	if (count > rows)
	{
		int sb_h = rows * lh;
		int knob = std::max(2 * s, sb_h * rows / count);
		int pos = (sb_h - knob) * top / (count - rows);
		fill_rect(fb_w - mx + s, list_y - 2 * s, 2 * s, sb_h, COL_SCROLL);
		fill_rect(fb_w - mx + s, list_y - 2 * s + pos, 2 * s, knob, COL_DIM);
	}

	// footer
	int fy = fb_h - footer_h;
	fill_rect(0, fy, fb_w, footer_h, COL_HEADER);
	const char *help = "A/Enter: open/start  B/Esc: back  hold X/F: favorite  L/R: letter  F12/OSD: menu";
	if (text_w(help, s) > fb_w - 2 * mx) help = "A: open/start  B: back  hold X: favorite  F12: menu";
	if (now_ms() - message_ms < FE_MSG_MS) draw_text(mx, fy + (footer_h - 8 * s) / 2, s, message.c_str(), COL_TITLE);
	else draw_text(mx, fy + (footer_h - 8 * s) / 2, s, help, COL_DIM);
}

// system and key of an entry for fe_media (gamelists/<system>, media/<system>)
static void media_key(const fe_entry &e, std::string &sys, std::string &key)
{
	sys.clear();
	key.clear();
	if (e.name == "..") return;
	if (starts_with(e.name, FE_MGL))
	{
		// a launcher of the system being shown: the data of the game of the same name
		std::string folder = is_sys_path(cur_dir) ? sys_folder(cur_dir) : is_games_path(cur_dir) ? cur_dir.substr(6) : "";
		folder = folder.substr(0, folder.find('/'));
		if (folder.empty()) return;
		for (auto &c : folder) c = tolower((unsigned char)c);
		sys = folder;
		key = e.label;
		return;
	}
	std::string dir, name;
	entry_place(e, dir, name);

	if (is_lists_path(dir))
	{
		// the games by their data: a system as in the list of the systems, nothing for the other values
		std::string g = fe_lists_system(e.name);
		if (g.empty()) return;
		sys = "systems";
		key = (g[0] == '@') ? g.substr(1) : g;
		return;
	}

	if (is_fav_path(dir))
	{
		// a system of the favorites: as in the list of the systems
		if (!e.dir) return;
		std::string g = fav_dir_group(e.name);
		sys = "systems";
		key = (g[0] == '@') ? g.substr(1) : g;
		return;
	}

	if (is_sys_path(dir))
	{
		// a game by title: media of the version it launches (of the selected one in the detail view)
		std::string folder = sys_folder(dir);
		for (auto &c : folder) c = tolower((unsigned char)c);
		const fe_grom *r = sys_rom(e);
		if (!r) return;
		sys = folder;
		key = r->name;
		if (detail && vsel < (int)version_paths.size())
		{
			key = version_paths[vsel].substr(version_paths[vsel].rfind('/') + 1);
			size_t dot = key.rfind('.');
			if (dot != std::string::npos) key.erase(dot);
		}
		// without data of its own: those of the other versions (a .neo of a zip,
		// a version not scraped)
		const fe_gsystem *s = fe_group_get(sys_folder(dir));
		const fe_gtitle *t = fe_group_title(s, name);
		if (t)
			for (int i : s->groups[t->group])
				if (s->roms[i].name != key) key += "\n" + s->roms[i].name;
		return;
	}

	if (starts_with(dir, FE_GAMES "/"))
	{
		// a system: media/systems/<type>/<games folder>
		sys = "systems";
		key = e.name;
		return;
	}

	if (e.dir)
	{
		if (is_games_path(dir)) return;
		sys = "folders";
		key = e.label;
		return;
	}

	// a game in the folder of its discs: "Xenogears/Xenogears (Disc 1).chd"
	if (is_games_path(dir)) name.erase(0, name.rfind('/') + 1);
	const char *ext = strrchr(name.c_str(), '.');
	key = ext ? name.substr(0, ext - name.c_str()) : name;
	if (!ext) return;

	if (is_games_path(dir))
	{
		// a game: gamelists/<games folder>, media/<games folder>, lowercase
		std::string folder = dir.substr(6);
		folder = folder.substr(0, folder.find('/'));
		for (auto &c : folder) c = tolower((unsigned char)c);
		sys = folder;
		return;
	}

	if (!strcasecmp(ext, ".mra")) sys = "arcade";
	else if (!strcasecmp(ext, ".mgl")) sys = "mgl";
	else if (!strcasecmp(ext, ".rbf"))
	{
		// core name without the date: "NES_20240101" -> "NES"
		sys = "cores";
		size_t u = key.rfind('_');
		if (u != std::string::npos && key.size() - u == 9 && strspn(key.c_str() + u + 1, "0123456789") == 8) key.erase(u);
	}
}

// images of the theme for the root and the systems: themes/<theme>/media/systems/<key>.png|.jpg,
// key = favorites, recent, arcade, computer, console, handheld, other, mister, or the games/
// folder or the systems.ini id of a system (lowercase)
static std::map<std::string, std::string> theme_images;

static std::string lower(std::string s)
{
	for (auto &c : s) c = tolower((unsigned char)c);
	return s;
}

static void load_theme_images(const std::string &dir)
{
	static const char *exts[] = { ".png", ".jpg", ".jpeg" }; // priority if a key has more files
	std::map<std::string, int> prio;
	theme_images.clear();
	DIR *d = opendir(dir.c_str());
	if (!d) return;
	while (struct dirent *de = readdir(d))
	{
		const char *ext = strrchr(de->d_name, '.');
		if (!ext || ext == de->d_name) continue;
		for (int i = 0; i < 3; i++)
		{
			if (strcasecmp(ext, exts[i])) continue;
			std::string key = lower(std::string(de->d_name, ext - de->d_name));
			if (prio.count(key) && prio[key] <= i) break;
			prio[key] = i;
			theme_images[key] = dir + "/" + de->d_name;
			break;
		}
	}
	closedir(d);
}

static std::string theme_image(const fe_entry &e)
{
	if (theme_images.empty()) return "";

	std::vector<std::string> keys;
	if (cur_dir.empty())
	{
		if (e.name == FE_FAV) keys.push_back("favorites");
		else if (e.name == FE_RECENT) keys.push_back("recent");
		else if (e.name == FE_MY) keys.push_back("mylists");
		else if (e.name == FE_ARCADE) keys.push_back("arcade");
		else if (e.name == FE_MISTER) keys.push_back("mister");
		else if (e.name == FE_SETTINGS)
		{
			keys.push_back("settings");
			keys.push_back("mister");
		}
		else if (starts_with(e.name, FE_GAMES "/")) keys.push_back(lower(e.name.substr(strlen(FE_GAMES "/"))));
	}
	else if (starts_with(cur_dir, FE_GAMES "/") || (is_fav_path(cur_dir) && e.dir && e.name != "..") ||
		(is_lists_path(cur_dir) && !fe_lists_system(e.name).empty()))
	{
		std::string folder = is_fav_path(cur_dir) ? fav_dir_group(e.name) : is_lists_path(cur_dir) ? fe_lists_system(e.name) : e.name;
		if (folder[0] == '@') keys.push_back(folder.substr(1)); // arcade, mister
		else
		{
			keys.push_back(lower(folder));
			const fe_games_folder *f = fe_games_find(folder);
			if (f) keys.push_back(lower(f->id));
		}
	}

	for (auto &k : keys)
	{
		auto it = theme_images.find(k);
		if (it != theme_images.end()) return it->second;
	}
	return "";
}

// state and ${variables} for the theme
static void set_game_vars(fe_view &v, const fe_entry &e)
{
	v.vars["game.name"] = (e.name == "..") ? std::string("..") : e.label;
	const fe_grom *rom = sys_rom(e);
	v.vars["game.file"] = rom ? rom->path.substr(rom->path.rfind('/') + 1) : e.name;
	v.vars["game.date"] = e.date;
	v.vars["game.title"] = v.vars["game.name"];
	v.vars["game.favorite"] = fe_fav_has(entry_key(e)) ? "1" : "";

	std::string sys, key;
	media_key(e, sys, key);
	v.vars["system"] = sys;
	fe_media_select(sys, key);
	fe_media_vars(v.vars);
	v.vars["media.system"] = theme_image(e);
}

static void fill_view(fe_view &v)
{
	char str[32];
	int count = entries.size();
	v.vars["message"] = (now_ms() - message_ms < FE_MSG_MS) ? message : std::string();

	if (saver)
	{
		// the variables of the game shown, read when it was chosen (fe_media is
		// already looking for the next one)
		for (auto &kv : saver_vars) v.vars[kv.first] = kv.second;
		v.entries = &saver_entries;
		v.list_gen = saver_gen;
		v.sel = 0;
		v.top = 0;
		v.show_date = 0;
		v.time_ms = now_ms();
		v.vars["pos"] = "1/1";
		v.vars["count"] = "1";
		return;
	}

	if (detail)
	{
		int vc = versions.size();
		v.entries = &versions;
		v.list_gen = versions_gen;
		v.sel = vsel;
		v.top = vtop;
		v.show_date = !cfg.rbf_hide_datecode;
		v.time_ms = now_ms();
		std::string folder = breadcrumb();
		v.vars["title"] = folder.empty() ? std::string("MiSTer") : folder;
		v.vars["folder"] = folder;
		snprintf(str, sizeof(str), "%d/%d", vc ? vsel + 1 : 0, vc);
		v.vars["pos"] = str;
		snprintf(str, sizeof(str), "%d", vc);
		v.vars["count"] = str;
		int alts = vc - 1;
		if (!picking)
			for (auto &e : versions) alts -= is_detail_action(e.name); // not "Add to list...", "Scrape this game"
		snprintf(str, sizeof(str), "%d", alts);
		v.vars["alternatives"] = (alts > 0 && !picking) ? str : "";
		v.vars["version"] = (vsel < vc) ? versions[vsel].label : "";
		v.vars["versions.status"] = picking ? "A: add to or remove from the list, B: back" : versions_pending ? "searching for versions..." : "";
		set_game_vars(v, detail_entry);
		return;
	}

	v.entries = &entries;
	v.list_gen = list_gen;
	v.sel = sel;
	v.top = top;
	v.show_date = !cfg.rbf_hide_datecode;
	v.time_ms = now_ms();

	std::string folder = breadcrumb();
	v.vars["title"] = folder.empty() ? std::string("MiSTer") : folder;
	v.vars["folder"] = folder;
	snprintf(str, sizeof(str), "%d/%d", count ? sel + 1 : 0, count);
	v.vars["pos"] = str;
	snprintf(str, sizeof(str), "%d", count);
	v.vars["count"] = str;
	v.vars["jump"] = (jump_letter && now_ms() - jump_ms < FE_JUMP_MS) ? std::string(1, jump_letter) : std::string();

	if (info_gen != list_gen || info_sel < 0 || info_sel >= count)
	{
		info_gen = list_gen;
		info_sel = sel;
	}
	int gi = info_sel;
	if (gi < count && entries[gi].name != "..") set_game_vars(v, entries[gi]);
	else fe_media_select("", "");
}

static void crt_save();

// renderer of the screen shown on the HDMI pages (+1: on the CRT pages)
static int view_inst()
{
	return saver ? 4 : detail ? 2 : 0;
}

static void load_theme()
{
	crt_save(); // settings not written yet
	std::string root = std::string(getRootDir()) + "/" FE_DIR;
	std::map<std::string, std::string> ini = fe_read_ini(root + "/frontier.ini");
	std::string name = ini.count("theme") ? ini["theme"] : std::string("citypop_blue");
	if (name == "default") name = "simple"; // the old name of the theme
	theme_name = name;
	load_theme_images(root + "/themes/" + name + "/media/systems");
	debug = ini.count("debug") ? atoi(ini["debug"].c_str()) : 0;
	fe_render_debug(debug);
	max_fps = ini.count("fps") ? atoi(ini["fps"].c_str()) : 30;
	// video_volume=0-100: sound of the mp4 videos (0 = none)
	fe_video_volume(ini.count("video_volume") ? atoi(ini["video_volume"].c_str()) : 40);
	fe_group_regions(ini.count("regions") ? ini["regions"] : std::string());
	fe_group_exclude(ini.count("exclude_dirs") ? ini["exclude_dirs"] : std::string("Extra"));
	// rescan=manual (default): the lists of the games come from frontier/.cache, read
	// again only when asked (X held on a system, F5); rescan=auto: at every start
	rescan_auto = ini.count("rescan") && ini["rescan"] == "auto";
	fe_group_manual(!rescan_auto);
	fe_games_manual(!rescan_auto);

	// crt=1: 640x240 pages, visible also on the CRT of the VGA output
	crt_enabled = ini.count("crt") ? atoi(ini["crt"].c_str()) : 0;
	video_fe_crt(crt_enabled);
	// crt_interlace=1: with the "fi" menu.rbf the CRT pages are 640x480 interlaced (flickers
	// on the CRT tested, so off by default: 240p)
	video_fe_interlace(ini.count("crt_interlace") ? atoi(ini["crt_interlace"].c_str()) : 0);
	// crt_flicker=1: vertical filter for the interlaced pages (off by default)
	crt_flicker = ini.count("crt_flicker") ? atoi(ini["crt_flicker"].c_str()) : 0;
	// picture on the CRT: crt_width/crt_height = percent of the screen, crt_hpos=N moved
	// right by N pixels (left if negative), crt_vpos=N moved down by N lines (up if negative)
	crt_wpct = std::max(50, std::min(100, ini.count("crt_width") ? atoi(ini["crt_width"].c_str()) : 100));
	crt_hpct = std::max(50, std::min(100, ini.count("crt_height") ? atoi(ini["crt_height"].c_str()) : 100));
	crt_hpos = std::max(-64, std::min(64, ini.count("crt_hpos") ? atoi(ini["crt_hpos"].c_str()) : 0));
	crt_vpos = std::max(-32, std::min(32, ini.count("crt_vpos") ? atoi(ini["crt_vpos"].c_str()) : 0));
	crt_hw_x = video_fe_hpos(crt_hpos);
	// coinop=1: the last game starts at power on (see coinop_boot)
	coinop = ini.count("coinop") ? atoi(ini["coinop"].c_str()) : 0;
	coinop_delay = std::max(0, std::min(30, ini.count("coinop_delay") ? atoi(ini["coinop_delay"].c_str()) : 0));
	// games_wait=N: games/ on a disk mounted after MiSTer starts (USB): Frontier and
	// Coin-Op wait for it up to N seconds; 0 (default) = games on the SD card, no wait
	games_wait = std::max(0, std::min(300, ini.count("games_wait") ? atoi(ini["games_wait"].c_str()) : 0));
	fe_games_wait(games_wait);
	// merge_games=0: only /media/fat/games (the other USB disks and the network shares are not read)
	show_folders = ini.count("folders") ? atoi(ini["folders"].c_str()) != 0 : 0;
		fe_games_merge(ini.count("merge_games") ? atoi(ini["merge_games"].c_str()) != 0 : 1);
	coinop_safe = std::max(10, std::min(600, ini.count("coinop_safe") ? atoi(ini["coinop_safe"].c_str()) : 60));
	// recent=N: games in "Recent" (0 = no "Recent", the games launched aren't written)
	// newest=N: days a new arcade game stays in "#Newest" of the Arcade folder (0 = no "#Newest")
	newest_days = std::max(0, std::min(365, ini.count("newest") ? atoi(ini["newest"].c_str()) : 30));
	recent_max = std::max(0, std::min(500, ini.count("recent") ? atoi(ini["recent"].c_str()) : 50));
	// screensaver=N: random games after N seconds without keys (0 = off);
	// screensaver_time=N: seconds for each game
	saver_after = std::max(0, std::min(7200, ini.count("screensaver") ? atoi(ini["screensaver"].c_str()) : 300));
	if (saver_after && saver_after < 10) saver_after = 10;
	saver_time = std::max(5, std::min(600, ini.count("screensaver_time") ? atoi(ini["screensaver_time"].c_str()) : 30));
	// screensaver_transition=fade|slide|wipe|none between two games, screensaver_transition_ms=N long
	saver_fx = 1;
	for (int i = 0; i < 4 && ini.count("screensaver_transition"); i++) if (ini["screensaver_transition"] == saver_fx_names[i]) saver_fx = i;
	// text_layout=1: the elements of the themes with layout=text in place of those
	// with layout=media (descriptions instead of the pictures of the games)
	text_layout = ini.count("text_layout") ? atoi(ini["text_layout"].c_str()) : 0;
	fe_render_text_layout(text_layout);
	saver_fx_ms = std::max(100, std::min(3000, ini.count("screensaver_transition_ms") ? atoi(ini["screensaver_transition_ms"].c_str()) : 700));
	if (max_fps < 1) max_fps = 1;
	if (max_fps > 60) max_fps = 60;
	// hidden=NES,Atari5200,_Arcade: systems not shown (also from "Frontier Settings" >
	// "Visible systems"); the scraper of the settings: scrape_systems=, scrape_lang=,
	// scrape_text=, scrape_media=, scrape_redo=
	hidden = split_list(ini.count("hidden") ? ini["hidden"] : std::string());
	scr_systems = split_list(ini.count("scrape_systems") ? ini["scrape_systems"] : std::string());
	scr_lang = ini.count("scrape_lang") && !ini["scrape_lang"].empty() ? ini["scrape_lang"] : std::string("en");
	scr_text = ini.count("scrape_text") ? atoi(ini["scrape_text"].c_str()) : 1;
	scr_media = split_list(ini.count("scrape_media") ? ini["scrape_media"] : std::string("box,snap,title,marquee,video"));
	scr_redo = std::max(0, std::min(3, ini.count("scrape_redo") ? atoi(ini["scrape_redo"].c_str()) : 0));

	// renderers: 0/1 list, 2/3 detail view (detail.ini), 4/5 screensaver
	// (screensaver.ini), the last two from the simple theme if the theme hasn't
	// them; 1/3/5 draw the CRT pages of Frontier's menu.rbf
	for (int inst = 5; inst >= 0; inst--)
	{
		fe_render_use(inst);
		const char *file = (inst & 4) ? "screensaver" : (inst & 2) ? "detail" : "theme";
		if (name.empty() || name == "none" || ((inst & 1) && !video_fe_crt_page(0, 0, 0))) fe_render_unload();
		else if (fe_render_load(root + "/themes/" + name, file)) continue;
		else if ((inst & 6) && fe_render_load(root + "/themes/simple", file)) continue;
		else if (!(inst & 6)) printf("frontier: theme %s not found, built-in look\n", name.c_str());
	}
	fe_render_use(0);
	crt_shown = -1;
}

// where the picture goes in a 15 kHz page of w x h pixels (crt_width, crt_hpos...)
static fe_rect crt_area(int w, int h)
{
	fe_rect a;
	a.w = (w * crt_wpct + 50) / 100;
	a.h = (h * crt_hpct + 50) / 100;
	a.x = (w - a.w) / 2 + crt_hpos - crt_hw_x;
	a.y = (h - a.h) / 2 + crt_vpos;
	return a;
}

// a CRT setting is selected: frame on the edges of the picture (inside it, on
// the part in the page), its strips added to rects
static void crt_frame(uint32_t *buf, int w, int h, const fe_rect &a, std::vector<fe_rect> &rects)
{
	int x0 = std::max(0, a.x), y0 = std::max(0, a.y);
	int x1 = std::min(w, a.x + a.w), y1 = std::min(h, a.y + a.h);
	if (x1 - x0 < 8 || y1 - y0 < 4) return;
	const uint32_t col = 0xFFFF00;
	for (int x = x0; x < x1; x++) buf[y0 * w + x] = buf[(y1 - 1) * w + x] = col;
	for (int y = y0; y < y1; y++)
	{
		uint32_t *r = buf + y * w;
		r[x0] = r[x0 + 1] = r[x1 - 1] = r[x1 - 2] = col; // 2 pixels: 1 is thin at 640 per line
	}
	rects.push_back({ x0, y0, x1 - x0, 1 });
	rects.push_back({ x0, y1 - 1, x1 - x0, 1 });
	rects.push_back({ x0, y0, 2, y1 - y0 });
	rects.push_back({ x1 - 2, y0, 2, y1 - y0 });
}

// 0..256 of the transition, eased (slow at both ends)
static int fx_k(uint64_t t0)
{
	uint64_t t = now_ms() - t0;
	if (t >= (uint64_t)saver_fx_ms) return 256;
	int k = (int)(t * 256 / saver_fx_ms);
	return (k * k * (768 - 2 * k)) >> 16; // smoothstep
}

// a frame of the transition from o to n (w x h) on the page dst, k = 0..256
static void fx_frame(const uint32_t *o, const uint32_t *n, volatile uint32_t *dst, int w, int h, int k)
{
	static std::vector<uint32_t> row;
	row.resize(w);
	int fx = saver_fx;
	for (int y = 0; y < h; y++)
	{
		const uint32_t *a = o + y * w, *b = n + y * w;
		uint32_t *r = row.data();
		if (fx == 2)
		{
			// slide: the new picture comes from the right and pushes the old one out
			int off = (w * k) >> 8;
			memcpy(r, a + off, (w - off) * 4);
			memcpy(r + w - off, b, off * 4);
		}
		else if (fx == 3)
		{
			// wipe: the new picture from the left, soft edge of w/16 pixels
			int edge = std::max(1, w / 16), pos = ((w + edge) * k >> 8) - edge;
			for (int x = 0; x < w; x++)
			{
				int m = (x < pos) ? 256 : (x >= pos + edge) ? 0 : 256 - (x - pos) * 256 / edge;
				r[x] = ((((a[x] & 0xFF00FF) * (256 - m) + (b[x] & 0xFF00FF) * m) >> 8) & 0xFF00FF) |
					((((a[x] & 0x00FF00) * (256 - m) + (b[x] & 0x00FF00) * m) >> 8) & 0x00FF00);
			}
		}
		else
		{
			// fade
			for (int x = 0; x < w; x++)
				r[x] = ((((a[x] & 0xFF00FF) * (256 - k) + (b[x] & 0xFF00FF) * k) >> 8) & 0xFF00FF) |
					((((a[x] & 0x00FF00) * (256 - k) + (b[x] & 0x00FF00) * k) >> 8) & 0x00FF00);
		}
		memcpy((void *)(dst + y * w), r, w * 4);
	}
}

static void present_hdmi()
{
	int w, h;
	video_fe_page(1, &w, &h);
	if (!w || !h) return;

	int full = 0;
	if (w != fb_w || h != fb_h || !back)
	{
		free(back);
		free(shadow);
		fb_w = w;
		fb_h = h;
		back = (uint32_t *)malloc(fb_w * fb_h * 4);
		shadow = (uint32_t *)malloc(fb_w * fb_h * 4);
		if (!back || !shadow)
		{
			printf("frontier: out of memory\n");
			free(back); free(shadow);
			back = shadow = 0;
			fb_w = fb_h = 0;
			return;
		}
		full = 1;
	}

	// the menu background was redrawn (F1, video mode change...)
	if (bg_gen != video_fe_bg_gen()) full = 1;
	if (!fe_page) full = 1;

	if (fx_hdmi == 2 && !full)
	{
		// transition running: only its frames on the hidden page
		int k = fx_k(fx_t0);
		fe_page = (video_fe_cur_page() == 1) ? 2 : 1;
		volatile uint32_t *fb = video_fe_page(fe_page, 0, 0);
		if (!fb) return;
		fx_frame(fx_old.data(), back, fb, fb_w, fb_h, k);
		video_fe_show(fe_page);
		if (k >= 256)
		{
			fx_hdmi = 0;
			memcpy(shadow, back, fb_w * fb_h * 4);
		}
		return;
	}
	if (fx_hdmi == 2) fx_hdmi = 0;
	if (fx_req & 1)
	{
		// a new game: the picture shown is kept, the new one drawn in full
		fx_req &= ~1;
		if (!full && !fx_hdmi && saver_fx)
		{
			fx_old.assign(back, back + fb_w * fb_h);
			fx_hdmi = 1;
			fx_t0 = now_ms();
		}
		full = 1;
	}
	if (fx_hdmi == 1) full = 1; // drawn again until its images are there

	struct timespec t0, t1;
	if (debug) clock_gettime(CLOCK_MONOTONIC, &t0);

	static std::vector<fe_rect> rects;
	rects.clear();
	int themed = 0;
	if (fe_render_active())
	{
		fe_view v;
		fill_view(v);
		// the menu pages are the CRT picture (direct_video, crt=1): its size and position
		int main_crt = video_fe_main_crt();
		fe_rect a = crt_area(fb_w, fb_h);
		static fe_rect last_a = {};
		if (main_crt && memcmp(&a, &last_a, sizeof(a))) full = 1;
		last_a = a;
		int changed = fe_render_draw(v, back, fb_w, fb_h, full, rects, main_crt ? &a : 0);
		if (fx_hdmi == 1)
		{
			// the picture before stays on the screen while the images of the new game load
			if (fe_render_loading() && now_ms() - fx_t0 < FE_FX_WAIT_MS) return;
			fx_hdmi = 2;
			fx_t0 = now_ms();
		}
		if (main_crt && crt_guide && (changed || full)) crt_frame(back, fb_w, fb_h, a, rects);
		if (saver) ;
		else if (detail)
		{
			vsel = v.sel;
			vtop = v.top;
		}
		else
		{
			sel = v.sel;
			top = v.top;
			rows = v.rows;
		}
		themed = changed || !full;
		if (!changed && !full) return;
	}

	if (!themed) render();

	if (full)
	{
		// draw on the page which is not shown, then flip
		fe_page = (video_fe_cur_page() == 1) ? 2 : 1;
		volatile uint32_t *fb = video_fe_page(fe_page, 0, 0);
		if (!fb) return;
		if (fx_hdmi == 2) fx_frame(fx_old.data(), back, fb, fb_w, fb_h, fx_k(fx_t0));
		else memcpy((void *)fb, back, fb_w * fb_h * 4);
		memcpy(shadow, back, fb_w * fb_h * 4);
		video_fe_show(fe_page);
		bg_gen = video_fe_bg_gen();
	}
	else if (themed)
	{
		// copy only the area redrawn by the theme renderer
		volatile uint32_t *fb = video_fe_page(fe_page, 0, 0);
		if (!fb) return;
		for (auto &r : rects)
		{
			for (int y = r.y; y < r.y + r.h; y++)
			{
				memcpy((void *)(fb + y * fb_w + r.x), back + y * fb_w + r.x, r.w * 4);
			}
		}
	}
	else
	{
		// copy only the rows which changed
		volatile uint32_t *fb = video_fe_page(fe_page, 0, 0);
		if (!fb) return;
		for (int y = 0; y < fb_h; y++)
		{
			uint32_t *b = back + y * fb_w;
			uint32_t *sh = shadow + y * fb_w;
			if (memcmp(b, sh, fb_w * 4))
			{
				memcpy((void *)(fb + y * fb_w), b, fb_w * 4);
				memcpy(sh, b, fb_w * 4);
			}
		}
	}

	if (debug)
	{
		clock_gettime(CLOCK_MONOTONIC, &t1);
		int px = 0;
		for (auto &r : rects) px += r.w * r.h;
		fprintf(stderr, "frontier: %s %dx%d %s %d areas %d px %.1f ms\n", themed ? "theme" : "basic", fb_w, fb_h, full ? "full" : "part",
			(int)rects.size(), full ? fb_w * fb_h : px, (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6);
	}
}

// interlaced CRT: each row becomes the average of itself and the row below, so a
// 1-pixel line is in both fields at half brightness and does not flicker at 30 Hz
static void crt_flicker_rows(const uint32_t *src, uint32_t *dst, int w, int h, int y0, int y1)
{
	for (int y = y0; y < y1; y++)
	{
		const uint32_t *a = src + y * w;
		const uint32_t *b = src + (y + 1 < h ? y + 1 : y) * w;
		uint32_t *d = dst + y * w;
		for (int x = 0; x < w; x++) d[x] = ((a[x] & 0xFEFEFE) >> 1) + ((b[x] & 0xFEFEFE) >> 1);
	}
}

// CRT pages of Frontier's menu.rbf: drawn by renderer 1 with the theme's
// 4:3 variant, as for the HDMI pages a full redraw goes to the hidden page
static void present_crt()
{
	int w, h;
	if (!video_fe_crt_page(0, &w, &h))
	{
		crt_shown = -1;
		return;
	}

	int full = (crt_shown < 0);
	if (w != crt_w || h != crt_h || !crt_back)
	{
		free(crt_back);
		free(crt_out);
		crt_w = w;
		crt_h = h;
		crt_back = (uint32_t *)malloc(crt_w * crt_h * 4);
		crt_out = crt_flicker ? (uint32_t *)malloc(crt_w * crt_h * 4) : 0;
		if (!crt_back)
		{
			crt_w = crt_h = 0;
			return;
		}
		full = 1;
	}
	const int filter = crt_flicker && crt_out;

	if (fx_crt == 2 && !full)
	{
		// transition running (as on the HDMI pages, without the flicker filter)
		int k = fx_k(crt_fx_t0);
		int page = !video_fe_crt_cur_page();
		volatile uint32_t *fb = video_fe_crt_page(page, 0, 0);
		if (!fb) return;
		fx_frame(crt_fx_old.data(), crt_back, fb, crt_w, crt_h, k);
		video_fe_crt_show(page);
		crt_shown = page;
		if (k >= 256)
		{
			fx_crt = 0;
			if (filter) crt_shown = -1; // the last frame again, with the flicker filter
		}
		return;
	}
	if (fx_crt == 2) fx_crt = 0;
	if (fx_req & 2)
	{
		fx_req &= ~2;
		if (!full && !fx_crt && saver_fx)
		{
			crt_fx_old.assign(crt_back, crt_back + crt_w * crt_h);
			fx_crt = 1;
			crt_fx_t0 = now_ms();
		}
		full = 1;
	}
	if (fx_crt == 1) full = 1;

	fe_render_use(view_inst() + 1);
	int changed = 0;
	std::vector<fe_rect> rects;
	if (fe_render_active())
	{
		fe_view v;
		fill_view(v);
		static int saver_top = 0;
		int &t = saver ? saver_top : detail ? crt_vtop : crt_top;
		v.top = t;
		fe_rect a = crt_area(crt_w, crt_h);
		static fe_rect last_a = {};
		if (memcmp(&a, &last_a, sizeof(a))) full = 1;
		last_a = a;
		changed = fe_render_draw(v, crt_back, crt_w, crt_h, full, rects, &a);
		if (fx_crt == 1)
		{
			if (fe_render_loading() && now_ms() - crt_fx_t0 < FE_FX_WAIT_MS)
			{
				fe_render_use(0);
				return;
			}
			fx_crt = 2;
			crt_fx_t0 = now_ms();
		}
		if (crt_guide && (changed || full)) crt_frame(crt_back, crt_w, crt_h, a, rects);
		t = v.top;
	}
	else if (full) memset(crt_back, 0, crt_w * crt_h * 4); // built-in look: HDMI only
	fe_render_use(0);
	if (!changed && !full) return;

	if (full)
	{
		int page = (crt_shown < 0) ? 0 : !video_fe_crt_cur_page();
		volatile uint32_t *fb = video_fe_crt_page(page, 0, 0);
		if (!fb) return;
		if (fx_crt == 2) fx_frame(crt_fx_old.data(), crt_back, fb, crt_w, crt_h, fx_k(crt_fx_t0));
		else if (filter)
		{
			crt_flicker_rows(crt_back, crt_out, crt_w, crt_h, 0, crt_h);
			memcpy((void *)fb, crt_out, crt_w * crt_h * 4);
		}
		else memcpy((void *)fb, crt_back, crt_w * crt_h * 4);
		video_fe_crt_show(page);
		crt_shown = page;
	}
	else
	{
		volatile uint32_t *fb = video_fe_crt_page(crt_shown, 0, 0);
		if (!fb) return;
		for (auto &r : rects)
		{
			if (filter)
			{
				// a row of the output also depends on the row below: one more row above and below
				int y0 = r.y > 0 ? r.y - 1 : 0, y1 = r.y + r.h < crt_h ? r.y + r.h : crt_h;
				crt_flicker_rows(crt_back, crt_out, crt_w, crt_h, y0, y1);
				for (int y = y0; y < y1; y++) memcpy((void *)(fb + y * crt_w), crt_out + y * crt_w, crt_w * 4);
				continue;
			}
			for (int y = r.y; y < r.y + r.h; y++)
			{
				memcpy((void *)(fb + y * crt_w + r.x), crt_back + y * crt_w + r.x, r.w * 4);
			}
		}
	}
}

static void present()
{
	fe_render_use(view_inst());
	present_hdmi();
	fe_render_use(0);
	present_crt();
}

static int animating()
{
	int a = 0;
	for (int inst = view_inst(); inst <= view_inst() + 1; inst++)
	{
		fe_render_use(inst);
		a |= fe_render_animating();
	}
	fe_render_use(0);
	return a;
}

/////////////////////////////////////////////////////////////////////////////
// Coin-Op mode: at power on the last game launched from Frontier starts
// again after a countdown (any key: Frontier stays). Against a game which
// doesn't show or hangs the MiSTer: the start is confirmed only after coinop_safe
// seconds of game, otherwise at the next power on nothing starts; L+R+Select+Start
// held in a game goes back to the menu (frontier_panic_*).

static std::string fe_file(const char *name)
{
	return std::string(getRootDir()) + "/" FE_DIR "/" + name;
}

static int file_there(const std::string &path)
{
	struct stat st;
	return !stat(path.c_str(), &st);
}

// tmp + rename + fsync: a power off doesn't leave half a file
static void write_file(const std::string &path, const std::string &text)
{
	std::string tmp = path + ".tmp";
	FILE *fp = fopen(tmp.c_str(), "w");
	if (!fp) return;
	fputs(text.c_str(), fp);
	fflush(fp);
	fsync(fileno(fp));
	fclose(fp);
	rename(tmp.c_str(), path.c_str());
	sync();
}

// ${message} for ms milliseconds
static void notice(const std::string &text, int ms)
{
	message = text;
	message_ms = now_ms();
	notice_until = now_ms() + ms;
	dirty = 1;
}

// launched game (launch_path, launch_label); path = file chosen in Frontier
static void coinop_save(const std::string &path)
{
	// file which must be there before the start: the game (games/ can be on a USB
	// disk mounted late), the roms of the arcade games
	std::string need;
	size_t len = launch_path.size();
	if (is_games_path(path)) need = path;
	else if (len > 4 && !strcasecmp(launch_path.c_str() + len - 4, ".mra") && is_dir(std::string(getRootDir()) + "/games/mame")) need = "games/mame";
	write_file(fe_file(FE_COINOP_LAST), launch_path + "\n" + launch_label + "\n" + need + "\n");
}

// at the first start of Frontier after power on
static void coinop_boot()
{
	if (file_there(FE_COINOP_BOOT)) return;
	write_file(FE_COINOP_BOOT, "1\n");

	if (file_there(fe_file(FE_COINOP_PEND)))
	{
		// the last automatic start didn't last coinop_safe seconds: power off during
		// the game, a game which doesn't show or which hangs. No start this time.
		unlink(fe_file(FE_COINOP_PEND).c_str());
		sync();
		printf("frontier: coin-op: last start not confirmed, skipped\n");
		if (coinop) notice("Coin-Op: last start did not complete, skipped", 8000);
		return;
	}
	if (!coinop || file_there(fe_file(FE_COINOP_OFF))) return;

	FILE *fp = fopen(fe_file(FE_COINOP_LAST).c_str(), "r");
	if (!fp) return;
	std::string l[3];
	char buf[1024];
	for (int i = 0; i < 3 && fgets(buf, sizeof(buf), fp); i++)
	{
		buf[strcspn(buf, "\r\n")] = 0;
		l[i] = buf;
	}
	fclose(fp);
	if (l[0].empty()) return;

	coinop_path = l[0];
	if (starts_with(coinop_path, "frontend/")) coinop_path = FE_DIR + coinop_path.substr(8); // saved before the name Frontier
	coinop_label = l[1].empty() ? l[0] : l[1];
	coinop_need = l[2];
	coinop_state = 1;
	coinop_t0 = now_ms();
	printf("frontier: coin-op: %s\n", coinop_path.c_str());
}

// the start is confirmed (the pending file removed) after coinop_safe seconds by a
// process of its own: MiSTer is replaced by a new one when the core is loaded
static void coinop_pending()
{
	std::string pend = fe_file(FE_COINOP_PEND);
	write_file(pend, coinop_path + "\n");

	pid_t pid = fork();
	if (pid == 0)
	{
		setsid();
		if (fork() == 0)
		{
			for (int fd = 3; fd < 1024; fd++) close(fd);
			char cmd[1024];
			snprintf(cmd, sizeof(cmd), "sleep %d; rm -f '%s'; sync", coinop_safe, pend.c_str());
			execl("/bin/sh", "sh", "-c", cmd, (char *)0);
		}
		_exit(0);
	}
	if (pid > 0) waitpid(pid, 0, 0);
}

// countdown of the automatic start; key = key of this poll (any key: cancelled)
static fe_action coinop_poll(uint32_t &key, int &menu)
{
	if (!coinop_state) return FE_NONE;
	if ((key && !(key & UPSTROKE)) || menu)
	{
		coinop_state = 0;
		key = 0;
		menu = 0;
		printf("frontier: coin-op: cancelled\n");
		notice("Coin-Op: cancelled", 3000);
		return FE_NONE;
	}

	if (coinop_state == 1)
	{
		if (coinop_need.empty() || file_there(std::string(getRootDir()) + "/" + coinop_need))
		{
			coinop_state = 2;
			coinop_t0 = now_ms();
		}
		else if (now_ms() - coinop_t0 >= (uint64_t)games_wait * 1000)
		{
			coinop_state = 0;
			printf("frontier: coin-op: %s not found\n", coinop_need.c_str());
			notice("Coin-Op: game not found, skipped", 8000);
			return FE_NONE;
		}
		else
		{
			notice("Coin-Op: waiting for the games disk...", 1000);
			return FE_NONE;
		}
	}

	if (now_ms() - coinop_t0 < (uint64_t)coinop_delay * 1000)
	{
		std::string text = "Coin-Op: " + coinop_label + " - any button: menu";
		if (message != text) notice(text, 1000);
		else notice_until = now_ms() + 1000;
		return FE_NONE;
	}

	coinop_state = 0;
	coinop_pending();
	launch_path = coinop_path;
	launch_label = coinop_label;
	printf("frontier: coin-op: launch %s\n", launch_path.c_str());
	return FE_LAUNCH;
}

static void coinop_toggle()
{
	coinop = !coinop;
	fe_write_ini_key(std::string(getRootDir()) + "/" FE_DIR "/frontier.ini", "coinop", coinop ? "1" : "0");
	sync();
	settings_tags();
	list_gen++;
	if (coinop && file_there(fe_file(FE_COINOP_OFF))) notice("Coin-Op ON, but frontier/" FE_COINOP_OFF " is there", 4000);
	else notice(coinop ? "Coin-Op ON: last game at power on" : "Coin-Op OFF", 3000);
	printf("frontier: coin-op %s\n", coinop ? "on" : "off");
}

// "Frontier Settings" > "Theme": the next (step 1) or previous (-1) folder of
// frontier/themes with a theme.ini, in name order; written in frontier.ini and
// loaded at once
static void theme_next(int step)
{
	std::string dir = std::string(getRootDir()) + "/" FE_DIR "/themes";
	std::vector<std::string> names;
	DIR *d = opendir(dir.c_str());
	if (d)
	{
		struct dirent *de;
		while ((de = readdir(d)))
		{
			if (de->d_name[0] == '.') continue;
			if (file_there(dir + "/" + de->d_name + "/theme.ini")) names.push_back(de->d_name);
		}
		closedir(d);
	}
	if (names.empty()) return;
	std::sort(names.begin(), names.end());
	std::string next;
	if (step > 0)
	{
		auto it = std::upper_bound(names.begin(), names.end(), theme_name);
		next = (it == names.end()) ? names[0] : *it;
	}
	else
	{
		auto it = std::lower_bound(names.begin(), names.end(), theme_name);
		next = (it == names.begin()) ? names.back() : *(it - 1);
	}

	fe_write_ini_key(std::string(getRootDir()) + "/" FE_DIR "/frontier.ini", "theme", next);
	sync();
	load_theme();
	if (!load_dir(cur_dir, FE_THEME)) load_dir("", 0);
	fe_page = 0;
	crt_shown = -1;
	dirty = 1;
	notice("Theme: " + next, 2000);
	printf("frontier: theme %s\n", next.c_str());
}

// the CRT settings, written in frontier.ini a while after the last change (Left/Right
// held change them every 50 ms) and before the theme is read again
static void crt_save()
{
	if (!crt_save_ms) return;
	crt_save_ms = 0;
	std::string ini = std::string(getRootDir()) + "/" FE_DIR "/frontier.ini";
	fe_write_ini_key(ini, "crt_width", std::to_string(crt_wpct));
	fe_write_ini_key(ini, "crt_height", std::to_string(crt_hpct));
	fe_write_ini_key(ini, "crt_hpos", std::to_string(crt_hpos));
	fe_write_ini_key(ini, "crt_vpos", std::to_string(crt_vpos));
	sync();
	printf("frontier: crt picture %d%% x %d%%, %+d %+d\n", crt_wpct, crt_hpct, crt_hpos, crt_vpos);
}

// the next (step 1) or previous (-1) value of a list, around; a value not in
// the list (written by hand in frontier.ini) goes to the next one
static int next_value(const int *values, int n, int cur, int step)
{
	int i = 0;
	while (i < n && values[i] < cur) i++;
	if (step < 0) i = (i > 0) ? i - 1 : n - 1;
	else if (i < n && values[i] == cur) i = (i + 1) % n;
	else if (i == n) i = 0;
	return values[i];
}

// the screensaver entries of the settings: time without keys (OFF after the
// longest one), time per game, transition; written in frontier.ini
static void saver_setting(const std::string &name, int step)
{
	std::string ini = std::string(getRootDir()) + "/" FE_DIR "/frontier.ini";
	if (name == FE_SAVER)
	{
		static const int times[] = { 0, 30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600 };
		saver_after = next_value(times, sizeof(times) / sizeof(times[0]), saver_after, step);
		fe_write_ini_key(ini, "screensaver", std::to_string(saver_after));
		notice(saver_after ? "Screensaver after " + saver_label(saver_after) + " without keys" : std::string("Screensaver OFF"), 2000);
	}
	else if (name == FE_SAVER_TIME)
	{
		static const int times[] = { 10, 15, 20, 30, 45, 60, 90, 120, 180, 300 };
		saver_time = next_value(times, sizeof(times) / sizeof(times[0]), saver_time, step);
		fe_write_ini_key(ini, "screensaver_time", std::to_string(saver_time));
		notice("Screensaver: a new game every " + saver_label(saver_time), 2000);
	}
	else
	{
		saver_fx = (saver_fx + (step < 0 ? 3 : 1)) % 4;
		fe_write_ini_key(ini, "screensaver_transition", saver_fx_names[saver_fx]);
		notice(std::string("Screensaver transition: ") + saver_fx_names[saver_fx], 2000);
	}
	sync();
	settings_tags();
	list_gen++;
	dirty = 1;
	printf("frontier: screensaver %d s, %d s per game, %s\n", saver_after, saver_time, saver_fx_names[saver_fx]);
}

// "Frontier Settings" > "Themes" > "Text layout": on/off, written in frontier.ini,
// the theme loaded again
static void text_layout_toggle()
{
	fe_write_ini_key(std::string(getRootDir()) + "/" FE_DIR "/frontier.ini", "text_layout", text_layout ? "0" : "1");
	sync();
	load_theme();
	if (!load_dir(cur_dir, FE_TEXT_LAYOUT)) load_dir("", 0);
	fe_page = 0;
	crt_shown = -1;
	dirty = 1;
	notice(text_layout ? "Text layout: ON" : "Text layout: OFF", 2000);
	printf("frontier: text layout %s\n", text_layout ? "on" : "off");
}

// "Frontier Settings" > "CRT output": crt=1/0 in frontier.ini, applied at once
// (also Scripts/frontier_crt, for a CRT alone: there the OSD is seen, Frontier not)
static void crt_out_toggle()
{
	fe_write_ini_key(std::string(getRootDir()) + "/" FE_DIR "/frontier.ini", "crt", crt_enabled ? "0" : "1");
	sync();
	load_theme();
	if (!load_dir(cur_dir, FE_CRT_OUT)) load_dir("", 0);
	fe_page = 0;
	crt_shown = -1;
	dirty = 1;
	notice(crt_enabled ? "CRT output: ON" : "CRT output: OFF", 2000);
	printf("frontier: crt output %s\n", crt_enabled ? "on" : "off");
}

// "Frontier Settings" > "Recent games": how many games "Recent" shows (OFF after
// the most), written in frontier.ini
static void recent_setting(int step)
{
	static const int counts[] = { 0, 10, 20, 30, 50, 100, 200 };
	recent_max = next_value(counts, sizeof(counts) / sizeof(counts[0]), recent_max, step);
	fe_write_ini_key(std::string(getRootDir()) + "/" FE_DIR "/frontier.ini", "recent", std::to_string(recent_max));
	sync();
	settings_tags();
	list_gen++;
	dirty = 1;
	notice(recent_max ? "Recent: the last " + std::to_string(recent_max) + " games" : std::string("Recent OFF"), 2000);
	printf("frontier: recent %d\n", recent_max);
}

/////////////////////////////////////////////////////////////////////////////
// "Visible systems" and "Scraper" of the settings

static void ini_key(const char *key, const std::string &value)
{
	fe_write_ini_key(std::string(getRootDir()) + "/" FE_DIR "/frontier.ini", key, value);
	sync();
}

static std::string system_label(const std::string &system)
{
	if (system == FE_ARCADE) return "Arcade";
	const fe_games_folder *f = fe_games_find(system);
	return f ? f->name : system;
}

// the scraper with the choices of the settings, in the background; sysinfo: only the
// data of the systems (Wikipedia: description, maker, year, hardware), in a few minutes
// what to download, from Frontier Settings -> Scraper; 0 (and a message) if nothing
static int scrape_content(std::vector<std::string> &args)
{
	if (!scr_text && scr_media.empty())
	{
		notice("Scraper: nothing to download (texts and media OFF)", 3000);
		return 0;
	}
	args.push_back("--lang");
	args.push_back(scr_lang);
	if (!scr_text) args.push_back("--no-text");
	args.push_back("--media");
	args.push_back(scr_media.empty() ? std::string("none") : join_list(scr_media));
	return 1;
}

// the system of a game for the scraper (--arcade or --system <folder>) and its names
// (the file names Frontier looks for its pictures with); 0 if it has none
static int scrape_target(const fe_entry &e, std::vector<std::string> &args)
{
	std::string sys, key;
	media_key(e, sys, key);
	if (key.empty()) return 0;
	if (sys == "arcade")
	{
		if (!arcade_there()) return 0;
		args.push_back("--arcade");
	}
	else
	{
		const fe_games_folder *f = 0;
		for (auto &g : fe_games_folders())
			if (!strcasecmp(g.dir.c_str(), sys.c_str())) f = &g;
		if (!f) return 0;
		args.push_back("--system");
		args.push_back(f->dir);
	}
	size_t a = 0;
	while (a <= key.size())
	{
		size_t b = key.find('\n', a);
		if (b == std::string::npos) b = key.size();
		if (b > a)
		{
			args.push_back("--game");
			args.push_back(key.substr(a, b - a));
		}
		a = b + 1;
	}
	return 1;
}

// "Scrape this game" in the detail view: its data and pictures again, with the
// content chosen in Frontier Settings -> Scraper
static void scrape_game()
{
	if (fe_scrape_get().running)
	{
		notice("Scraper: already running (Stop scraping first)", 3000);
		return;
	}
	std::vector<std::string> args;
	if (!scrape_target(detail_entry, args) || !scrape_content(args)) return;
	if (!fe_scrape_start(args))
	{
		notice("Scraper: it can not start (python3, frontier/scraper)", 4000);
		return;
	}
	notice("Scraping " + detail_entry.label + "...", 3000);
}

static void scrape_start(int sysinfo = 0)
{
	std::vector<std::string> args;
	int systems = 0;
	if (fe_scrape_get().running)
	{
		notice("Scraper: already running (Stop scraping first)", 3000);
		return;
	}
	if (sysinfo) args.push_back("--systems-info");
	if (!sysinfo && arcade_there() && in_list(scr_systems, FE_ARCADE))
	{
		args.push_back("--arcade");
		systems++;
	}
	for (auto &f : fe_games_folders())
	{
		if (!in_list(scr_systems, f.dir)) continue;
		args.push_back("--system");
		args.push_back(f.dir);
		systems++;
	}
	if (!systems)
	{
		notice("Scraper: choose the systems first (Systems)", 3000);
		return;
	}
	if (!sysinfo && !scrape_content(args)) return;
	if (scr_redo == 1) args.push_back("--refresh-data");
	if (scr_redo == 2) args.push_back("--force");
	if (scr_redo == 3) args.push_back("--retry-missing");

	if (!fe_scrape_start(args))
	{
		notice("Scraper: it can not start (python3, frontier/scraper)", 4000);
		return;
	}
	if (sysinfo) notice("Scraper started: data of " + std::to_string(systems) + (systems == 1 ? " system" : " systems") + " (Wikipedia)", 3000);
	else if (fe_scrape_cred("user").empty() || fe_scrape_cred("password").empty())
		notice("Scraper started, no ScreenScraper account: ArcadeDB and libretro only", 4000);
	else notice("Scraper started: " + std::to_string(systems) + (systems == 1 ? " system" : " systems"), 3000);
}

// a key of a keyboard -> character (US layout), 0 if none
static char key_char(uint32_t key, int shift)
{
	static const char *low = "\0\0" "1234567890-=\0\0" "qwertyuiop[]\0\0" "asdfghjkl;'`\0\\" "zxcvbnm,./";
	static const char *up  = "\0\0" "!@#$%^&*()_+\0\0" "QWERTYUIOP{}\0\0" "ASDFGHJKL:\"~\0|" "ZXCVBNM<>?";
	if (key == KEY_SPACE) return ' ';
	if (key >= KEY_1 && key <= KEY_SLASH) return (shift ? up : low)[key];
	switch (key)
	{
	case KEY_KP0: return '0';
	case KEY_KP1: return '1';
	case KEY_KP2: return '2';
	case KEY_KP3: return '3';
	case KEY_KP4: return '4';
	case KEY_KP5: return '5';
	case KEY_KP6: return '6';
	case KEY_KP7: return '7';
	case KEY_KP8: return '8';
	case KEY_KP9: return '9';
	case KEY_KPDOT: return '.';
	case KEY_KPMINUS: return '-';
	case KEY_KPPLUS: return '+';
	}
	return 0;
}

// the games of the filter in a new list named name (list < 0) or added to a list;
// then the filter is empty again and the list is shown
static void filter_to_list(const std::string &name, int list)
{
	std::vector<std::pair<std::string, std::string>> found;
	fe_lists_games(found);
	std::vector<fe_fav> games;
	for (auto &g : found) games.push_back({ g.first, g.second });
	int made = list < 0, added = games.size();
	if (made) list = fe_mylists_add(name, games);
	else added = fe_mylists_append(list, games);
	if (list < 0) return;
	const std::string n = fe_mylists()[list].name;
	printf("frontier: list %s, %d games added\n", n.c_str(), added);
	notice(made ? "New list: " + n : n + ": " + std::to_string(added) + " games added", 2500);
	fe_lists_clear();
	load_dir(FE_MY "/" + n, 0);
}

static std::string trim(const std::string &s)
{
	size_t a = s.find_first_not_of(' '), b = s.find_last_not_of(' ');
	return (a == std::string::npos) ? std::string() : s.substr(a, b - a + 1);
}

// what was typed on a keyboard: Enter saves it (the ScreenScraper user or password
// in scraper.ini, the name of a list), Esc (B) gives up
static void edit_end(int save)
{
	int mode = editing;
	std::string buf = edit_buf;
	editing = 0;
	edit_buf.clear();
	if (save && mode <= 2)
	{
		const char *key = (mode == 2) ? "password" : "user";
		if (fe_scrape_set_cred(key, buf)) notice(std::string("ScreenScraper ") + key + (buf.empty() ? " removed" : " saved"), 2000);
		else notice("scraper.ini can not be written", 3000);
	}
	else if (save && mode == 3)
	{
		std::string name = trim(buf);
		int idx = my_list_index(cur_dir);
		if (idx < 0) return;
		if (name.empty() || name == fe_mylists()[idx].name) notice("Name not changed", 1500);
		else if (!fe_mylists_rename(idx, name)) notice("There is a list named " + name + " already", 3000);
		else
		{
			notice("List renamed: " + name, 2000);
			load_dir(FE_MY "/" + name, FE_REN_LIST);
			return;
		}
	}
	else if (save && mode == 4)
	{
		std::string name = trim(buf);
		if (!name.empty())
		{
			filter_to_list(name, -1);
			return;
		}
		notice("No name typed", 1500);
	}
	settings_tags();
	list_labels();
	list_gen++;
	dirty = 1;
}

// typing starts on an entry: what is there (the user, the name of the list) can be changed
static void edit_start(int mode, const std::string &text)
{
	editing = mode;
	edit_buf = text;
	notice("Type on the keyboard - Enter: save, Esc or B: cancel", 4000);
	settings_tags();
	list_labels();
	list_gen++;
	dirty = 1;
}

// a key while typing; 1 if it was used
static int edit_key(uint32_t key)
{
	if (!key || (key & UPSTROKE)) return 1;
	if (key == KEY_ENTER || key == KEY_KPENTER) edit_end(1);
	else if (key == KEY_BACKSPACE)
	{
		if (!edit_buf.empty()) edit_buf.pop_back();
	}
	else if (char c = key_char(key, get_key_mod() & (LSHIFT | RSHIFT)))
	{
		if (edit_buf.size() < 64) edit_buf += c;
	}
	else return 1;
	settings_tags();
	list_labels();
	list_gen++;
	dirty = 1;
	return 1;
}

// the entries of "Visible systems" and "Scraper"; 1 if name is one of them
static int scrape_setting(const std::string &name, int step)
{
	if (starts_with(name, FE_HIDE))
	{
		std::string system = name.substr(strlen(FE_HIDE));
		int hide = !is_hidden(system);
		list_set(hidden, system, hide);
		ini_key("hidden", join_list(hidden));
		notice(system_label(system) + (hide ? " hidden" : " shown"), 1500);
	}
	else if (starts_with(name, FE_SCR_SYS))
	{
		std::string system = name.substr(strlen(FE_SCR_SYS));
		list_set(scr_systems, system, !in_list(scr_systems, system));
		ini_key("scrape_systems", join_list(scr_systems));
	}
	else if (starts_with(name, FE_SCR_ALL))
	{
		std::string cat = name.substr(strlen(FE_SCR_ALL));
		int all, on = count_in(scr_systems, cat, all) < all;
		for (auto &f : fe_games_folders()) if (f.category == cat) list_set(scr_systems, f.dir, on);
		ini_key("scrape_systems", join_list(scr_systems));
	}
	else if (name == FE_SCR_LANG)
	{
		int n = sizeof(scr_langs) / sizeof(scr_langs[0]), i = 0;
		while (i < n && scr_lang != scr_langs[i][0]) i++;
		i = (i == n) ? 0 : (i + (step < 0 ? n - 1 : 1)) % n;
		scr_lang = scr_langs[i][0];
		ini_key("scrape_lang", scr_lang);
	}
	else if (name == FE_SCR_TEXT)
	{
		scr_text = !scr_text;
		ini_key("scrape_text", scr_text ? "1" : "0");
	}
	else if (starts_with(name, FE_SCR_MEDIA))
	{
		std::string m = name.substr(strlen(FE_SCR_MEDIA));
		list_set(scr_media, m, !in_list(scr_media, m));
		// in the order of the menu
		std::vector<std::string> sorted;
		for (auto &n : scr_media_names) if (in_list(scr_media, n[0])) sorted.push_back(n[0]);
		scr_media = sorted;
		ini_key("scrape_media", join_list(scr_media));
	}
	else if (name == FE_SCR_REDO)
	{
		scr_redo = (scr_redo + (step < 0 ? 3 : 1)) % 4;
		ini_key("scrape_redo", std::to_string(scr_redo));
	}
	else if (name == FE_SCR_RUN)
	{
		if (step) return 1;
		if (fe_scrape_get().running)
		{
			fe_scrape_stop();
			notice("Scraper: stopping (what is downloaded stays)", 3000);
		}
		else scrape_start();
	}
	else if (name == FE_SCR_SYSINFO)
	{
		if (step) return 1;
		scrape_start(1);
	}
	else if (name == FE_SCR_USER || name == FE_SCR_PASS)
	{
		if (step) return 1;
		if (name == FE_SCR_PASS) edit_start(2, "");
		else edit_start(1, fe_scrape_cred("user"));
		return 1;
	}
	else return 0;
	settings_tags();
	list_gen++;
	dirty = 1;
	return 1;
}

// Left/Right on a setting: its value changes at once (the CRT shows it); 0 = Enter
static void setting_change(const std::string &name, int step)
{
	if (scrape_setting(name, step)) return;
	if (name == FE_COINOP)
	{
		coinop_toggle();
		return;
	}
	if (name == FE_THEME)
	{
		theme_next(step ? step : 1);
		return;
	}
	if (name == FE_TEXT_LAYOUT)
	{
		text_layout_toggle();
		return;
	}
	if (name == FE_CRT_OUT)
	{
		crt_out_toggle();
		return;
	}
	if (starts_with(name, FE_SAVER))
	{
		saver_setting(name, step ? step : 1);
		return;
	}
	if (name == FE_RECENT_MAX)
	{
		recent_setting(step ? step : 1);
		return;
	}
	if (name == FE_CRT_RESET)
	{
		if (step) return;
		crt_wpct = crt_hpct = 100;
		crt_hpos = crt_vpos = 0;
		notice("CRT picture: as it comes", 2000);
	}
	else if (!step) return;
	else if (name == FE_CRT_W) crt_wpct = std::max(50, std::min(100, crt_wpct + step));
	else if (name == FE_CRT_H) crt_hpct = std::max(50, std::min(100, crt_hpct + step));
	else if (name == FE_CRT_X) crt_hpos = std::max(-64, std::min(64, crt_hpos + step));
	else if (name == FE_CRT_Y) crt_vpos = std::max(-32, std::min(32, crt_vpos + step));
	else return;
	crt_hw_x = video_fe_hpos(crt_hpos);
	crt_save_ms = now_ms();
	settings_tags();
	list_gen++;
	crt_shown = -1;
	if (video_fe_main_crt()) fe_page = 0;
	dirty = 1;
}

// path relative to the root; remember = file whose folder is reopened next time;
// title = name in "Recent" if not label (a version of the detail view)
static fe_action launch(const std::string &path, const std::string &label, const std::string &remember, const std::string &title = "")
{
	launch_path = path;
	launch_label = label;

	// a game in games/: loaded by an MGL with its core
	size_t len = path.size();
	if (is_games_path(path) && !(len > 4 && !strcasecmp(path.c_str() + len - 4, ".mgl")))
	{
		launch_path = fe_games_mgl(path);
		if (launch_path.empty()) return FE_NONE;
	}
	else if (is_games_path(path))
	{
		// an MGL of games/ in another storage (USB disk, network share)
		std::string f = fe_games_file(path);
		if (f != std::string(getRootDir()) + "/" + path) launch_path = f;
	}

	std::string name = std::string(getRootDir()) + "/" FE_LAST_FILE;
	FILE *fp = fopen(name.c_str(), "w");
	if (fp)
	{
		fprintf(fp, "%s\n", remember.c_str());
		fclose(fp);
	}
	coinop_save(path);
	// "Recent": the key of the game, as for the favorites; only games, not the
	// cores started from "MiSTer" (or from the favorites)
	int core = len > 4 && !strcasecmp(path.c_str() + len - 4, ".rbf");
	if (recent_max && !core) fe_recent_add(remember.substr(remember.find('\t') + 1), title.empty() ? label : title, recent_max);

	// for the loading screen: the game shown (screensaver) or selected (its media
	// are known by fe_media), its system
	std::map<std::string, std::string> vars;
	if (saver) vars = saver_vars;
	else if (detail || info_sel == sel) fe_media_vars(vars); // not those of the game before (FE_SETTLE_MS)
	vars["game.name"] = label;
	if (vars["game.title"].empty()) vars["game.title"] = label;
	if (is_games_path(path))
	{
		std::string folder = path.substr(6);
		const fe_games_folder *f = fe_games_find(folder.substr(0, folder.find('/')));
		if (f) vars["system.name"] = f->name;
	}
	else if (len > 4 && !strcasecmp(path.c_str() + len - 4, ".mra")) vars["system.name"] = "Arcade";
	fe_loading_save(vars);

	printf("frontier: launch %s\n", launch_path.c_str());
	return FE_LAUNCH;
}

static void show_message(const char *text);

// versions of the detail view: the file, then its alternatives (arcade)
static void game_versions()
{
	versions.clear();
	version_paths.clear();
	fe_entry main = detail_entry;
	main.dir = 0;
	versions.push_back(main);
	version_paths.push_back(detail_path);
	versions_pending = 0;

	std::string dir, name;
	entry_place(detail_entry, dir, name);
	if (is_sys_path(dir))
	{
		// all the versions of the game (also with other titles), the launched one first
		const fe_gsystem *s = fe_group_get(sys_folder(dir));
		const fe_gtitle *t = fe_group_title(s, name);
		if (t)
		{
			versions.clear();
			version_paths.clear();
			std::vector<int> order = { t->def };
			for (int r : s->groups[t->group]) if (r != t->def) order.push_back(r);
			for (int r : order)
			{
				fe_entry e;
				e.name = s->roms[r].path;
				e.label = s->roms[r].label.empty() ? s->roms[r].name : s->roms[r].label;
				e.dir = 0;
				versions.push_back(e);
				version_paths.push_back(s->roms[r].path);
			}
		}
		versions_gen++;
		return;
	}

	// the discs of a game in its own folder: the first one starts, the others are versions
	if (detail_entry.discs.size() > 1 && is_games_path(dir))
	{
		versions.clear();
		version_paths.clear();
		for (size_t i = 0; i < detail_entry.discs.size(); i++)
		{
			const std::string &d = detail_entry.discs[i];
			std::string stem = d.substr(d.rfind('/') + 1);
			size_t dot = stem.rfind('.');
			fe_entry e;
			e.name = d;
			e.label = (dot == std::string::npos || dot == 0) ? stem : stem.substr(0, dot);
			e.dir = 0;
			versions.push_back(e);
			version_paths.push_back(dir + "/" + d);
		}
		versions_gen++;
		return;
	}

	size_t len = detail_path.size();
	if (len > 4 && !strcasecmp(detail_path.c_str() + len - 4, ".mra") && !is_games_path(detail_path))
	{
		std::vector<fe_version> alts;
		if (!fe_alt_versions(detail_path, alts)) versions_pending = 1;
		for (auto &a : alts)
		{
			// copies of the main .mra in _alternatives are not listed again
			std::string file = main.name.substr(0, main.name.size() - 4);
			if (a.path == detail_path || !strcasecmp(a.label.c_str(), main.label.c_str()) || !strcasecmp(a.label.c_str(), file.c_str())) continue;
			fe_entry e;
			e.name = a.path;
			e.label = a.label;
			e.dir = 0;
			versions.push_back(e);
			version_paths.push_back(a.path);
		}
		// "#Newest": the new .mra of the same game are its versions
		if (cur_dir == FE_NEWEST)
		{
			for (auto &o : fe_newest_versions(detail_path))
			{
				fe_entry e;
				e.name = o;
				e.label = o.substr(o.rfind('/') + 1);
				e.label.erase(e.label.size() - 4); // ".mra"
				e.dir = 0;
				versions.push_back(e);
				version_paths.push_back(o);
			}
		}
	}
	versions_gen++;
}

// the versions, then "Add to list..." (My Lists); from a list "Remove from this list"
static void load_versions()
{
	game_versions();
	if (detail_key.empty()) return;
	int in_list = my_list_index(cur_dir) >= 0;
	fe_entry e;
	e.name = in_list ? FE_REM_LIST : FE_ADD_LIST;
	e.label = in_list ? "Remove from this list" : "Add to list...";
	e.dir = 0;
	versions.push_back(e);
	version_paths.push_back(version_paths.empty() ? detail_path : version_paths[0]); // the media of the game
	std::vector<std::string> args;
	if (scrape_target(detail_entry, args))
	{
		e.name = FE_SCR_GAME;
		e.label = "Scrape this game";
		versions.push_back(e);
		version_paths.push_back(version_paths.back());
	}
}

// "Add to list...": the lists, "in list" on the right of those with the game, and
// "+ New list"; the media stay those of the version launched
static void load_picker()
{
	std::string path = version_paths.empty() ? detail_path : version_paths[0];
	versions.clear();
	version_paths.clear();
	for (auto &l : fe_mylists())
	{
		fe_entry e;
		e.name = FE_MY "/" + l.name;
		e.label = l.name;
		e.tag = fe_mylists_has(fe_mylists_find(l.name), detail_key) ? "in list" : "";
		e.dir = 0;
		versions.push_back(e);
		version_paths.push_back(path);
	}
	fe_entry e;
	e.name = FE_NEW_LIST;
	e.label = "+ New list";
	e.dir = 0;
	versions.push_back(e);
	version_paths.push_back(path);
	versions_gen++;
	if (vsel >= (int)versions.size()) vsel = versions.size() - 1;
	dirty = 1;
}

static void picker_open()
{
	picking = 1;
	vsel = vtop = crt_vtop = 0;
	load_picker();
}

// back to the versions, on "Add to list..."
static void picker_close()
{
	picking = 0;
	load_versions();
	vsel = 0;
	while (vsel < (int)versions.size() - 1 && versions[vsel].name != FE_ADD_LIST) vsel++;
	dirty = 1;
}

// A in "Add to list...": the game goes in (or out of) the list, or in a new one
static void picker_choose()
{
	if (vsel >= (int)versions.size()) return;
	const std::string name = versions[vsel].name;
	int added, idx;
	if (name == FE_NEW_LIST)
	{
		idx = fe_mylists_new(detail_key, detail_entry.label);
		added = 1;
	}
	else
	{
		idx = fe_mylists_find(name.substr(strlen(FE_MY "/")));
		if (idx < 0) return;
		added = fe_mylists_toggle(idx, detail_key, detail_entry.label);
	}
	std::string list = fe_mylists()[idx].name;
	printf("frontier: %s %s %s\n", detail_key.c_str(), added ? "added to" : "removed from", list.c_str());
	show_message(((added ? "Added to " : "Removed from ") + list).c_str());
	load_picker();
	if (name == FE_NEW_LIST) vsel = idx; // the new list
}

static void detail_open()
{
	if (sel >= (int)entries.size()) return;
	const fe_entry &e = entries[sel];
	if (e.dir || e.name == ".." || e.name.empty() || is_list_action(e.name)) return;

	fe_render_use(2);
	int ok = fe_render_active();
	fe_render_use(0);
	if (!ok) return; // no theme: no detail view

	detail_entry = e;
	detail_path = full_path(e);
	detail_key = entry_key(e);
	info_sel = sel;
	vsel = vtop = crt_vtop = 0;
	picking = 0;
	load_versions();
	detail = 1;
	fe_page = 0;     // full redraw
	crt_shown = -1;
	dirty = 1;
}

// the favorites (a list of My Lists) changed: the list again, on the same game or
// at the same position; a system without favorites any more: back to all of them
static void reload_favorites()
{
	if (is_my_list(cur_dir) && my_list_index(cur_dir) < 0)
	{
		load_dir(FE_MY, 0);
		return;
	}
	if (!is_fav_path(cur_dir) && !is_my_list(cur_dir)) return;
	std::string group = is_fav_path(cur_dir) ? fav_dir_group(cur_dir) : std::string();
	if (!group.empty() && !fav_count(group))
	{
		load_dir(FE_FAV, 0);
		return;
	}
	std::string want = (sel < (int)entries.size()) ? entries[sel].name : std::string();
	int keep = sel, keep_top = top;
	load_dir(cur_dir, want.c_str());
	if (sel >= (int)entries.size() || entries[sel].name != want) sel = std::max(0, std::min(keep, (int)entries.size() - 1));
	top = keep_top; // the list doesn't jump (adjusted by the renderer)
	info_sel = -1;
}

static void detail_close()
{
	fe_video_stop(); // its sound stops at once
	detail = 0;
	picking = 0;
	fe_page = 0;
	crt_shown = -1;
	dirty = 1;
	reload_favorites(); // one could have been removed in the detail view (or from a list)
}

static void show_message(const char *text)
{
	message = text;
	message_ms = now_ms();
	dirty = 1;
}

static void toggle_favorite(const fe_entry *e);

// the games of these folders are read again; the list shown stays until the
// new one is there, the theme shows the progress in ${message}
static void rescan(const std::vector<std::string> &dirs)
{
	for (auto &d : dirs)
	{
		if (std::find(rescanning.begin(), rescanning.end(), d) != rescanning.end()) continue;
		fe_group_rescan(d);
		rescanning.push_back(d);
	}
}

// "Updating: Mega Drive..." while the folders are read, then the result
static void rescan_progress()
{
	static int total = 0, alt_was = 0;
	static std::string last;
	std::string first;
	int busy = 0;
	for (auto &d : rescanning)
	{
		if (!fe_group_busy(d)) continue;
		if (!busy++) first = d;
	}
	int alt = rescanning_alt && fe_alt_busy();
	if (busy || alt)
	{
		total = std::max(total, (int)rescanning.size());
		alt_was |= rescanning_alt;
		const fe_games_folder *f = fe_games_find(first);
		std::string text = busy ? "Updating: " + (f ? f->name : first) : std::string("Updating the arcade versions");
		if (busy > 1) text += " and " + std::to_string(busy - 1) + " more";
		if (busy && alt) text += ", arcade versions";
		message = text + "...";
		message_ms = now_ms(); // stays until it's finished
		if (message != last) dirty = 1;
		last = message;
		return;
	}
	if (rescanning.empty() && !rescanning_alt) return;

	// finished
	std::string text;
	if (total == 1)
	{
		const fe_games_folder *f = fe_games_find(rescanning[0]);
		const fe_gsystem *s = fe_group_get(rescanning[0]);
		text = "List updated: " + (f ? f->name : rescanning[0]);
		if (s) text += ", " + std::to_string(s->titles.size()) + " games";
	}
	else if (total > 1) text = "Lists updated: " + std::to_string(total) + " systems";
	if (alt_was) text += std::string(text.empty() ? "Arcade versions updated: " : ", arcade versions: ") + std::to_string(fe_alt_count());
	rescanning.clear();
	rescanning_alt = 0;
	total = alt_was = 0;
	last.clear();
	show_message(text.c_str());
}

// X held (F on the keyboard): a game is added to or removed from the favorites;
// on a system (or "Folders" in its list) its games are read again, on a
// category all its systems, on Arcade the index of the alternatives
static void hold_action()
{
	const fe_entry *e = detail ? &detail_entry : (sel < (int)entries.size() ? &entries[sel] : 0);
	if (e && !detail && (is_setting(e->name) || is_list_action(e->name))) return;
	if (e && !detail && e->dir && e->name != "..")
	{
		std::vector<std::string> dirs;
		if (starts_with(cur_dir, FE_GAMES "/")) dirs.push_back(e->name);
		else if (is_sys_path(cur_dir) && e->name == FE_FOLDERS) dirs.push_back(sys_folder(cur_dir));
		else if (cur_dir.empty() && starts_with(e->name, FE_GAMES "/"))
		{
			// new systems (folders, cores) too
			std::string cat = e->name.substr(strlen(FE_GAMES "/"));
			fe_games_rescan();
			for (auto &f : fe_games_folders()) if (f.category == cat) dirs.push_back(f.dir);
			load_dir("", e->name.c_str());
		}
		else if (cur_dir.empty() && e->name == FE_ARCADE)
		{
			fe_alt_rescan();
			rescanning_alt = 1;
		}
		rescan(dirs);
		rescan_progress();
		return;
	}
	toggle_favorite(e);
}

// adds or removes the selected game (the game of the detail view) from the favorites
static void toggle_favorite(const fe_entry *e)
{
	std::string key = !e ? std::string() : detail ? detail_key : entry_key(*e);
	if (key.empty()) return; // a folder
	int added = fe_fav_toggle(key, e->label);
	printf("frontier: favorite %s %s\n", added ? "added" : "removed", key.c_str());
	show_message(added ? "Added to favorites" : "Removed from favorites");
	if (!detail) reload_favorites();
	info_sel = -1; // ${game.favorite}
}

/////////////////////////////////////////////////////////////////////////////
// Screensaver: after screensaver= seconds without keys random games are shown
// with the theme's screensaver.ini (renderers 4/5): their video or picture and
// description, a new game every screensaver_time seconds. Only the games with
// a video or a picture: a game by title of a system or an .mra of _Arcade.
// Start on the joypad (Space on the keyboard) starts the game shown, any other
// key goes back to the screen of before.

#define FE_SAVER_TRIES 40          // games without media skipped before giving up

struct saver_game
{
	std::string sys, key;        // fe_media
	std::string path, label;     // launched
	std::string remember;        // line of frontier_last.txt
	std::string folder;          // games/ folder, "" = arcade
};

static uint64_t idle_ms = 0;       // last key, or Frontier shown again
static uint64_t saver_ms = 0;      // the game shown since
static uint64_t start_ms = 0;      // last press of Start on a joypad (frontier_panic_key)
static saver_game saver_cur, saver_try;
static int saver_trying = 0;       // fe_media is reading saver_try
static int saver_tries = 0;
static uint32_t saver_wake = 0;    // key which ended the screensaver: its repeats and release are not used
static std::vector<std::string> saver_mras; // _Arcade/*.mra, read once
static int saver_mras_read = 0;

// a random game: a random system (Arcade is one), then a random title of it;
// 0 if the system has no titles (not known yet, only folders)
static int saver_pick(saver_game &g)
{
	if (!saver_mras_read)
	{
		saver_mras_read = 1;
		DIR *d = opendir((std::string(getRootDir()) + "/" FE_ARCADE).c_str());
		while (d)
		{
			struct dirent *de = readdir(d);
			if (!de) break;
			size_t len = strlen(de->d_name);
			if (de->d_name[0] != '.' && len > 4 && !strcasecmp(de->d_name + len - 4, ".mra")) saver_mras.push_back(de->d_name);
		}
		if (d) closedir(d);
	}

	// the systems shown (not hidden in the settings)
	std::vector<const fe_games_folder *> folders;
	for (auto &f : fe_games_folders()) if (!is_hidden(f.dir)) folders.push_back(&f);
	int arcade = !saver_mras.empty() && !is_hidden(FE_ARCADE);
	int n = folders.size() + arcade;
	if (!n) return 0;
	int i = rand() % n;
	if (i == (int)folders.size())
	{
		const std::string &file = saver_mras[rand() % saver_mras.size()];
		g.sys = "arcade";
		g.key = file.substr(0, file.size() - 4);
		g.path = std::string(FE_ARCADE "/") + file;
		g.label = g.key;
		g.remember = g.path;
		g.folder.clear();
		return 1;
	}

	// the list of the last time (frontier/.cache), at once
	const fe_games_folder &f = *folders[i];
	fe_group_request(f.dir);
	const fe_gsystem *s = fe_group_get(f.dir);
	if (!s || s->titles.empty()) return 0;
	const fe_gtitle &t = s->titles[rand() % s->titles.size()];
	const fe_grom &r = s->roms[t.def];
	g.sys = lower(f.dir);
	g.key = r.name;
	g.path = r.path;
	g.label = t.title;
	g.remember = FE_SYS + f.dir + "/" + t.title;
	g.folder = f.dir;
	return 1;
}

// asks fe_media for the next random game
static void saver_next()
{
	for (int i = 0; i < 8; i++)
	{
		if (!saver_pick(saver_try)) continue;
		if (saver == 2 && saver_try.path == saver_cur.path) continue;
		fe_media_select(saver_try.sys, saver_try.key);
		saver_trying = 1;
		return;
	}
	saver_trying = 0;
	saver_tries += 8; // systems without titles
}

static void saver_begin()
{
	static int seeded = 0;
	if (!seeded++) srand(time(0) ^ getpid());
	fe_video_stop();
	saver = 1;
	saver_tries = 0;
	saver_next();
}

static void saver_end()
{
	fe_video_stop();
	saver = 0;
	saver_trying = 0;
	fx_req = fx_hdmi = fx_crt = 0;
	idle_ms = now_ms();
	info_sel = -1;   // the list selects its game in fe_media again
	fe_page = 0;     // full redraw
	crt_shown = -1;
	dirty = 1;
}

// the game read by fe_media is shown if it has a video or a picture
static void saver_check()
{
	std::map<std::string, std::string> vars;
	if (!saver_trying || !fe_media_vars(vars)) return;
	saver_trying = 0;
	if (vars["media.video"].empty() && vars["media.snap"].empty() && vars["media.title"].empty() && vars["media.fanart"].empty())
	{
		saver_tries++; // another one at the next poll (saver_poll)
		return;
	}

	saver_cur = saver_try;
	saver_tries = 0;
	saver_vars = vars;
	saver_vars["game.name"] = saver_cur.label;
	if (!saver_vars.count("game.title")) saver_vars["game.title"] = saver_cur.label;
	saver_vars["game.file"] = saver_cur.path.substr(saver_cur.path.rfind('/') + 1);
	saver_vars["game.favorite"] = fe_fav_has(saver_cur.remember) ? "1" : "";
	saver_vars["system"] = saver_cur.sys;
	const fe_games_folder *f = saver_cur.folder.empty() ? 0 : fe_games_find(saver_cur.folder);
	std::string sysname = f ? f->name : std::string("Arcade");
	saver_vars["title"] = sysname;
	saver_vars["folder"] = f ? std::string(category_label(f->category)) + " / " + f->name : sysname;
	saver_vars["system.name"] = sysname;
	std::string img;
	for (auto &k : { lower(saver_cur.folder.empty() ? std::string("arcade") : saver_cur.folder), f ? lower(f->id) : std::string() })
	{
		auto it = theme_images.find(k);
		if (!k.empty() && it != theme_images.end()) { img = it->second; break; }
	}
	saver_vars["media.system"] = img;

	fe_entry e;
	e.name = saver_cur.path;
	e.label = saver_cur.label;
	e.dir = 0;
	e.tag = sysname;
	saver_entries.assign(1, e);
	saver_gen++;
	// full redraw, with the transition from the picture shown (screensaver_transition)
	fx_req = 3;
	saver = 2;
	saver_ms = now_ms();
	dirty = 1;
}

// at every poll before the keys are used: starts, runs and ends the
// screensaver; key and menu are cleared when the screensaver used them
static fe_action saver_poll(uint32_t &key, int &menu)
{
	uint64_t t = now_ms();
	static uint64_t last_poll = 0, start_seen = 0;
	if (t - last_poll > 1000) idle_ms = t; // not polled for a while: OSD, file browser
	last_poll = t;
	int start = (start_ms != start_seen);
	start_seen = start_ms;

	// the key which ended the screensaver: its repeats and its release (B, Esc
	// and F12 open the OSD or go back when released)
	if (saver_wake && !saver)
	{
		if (key == saver_wake) key = 0;
		else if (key == (saver_wake | UPSTROKE))
		{
			key = 0;
			menu = 0;
			saver_wake = 0;
		}
		else if (key && !(key & UPSTROKE)) saver_wake = 0;
	}

	if (!saver)
	{
		if ((key && !(key & UPSTROKE)) || menu || start || coinop_state) idle_ms = t;
		if (!saver_after || t - idle_ms < (uint64_t)saver_after * 1000) return FE_NONE;
		fe_render_use(4);
		int themed = fe_render_active();
		fe_render_use(0);
		if (!themed)
		{
			idle_ms = t; // built-in look: no screensaver
			return FE_NONE;
		}
		saver_begin();
		return FE_NONE;
	}

	// Start (Space): the game shown starts
	if (saver == 2 && (start || key == KEY_SPACE))
	{
		saver_game g = saver_cur;
		saver_end();
		saver_wake = key;
		key = 0;
		menu = 0;
		printf("frontier: screensaver: start %s\n", g.path.c_str());
		return launch(g.path, g.label, g.remember);
	}
	// any other key: back to the screen of before
	if (start || (key && !(key & UPSTROKE)) || menu)
	{
		saver_wake = (key & UPSTROKE) ? 0 : key;
		key = 0;
		menu = 0;
		saver_end();
		return FE_NONE;
	}
	key = 0;

	saver_check();
	if (!saver_trying && (saver == 1 || saver_tries || t - saver_ms >= (uint64_t)saver_time * 1000))
	{
		if (saver_tries < FE_SAVER_TRIES) saver_next();
		else
		{
			// nothing found: the list stays (or the game shown), tried again later
			saver_tries = 0;
			saver_ms = t;
			if (saver == 1) saver_end();
		}
	}
	return FE_NONE;
}

// the screensaver is on: only its screen is drawn (nothing while it looks for
// the first game)
static void saver_frame()
{
	if (saver != 2) return;
	if (fe_media_changed()) dirty = 1;
	// transition: as fast as it goes; waiting for the images: now and then
	if ((fx_hdmi || fx_crt) && now_ms() - last_frame >= ((fx_hdmi == 2 || fx_crt == 2) ? 15u : 50u)) dirty = 1;
	if (!message.empty() && now_ms() - message_ms >= FE_MSG_MS)
	{
		message.clear();
		dirty = 1;
	}
	if (!dirty && animating() && now_ms() - last_frame >= (uint64_t)(1000 / max_fps)) dirty = 1;
	if (bg_gen != video_fe_bg_gen()) dirty = 1;
	if (!dirty) return;
	dirty = 0;
	last_frame = now_ms();
	present();
}

/////////////////////////////////////////////////////////////////////////////
// public interface

// the old names (before the name Frontier): frontend/ -> frontier/,
// frontend.ini, frontend.off, config/frontend_last.txt, once if the new one is missing
static void migrate_names()
{
	static const char *names[][2] = {
		{ "frontend", FE_DIR }, { FE_DIR "/frontend.ini", FE_DIR "/frontier.ini" },
		{ "frontend.off", FE_DISABLE_FILE }, { "config/frontend_last.txt", FE_LAST_FILE },
	};
	for (auto &n : names)
	{
		std::string from = std::string(getRootDir()) + "/" + n[0], to = std::string(getRootDir()) + "/" + n[1];
		if (!file_there(from) || file_there(to)) continue;
		int ok = !rename(from.c_str(), to.c_str());
		fprintf(stderr, "frontier: %s -> %s%s\n", n[0], n[1], ok ? "" : " failed");
	}
	sync();
}

int frontier_enabled()
{
	static int enabled = -1;
	if (enabled < 0)
	{
		migrate_names();
		enabled = !FileExists(FE_DISABLE_FILE);
		printf("frontier: %s\n", enabled ? "enabled" : "disabled (" FE_DISABLE_FILE " found)");
	}
	return enabled;
}

void frontier_start()
{
	if (!started)
	{
		started = 1;
		fe_update_boot();
		fe_media_init(std::string(getRootDir()) + "/" FE_DIR);
		fe_games_load(std::string(getRootDir()) + "/" FE_DIR "/systems.ini");
		fe_fav_load(std::string(getRootDir()) + "/" FE_DIR "/" FE_FAV_FILE);
		fe_recent_load(std::string(getRootDir()) + "/" FE_DIR "/" FE_RECENT_FILE);
		fe_mylists_load(std::string(getRootDir()) + "/" FE_DIR "/" FE_MYLISTS_FILE);
		fe_scrape_init(getRootDir(), std::string(getRootDir()) + "/" FE_DIR);
		load_theme();
		fe_alt_start(getRootDir(), rescan_auto);
		if (newest_days) fe_newest_scan(getRootDir(), std::string(getRootDir()) + "/" FE_DIR "/" FE_NEWEST_FILE); // the first time: what is there is known

		// reopen the folder of the last launched title
		std::string last;
		std::string name = std::string(getRootDir()) + "/" FE_LAST_FILE;
		FILE *fp = fopen(name.c_str(), "r");
		if (fp)
		{
			char line[1024];
			if (fgets(line, sizeof(line), fp))
			{
				line[strcspn(line, "\r\n")] = 0;
				last = line;
			}
			fclose(fp);
		}

		// power on or cold reboot (no marker in tmpfs yet, coinop_boot() writes it below):
		// the main screen; after a game or a core the folder of the last title
		if (!file_there(FE_COINOP_BOOT)) last.clear();

		// "<list>\t<key>": launched from the favorites or the recent games
		size_t tab = last.find('\t');
		size_t pos = (tab != std::string::npos) ? tab : last.rfind('/');
		std::string dir = (pos == std::string::npos) ? "" : last.substr(0, pos);
		std::string file = (pos == std::string::npos) ? last : last.substr(pos + 1);
		// a file of the SD root: from "MiSTer"
		if (dir.empty() && !file.empty()) dir = FE_MISTER;
		// a disc of a game in its own folder: the folder is a game in the one above
		int done = 0;
		if (tab == std::string::npos && is_games_path(dir) && dir.find('/', 6) != std::string::npos)
		{
			size_t sl = dir.rfind('/');
			std::string sub = dir.substr(sl + 1) + "/" + file;
			done = load_dir(dir.substr(0, sl), sub.c_str()) && sel < (int)entries.size() &&
				std::find(entries[sel].discs.begin(), entries[sel].discs.end(), sub) != entries[sel].discs.end();
		}
		if (!done && !load_dir(dir, file.c_str())) load_dir("", 0);
		coinop_boot();
	}

	if (saver) saver_end(); // OSD closed with the screensaver on (it can't be opened from it)
	idle_ms = now_ms();
	fe_page = 0; // force a full redraw
	dirty = 1;
}

static fe_action poll(uint32_t key, int menu);

fe_action frontier_poll(uint32_t key, int menu)
{
	// a game starts, the OSD or the file browser opens: the video sound stops, the
	// CRT settings are written
	fe_action a = poll(key, menu);
	if (a != FE_NONE)
	{
		fe_video_stop();
		crt_save();
	}
	return a;
}

static fe_action poll(uint32_t key, int menu)
{
	fe_action ca = coinop_poll(key, menu);
	if (ca != FE_NONE) return ca;

	fe_action sa = saver_poll(key, menu);
	if (sa != FE_NONE) return sa;
	if (saver)
	{
		saver_frame();
		return FE_NONE;
	}

	// ScreenScraper user or password typed on a keyboard: the keys go there
	if (editing)
	{
		if (menu)
		{
			// Esc (B): given up; F12: given up and the menu opens
			int back = key == (KEY_BACK | UPSTROKE) || key == (KEY_ESC | UPSTROKE);
			edit_end(0);
			if (back) key = menu = 0;
		}
		else if (edit_key(key)) key = 0;
	}

	if (menu && detail && (key == (KEY_BACK | UPSTROKE) || key == (KEY_ESC | UPSTROKE)))
	{
		if (picking) picker_close();
		else detail_close();
		key = 0;
		menu = 0;
	}

	if (menu)
	{
		// B (joypad) and Esc go back one folder, F12/OSD button opens the menu
		if (!cur_dir.empty() && (key == (KEY_BACK | UPSTROKE) || key == (KEY_ESC | UPSTROKE))) go_up();
		else return FE_OPEN_OSD;
	}

	// the menu repeats a held key (also one whose release was lost): only the
	// keys which move in the lists repeat, the others (F5, Enter, X...) act once
	static uint32_t last_down = 0;
	if (key & UPSTROKE) last_down = 0;
	else if (key)
	{
		int moves = key == KEY_UP || key == KEY_DOWN || key == KEY_LEFT || key == KEY_RIGHT ||
			key == KEY_PAGEUP || key == KEY_PAGEDOWN || key == KEY_MINUS || key == KEY_EQUAL;
		if (key == last_down && !moves) key = 0;
		else last_down = key;
	}

	// X (Tab): pressed and released = detail view, held for FE_HOLD_MS = favorite
	static uint64_t x_down = 0; // 0: not held, or already used
	if (key == KEY_TAB)
	{
		x_down = now_ms();
		key = 0;
	}
	else if (key == (KEY_TAB | UPSTROKE))
	{
		key = x_down ? KEY_TAB : 0;
		x_down = 0;
	}
	else if (key && !(key & UPSTROKE)) x_down = 0; // another key in the meantime
	if (x_down && now_ms() - x_down >= FE_HOLD_MS)
	{
		x_down = 0;
		hold_action();
	}

	int count = entries.size();
	int old_sel = sel, old_vsel = vsel;

	if (detail && key && !(key & UPSTROKE))
	{
		int vc = versions.size();
		switch (key)
		{
		case KEY_UP:
			if (vc) vsel = (vsel > 0) ? vsel - 1 : vc - 1;
			break;

		case KEY_DOWN:
			if (vc) vsel = (vsel < vc - 1) ? vsel + 1 : 0;
			break;

		case KEY_LEFT:
		case KEY_PAGEUP:
		case KEY_MINUS:
		case KEY_HOME:
			vsel = 0;
			break;

		case KEY_RIGHT:
		case KEY_PAGEDOWN:
		case KEY_EQUAL:
		case KEY_END:
			vsel = vc ? vc - 1 : 0;
			break;

		case KEY_TAB:       // X on the joypad (released before FE_HOLD_MS)
		case KEY_BACKSPACE:
		case KEY_I:
			if (picking) picker_close();
			else detail_close();
			break;

		case KEY_F:         // keyboard: favorite (X held on the joypad)
			hold_action();
			break;

		case KEY_ENTER:
		case KEY_KPENTER:
		case KEY_SPACE:
			if (picking) picker_choose();
			else if (vsel < vc && versions[vsel].name == FE_ADD_LIST) picker_open();
			else if (vsel < vc && versions[vsel].name == FE_REM_LIST)
			{
				// the game out of the list it was opened from: back to the list
				int idx = my_list_index(cur_dir);
				if (idx >= 0 && fe_mylists_has(idx, detail_key))
				{
					fe_mylists_toggle(idx, detail_key, detail_entry.label);
					printf("frontier: %s removed from %s\n", detail_key.c_str(), fe_mylists()[idx].name.c_str());
					notice("Removed from " + fe_mylists()[idx].name, 2000);
				}
				detail_close();
			}
			else if (vsel < vc && versions[vsel].name == FE_SCR_GAME) scrape_game();
			else if (vsel < vc)
			{
				fe_action a = launch(version_paths[vsel], versions[vsel].label, remember_of(detail_key), detail_entry.label);
				if (a != FE_NONE) return a;
			}
			break;

		case KEY_GRAVE:     // R2 on the joypad
			return FE_OPEN_BROWSER;
		}
		if (key != KEY_F5) key = 0; // F5 (reload the theme) works here too
	}

	// Up/Down held: faster after a while (the menu repeats them every 50 ms)
	static uint32_t hold_key = 0;
	static uint64_t hold_start = 0, hold_last = 0;
	int step = 1;
	if (key == KEY_UP || key == KEY_DOWN)
	{
		uint64_t t = now_ms();
		if (key != hold_key || t - hold_last > 500) hold_start = t; // the release resets it too (UPSTROKE)
		hold_key = key;
		hold_last = t;
		uint64_t held = t - hold_start;
		step = (held < 1500) ? 1 : (held < 3000) ? 3 : 8;
	}
	else if (key & UPSTROKE) hold_key = 0;

	// "Frontier Settings": Left/Right (L/R) change the selected setting
	if (!detail && is_settings_dir(cur_dir) && key && !(key & UPSTROKE) && sel < count && is_setting(entries[sel].name))
	{
		int dir = (key == KEY_LEFT || key == KEY_MINUS) ? -1 : (key == KEY_RIGHT || key == KEY_EQUAL) ? 1 : 0;
		static uint64_t slow_ms = 0;
		int slow = !starts_with(entries[sel].name, "@crt_"); // held: not a theme every 50 ms (the CRT picture: fast)
		if (dir && slow && now_ms() - slow_ms < 500) key = 0;
		else if (dir)
		{
			if (slow) slow_ms = now_ms();
			setting_change(entries[sel].name, dir);
			key = 0;
		}
	}

	if (key && !(key & UPSTROKE))
	{
		switch (key)
		{
		case KEY_UP:
			if (count && step > 1) sel = std::max(0, sel - step); // no wrap while it runs
			else if (count) sel = (sel > 0) ? sel - 1 : count - 1;
			break;

		case KEY_DOWN:
			if (count && step > 1) sel = std::min(count - 1, sel + step);
			else if (count) sel = (sel < count - 1) ? sel + 1 : 0;
			break;

		case KEY_LEFT:
		case KEY_PAGEUP:
			sel = std::max(0, sel - rows);
			break;

		case KEY_RIGHT:
		case KEY_PAGEDOWN:
			sel = std::max(0, std::min(count - 1, sel + rows));
			break;

		case KEY_MINUS:     // L on the joypad: previous letter
		case KEY_EQUAL:     // R on the joypad: next letter
			if (count && (cur_dir == FE_RECENT || cur_dir == FE_NEWEST))
			{
				// not sorted by name: a page
				sel = std::max(0, std::min(count - 1, sel + (key == KEY_EQUAL ? rows : -rows)));
			}
			else if (count)
			{
				sel = letter_jump(key == KEY_EQUAL ? 1 : -1);
				jump_letter = entry_letter(entries[sel]);
				jump_ms = now_ms();
				dirty = 1;
			}
			break;

		case KEY_HOME:
			sel = 0;
			break;

		case KEY_END:
			sel = count ? count - 1 : 0;
			break;

		case KEY_F:         // keyboard: favorite (X held on the joypad)
			hold_action();
			break;

		case KEY_TAB:       // X on the joypad, released before FE_HOLD_MS (Y never reaches the menu: input.cpp)
		case KEY_BACKSPACE: // A+B on the joypad
		case KEY_I:
			// detail view of a file; Backspace on a folder: one folder up
			if (count && !entries[sel].dir && entries[sel].name != ".." && !is_setting(entries[sel].name)) detail_open();
			else if (key == KEY_BACKSPACE) go_up();
			break;

		case KEY_ENTER:
		case KEY_KPENTER:
		case KEY_SPACE:
			if (count)
			{
				const fe_entry &e = entries[sel];
				if (e.name == "..")
				{
					go_up();
				}
				else if (e.name == FE_MAKE_LIST)
				{
					// the games of the filter in a new list with the suggested name
					filter_to_list(fe_lists_name(), -1);
				}
				else if (starts_with(e.name, FE_LISTS_ADD "/"))
				{
					int idx = fe_mylists_find(e.name.substr(strlen(FE_LISTS_ADD "/")));
					if (idx >= 0) filter_to_list("", idx);
				}
				else if (e.name == FE_LISTS_NEW)
				{
					load_dir(FE_LISTS_NEW, 0);
				}
				else if (e.name == FE_TYPED_LIST)
				{
					edit_start(4, "");
				}
				else if (e.name == FE_REN_LIST)
				{
					int idx = my_list_index(cur_dir);
					if (idx >= 0) edit_start(3, fe_mylists()[idx].name);
				}
				else if (e.name == FE_CLEAR_FILTER)
				{
					fe_lists_clear();
					load_dir(FE_LISTS, 0);
					notice("Filter cleared", 1500);
				}
				else if (starts_with(e.name, FE_LISTS "/v/") && fe_lists_toggle(e.name))
				{
					// a value of the filter chosen or not: same place in the list
					std::string want = e.name;
					int keep_top = top;
					load_dir(cur_dir, want.c_str());
					top = keep_top;
				}
				else if (e.name == FE_DEL_LIST)
				{
					// a list of My Lists: with games A twice
					int idx = my_list_index(cur_dir);
					int n = (idx >= 0) ? fe_mylists()[idx].games.size() : 0;
					if (n && (del_armed != cur_dir || now_ms() > del_ms))
					{
						del_armed = cur_dir;
						del_ms = now_ms() + 4000;
						notice("A again to delete the list and its " + std::to_string(n) + (n == 1 ? " game" : " games"), 4000);
					}
					else
					{
						if (idx >= 0) fe_mylists_remove(idx);
						del_armed.clear();
						notice("List deleted", 2000);
						load_dir(FE_MY, 0);
					}
				}
				else if (is_setting(e.name))
				{
					setting_change(e.name, 0);
				}
				else if (e.dir)
				{
					load_dir(full_path(e), 0);
				}
				else if (!e.name.empty())
				{
					// by title: the rom is launched, the title is remembered
					std::string path = full_path(e);
					// a launcher (@mgl:) is reopened in the list where it is, not in the folder of its file
					std::string last = (starts_with(e.name, FE_MGL) && !is_key_list(cur_dir)) ? cur_dir + "\t" + e.name : remember_of(entry_key(e));
					fe_action a = path.empty() ? FE_NONE : launch(path, e.label, last);
					if (a != FE_NONE) return a;
				}
			}
			break;

		case KEY_GRAVE:     // R2 on the joypad
			return FE_OPEN_BROWSER;

		case KEY_F5:
			// reload the theme and the media (for theme authors); the games of the
			// systems opened from now on and the arcade alternatives are read again
			// (until the next start, as with rescan=auto)
			fe_media_reset();
			fe_group_reset();
			fe_games_load(std::string(getRootDir()) + "/" FE_DIR "/systems.ini");
			fe_games_rescan();
			fe_fav_load(std::string(getRootDir()) + "/" FE_DIR "/" FE_FAV_FILE);
			fe_recent_load(std::string(getRootDir()) + "/" FE_DIR "/" FE_RECENT_FILE);
			fe_mylists_load(std::string(getRootDir()) + "/" FE_DIR "/" FE_MYLISTS_FILE);
			fe_lists_reset();
			load_theme();
			fe_group_manual(0);
			fe_alt_rescan();
			saver_mras_read = 0; // the arcade games of the screensaver too
			saver_mras.clear();
			if (!load_dir(cur_dir, entries.empty() ? 0 : entries[sel].name.c_str())) load_dir("", 0);
			fe_page = 0;
			dirty = 1;
			break;
		}
	}

	if (sel != old_sel)
	{
		del_ms = 0; // "Delete this list": A twice on it
		// first press: the panel follows at once; repeated keys: it waits
		uint64_t t = now_ms();
		if (t - sel_ms >= FE_SETTLE_MS) info_sel = sel;
		sel_ms = t;
		dirty = 1;
	}
	if (info_sel != sel && now_ms() - sel_ms >= FE_SETTLE_MS)
	{
		info_sel = sel;
		dirty = 1;
	}
	if (vsel != old_vsel) dirty = 1;
	// a CRT setting selected: the edges of the picture are shown
	int guide = !detail && cur_dir == FE_SET_CRT && sel < (int)entries.size() && starts_with(entries[sel].name, "@crt_");
	if (guide != crt_guide)
	{
		crt_guide = guide;
		crt_shown = -1;
		if (video_fe_main_crt()) fe_page = 0;
		dirty = 1;
	}
	if (crt_save_ms && (now_ms() - crt_save_ms > 1000 || cur_dir != FE_SET_CRT)) crt_save();
	if (jump_letter && now_ms() - jump_ms >= FE_JUMP_MS)
	{
		jump_letter = 0; // the letter of L/R disappears
		dirty = 1;
	}
	if (detail && versions_pending && !picking)
	{
		// the index of the alternatives was not ready: try again
		static uint64_t last_try = 0;
		if (now_ms() - last_try > 500)
		{
			last_try = now_ms();
			load_versions();
			if (!versions_pending) dirty = 1;
		}
	}
	// games/ on a USB disk mounted after MiSTer starts: the categories come later
	if (cur_dir.empty() && !root_has_games && !fe_games_folders().empty())
	{
		load_dir("", sel < (int)entries.size() ? entries[sel].name.c_str() : 0);
		info_sel = -1;
	}

	if (notice_until > now_ms()) message_ms = now_ms(); // Coin-Op notices: longer
	if (!message.empty() && now_ms() - message_ms >= FE_MSG_MS)
	{
		message.clear(); // ${message} disappears
		dirty = 1;
	}

	std::string updated;
	int group_updated = fe_group_poll(updated);
	if (group_updated && is_key_list(cur_dir))
	{
		// the roms of the favorites (recent games) by title are known now
		info_sel = -1;
		dirty = 1;
	}
	if (group_updated)
	{
		// the games by their data: those of that system are known or changed
		fe_lists_group_changed();
		if (is_lists_path(cur_dir) && !detail)
		{
			std::string want = (sel < (int)entries.size()) ? entries[sel].name : std::string();
			int keep_top = top;
			if (!load_dir(cur_dir, want.c_str())) load_dir(FE_LISTS, 0);
			else top = keep_top;
		}
	}
	if (group_updated && cur_dir == FE_SYS + updated)
	{
		// the games of this system were read (first time) or changed: same selection
		int first = !entries.empty() && entries.back().name.empty();
		std::string want = first ? scan_want : (sel < (int)entries.size() ? entries[sel].name : std::string());
		if (!load_dir(cur_dir, want.empty() ? 0 : want.c_str())) load_dir("", 0);
		info_sel = -1;
	}
	rescan_progress();
	// the scraper in the background: its progress in the settings, the new pictures
	// when a system is finished
	fe_scrape_state scr;
	int scr_sys_end, scr_end;
	if (fe_scrape_poll(scr, scr_sys_end, scr_end) && is_settings_dir(cur_dir))
	{
		settings_tags();
		list_gen++;
		dirty = 1;
	}
	if (scr_sys_end)
	{
		fe_media_reset();
		dirty = 1;
	}
	if (scr_end)
	{
		fe_lists_reset(); // the index of "My Lists" was made again
		if (scr.state == "done")
		{
			std::string r = scrape_result(scr);
			if (scr.updated > 0) r = std::to_string(scr.updated) + (scr.updated == 1 ? " game" : " games") + " with new data or pictures";
			if (scr.notfound > 0) r += (r.empty() ? "" : ", ") + std::to_string(scr.notfound) + " not found";
			notice(r.empty() ? "Scraper finished" : "Scraper finished: " + r, 5000);
		}
		else if (scr.state == "error") notice("Scraper error: see frontier/.cache/scrape.log", 6000);
		else notice("Scraper stopped", 3000);
	}
	if (bg_gen != video_fe_bg_gen()) dirty = 1;
	if (fe_media_changed()) dirty = 1;
	if (hide_date != cfg.rbf_hide_datecode)
	{
		hide_date = cfg.rbf_hide_datecode;
		dirty = 1;
	}

	// animations: next frame
	if (!dirty && animating() && now_ms() - last_frame >= (uint64_t)(1000 / max_fps)) dirty = 1;

	if (dirty)
	{
		dirty = 0;
		last_frame = now_ms();
		present();
	}

	return FE_NONE;
}

const char *frontier_selected_path()
{
	return launch_path.c_str();
}

const char *frontier_selected_label()
{
	return launch_label.c_str();
}

// L+R+Select+Start (the joypad's mapping for the menu) held FE_PANIC_MS in a game:
// back to the menu, also when the game doesn't show. A short press stays for the
// game (soft reset of many SNES games). panic_combo=0 in frontier.ini: off.
#define FE_PANIC_DEVS 64
static uint8_t panic_mask[FE_PANIC_DEVS] = {};
static int panic_dev = -1;
static uint64_t panic_t0 = 0;

void frontier_panic_key(int dev, int bit, int value)
{
	if ((bit & 8) && value == 1) start_ms = now_ms(); // the screensaver starts the game shown
	if (!bit || dev < 0 || dev >= FE_PANIC_DEVS) return;
	if (value) panic_mask[dev] |= bit;
	else panic_mask[dev] &= ~bit;
	if (panic_mask[dev] == 15)
	{
		if (panic_dev != dev)
		{
			panic_dev = dev;
			panic_t0 = now_ms();
		}
	}
	else if (panic_dev == dev) panic_dev = -1;
}

int frontier_progress(const char *title, const char *text, int current, int max)
{
	return fe_loading_progress(title, text, current, max);
}

void frontier_panic_poll()
{
	fe_loading_poll();

	if (panic_dev < 0 || now_ms() - panic_t0 < FE_PANIC_MS) return;
	panic_dev = -1;
	memset(panic_mask, 0, sizeof(panic_mask));
	if (is_menu() || !frontier_enabled()) return;

	// read here: in a game Frontier is not started
	static int on = -1;
	if (on < 0)
	{
		std::map<std::string, std::string> ini = fe_read_ini(std::string(getRootDir()) + "/" FE_DIR "/frontier.ini");
		on = ini.count("panic_combo") ? atoi(ini["panic_combo"].c_str()) : 1;
	}
	if (!on) return;
	printf("frontier: L+R+Select+Start held, back to the menu\n");
	fpga_load_rbf("menu.rbf");
}
