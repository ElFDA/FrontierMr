#ifndef FE_RENDER_H
#define FE_RENDER_H

// Theme renderer for Frontier (Imlib2 + freetype).
// Static elements are drawn once in a cached layer; on every update only the
// areas of the dynamic elements which changed are redrawn.

#include <inttypes.h>
#include <string>
#include <vector>
#include <map>

struct fe_entry
{
	std::string name;   // file/folder name on disk
	std::string label;  // display name
	std::string date;   // rbf datecode, "yy.mm.dd"
	std::string tag;    // shown on the right instead of the date (system of a favorite)
	int dir;
};

struct fe_view
{
	const std::vector<fe_entry> *entries = 0;
	int list_gen = 0;   // must change when entries are reloaded
	int sel = 0;
	int top = 0;        // in/out: first visible row of the list
	int rows = 1;       // out: visible rows of the list
	int show_date = 1;
	uint64_t time_ms = 0;  // for the animations
	std::map<std::string, std::string> vars; // ${name} in the theme
};

struct fe_rect
{
	int x, y, w, h;
};

// 0 if the theme can't be loaded (then the built-in look is used).
// file: "theme" (theme.ini, theme_43.ini), "detail" (detail.ini, detail_43.ini) or
// "screensaver" (screensaver.ini, screensaver_43.ini)
int  fe_render_load(const std::string &theme_dir, const char *file = "theme");
// selects the renderer the other calls work on: 0/1 = list on the HDMI/CRT
// pages, 2/3 = detail view on the HDMI/CRT pages, 4/5 = screensaver
void fe_render_use(int inst);
// 1 = text layout: the elements with layout=text instead of those with
// layout=media (for games without pictures); used by the next fe_render_load
void fe_render_text_layout(int on);
// debug: prints the time spent per element of slow frames on stderr
void fe_render_debug(int on);
void fe_render_unload();
int  fe_render_active();
// 1 if the last frame had animations running (draw again after a while)
int  fe_render_animating();
// 1 if the last frame had pictures still loading (shown when they are ready)
int  fe_render_loading();
const char *fe_render_theme_name();

// Draws the view into buf (w*h pixels, 0x00RRGGBB) which must keep the
// previous frame. full = redraw everything. Returns 0 if nothing changed,
// otherwise the changed areas (framebuffer pixels) are in dirty.
// area: where the picture goes in buf, 0 = all of it (size and position of the
// picture on a CRT); it may go past the edges, the rest of buf is black.
int  fe_render_draw(fe_view &view, uint32_t *buf, int w, int h, int full, std::vector<fe_rect> &dirty, const fe_rect *area = 0);

#endif
