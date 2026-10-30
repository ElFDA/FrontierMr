// Loading screen of Frontier (see fe_loading.h).
//
// A core loads its game right after it starts, in the MiSTer process started
// with it: ProgressMessage() is called for every block sent. The first call
// reads frontier.ini and the theme (loading.ini, from the simple theme if the
// theme hasn't it), draws it on page 1 of the HPS framebuffer and switches HDMI
// to it; the next ones redraw only what changed (animation, bar) at most every
// FE_LOAD_FRAME_MS. Between the files of a game (Neo Geo: P, S, M, V, C roms)
// the screen stays; fe_loading_poll() gives HDMI back to the core FE_LOAD_END_MS
// after the last block. The CRT keeps the core's own picture (the analog
// output of a core doesn't read the framebuffer): meanwhile the OSD commands
// go only to the VGA OSD (EnableOsd_on), so the bar of the OSD is on the CRT
// and not over the loading screen. The OSD is closed only after the
// framebuffer is off, or vga_nag() of menu.cpp would put its "If you see
// this... fb_terminal" message on the CRT. With direct_video nothing changes.
// The page has the size Main gives the framebuffer in this HDMI mode (its
// aspect, e.g. 960x672 for 1920x1344, 1280x720 for 2560x1440 with pixel
// repetition): as small as the menu's, the scaler only enlarges it.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>
#include <unistd.h>

#include <math.h>
#include <vector>

#include "fe_loading.h"
#include "fe_render.h"
#include "fe_media.h"
#include "fe_games.h"
#include "fe_theme.h"
#include "frontier.h"
#include "file_io.h"
#include "user_io.h"
#include "video.h"
#include "cfg.h"
#include "spi.h"
#include "menu.h"
#include "osd.h"
#include "charrom.h"

#define FE_LOAD_GAME     "/tmp/frontier_game.txt" // tmpfs: written at the launch, read once
#define FE_LOAD_GAME_AGE 60                       // s: older = another loading (e.g. from the OSD)
#define FE_LOAD_FRAME_MS 40
#define FE_LOAD_END_MS   500

#define OSD_CMD_WRITE    0x20                     // as in osd.cpp: + line, then 256 bytes
#define FE_OSD_FRAME_MS  80
#define FE_OSD_W 256
#define FE_OSD_H 128                              // 16 lines of 8 pixels (the big OSD)

static int state = 0;            // 0 off, 1 shown, -1 not in this process (no theme, off...)
static int crt_osd = 0;          // the CRT gets the loading screen of the OSD (loading_crt=1)
static int osd_shown = 0;
static uint64_t last_osd = 0;
static int direct = 0;           // direct_video: the framebuffer is on the CRT too
static uint64_t t0 = 0, last_call = 0, last_draw = 0;
static int last_pct = -1;
static std::string last_file;
static uint32_t *buf = 0;
static int w = 0, h = 0;
static std::map<std::string, std::string> vars;

static uint64_t now_ms()
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

void fe_loading_save(const std::map<std::string, std::string> &v)
{
	FILE *fp = fopen(FE_LOAD_GAME, "w");
	if (!fp) return;
	for (auto &kv : v)
	{
		if (kv.first.compare(0, 5, "game.") && kv.first.compare(0, 6, "media.") && kv.first.compare(0, 7, "system.")) continue;
		std::string val = kv.second;
		for (auto &c : val) if (c == '\n' || c == '\r') c = ' ';
		fprintf(fp, "%s=%s\n", kv.first.c_str(), val.c_str());
	}
	fclose(fp);
}

// the game written by Frontier, if it's this loading
static void read_game()
{
	vars.clear();
	struct stat st;
	if (stat(FE_LOAD_GAME, &st) || time(0) - st.st_mtime > FE_LOAD_GAME_AGE) return;
	FILE *fp = fopen(FE_LOAD_GAME, "r");
	if (!fp) return;
	char line[2048];
	while (fgets(line, sizeof(line), fp))
	{
		line[strcspn(line, "\r\n")] = 0;
		char *eq = strchr(line, '=');
		if (eq) vars[std::string(line, eq - line)] = eq + 1;
	}
	fclose(fp);
	unlink(FE_LOAD_GAME); // a game loaded later from the OSD isn't this one
}

