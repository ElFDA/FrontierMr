// Theme renderer for Frontier.
//
// Everything is drawn on a canvas with (about) square pixels: in modes with
// few lines (e.g. 640x240 on a CRT) the canvas has twice the lines of the
// framebuffer and is averaged down, so images keep the right proportions; TTF
// text is drawn on the lines of the framebuffer (see fe_font). Theme coordinates are in "base" units (default 1280x720) and
// are scaled to the canvas.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <math.h>
#include <glob.h>

#include <algorithm>

#include "lib/imlib2/Imlib2.h"
#include <ft2build.h>
#include FT_FREETYPE_H
#include "fe_render.h"
#include "fe_theme.h"
#include "fe_media.h"

struct fe_font;

enum { EL_RECT, EL_IMAGE, EL_TEXT, EL_LIST, EL_VIDEO, EL_BAR };
enum { FIT_CONTAIN, FIT_COVER, FIT_STRETCH };
enum { SCROLL_NONE, SCROLL_H, SCROLL_V };

struct frame
{
	std::shared_ptr<fe_bitmap> bm;
	int x, y;
};

struct element
{
	const fe_section *sec = 0;
	int type = EL_RECT;
	int base[4] = {};
	int x = 0, y = 0, w = 0, h = 0;  // canvas pixels
	int dynamic = 0;  // depends on the view
	int overlay = 0;  // static, but above a dynamic element: drawn with it

	uint32_t color = 0xFFFFFFFF;
	uint32_t color2 = 0;
	int gradient = 0;
	std::string text;    // text template or image file
	int fit = FIT_CONTAIN;
	std::shared_ptr<fe_bitmap> img; // static image, already scaled
	int img_x = 0, img_y = 0;
	std::shared_ptr<fe_bitmap> bm; // dynamic image (fe_media)
	std::string cond_if, cond_ifnot;
	int visible = 1;
	fe_font *font = 0;
	int font_h = 0;    // line height
	int font_off = 0;  // offset of the ascent line from the top of the line (0)
	int align = 0, valign = 0;
	int wrap = 0;
	uint32_t shadow = 0;
	int shadow_d = 1;

	// list
	int row_h = 0, pad = 0;
	uint32_t sel_bg = 0, sel_color = 0, dir_color = 0, tag_color = 0;
	uint32_t sb_color = 0, sb_knob = 0;
	int sb_w = 0;
	std::shared_ptr<fe_bitmap> sel_img;
	std::shared_ptr<fe_bitmap> sel_scaled;               // sel_img at the row size
	std::map<std::string, std::string> fit_cache;      // label -> label cut with "..."
	std::string tag_dir, tag_up, empty;

	// animation
	int fade_ms = 0;                     // image: cross fade when it changes
	std::shared_ptr<fe_bitmap> prev_bm;
	uint64_t fade_start = 0;
	int alpha = 255;
	std::vector<frame> frames;           // image: animation from files (src with '*')
	int fps = 10;
	int frame_idx = 0;
	int scroll = SCROLL_NONE;            // text: scrolls when it doesn't fit
	int scroll_speed = 0;                // canvas pixels per second
	int scroll_delay = 0;                // ms before scrolling
	uint64_t scroll_start = 0;
	int offset = 0;
	std::vector<std::string> lines;      // text split in lines
	std::string lines_for;
	int text_wd = 0;
	int sel_scroll = 0;                  // list: the selected label scrolls if too long
	int center = 0;                      // list: the selection stays in the middle, the list moves
	int sel_lw = 0;                      // width of the selected label, 0 if it fits
	int sel_off = 0;
	int sel_row = -1;
	std::string video_path;              // video: plays after delay ms on the same file
	uint64_t video_start = 0;
	int video_delay = 1500;

	// last drawn state
	std::string cur, last, last_text;
	int last_sel = -1, last_top = -1, last_gen = -1, last_count = -1, last_date = -1;
};


static fe_theme theme;
static std::string theme_dir;
static std::string theme_file = "theme"; // theme.ini / theme_43.ini, detail.ini / detail_43.ini, screensaver.ini...
static int variant = 0;
static int has_43 = 0;
static std::vector<element> els;
static int loaded = 0;
static int base_w = 1280, base_h = 720;
static std::map<std::string, fe_font *> fonts;

static int cw = 0, ch = 0, vmul = 1;
static int text_wpct = 100;  // text width for a picture narrower or lower than its page (area of fe_render_draw)
static uint32_t *canvas = 0, *stat = 0;
static Imlib_Image canvas_img = 0, stat_img = 0;
static Imlib_Image dst = 0;
static uint32_t *dst_px = 0; // pixels of dst (canvas or stat), for blit_bitmap
static fe_rect bclip = {};   // clip of blit_bitmap (clip, narrowed by clip_to)
static int need_static = 1;
static fe_rect clip = {};   // area being redrawn
static uint64_t now = 0;     // time of the frame being drawn, ms
static int animating = 0;    // some element changes with the time

// Several renderers (list, detail view and screensaver, each for the HDMI and the CRT pages):
// fe_render_use() swaps the state above with the one of the chosen renderer.
struct rstate
{
	fe_theme theme;
	std::string theme_dir, theme_file = "theme";
	int variant = 0, has_43 = 0, loaded = 0;
	std::vector<element> els;
	int base_w = 1280, base_h = 720;
	std::map<std::string, fe_font *> fonts;
	int cw = 0, ch = 0, vmul = 1, text_wpct = 100;
	uint32_t *canvas = 0, *stat = 0;
	Imlib_Image canvas_img = 0, stat_img = 0, dst = 0;
	int need_static = 1;
	fe_rect clip = {};
	uint64_t now = 0;
	int animating = 0;
};
#define FE_RENDERERS 6
static rstate saved[FE_RENDERERS]; // saved[cur_inst] is unused while cur_inst is active
static int cur_inst = 0;
static int prof = 0;         // debug: time spent per element

static double ms_now()
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

void fe_render_debug(int on)
{
	prof = on;
}

// elements with layout=media are for the pictures of the games, layout=text
// replaces them with texts; the others are always there
static int layout_text = 0;

void fe_render_text_layout(int on)
{
	layout_text = on ? 1 : 0;
}

/////////////////////////////////////////////////////////////////////////////
// helpers