// copies the areas of buf to page 1 of the framebuffer
static void copy(const std::vector<fe_rect> *rects)
{
	volatile uint32_t *fb = video_fe_page(1, 0, 0);
	if (!fb) return;
	if (!rects)
	{
		memcpy((void *)fb, buf, w * h * 4);
		return;
	}
	for (auto &r : *rects)
		for (int y = r.y; y < r.y + r.h; y++) memcpy((void *)(fb + y * w + r.x), buf + y * w + r.x, r.w * 4);
}

static int draw(int full, int pct, const char *file)
{
	fe_view v;
	v.vars = vars;
	v.time_ms = now_ms() - t0;
	v.vars["progress"] = std::to_string(pct);
	std::string name = file ? file : "";
	v.vars["loading.file"] = name;
	v.vars["title"] = v.vars["game.title"];
	std::vector<fe_rect> rects;
	int changed = fe_render_draw(v, buf, w, h, full, rects);
	if (full) copy(0);
	else if (changed) copy(&rects);
	last_draw = now_ms();
	return 1;
}

/////////////////////////////////////////////////////////////////////////////
// CRT: the OSD of the VGA output (the only thing of Main in the core's analog
// picture) shows a loading screen of its own: 256x128 pixels of 1 bit (osd.v:
// on = white, off = the core's picture darkened and tinted), sent as 16 lines
// of 256 bytes (a byte = 8 pixels of a column, bit 0 on top). A record turning
// as on the HDMI, "NOW LOADING" with jumping bubbles, the game, the bar.

static uint8_t opx[FE_OSD_H][FE_OSD_W];
static int clip_x0 = 0, clip_x1 = FE_OSD_W;

static void oplot(int x, int y)
{
	if (x >= clip_x0 && x < clip_x1 && y >= 0 && y < FE_OSD_H) opx[y][x] = 1;
}

// 8x8 font of the OSD, scale 1 or 2; utf-8 continuation bytes skipped
static void otext(int x, int y, const std::string &str, int scale)
{
	for (const unsigned char *p = (const unsigned char *)str.c_str(); *p; p++)
	{
		unsigned char c = *p;
		if (c >= 0x80)
		{
			if ((c & 0xC0) == 0x80) continue;
			c = '?';
		}
		for (int col = 0; col < 8; col++)
			for (int row = 0; row < 8; row++)
				if (charfont[c][col] & (1 << row))
					for (int k = 0; k < scale * scale; k++) oplot(x + col * scale + k % scale, y + row * scale + k / scale);
		x += 8 * scale;
		if (x >= clip_x1) break;
	}
}

static int otext_w(const std::string &str, int scale)
{
	int n = 0;
	for (unsigned char c : str) if ((c & 0xC0) != 0x80) n++;
	return n * 8 * scale;
}

// a text in [x0, x1): scrolls when it doesn't fit
static void otext_line(int x0, int x1, int y, const std::string &str, uint64_t t)
{
	clip_x0 = x0;
	clip_x1 = x1;
	int tw = otext_w(str, 1);
	int off = (tw > x1 - x0) ? (int)((t / 33) % (tw + 40)) : 0;
	otext(x0 - off, y, str, 1);
	if (off) otext(x0 - off + tw + 40, y, str, 1);
	clip_x0 = 0;
	clip_x1 = FE_OSD_W;
}

static void ocircle(int cx, int cy, double r)
{
	for (int y = (int)(cy - r); y <= cy + r; y++)
		for (int x = (int)(cx - r); x <= cx + r; x++)
			if ((x - cx) * (x - cx) + (y - cy) * (y - cy) <= r * r) oplot(x, y);
}

static void draw_osd(int pct, const char *file)
{
	uint64_t t = now_ms() - t0;
	memset(opx, 0, sizeof(opx));

	// the record: grooves, a fixed sheen, the label with a segment turning
	const int cx = 54, cy = 62, R = 48;
	double rot = t / 1000.0 * M_PI; // half a turn per second
	for (int y = cy - R; y <= cy + R; y++)
	{
		for (int x = cx - R; x <= cx + R; x++)
		{
			double dx = x - cx, dy = y - cy, d = sqrt(dx * dx + dy * dy);
			if (d > R) continue;
			double a = atan2(dy, dx);
			int on;
			if (d <= 2.5) on = 0;                                  // the hole
			else if (d <= 17)
			{
				double la = fmod(a - rot + 4 * M_PI, 2 * M_PI);
				double ddx = dx - 10 * cos(rot + M_PI), ddy = dy - 10 * sin(rot + M_PI);
				on = !(la < 1.3) && (ddx * ddx + ddy * ddy > 6.5); // segment and dot of the label
			}
			else if (d >= R - 1.2) on = 1;                         // rim
			else
			{
				double sa = fmod(a + 3 * M_PI / 4 + 4 * M_PI, M_PI);
				on = ((int)d % 4 == 0) || (sa < 0.35 && ((x + y) & 1)); // grooves, sheen
			}
			if (on) oplot(x, y);
		}
	}

	// NOW / LOADING, three bubbles jumping one after the other
	otext(114, 6, "NOW", 2);
	otext(114, 24, "LOADING", 2);
	for (int k = 0; k < 3; k++)
	{
		double ph = fmod(t / 900.0 - k / 6.0 + 1.0, 1.0);
		int jump = (ph < 0.5) ? (int)(sin(ph * 2 * M_PI) * 8) : 0;
		ocircle(178 + k * 14, 17 - jump, 3.5);
	}

	// the game, its system, the bar
	otext_line(114, 252, 48, vars["game.title"], t);
	otext_line(114, 252, 60, vars["system.name"], t);
	std::string p = std::to_string(pct) + "%";
	otext(252 - otext_w(p, 1), 80, p, 1);
	for (int x = 114; x < 252; x++) { oplot(x, 92); oplot(x, 103); }
	for (int y = 92; y <= 103; y++) { oplot(114, y); oplot(251, y); }
	int fw = (252 - 118) * pct / 100;
	for (int y = 95; y <= 100; y++) for (int x = 117; x < 117 + fw; x++) oplot(x, y);
	otext_line(4, 252, 118, std::string("LOADING ") + (file ? file : ""), t);

	// debug: /tmp/fe_osd_dump there -> the frame in /tmp/fe_osd.pgm
	struct stat st;
	if (!stat("/tmp/fe_osd_dump", &st))
	{
		FILE *fp = fopen("/tmp/fe_osd.pgm", "wb");
		if (fp)
		{
			fprintf(fp, "P5 %d %d 255\n", FE_OSD_W, FE_OSD_H);
			for (int y = 0; y < FE_OSD_H; y++) for (int x = 0; x < FE_OSD_W; x++) fputc(opx[y][x] ? 255 : 40, fp);
			fclose(fp);
		}
	}

	// 16 lines of 256 bytes to the OSD of the VGA output
	static uint8_t lines[FE_OSD_H / 8][FE_OSD_W];
	memset(lines, 0, sizeof(lines));
	for (int y = 0; y < FE_OSD_H; y++)
		for (int x = 0; x < FE_OSD_W; x++)
			if (opx[y][x]) lines[y / 8][x] |= 1 << (y & 7);
	EnableOsd_on(OSD_VGA);
	for (int i = 0; i < FE_OSD_H / 8; i++)
	{
		spi_osd_cmd_cont(OSD_CMD_WRITE | i);
		spi_write(lines[i], FE_OSD_W, 0);
		DisableOsd();
	}
	if (!osd_shown)
	{
		OsdSetSize(FE_OSD_H / 8);
		OsdEnable(OSD_MSG);
		osd_shown = 1;
	}
	last_osd = now_ms();
}

/////////////////////////////////////////////////////////////////////////////