static void set_color(uint32_t c)
{
	imlib_context_set_color((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF, c >> 24);
}

static void fill(int x, int y, int w, int h, uint32_t c)
{
	if (w <= 0 || h <= 0 || !(c >> 24)) return;
	imlib_context_set_image(dst);
	imlib_context_set_blend(1);
	set_color(c);
	imlib_image_fill_rectangle(x, y, w, h);
}

static void free_image(Imlib_Image &img)
{
	if (!img) return;
	imlib_context_set_image(img);
	imlib_free_image();
	img = 0;
}

// theme file (relative to the theme) or absolute path
static std::string theme_path(const std::string &file)
{
	if (file.empty()) return file;
	return (file[0] == '/') ? file : theme.dir + "/" + file;
}

// theme images are decoded like the game images (libpng, libturbojpeg):
// they don't depend on the Imlib2 loaders
static std::shared_ptr<fe_bitmap> load_fit(const std::string &file, int w, int h, int fit)
{
	if (file.empty()) return 0;
	std::shared_ptr<fe_bitmap> bm = fe_media_load(theme_path(file), w, h, fit);
	if (!bm) fprintf(stderr, "frontier: can't load image %s\n", theme_path(file).c_str());
	return bm;
}

// Text is drawn with FreeType on the framebuffer's own grid: on a canvas with doubled
// lines (vmul 2, e.g. 640x240) the glyphs are rendered at half height and every row
// is doubled, so the averaging down gives back the hinted glyph. Hinting (light =
// vertical only, as default) puts the horizontal strokes on whole lines: without it
// the bar of an "A" falls between two lines and becomes two dim lines on a CRT.
struct fe_glyph
{
	int ok = 0;          // rendered
	int adv = 0;         // advance, 26.6
	int lsb = 0, rsb = 0; // hinting deltas, 26.6
	int left = 0, top = 0, w = 0, h = 0;
	std::vector<uint8_t> cov;  // coverage w*h
};

struct fe_font
{
	FT_Face face = 0;
	int vmul = 1;
	int asc = 0, desc = 0;    // framebuffer lines
	int32_t load = 0;
	FT_Render_Mode mode = FT_RENDER_MODE_NORMAL;
	std::map<uint32_t, fe_glyph> glyphs;
};

static FT_Library ft_lib = 0;

static uint32_t utf8_next(const std::string &s, size_t &i)
{
	unsigned char c = s[i++];
	if (c < 0x80) return c;
	int n = (c >= 0xF0) ? 3 : (c >= 0xE0) ? 2 : (c >= 0xC0) ? 1 : 0;
	uint32_t cp = c & (0x3F >> n);
	while (n-- > 0 && i < s.size() && ((unsigned char)s[i] & 0xC0) == 0x80) cp = (cp << 6) | (s[i++] & 0x3F);
	return cp;
}

// glyph of the font; with render=0 only the advance is needed
static fe_glyph &glyph_get(fe_font *f, uint32_t cp, int render)
{
	fe_glyph &g = f->glyphs[cp];
	if (g.ok || (!render && g.adv)) return g;

	FT_UInt gi = FT_Get_Char_Index(f->face, cp);
	if (FT_Load_Glyph(f->face, gi, f->load))
	{
		g.ok = 1;
		return g;
	}
	FT_GlyphSlot sl = f->face->glyph;
	g.adv = sl->advance.x;
	g.lsb = sl->lsb_delta;
	g.rsb = sl->rsb_delta;
	if (!render) return g;

	g.ok = 1;
	if (FT_Render_Glyph(sl, f->mode)) return g;
	const FT_Bitmap &b = sl->bitmap;
	g.left = sl->bitmap_left;
	g.top = sl->bitmap_top;
	g.w = b.width;
	g.h = b.rows;
	g.cov.resize(g.w * g.h);
	for (int y = 0; y < g.h; y++)
	{
		const uint8_t *row = b.buffer + y * b.pitch;
		for (int x = 0; x < g.w; x++)
		{
			g.cov[y * g.w + x] = (b.pixel_mode == FT_PIXEL_MODE_MONO) ? (((row[x >> 3] >> (7 - (x & 7))) & 1) ? 255 : 0) : row[x];
		}
	}
	return g;
}

// pen positions (pixels) of the glyphs of s, returns the width of the text
static int text_layout(fe_font *f, const std::string &s, std::vector<std::pair<uint32_t, int>> *pos, int render)
{
	int pen = 0, prev_rsb = 0, w = 0;
	FT_UInt prev = 0;
	int kern = FT_HAS_KERNING(f->face);
	for (size_t i = 0; i < s.size();)
	{
		uint32_t cp = utf8_next(s, i);
		fe_glyph &g = glyph_get(f, cp, render);
		if (kern)
		{
			FT_UInt gi = FT_Get_Char_Index(f->face, cp);
			if (prev && gi)
			{
				FT_Vector k;
				if (!FT_Get_Kerning(f->face, prev, gi, FT_KERNING_DEFAULT, &k)) pen += k.x;
			}
			prev = gi;
		}
		// hinting changed the side bearings: move by one pixel when they add up
		if (prev_rsb - g.lsb > 32) pen -= 64;
		else if (prev_rsb - g.lsb < -31) pen += 64;
		prev_rsb = g.rsb;
		int x = (pen + 32) >> 6;
		if (pos) pos->push_back({ cp, x });
		w = std::max(w, x + std::max(g.left + g.w, (g.adv + 63) >> 6));
		pen += g.adv;
	}
	return std::max(w, (pen + 63) >> 6);
}

// font from "fonts/DejaVuSans.ttf" (relative to the theme), px = em size in canvas
// pixels, wpct = width of the glyphs in percent (narrower: more text in a line)
static fe_font *font_get(const char *spec, int px, int wpct)
{
	if (!spec || !*spec) spec = theme.global.get("font", "");
	if (!*spec) return 0;
	if (!ft_lib && FT_Init_FreeType(&ft_lib)) return 0;

	std::string path = theme_path(spec);
	std::string hint = theme.global.get("font_hinting", "light");
	char key[64];
	wpct = std::max(30, std::min(300, wpct));
	snprintf(key, sizeof(key), "|%d|%d|%d|", px, wpct, vmul);
	std::string k = path + key + hint;
	auto it = fonts.find(k);
	if (it != fonts.end()) return it->second;

	fe_font *f = new fe_font;
	if (FT_New_Face(ft_lib, path.c_str(), 0, &f->face))
	{
		fprintf(stderr, "frontier: can't load font %s\n", path.c_str());
		delete f;
		fonts[k] = 0;
		return 0;
	}
	f->vmul = vmul;
	// the em is px canvas pixels wide and px canvas pixels (px / vmul lines) high
	FT_Set_Char_Size(f->face, px * 64 * wpct / 100, px * 64 / vmul, 72, 72);
	if (hint == "mono")
	{
		f->load = FT_LOAD_TARGET_MONO;
		f->mode = FT_RENDER_MODE_MONO;
	}
	else if (hint == "none") f->load = FT_LOAD_NO_HINTING;
	else if (hint == "full") f->load = FT_LOAD_TARGET_NORMAL;
	else f->load = FT_LOAD_TARGET_LIGHT;
	f->asc = (int)((f->face->size->metrics.ascender + 63) >> 6);
	f->desc = (int)((-f->face->size->metrics.descender + 63) >> 6);
	fonts[k] = f;
	return f;
}

static void font_free(fe_font *f)
{
	if (!f) return;
	FT_Done_Face(f->face);
	delete f;
}

static int text_w(fe_font *f, const std::string &s)
{
	if (!f || s.empty()) return 0;
	return text_layout(f, s, 0, 0) + 1;
}

static void utf8_pop(std::string &s)
{
	if (s.empty()) return;
	size_t n = s.size() - 1;
	while (n > 0 && ((unsigned char)s[n] & 0xC0) == 0x80) n--;
	s.erase(n);
}

// cuts the text with "..." to fit in maxw
static std::string fit_text(fe_font *f, const std::string &s, int maxw)
{
	int w = text_w(f, s);
	if (w <= maxw) return s;

	std::string t = s;
	// start near the right length, then remove one char at a time
	size_t guess = (size_t)((double)s.size() * maxw / w) + 2;
	if (guess < t.size())
	{
		t.erase(guess);
		while (!t.empty() && ((unsigned char)t.back() & 0xC0) == 0x80) t.pop_back();
		if (!t.empty() && ((unsigned char)t.back() & 0x80)) t.pop_back();
	}

	while (!t.empty())
	{
		utf8_pop(t);
		while (!t.empty() && t.back() == ' ') t.pop_back();
		if (text_w(f, t + "...") <= maxw) return t + "...";
	}
	return "";
}

static void blit_bitmap(const fe_bitmap &bm, int x, int y, int alpha = 255);

// Texts are rendered once (with their shadow) on a transparent bitmap and then
// blitted: drawing the glyphs is the slowest part of a list redraw.
static std::map<std::string, std::shared_ptr<fe_bitmap>> text_cache;
static size_t text_cache_bytes = 0;

// "over" of color c with coverage a (0..255) on a non premultiplied pixel
static inline void text_px(uint32_t &d, uint32_t c, uint32_t a)
{
	a = a * (c >> 24) / 255;
	if (!a) return;
	uint32_t da = d >> 24;
	if (a == 255 || !da)
	{
		d = (a << 24) | (c & 0xFFFFFF);
		return;
	}
	uint32_t ob = da * (255 - a) / 255;     // weight of the pixel below
	uint32_t oa = a + ob;
	uint32_t r = (((c >> 16) & 0xFF) * a + ((d >> 16) & 0xFF) * ob) / oa;
	uint32_t g = (((c >> 8) & 0xFF) * a + ((d >> 8) & 0xFF) * ob) / oa;
	uint32_t b = ((c & 0xFF) * a + (d & 0xFF) * ob) / oa;
	d = (oa << 24) | (r << 16) | (g << 8) | b;
}

// bitmap of s, with the ascent line at the top; on a canvas with doubled lines
// (vmul) it is drawn at the framebuffer's lines and every row is repeated
static std::shared_ptr<fe_bitmap> render_string(fe_font *f, const std::string &s, uint32_t color, uint32_t shadow, int sd)
{
	char k[64];
	snprintf(k, sizeof(k), "%p|%08X|%08X|%d|", (void *)f, color, shadow, sd);
	std::string key = k + s;
	auto it = text_cache.find(key);
	if (it != text_cache.end()) return it->second;

	std::vector<std::pair<uint32_t, int>> pos;
	int tw = text_layout(f, s, &pos, 1);
	int sx = (shadow >> 24) ? std::max(0, sd) : 0;
	int sy = sx ? std::max(1, sd / f->vmul) : 0;
	int w = tw + 1 + sx;
	int lh = f->asc + f->desc + 1 + sy;  // lines
	if (w <= 0 || lh <= 0 || w > 8192 || lh * f->vmul > 2048) return nullptr;

	std::vector<uint32_t> img(w * lh, 0);
	for (int pass = (sx ? 0 : 1); pass < 2; pass++)
	{
		uint32_t c = pass ? color : shadow;
		int ox = pass ? 0 : sx, oy = pass ? 0 : sy;
		for (auto &p : pos)
		{
			fe_glyph &g = glyph_get(f, p.first, 1);
			int x0 = p.second + g.left + ox, y0 = f->asc - g.top + oy;
			for (int y = 0; y < g.h; y++)
			{
				int yy = y0 + y;
				if (yy < 0 || yy >= lh) continue;
				for (int x = 0; x < g.w; x++)
				{
					int xx = x0 + x;
					uint8_t a = g.cov[y * g.w + x];
					if (a && xx >= 0 && xx < w) text_px(img[yy * w + xx], c, a);
				}
			}
		}
	}

	auto bm = std::make_shared<fe_bitmap>();
	bm->w = w;
	bm->h = lh * f->vmul;
	bm->px.resize(bm->w * bm->h);
	for (int y = 0; y < bm->h; y++) memcpy(bm->px.data() + y * w, img.data() + (y / f->vmul) * w, w * 4);

	if (text_cache_bytes > 16 * 1024 * 1024)
	{
		text_cache.clear();
		text_cache_bytes = 0;
	}
	text_cache[key] = bm;
	text_cache_bytes += bm->w * bm->h * 4 + key.size() + 64;
	return bm;
}

// y is moved up to a framebuffer line, as the rows of the bitmap
static void draw_string(fe_font *f, int x, int y, const std::string &s, uint32_t color, uint32_t shadow = 0, int sd = 1)
{
	if (!f || s.empty()) return;
	std::shared_ptr<fe_bitmap> bm = render_string(f, s, color, shadow, sd);
	if (f->vmul > 1) y -= ((y % f->vmul) + f->vmul) % f->vmul;
	if (bm) blit_bitmap(*bm, x, y);
}

// ${name} -> view variable
static std::string expand(const std::string &t, const fe_view *v)
{
	std::string out;
	size_t pos = 0;
	while (pos < t.size())
	{
		size_t b = t.find("${", pos);
		if (b == std::string::npos) break;
		size_t e = t.find('}', b);
		if (e == std::string::npos) break;

		out += t.substr(pos, b - pos);
		if (v)
		{
			auto it = v->vars.find(t.substr(b + 2, e - b - 2));
			if (it != v->vars.end()) out += it->second;
		}
		pos = e + 1;
	}
	out += t.substr(pos);
	return out;
}

static int parse_align(const char *s)
{
	if (!strcasecmp(s, "center") || !strcasecmp(s, "middle")) return 1;
	if (!strcasecmp(s, "right") || !strcasecmp(s, "bottom")) return 2;
	return 0;
}

static int parse_fit(const char *s)
{
	if (!strcasecmp(s, "cover")) return FIT_COVER;
	if (!strcasecmp(s, "stretch")) return FIT_STRETCH;
	return FIT_CONTAIN;
}

// bitmap (0xAARRGGBB) onto dst at x,y, only inside bclip; alpha = global opacity.
// Opaque bitmaps are copied, the others blended in fixed point.
static void blit_bitmap(const fe_bitmap &bm, int x, int y, int alpha)
{
	if (!dst_px || alpha <= 0) return;
	int x0 = std::max(x, bclip.x), y0 = std::max(y, bclip.y);
	int x1 = std::min(x + bm.w, std::min(bclip.x + bclip.w, cw));
	int y1 = std::min(y + bm.h, std::min(bclip.y + bclip.h, ch));
	x0 = std::max(x0, 0);
	y0 = std::max(y0, 0);
	if (x0 >= x1 || y0 >= y1) return;

	if (bm.opaque < 0)
	{
		bm.opaque = 1;
		for (uint32_t p : bm.px) if ((p >> 24) != 0xFF) { bm.opaque = 0; break; }
	}

	int n = x1 - x0;
	for (int yy = y0; yy < y1; yy++)
	{
		const uint32_t *sp = bm.px.data() + (yy - y) * bm.w + (x0 - x);
		uint32_t *dp = dst_px + yy * cw + x0;
		if (bm.opaque && alpha >= 255)
		{
			memcpy(dp, sp, n * 4);
			continue;
		}
		for (int i = 0; i < n; i++)
		{
			uint32_t sc = sp[i];
			uint32_t a = sc >> 24;
			if (alpha < 255) a = a * alpha / 255;
			if (!a) continue;
			if (a == 255)
			{
				dp[i] = sc | 0xFF000000;
				continue;
			}
			a += a >> 7; // 0..256
			uint32_t dc = dp[i];
			uint32_t rb = (((sc & 0xFF00FF) * a + (dc & 0xFF00FF) * (256 - a)) >> 8) & 0xFF00FF;
			uint32_t g = (((sc & 0x00FF00) * a + (dc & 0x00FF00) * (256 - a)) >> 8) & 0x00FF00;
			dp[i] = 0xFF000000 | rb | g;
		}
	}
}

// bitmap scaled to w x h (once: the result is kept by the caller)
static std::shared_ptr<fe_bitmap> scale_bitmap(const fe_bitmap &bm, int w, int h)
{
	// not with imlib: the bar scaled from an imlib image made with
	// imlib_create_image_using_data came out as garbage after a few rescales
	return fe_bitmap_scale(bm, w, h);
}

// position of a bitmap in the element with its alignment
// the part of a frame of an animation which isn't transparent (less memory: a figure
// which appears now and then in a large frame); 0 for an empty frame, dx/dy = its offset
static std::shared_ptr<fe_bitmap> crop_alpha(const std::shared_ptr<fe_bitmap> &bm, int &dx, int &dy)
{
	int x0 = bm->w, y0 = bm->h, x1 = -1, y1 = -1;
	for (int y = 0; y < bm->h; y++)
		for (int x = 0; x < bm->w; x++)
			if (bm->px[y * bm->w + x] >> 24)
			{
				x0 = std::min(x0, x); x1 = std::max(x1, x);
				y0 = std::min(y0, y); y1 = std::max(y1, y);
			}
	dx = dy = 0;
	if (x1 < 0) return 0;
	if (x0 == 0 && y0 == 0 && x1 == bm->w - 1 && y1 == bm->h - 1) return bm;
	auto out = std::make_shared<fe_bitmap>();
	out->w = x1 - x0 + 1;
	out->h = y1 - y0 + 1;
	out->px.resize(out->w * out->h);
	for (int y = 0; y < out->h; y++)
		memcpy(&out->px[y * out->w], &bm->px[(y0 + y) * bm->w + x0], out->w * 4);
	dx = x0;
	dy = y0;
	return out;
}

static void place(const element &e, const fe_bitmap &bm, int *x, int *y)
{
	*x = e.x + (e.w - bm.w) * e.align / 2;
	*y = e.y + (e.h - bm.h) * e.valign / 2;
}

// limits the drawing to the element too (scrolling text)
static void clip_to(const element &e)
{
	int x0 = std::max(clip.x, e.x), y0 = std::max(clip.y, e.y);
	int x1 = std::min(clip.x + clip.w, e.x + e.w), y1 = std::min(clip.y + clip.h, e.y + e.h);
	imlib_context_set_cliprect(x0, y0, std::max(1, x1 - x0), std::max(1, y1 - y0));
	bclip = { x0, y0, std::max(0, x1 - x0), std::max(0, y1 - y0) };
}

static void clip_restore()
{
	imlib_context_set_cliprect(clip.x, clip.y, clip.w, clip.h);
	bclip = clip;
}

// "${media.box}|${media.snap}|img/nobox.png": first one which is not empty,
// plain names are files of the theme
static std::string resolve_src(const std::string &src, const fe_view *v)
{
	size_t pos = 0;
	while (pos <= src.size())
	{
		size_t end = src.find('|', pos);
		if (end == std::string::npos) end = src.size();
		std::string alt = src.substr(pos, end - pos);
		while (!alt.empty() && alt[0] == ' ') alt.erase(0, 1);
		while (!alt.empty() && alt.back() == ' ') alt.pop_back();

		if (alt.find("${") != std::string::npos)
		{
			std::string p = expand(alt, v);
			if (!p.empty()) return p;
		}
		else if (!alt.empty())
		{
			return (alt[0] == '/') ? alt : theme.dir + "/" + alt;
		}
		pos = end + 1;
	}
	return "";
}

static int intersects(const element &e, const fe_rect &r)
{
	return e.x < r.x + r.w && r.x < e.x + e.w && e.y < r.y + r.h && r.y < e.y + e.h;
}

/////////////////////////////////////////////////////////////////////////////
// elements

// e.cur -> e.lines (wrapped if needed), e.text_wd
static void prepare_text(element &e)
{
	if (e.lines_for == e.cur && !e.lines.empty()) return;
	e.lines_for = e.cur;
	e.lines.clear();
	e.text_wd = 0;
	if (!e.font) return;

	if (e.wrap)
	{
		std::string line;
		size_t pos = 0;
		while (pos <= e.cur.size())
		{
			size_t end = e.cur.find_first_of(" \n", pos);
			if (end == std::string::npos) end = e.cur.size();
			std::string word = e.cur.substr(pos, end - pos);
			std::string test = line.empty() ? word : line + " " + word;
			if (!line.empty() && text_w(e.font, test) > e.w)
			{
				e.lines.push_back(line);
				line = word;
			}
			else line = test;

			if (end < e.cur.size() && e.cur[end] == '\n')
			{
				e.lines.push_back(line);
				line.clear();
			}
			pos = end + 1;
		}
		if (!line.empty()) e.lines.push_back(line);
	}
	else
	{
		e.lines.push_back(e.cur);
		e.text_wd = text_w(e.font, e.cur);
	}
}

// pixels the text is longer than its area (0 = it fits)
static int text_overflow(element &e)
{
	prepare_text(e);
	if (e.scroll == SCROLL_H) return std::max(0, e.text_wd - e.w);
	if (e.scroll == SCROLL_V) return std::max(0, (int)e.lines.size() * e.font_h - e.h);
	return 0;
}

static void draw_text_el(element &e)
{
	if (!e.font || e.cur.empty()) return;
	prepare_text(e);

	if (e.scroll == SCROLL_H && text_overflow(e))
	{
		// marquee: two copies, one after the other
		int gap = e.font_h * 3;
		int y = e.y + (e.h - e.font_h) * e.valign / 2;
		clip_to(e);
		draw_string(e.font, e.x - e.offset, y - e.font_off, e.cur, e.color, e.shadow, e.shadow_d);
		draw_string(e.font, e.x - e.offset + e.text_wd + gap, y - e.font_off, e.cur, e.color, e.shadow, e.shadow_d);
		clip_restore();
		return;
	}

	if (e.scroll == SCROLL_V && text_overflow(e))
	{
		int total = e.lines.size() * e.font_h;
		int gap = e.font_h * 2;
		clip_to(e);
		for (int copy = 0; copy < 2; copy++)
		{
			int y = e.y - e.offset + copy * (total + gap);
			for (auto &l : e.lines)
			{
				if (y + e.font_h > e.y && y < e.y + e.h)
				{
					int w = text_w(e.font, l);
					int x = e.x + (e.w - w) * e.align / 2;
					draw_string(e.font, x, y - e.font_off, fit_text(e.font, l, e.w), e.color, e.shadow, e.shadow_d);
				}
				y += e.font_h;
			}
		}
		clip_restore();
		return;
	}

	std::vector<std::string> lines = e.lines;
	int maxl = std::max(1, e.h / e.font_h);
	if ((int)lines.size() > maxl)
	{
		lines.resize(maxl);
		lines.back() += "...";
	}

	int total = lines.size() * e.font_h;
	int y = e.y;
	if (e.valign == 1) y += (e.h - total) / 2;
	else if (e.valign == 2) y += e.h - total;

	for (auto &l : lines)
	{
		std::string s = fit_text(e.font, l, e.w);
		int w = text_w(e.font, s);
		int x = e.x;
		if (e.align == 1) x += (e.w - w) / 2;
		else if (e.align == 2) x += e.w - w;
		draw_string(e.font, x, y - e.font_off, s, e.color, e.shadow, e.shadow_d);
		y += e.font_h;
	}
}

static int list_rows(const element &e)
{
	return std::max(1, e.row_h ? e.h / e.row_h : 1);
}

static void draw_list(element &e, const fe_view *v)
{
	if (!v || !v->entries) return;

	const std::vector<fe_entry> &en = *v->entries;
	int count = en.size();
	int rows = list_rows(e);
	int sb = (count > rows && e.sb_w) ? e.sb_w + e.pad : 0;
	int row_w = e.w - sb;

	if (!count)
	{
		std::string s = fit_text(e.font, e.empty, row_w - 2 * e.pad);
		draw_string(e.font, e.x + e.pad, e.y + (e.row_h - e.font_h) / 2 - e.font_off, s, e.color, e.shadow, e.shadow_d);
	}

	for (int i = 0; i < rows; i++)
	{
		int idx = v->top + i;
		if (e.center && count > rows) idx = ((idx % count) + count) % count; // a ring around the selection
		if (idx < 0) continue;
		if (idx >= count) break;

		const fe_entry &it = en[idx];
		int y = e.y + i * e.row_h;
		if (y >= clip.y + clip.h || y + e.row_h <= clip.y) continue;
		int is_sel = (idx == v->sel);

		if (is_sel)
		{
			if (e.sel_img)
			{
				if (!e.sel_scaled || e.sel_scaled->w != row_w || e.sel_scaled->h != e.row_h) e.sel_scaled = scale_bitmap(*e.sel_img, row_w, e.row_h);
				if (e.sel_scaled) blit_bitmap(*e.sel_scaled, e.x, y);
			}
			else fill(e.x, y, row_w, e.row_h, e.sel_bg);
		}

		std::string tag;
		if (it.dir) tag = (it.name == "..") ? e.tag_up : it.tag.empty() ? e.tag_dir : it.tag + "  " + e.tag_dir; // My Lists: number of games
		else if (!it.tag.empty()) tag = it.tag;
		else if (v->show_date) tag = it.date;

		int ty = y + (e.row_h - e.font_h) / 2 - e.font_off;
		int right = e.x + row_w - e.pad;
		if (!tag.empty())
		{
			int tw = text_w(e.font, tag);
			draw_string(e.font, right - tw, ty, tag, is_sel ? e.sel_color : e.tag_color, e.shadow, e.shadow_d);
			right -= tw + e.font_h;
		}

		uint32_t c = is_sel ? e.sel_color : (it.dir ? e.dir_color : e.color);
		std::string label = (it.name == "..") ? std::string("..") : it.label;
		int avail = right - e.x - e.pad;
		if (is_sel)
		{
			int lw = text_w(e.font, label);
			e.sel_lw = (e.sel_scroll && lw > avail) ? lw : 0;
			e.sel_row = i;
		}

		if (is_sel && e.sel_lw)
		{
			// too long: it scrolls (see fe_render_draw)
			element area = e;
			area.x = e.x + e.pad;
			area.y = y;
			area.w = avail;
			area.h = e.row_h;
			clip_to(area);
			draw_string(e.font, area.x - e.sel_off, ty, label, c, e.shadow, e.shadow_d);
			draw_string(e.font, area.x - e.sel_off + e.sel_lw + e.font_h * 3, ty, label, c, e.shadow, e.shadow_d);
			clip_restore();
		}
		else
		{
			std::string &fit = e.fit_cache[std::to_string(avail) + "|" + label];
			if (fit.empty()) fit = fit_text(e.font, label, avail);
			if (e.fit_cache.size() > 4000) e.fit_cache.clear();
			draw_string(e.font, e.x + e.pad, ty, fit, c, e.shadow, e.shadow_d);
		}
	}

	if (sb)
	{
		int sx = e.x + e.w - e.sb_w;
		int sh = rows * e.row_h;
		int knob = std::max(e.sb_w * 2, sh * rows / count);
		int pos = e.center ? (sh - knob) * v->sel / std::max(1, count - 1) : (sh - knob) * v->top / std::max(1, count - rows);
		fill(sx, e.y, e.sb_w, sh, e.sb_color);
		fill(sx, e.y + pos, e.sb_w, knob, e.sb_knob);
	}
}

static void draw_element(element &e, const fe_view *v)
{
	if (!e.visible) return;

	switch (e.type)
	{
	case EL_RECT:
		if (e.gradient && e.h > 1)
		{
			for (int i = 0; i < e.h; i++)
			{
				uint32_t c = 0;
				for (int sh = 0; sh < 32; sh += 8)
				{
					int a = (e.color >> sh) & 0xFF;
					int b = (e.color2 >> sh) & 0xFF;
					c |= (uint32_t)(a + (b - a) * i / (e.h - 1)) << sh;
				}
				fill(e.x, e.y + i, e.w, 1, c);
			}
		}
		else fill(e.x, e.y, e.w, e.h, e.color);
		break;

	case EL_IMAGE:
		if (!e.frames.empty())
		{
			const frame &f = e.frames[e.frame_idx % e.frames.size()];
			if (f.bm) blit_bitmap(*f.bm, f.x, f.y);
		}
		else if (e.bm)
		{
			if (e.prev_bm && e.alpha < 255)
			{
				int x = e.x + (e.w - e.prev_bm->w) * e.align / 2;
				int y = e.y + (e.h - e.prev_bm->h) * e.valign / 2;
				blit_bitmap(*e.prev_bm, x, y);
			}
			int x = e.x + (e.w - e.bm->w) * e.align / 2;
			int y = e.y + (e.h - e.bm->h) * e.valign / 2;
			blit_bitmap(*e.bm, x, y, e.alpha);
		}
		else if (e.img) blit_bitmap(*e.img, e.img_x, e.img_y);
		break;

	case EL_TEXT:
		draw_text_el(e);
		break;

	case EL_BAR:
	{
		// progress bar: background, then value= percent of the width in color
		int pct = std::max(0, std::min(100, atoi(e.cur.c_str())));
		if (e.color2 >> 24) fill(e.x, e.y, e.w, e.h, e.color2);
		if (pct) fill(e.x, e.y, e.w * pct / 100, e.h, e.color);
		break;
	}

	case EL_LIST:
		draw_list(e, v);
		break;

	case EL_VIDEO:
		if (e.bm)
		{
			int x = e.x + (e.w - e.bm->w) * e.align / 2;
			int y = e.y + (e.h - e.bm->h) * e.valign / 2;
			blit_bitmap(*e.bm, x, y);
		}
		break;
	}
}

/////////////////////////////////////////////////////////////////////////////
// theme

static void compile()
{
	const fe_section &g = theme.global;
	int b[2];
	if (fe_parse_ints(g.get("base", "1280,720"), b, 2) == 2 && b[0] > 0 && b[1] > 0)
	{
		base_w = b[0];
		base_h = b[1];
	}
	// also accept "1280x720"
	const char *bs = g.get("base", "");
	if (strchr(bs, 'x') && sscanf(bs, "%dx%d", &b[0], &b[1]) == 2 && b[0] > 0 && b[1] > 0)
	{
		base_w = b[0];
		base_h = b[1];
	}

	uint32_t def_color = fe_parse_color(g.get("color", "#F0F0F0"), 0xFFF0F0F0);

	els.clear();
	for (auto &s : theme.elements)
	{
		const char *lay = s.get("layout", "");
		if (!strcasecmp(lay, layout_text ? "media" : "text")) continue;

		element e;
		e.sec = &s;

		const char *type = s.get("type", "rect");
		if (!strcasecmp(type, "image")) e.type = EL_IMAGE;
		else if (!strcasecmp(type, "text")) e.type = EL_TEXT;
		else if (!strcasecmp(type, "list")) e.type = EL_LIST;
		else if (!strcasecmp(type, "video")) e.type = EL_VIDEO;
		else if (!strcasecmp(type, "bar")) e.type = EL_BAR;
		else e.type = EL_RECT;

		fe_parse_ints(s.get("rect", "0,0,0,0"), e.base, 4);

		e.color = fe_parse_color(s.get("color", ""), (e.type == EL_RECT) ? 0xFF000000 : def_color);
		e.gradient = s.has("gradient");
		e.color2 = fe_parse_color(s.get("gradient", ""), e.color);
		if (e.type == EL_BAR) e.color2 = fe_parse_color(s.get("background", ""), 0); // bar: the empty part
		if (e.type == EL_BAR) e.cur = e.text; // a value without variables
		e.text = s.get((e.type == EL_IMAGE || e.type == EL_VIDEO) ? "src" : (e.type == EL_BAR) ? "value" : "text", "");
		e.fit = parse_fit(s.get("fit", "contain"));
		int media = (e.type == EL_IMAGE || e.type == EL_VIDEO);
		e.align = parse_align(s.get("align", media ? "center" : "left"));
		e.valign = parse_align(s.get("valign", (e.type == EL_TEXT || media) ? "middle" : "top"));
		e.video_delay = s.get_int("delay", 1500);
		e.cond_if = s.get("if", "");
		e.cond_ifnot = s.get("ifnot", "");

		// animations
		const char *tr = s.get("transition", "");
		if (!strncasecmp(tr, "fade", 4)) e.fade_ms = atoi(tr + 4) > 0 ? atoi(tr + 4) : 250;
		e.fps = std::max(1, s.get_int("fps", 10));
		const char *sc = s.get("scroll", "");
		if (!strcasecmp(sc, "horizontal") || !strcasecmp(sc, "marquee")) e.scroll = SCROLL_H;
		else if (!strcasecmp(sc, "vertical")) e.scroll = SCROLL_V;
		e.sel_scroll = s.get_int("sel_scroll", 0);
		e.center = s.get_int("center", 0);
		e.wrap = s.get_int("wrap", 0);
		e.shadow = fe_parse_color(s.get("shadow", g.get("shadow", "")), 0);

		e.sel_bg = fe_parse_color(s.get("sel_background", "#2F5FB3"), 0xFF2F5FB3);
		e.sel_color = fe_parse_color(s.get("sel_color", "#FFFFFF"), 0xFFFFFFFF);
		e.dir_color = fe_parse_color(s.get("dir_color", ""), e.color);
		e.tag_color = fe_parse_color(s.get("tag_color", ""), e.color);
		e.sb_color = fe_parse_color(s.get("scrollbar_color", "#3A4A66"), 0xFF3A4A66);
		e.sb_knob = fe_parse_color(s.get("scrollbar_knob", "#8CA0C0"), 0xFF8CA0C0);
		e.tag_dir = s.get("tag_dir", "");
		e.tag_up = s.get("tag_up", "");
		e.empty = s.get("empty_text", "");

		e.dynamic = (e.type == EL_LIST) || e.text.find("${") != std::string::npos ||
			e.cond_if.find("${") != std::string::npos || e.cond_ifnot.find("${") != std::string::npos ||
			(e.type == EL_IMAGE && e.text.find('*') != std::string::npos) || e.scroll || e.type == EL_VIDEO;
		els.push_back(e);
	}

	// static elements drawn above a dynamic one must be redrawn with it
	for (size_t i = 0; i < els.size(); i++)
	{
		if (els[i].dynamic) continue;
		for (size_t j = 0; j < i; j++)
		{
			if (!els[j].dynamic) continue;
			fe_rect r = { els[j].base[0], els[j].base[1], els[j].base[2], els[j].base[3] };
			element tmp = els[i];
			tmp.x = tmp.base[0]; tmp.y = tmp.base[1]; tmp.w = tmp.base[2]; tmp.h = tmp.base[3];
			if (intersects(tmp, r)) els[i].overlay = 1;
		}
	}
}

// positions and sizes for the current canvas
static void layout()
{
	const double sx = (double)cw / base_w;
	const double sy = (double)ch / base_h;
	const fe_section &g = theme.global;

	for (auto &e : els)
	{
		const fe_section &s = *e.sec;
		e.x = lround(e.base[0] * sx);
		e.y = lround(e.base[1] * sy);
		e.w = lround((e.base[0] + e.base[2]) * sx) - e.x;
		e.h = lround((e.base[1] + e.base[3]) * sy) - e.y;

		if (e.type == EL_TEXT || e.type == EL_LIST)
		{
			int px = std::max(6, (int)lround(s.get_int("size", g.get_int("size", 24)) * sy));
			e.font = font_get(s.get("font", ""), px, s.get_int("font_width", g.get_int("font_width", 100)) * text_wpct / 100);
			e.font_h = px;
			e.font_off = 0;
			if (e.font && e.font->asc + e.font->desc > 0) e.font_h = (e.font->asc + e.font->desc) * vmul;
			e.shadow_d = std::max(1, (int)lround(s.get_int("shadow_offset", 2) * sy));
		}

		if (e.type == EL_LIST)
		{
			e.row_h = std::max(e.font_h + 1, (int)lround(s.get_int("row_height", 0) * sy));
			e.pad = lround(s.get_int("padding", 8) * sx);
			e.sb_w = s.get_int("scrollbar_width", 6) ? std::max(1, (int)lround(s.get_int("scrollbar_width", 6) * sx)) : 0;
		}

		// speeds in base pixels per second
		int def_speed = (e.scroll == SCROLL_V) ? 20 : 60;
		e.scroll_speed = std::max(1, (int)lround(s.get_int("scroll_speed", def_speed) * ((e.scroll == SCROLL_V) ? sy : sx)));
		e.scroll_delay = s.get_int("scroll_delay", (e.scroll == SCROLL_V) ? 3000 : 1500);
		e.lines_for.clear();
		e.lines.clear();

		if (e.type == EL_IMAGE && e.text.find('*') != std::string::npos)
		{
			// animation: all the files matching the pattern, in name order
			e.frames.clear();
			glob_t gl;
			if (!glob(theme_path(e.text).c_str(), 0, 0, &gl))
			{
				for (size_t i = 0; i < gl.gl_pathc; i++)
				{
					frame f;
					f.bm = load_fit(gl.gl_pathv[i], e.w, e.h, e.fit);
					if (!f.bm) continue;
					place(e, *f.bm, &f.x, &f.y);
					int dx, dy;
					f.bm = crop_alpha(f.bm, dx, dy); // 0 = an empty frame, drawn as nothing
					f.x += dx;
					f.y += dy;
					e.frames.push_back(f);
				}
				globfree(&gl);
			}
		}
		else if (e.type == EL_IMAGE && !e.dynamic)
		{
			e.img = load_fit(e.text, e.w, e.h, e.fit);
			if (e.img) place(e, *e.img, &e.img_x, &e.img_y);
		}

		if (e.type == EL_LIST) e.sel_img = load_fit(s.get("sel_image", ""), e.w, e.row_h, FIT_STRETCH);

		e.last.clear();
		e.last_sel = -1;
	}

	need_static = 1;
}

static void build_static()
{
	dst = stat_img;
	dst_px = stat;
	imlib_context_set_cliprect(0, 0, 0, 0);
	clip = bclip = { 0, 0, cw, ch };

	const fe_section &g = theme.global;
	uint32_t bgc = fe_parse_color(g.get("background_color", "#000000"), 0xFF000000) | 0xFF000000;
	fill(0, 0, cw, ch, bgc);

	std::shared_ptr<fe_bitmap> bg = load_fit(g.get("background", ""), cw, ch, parse_fit(g.get("background_fit", "cover")));
	if (bg) blit_bitmap(*bg, (cw - bg->w) / 2, (ch - bg->h) / 2);

	for (auto &e : els)
	{
		if (e.dynamic || e.overlay) continue;
		e.cur = e.text;
		draw_element(e, 0);
	}

	need_static = 0;
}

static void free_canvas()
{
	free_image(canvas_img);
	free_image(stat_img);
	free(canvas);
	free(stat);
	canvas = stat = 0;
	cw = ch = 0;
}

/////////////////////////////////////////////////////////////////////////////
// public interface

static void free_theme()
{
	for (auto &e : els)
	{
		e.img.reset();
		e.sel_img.reset();
		e.sel_scaled.reset();
		e.fit_cache.clear();
		e.frames.clear();
		e.bm.reset();
		e.prev_bm.reset();
	}
	els.clear();

	text_cache.clear(); // keys use the font pointers
	text_cache_bytes = 0;
	for (auto &f : fonts) font_free(f.second);
	fonts.clear();

	theme = fe_theme();
}

// variant 1 = theme_43.ini, for 4:3 screens
static int load_variant(int v)
{
	free_theme();
	std::string file = theme_file + (v ? "_43.ini" : ".ini");
	if (!fe_theme_load(theme, theme_dir, file.c_str())) return 0;
	variant = v;
	compile();
	fprintf(stderr, "frontier: theme '%s' (%s) loaded, %d elements\n", fe_render_theme_name(), file.c_str(), (int)els.size());
	return 1;
}

void fe_render_unload()
{
	free_theme();
	free_canvas();
	loaded = 0;
}

int fe_render_load(const std::string &dir, const char *file)
{
	fe_render_unload();
	theme_dir = dir;
	theme_file = file;
	has_43 = 0;

	FILE *fp = fopen((dir + "/" + theme_file + "_43.ini").c_str(), "r");
	if (fp)
	{
		has_43 = 1;
		fclose(fp);
	}

	if (!load_variant(0))
	{
		fprintf(stderr, "frontier: no %s.ini in %s\n", file, dir.c_str());
		return 0;
	}

	loaded = 1;
	return 1;
}

static void swap_state(rstate &other)
{
	std::swap(theme, other.theme);
	std::swap(theme_file, other.theme_file);
	std::swap(theme_dir, other.theme_dir);
	std::swap(variant, other.variant);
	std::swap(has_43, other.has_43);
	std::swap(loaded, other.loaded);
	std::swap(els, other.els);
	std::swap(base_w, other.base_w);
	std::swap(base_h, other.base_h);
	std::swap(fonts, other.fonts);
	std::swap(cw, other.cw);
	std::swap(ch, other.ch);
	std::swap(vmul, other.vmul);
	std::swap(text_wpct, other.text_wpct);
	std::swap(canvas, other.canvas);
	std::swap(stat, other.stat);
	std::swap(canvas_img, other.canvas_img);
	std::swap(stat_img, other.stat_img);
	std::swap(dst, other.dst);
	std::swap(need_static, other.need_static);
	std::swap(clip, other.clip);
	std::swap(now, other.now);
	std::swap(animating, other.animating);
}

void fe_render_use(int inst)
{
	if (inst == cur_inst || inst < 0 || inst >= FE_RENDERERS) return;
	swap_state(saved[cur_inst]);
	swap_state(saved[inst]);
	cur_inst = inst;
}

int fe_render_active()
{
	return loaded;
}

int fe_render_animating()
{
	return loaded && animating;
}

const char *fe_render_theme_name()
{
	return theme.global.get("name", "");
}

static int images_loading = 0; // the last fe_render_draw() had pictures not loaded yet

int fe_render_loading()
{
	return images_loading;
}

int fe_render_draw(fe_view &v, uint32_t *buf, int w, int h, int full, std::vector<fe_rect> &dirty, const fe_rect *area)
{
	images_loading = 0;
	if (!loaded || w <= 0 || h <= 0) return 0;

	// the picture: all of buf, or area (may go past the edges of buf)
	fe_rect a = area ? *area : fe_rect{ 0, 0, w, h };
	if (a.w <= 0 || a.h <= 0) return 0;
	int nm = (w >= 2 * h) ? 2 : 1;
	if (!canvas || a.w != cw || a.h * nm != ch)
	{
		free_canvas();
		vmul = nm;
		cw = a.w;
		ch = a.h * nm;
		// narrower than high (relative to the page): the text gets narrower too
		text_wpct = (int)lround(100.0 * a.w * h / ((double)a.h * w));
		canvas = (uint32_t *)malloc(cw * ch * 4);
		stat = (uint32_t *)malloc(cw * ch * 4);
		if (!canvas || !stat)
		{
			fprintf(stderr, "frontier: out of memory\n");
			free_canvas();
			return 0;
		}

		// 4:3 screens use theme_43.ini when the theme has it
		int want = (has_43 && cw * 100 < ch * 155) ? 1 : 0;
		if (want != variant && !load_variant(want)) load_variant(0);

		canvas_img = imlib_create_image_using_data(cw, ch, canvas);
		stat_img = imlib_create_image_using_data(cw, ch, stat);
		imlib_context_set_image(canvas_img);
		imlib_image_set_has_alpha(0);
		imlib_context_set_image(stat_img);
		imlib_image_set_has_alpha(0);

		layout();
		full = 1;
	}

	if (need_static)
	{
		build_static();
		full = 1;
	}

	// update the state of the dynamic elements, collect what changed
	now = v.time_ms;
	animating = 0;
	std::vector<fe_rect> rects;
	int list_done = 0;
	for (auto &e : els)
	{
		if (!e.dynamic) continue;

		int changed = 0;
		if (e.type == EL_LIST)
		{
			int count = v.entries ? v.entries->size() : 0;
			int rows = list_rows(e);
			if (!list_done)
			{
				// the first list drives the scrolling
				if (v.sel >= count) v.sel = count ? count - 1 : 0;
				if (e.center) v.top = v.sel - rows / 2; // may be < 0: empty rows or the end of the ring
				else
				{
					if (v.sel < v.top) v.top = v.sel;
					if (v.sel >= v.top + rows) v.top = v.sel - rows + 1;
					if (v.top > count - rows) v.top = count - rows;
					if (v.top < 0) v.top = 0;
				}
				v.rows = rows;
				list_done = 1;
			}

			changed = (e.last_sel != v.sel || e.last_top != v.top || e.last_gen != v.list_gen || e.last_count != count || e.last_date != v.show_date);
			if (changed)
			{
				e.scroll_start = now;
				e.sel_off = 0;
				e.sel_lw = 0;
			}

			if (changed && e.last_top == v.top && e.last_gen == v.list_gen && e.last_count == count && e.last_date == v.show_date)
			{
				// only the selection moved inside the page: redraw the two rows
				rects.push_back({ e.x, e.y + (e.last_sel - v.top) * e.row_h, e.w, e.row_h });
				rects.push_back({ e.x, e.y + (v.sel - v.top) * e.row_h, e.w, e.row_h });
				changed = 0;
			}
			else if (!changed && e.sel_lw && e.sel_row >= 0)
			{
				// the selected label is too long: it scrolls after a while
				animating = 1;
				int off = 0;
				uint64_t t = now - e.scroll_start;
				if (t > (uint64_t)e.scroll_delay) off = (int)(((t - e.scroll_delay) * e.scroll_speed / 1000) % (e.sel_lw + e.font_h * 3));
				if (off != e.sel_off)
				{
					e.sel_off = off;
					rects.push_back({ e.x, e.y + e.sel_row * e.row_h, e.w, e.row_h });
				}
			}

			e.last_sel = v.sel;
			e.last_top = v.top;
			e.last_gen = v.list_gen;
			e.last_count = count;
			e.last_date = v.show_date;
		}
		else
		{
			e.visible = (e.cond_if.empty() || !expand(e.cond_if, &v).empty()) && (e.cond_ifnot.empty() || expand(e.cond_ifnot, &v).empty());
			std::string key;
			if (e.type == EL_IMAGE && !e.frames.empty())
			{
				e.frame_idx = (e.frames.size() > 1) ? (int)((now * e.fps / 1000) % e.frames.size()) : 0;
				if (e.frames.size() > 1 && e.visible) animating = 1;
				key = "#f" + std::to_string(e.frame_idx);
			}
			else if (e.type == EL_VIDEO)
			{
				// starts after delay ms on the same file, the thread gives the frames
				std::string path = e.visible ? resolve_src(e.text, &v) : std::string();
				if (path != e.video_path)
				{
					e.video_path = path;
					e.video_start = now;
				}

				int fr = -1;
				e.bm.reset();
				if (!path.empty()) // HDMI and CRT renderers: two sizes of the same video (fe_media)
				{
					animating = 1;
					if (now - e.video_start >= (uint64_t)e.video_delay) e.bm = fe_video_frame(path, e.w, e.h, e.fit, &fr);
				}
				key = path + "#v" + std::to_string(fr);
			}
			else if (e.type == EL_IMAGE)
			{
				std::string path = e.visible ? resolve_src(e.text, &v) : std::string();
				int loading = 0;
				std::shared_ptr<fe_bitmap> bm = path.empty() ? nullptr : fe_media_image(path, e.w, e.h, e.fit, &loading);
				if (loading) images_loading = 1;
				if (loading && e.bm) bm = e.bm; // the old one stays until the new one is ready
				if (bm != e.bm)
				{
					// fade from the previous image (or from the background)
					e.prev_bm = (bm && e.fade_ms) ? e.bm : nullptr;
					e.fade_start = now;
					e.bm = bm;
				}

				e.alpha = 255;
				if (e.bm && e.fade_ms && now - e.fade_start < (uint64_t)e.fade_ms)
				{
					e.alpha = std::min(255, (int)((now - e.fade_start) * 256 / e.fade_ms)) & ~15;
					animating = 1;
					images_loading = 1; // not the final picture yet
				}
				if (e.alpha == 255) e.prev_bm.reset();
				// the bitmap itself: the old one may stay while the new one loads
				key = path + "#" + std::to_string((uintptr_t)e.bm.get()) + "#a" + std::to_string(e.alpha);
			}
			else if (e.type == EL_BAR)
			{
				e.cur = expand(e.text, &v);
				key = e.cur;
			}
			else
			{
				e.cur = expand(e.text, &v);
				if (e.cur != e.last_text)
				{
					e.last_text = e.cur;
					e.scroll_start = now;
					e.offset = 0;
				}

				if (e.scroll && e.visible && text_overflow(e))
				{
					animating = 1;
					int period = (e.scroll == SCROLL_H) ? e.text_wd + e.font_h * 3 : (int)e.lines.size() * e.font_h + e.font_h * 2;
					uint64_t t = now - e.scroll_start;
					e.offset = (t > (uint64_t)e.scroll_delay) ? (int)(((t - e.scroll_delay) * e.scroll_speed / 1000) % period) : 0;
				}
				key = e.cur + "#o" + std::to_string(e.offset);
			}

			if (!e.visible) key = "\x01hidden";
			changed = (key != e.last);
			e.last = key;
		}

		if (changed) rects.push_back({ e.x, e.y, e.w, e.h });
	}

	if (full)
	{
		rects.clear();
		rects.push_back({ 0, 0, cw, ch });
		// black around a smaller picture
		for (int y = 0; y < h; y++)
		{
			if (y < a.y || y >= a.y + a.h) memset(buf + y * w, 0, w * 4);
			else
			{
				if (a.x > 0) memset(buf + y * w, 0, std::min(a.x, w) * 4);
				if (a.x + a.w < w) memset(buf + y * w + std::max(0, a.x + a.w), 0, (w - std::max(0, a.x + a.w)) * 4);
			}
		}
	}
	if (rects.empty()) return 0;

	dst = canvas_img;
	dst_px = canvas;
	dirty.clear();

	// overlapping areas are drawn once: merge them
	for (size_t i = 0; i < rects.size(); i++)
	{
		for (size_t j = i + 1; j < rects.size(); j++)
		{
			fe_rect &a = rects[i], &b = rects[j];
			if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h)
			{
				int x0 = std::min(a.x, b.x), y0 = std::min(a.y, b.y);
				int x1 = std::max(a.x + a.w, b.x + b.w), y1 = std::max(a.y + a.h, b.y + b.h);
				a = { x0, y0, x1 - x0, y1 - y0 };
				rects.erase(rects.begin() + j);
				j = i; // a grew: check again the others
			}
		}
	}

	std::map<std::string, double> pt;
	double t_all = prof ? ms_now() : 0, t0 = 0;
	for (auto r : rects)
	{
		int x1 = std::min(cw, r.x + r.w), y1 = std::min(ch, r.y + r.h);
		r.x = std::max(0, r.x);
		r.y = std::max(0, r.y);
		r.w = x1 - r.x;
		r.h = y1 - r.y;
		if (r.w <= 0 || r.h <= 0) continue;

		if (prof) t0 = ms_now();
		for (int y = r.y; y < y1; y++) memcpy(canvas + y * cw + r.x, stat + y * cw + r.x, r.w * 4);
		if (prof) pt["(static)"] += ms_now() - t0;

		imlib_context_set_cliprect(r.x, r.y, r.w, r.h);
		clip = bclip = r;
		for (auto &e : els)
		{
			if ((e.dynamic || e.overlay) && intersects(e, r))
			{
				if (e.overlay) e.cur = e.text;
				if (prof) t0 = ms_now();
				draw_element(e, &v);
				if (prof) pt[e.sec->name] += ms_now() - t0;
			}
		}
		if (prof) t0 = ms_now();

		// canvas -> framebuffer pixels (at the place of the picture, clipped to buf)
		int fy0 = r.y / vmul;
		int fy1 = (y1 + vmul - 1) / vmul;
		int cx0 = std::max(r.x, -a.x), cx1 = std::min(r.x + r.w, w - a.x);
		fy0 = std::max(fy0, -a.y);
		fy1 = std::min(fy1, h - a.y);
		if (cx0 >= cx1 || fy0 >= fy1) continue;
		for (int y = fy0; y < fy1; y++)
		{
			uint32_t *d = buf + (y + a.y) * w + a.x;
			if (vmul == 1)
			{
				const uint32_t *s = canvas + y * cw;
				for (int x = cx0; x < cx1; x++) d[x] = s[x] & 0xFFFFFF;
			}
			else
			{
				const uint32_t *p = canvas + (2 * y) * cw;
				const uint32_t *q = p + cw;
				for (int x = cx0; x < cx1; x++) d[x] = ((p[x] & 0xFEFEFE) >> 1) + ((q[x] & 0xFEFEFE) >> 1);
			}
		}

		dirty.push_back({ cx0 + a.x, fy0 + a.y, cx1 - cx0, fy1 - fy0 });
		if (prof) pt["(out)"] += ms_now() - t0;
	}
	imlib_context_set_cliprect(0, 0, 0, 0);

	if (prof && ms_now() - t_all > 10)
	{
		std::string line;
		char str[96];
		for (auto &p : pt) if (p.second >= 1) { snprintf(str, sizeof(str), " %s=%.1f", p.first.c_str(), p.second); line += str; }
		for (auto &r : rects) { snprintf(str, sizeof(str), " [%d,%d %dx%d]", r.x, r.y, r.w, r.h); line += str; }
		fprintf(stderr, "frontier: r%d %dx%d %.1f ms:%s\n", cur_inst, cw, ch, ms_now() - t_all, line.c_str());
	}
	return !dirty.empty();
}