// first block of a loading: theme, framebuffer, HDMI to it (and the CRT with
// direct_video, where the framebuffer goes to the VGA output too)
static int start(const char *file)
{
	if (!frontier_enabled()) return 0;
	std::string root = fe_root() + "/frontier";
	std::map<std::string, std::string> ini = fe_read_ini(root + "/frontier.ini");
	if (ini.count("loading_screen") && !atoi(ini["loading_screen"].c_str())) return 0;
	std::string theme = ini.count("theme") ? ini["theme"] : std::string("citypop_blue");
	if (theme == "default") theme = "simple"; // the old name of the theme
	if (theme.empty() || theme == "none") return 0;
	// loading_crt=0: the bar of the OSD on the CRT as before
	crt_osd = !ini.count("loading_crt") || atoi(ini["loading_crt"].c_str());
	direct = cfg.direct_video;

	// page 1 as the menu uses it: the size Main gives the framebuffer for this
	// HDMI mode (its aspect, pixel repetition counted; a bigger page made the
	// scaler shrink it and read more while the core loads into DDR: glitches)
	video_fe_page(1, &w, &h);
	if (!w || !h) return 0;
	fe_render_use(0);
	if (!fe_render_load(root + "/themes/" + theme, "loading") && !fe_render_load(root + "/themes/simple", "loading")) return 0;
	fe_media_init(root, 0); // pictures of the game decoded here, once
	free(buf);
	buf = (uint32_t *)calloc(w * h, 4);
	if (!buf) return 0;

	read_game();
	if (vars["game.title"].empty())
	{
		// not launched from Frontier: the name of the file
		std::string name = file ? file : "";
		size_t slash = name.rfind('/');
		name = name.substr(slash == std::string::npos ? 0 : slash + 1);
		size_t dot = name.rfind('.');
		if (dot != std::string::npos && dot > 0) name.erase(dot);
		vars["game.title"] = name;
	}
	t0 = now_ms();
	draw(1, 0, file);
	video_fb_enable(1, 1);
	if (!video_fb_state())
	{
		fprintf(stderr, "frontier: loading screen: no HPS framebuffer in this core\n");
		return 0;
	}
	fprintf(stderr, "frontier: loading screen %dx%d (%s)%s\n", w, h, theme.c_str(),
		direct ? ", direct_video: also on the CRT" : crt_osd ? ", OSD on the CRT" : "");
	return 1;
}

int fe_loading_progress(const char *, const char *text, int current, int max)
{
	if (is_menu() || state < 0) return 0;
	if (!current && !max)
	{
		// end of a file: the screens stay for the next one; MenuHide() would
		// show the "fb_terminal" nag on the CRT (vga_nag(): the framebuffer is
		// on), everything is closed by fe_loading_poll()
		if (state != 1) return 0;
		last_call = now_ms();
		return 1;
	}

	if (!state)
	{
		state = start(text) ? 1 : -1;
		if (state < 0) return 0;
		// the OSD bar (loading_crt=0) only on the CRT: the analog output of the
		// core doesn't read the framebuffer
		if (!direct && !crt_osd) EnableOsd_on(OSD_VGA);
	}

	last_call = now_ms();
	int pct = max ? (int)((uint64_t)current * 100 / max) : 0;
	if (last_call - last_draw >= FE_LOAD_FRAME_MS)
	{
		last_pct = pct;
		last_file = text ? text : "";
		draw(0, pct, text);
	}
	if (direct) return 1;   // the framebuffer is on the CRT too: no OSD
	if (!crt_osd) return 0; // ProgressMessage() goes on: the bar on the CRT
	if (last_call - last_osd >= FE_OSD_FRAME_MS) draw_osd(pct, text);
	return 1;
}

int fe_loading_active()
{
	return state == 1;
}

void fe_loading_poll()
{
	if (state != 1 || now_ms() - last_call < FE_LOAD_END_MS) return;
	video_fb_enable(0);
	if (osd_shown)
	{
		EnableOsd_on(OSD_VGA);
		OsdDisable();
		osd_shown = 0;
	}
	EnableOsd_on(OSD_ALL);
	if (!direct && !crt_osd) MenuHide(); // the bar of the CRT; the framebuffer is off: no nag
	state = 0;
	last_pct = -1;
	free(buf);
	buf = 0;
	fprintf(stderr, "frontier: loading screen closed after %d ms\n", (int)(now_ms() - t0));
}
