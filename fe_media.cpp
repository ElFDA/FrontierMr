// Game metadata and images for Frontier (see fe_media.h).
//
// The worker thread never touches Imlib2 (not thread safe, also used by
// video.cpp): PNG is decoded with libpng (already linked for Imlib2), JPEG
// with libturbojpeg loaded with dlopen. Images are scaled here and handed to
// the renderer as plain ARGB bitmaps. Videos: .mjv (JPEG sequence) or mp4
// decoded by frontier/lib/fe_av.so (FFmpeg, see tools/fe/fe_av), also loaded
// with dlopen, in a thread of their own on the core Main does not use.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include <dirent.h>
#include <dlfcn.h>
#include <pthread.h>
#include <sched.h>
#include <time.h>
#include <sys/stat.h>

#include <algorithm>

#include "fe_media.h"
#include "sxmlc.h"

#ifdef FE_PREVIEW
#include "lib/imlib2/Imlib2.h"
#endif

#define IMAGE_DELAY_MS 80                  // wait for the selection to settle
#define CACHE_BYTES    (24 * 1024 * 1024)  // decoded images kept in memory
#define MAX_PIXELS     (4096 * 4096)
#define MAX_FILE       (16 * 1024 * 1024)

static const char *media_types[] = { "box", "snap", "title", "marquee", "fanart", "video" };
// gamelist.xml tags of the same media
static const char *media_tags[] = { "thumbnail", "image", "titleshot", "marquee", "fanart", "video" };
#define MEDIA_TYPES (int)(sizeof(media_types) / sizeof(media_types[0]))

struct game
{
	std::map<std::string, std::string> fields; // gamelist tag -> text
};

struct sysdata
{
	std::map<std::string, game> games;                      // lowercase key
	std::map<std::string, std::string> files[MEDIA_TYPES];  // lowercase file name -> real name
	uint64_t used = 0;                                      // last get_sys()
};
// systems kept in memory: the screensaver goes through all of them (41 MB of
// gamelists on the test MiSTer), the least recently used is forgotten
#define MAX_SYSTEMS 12

static std::string root;
static int threaded = 0;
static int started = 0;
static pthread_t thread;
static pthread_mutex_t mtx = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cond = PTHREAD_COND_INITIALIZER;

// worker only
static std::map<std::string, sysdata> systems;

// shared, under mtx
static std::string sel_sys, sel_key;
static int sel_gen = 0;
static int info_gen = -1;
static std::map<std::string, std::string> info_vars;
static int reset_req = 0;
static int changed_flag = 0;

struct img_req
{
	std::string id, path;
	int w, h, fit;
	uint64_t time;
};
static std::vector<img_req> pending;

struct cache_item
{
	std::shared_ptr<fe_bitmap> bm;  // null if the file can't be decoded
	uint64_t used;
	size_t bytes;
};
static std::map<std::string, cache_item> cache;
static size_t cache_bytes = 0;
static uint64_t use_counter = 0;

/////////////////////////////////////////////////////////////////////////////
// helpers

static uint64_t now_ms()
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

#ifndef FE_PREVIEW
static uint64_t now_us()
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000;
}
#endif

static std::string lower(std::string s)
{
	for (auto &c : s) c = tolower((unsigned char)c);
	return s;
}

// "./roms/1942 (Revision B).mra" -> "1942 (revision b)"
static std::string path_key(const std::string &path)
{
	size_t b = path.find_last_of("/\\");
	std::string name = (b == std::string::npos) ? path : path.substr(b + 1);
	size_t dot = name.rfind('.');
	if (dot != std::string::npos && dot > 0) name.erase(dot);
	return lower(name);
}

static void put_utf8(std::string &out, uint32_t c)
{
	if (c < 0x80) out += (char)c;
	else if (c < 0x800) { out += (char)(0xC0 | (c >> 6)); out += (char)(0x80 | (c & 0x3F)); }
	else if (c < 0x10000) { out += (char)(0xE0 | (c >> 12)); out += (char)(0x80 | ((c >> 6) & 0x3F)); out += (char)(0x80 | (c & 0x3F)); }
	else { out += (char)(0xF0 | (c >> 18)); out += (char)(0x80 | ((c >> 12) & 0x3F)); out += (char)(0x80 | ((c >> 6) & 0x3F)); out += (char)(0x80 | (c & 0x3F)); }
}

// XML entities
static std::string entities(const std::string &s)
{
	std::string out;
	for (size_t i = 0; i < s.size(); i++)
	{
		if (s[i] == '\r') continue; // CR LF of some texts: the CR would be drawn as a box
		if (s[i] != '&')
		{
			out += s[i];
			continue;
		}

		size_t e = s.find(';', i);
		if (e == std::string::npos || e - i > 10)
		{
			out += s[i];
			continue;
		}

		std::string ent = s.substr(i + 1, e - i - 1);
		if (ent == "amp") out += '&';
		else if (ent == "lt") out += '<';
		else if (ent == "gt") out += '>';
		else if (ent == "quot") out += '"';
		else if (ent == "apos") out += '\'';
		else if (ent.size() > 1 && ent[0] == '#') put_utf8(out, (ent[1] == 'x' || ent[1] == 'X') ? strtoul(ent.c_str() + 2, 0, 16) : strtoul(ent.c_str() + 1, 0, 10));
		else out += "&" + ent + ";";
		i = e;
	}
	return out;
}

// XML entities and surrounding blanks; entities twice, as some scraped texts
// have them ("&amp;quot;" from Arcade Database)
static std::string xml_text(const std::string &s)
{
	std::string out = entities(s);
	if (out.find('&') != std::string::npos) out = entities(out);

	size_t b = out.find_first_not_of(" \t\r\n");
	size_t e = out.find_last_not_of(" \t\r\n");
	return (b == std::string::npos) ? std::string() : out.substr(b, e - b + 1);
}

/////////////////////////////////////////////////////////////////////////////
// gamelist.xml

struct parse_ctx
{
	sysdata *sys;
	int in_game;
	game cur;
	std::string tag, text;
};

static int gamelist_event(XMLEvent event, const XMLNode *node, SXML_CHAR *text, const int, SAX_Data *sd)
{
	parse_ctx *c = (parse_ctx *)sd->user;

	switch (event)
	{
	case XML_EVENT_START_NODE:
		if (!strcasecmp(node->tag, "game"))
		{
			c->in_game = 1;
			c->cur = game();
		}
		else if (c->in_game)
		{
			c->tag = lower(node->tag);
			c->text.clear();
		}
		break;

	case XML_EVENT_TEXT:
		if (c->in_game && !c->tag.empty()) c->text += text;
		break;

	case XML_EVENT_END_NODE:
		if (!strcasecmp(node->tag, "game"))
		{
			auto it = c->cur.fields.find("path");
			if (it != c->cur.fields.end() && !it->second.empty()) c->sys->games[path_key(it->second)] = c->cur;
			c->in_game = 0;
		}
		else if (c->in_game && !c->tag.empty())
		{
			c->cur.fields[c->tag] = xml_text(c->text);
			c->tag.clear();
		}
		break;

	default:
		break;
	}

	return true;
}

static sysdata &get_sys(const std::string &name)
{
	static uint64_t use = 0;
	auto it = systems.find(name);
	if (it != systems.end())
	{
		it->second.used = ++use;
		return it->second;
	}

	if (systems.size() >= MAX_SYSTEMS)
	{
		auto old = systems.begin();
		for (auto i = systems.begin(); i != systems.end(); ++i) if (i->second.used < old->second.used) old = i;
		systems.erase(old);
	}
	sysdata &s = systems[name];
	s.used = ++use;
	uint64_t t0 = now_ms();

	std::string gl = root + "/gamelists/" + name + "/gamelist.xml";
	struct stat st;
	if (!stat(gl.c_str(), &st))
	{
		parse_ctx ctx = {};
		ctx.sys = &s;
		SAX_Callbacks sax;
		SAX_Callbacks_init(&sax);
		sax.all_event = gamelist_event;
		XMLDoc_parse_file_SAX(gl.c_str(), &sax, &ctx);
	}

	int files = 0;
	for (int t = 0; t < MEDIA_TYPES; t++)
	{
		std::string dir = root + "/media/" + name + "/" + media_types[t];
		DIR *d = opendir(dir.c_str());
		if (!d) continue;
		while (struct dirent *de = readdir(d))
		{
			if (de->d_name[0] == '.') continue;
			s.files[t][lower(de->d_name)] = de->d_name;
			files++;
		}
		closedir(d);
	}

	fprintf(stderr, "frontier: media '%s': %d games, %d files, %d ms\n", name.c_str(), (int)s.games.size(), files, (int)(now_ms() - t0));
	return s;
}

static int fev_load();

static std::string media_path(sysdata &s, const std::string &sys, const std::string &lkey, int type, const game *g)
{
	// path written in the gamelist (relative to the gamelist folder)
	if (g)
	{
		auto it = g->fields.find(media_tags[type]);
		if (it != g->fields.end() && !it->second.empty())
		{
			std::string p = it->second;
			if (p.compare(0, 2, "./") == 0) p = root + "/gamelists/" + sys + "/" + p.substr(2);
			else if (p[0] != '/') p = root + "/gamelists/" + sys + "/" + p;
			struct stat st;
			int mp4 = p.size() > 4 && !strcasecmp(p.c_str() + p.size() - 4, ".mp4");
			if ((!mp4 || fev_load()) && !stat(p.c_str(), &st)) return p;
		}
	}

	// media/<system>/<type>/<key>.<ext>
	static const char *img_ext[] = { ".png", ".jpg", ".jpeg", 0 };
	static const char *vid_ext[] = { ".mjv", ".mp4", 0 };  // .mjv is lighter to play
	static const char *mjv_ext[] = { ".mjv", 0 };
	const char **ext = strcmp(media_types[type], "video") ? img_ext : fev_load() ? vid_ext : mjv_ext;
	for (; *ext; ext++)
	{
		auto it = s.files[type].find(lkey + *ext);
		if (it != s.files[type].end()) return root + "/media/" + sys + "/" + media_types[type] + "/" + it->second;
	}
	return "";
}

// key: "name" or "name\nother\n...": the first one with data in the gamelist (the
// other versions of a game, when the one chosen hasn't been scraped)
static void make_vars(const std::string &sys, const std::string &key, std::map<std::string, std::string> &vars)
{
	sysdata &s = get_sys(sys);
	std::string lkey = lower(key.substr(0, key.find('\n')));
	auto it = s.games.find(lkey);
	for (size_t p = key.find('\n'); it == s.games.end() && p != std::string::npos; p = key.find('\n', p + 1))
	{
		std::string k = lower(key.substr(p + 1, key.find('\n', p + 1) - p - 1));
		auto alt = s.games.find(k);
		if (alt == s.games.end()) continue;
		it = alt;
		lkey = k;
	}
	const game *g = (it != s.games.end()) ? &it->second : 0;

	if (g)
	{
		static const char *fields[] = { "desc", "developer", "publisher", "genre", "players", "rating" };
		for (auto f : fields)
		{
			auto fi = g->fields.find(f);
			if (fi != g->fields.end()) vars[std::string("game.") + f] = fi->second;
		}

		// other tags as they are: ${game.cpu}, ${game.memory}... of the systems
		static const char *skip[] = { "path", "name", "releasedate", "image", "thumbnail", "titleshot", "marquee", "fanart", "video" };
		for (auto &f : g->fields)
		{
			if (vars.count("game." + f.first)) continue;
			int known = 0;
			for (auto k : skip) known |= (f.first == k);
			if (!known) vars["game." + f.first] = f.second;
		}

		auto fi = g->fields.find("name");
		if (fi != g->fields.end() && !fi->second.empty()) vars["game.title"] = fi->second;

		fi = g->fields.find("releasedate");
		if (fi != g->fields.end() && fi->second.size() >= 4)
		{
			const std::string &d = fi->second;
			vars["game.year"] = d.substr(0, 4);
			vars["game.released"] = (d.size() >= 8) ? d.substr(6, 2) + "/" + d.substr(4, 2) + "/" + d.substr(0, 4) : d.substr(0, 4);
		}

		fi = g->fields.find("rating");
		if (fi != g->fields.end() && !fi->second.empty())
		{
			int n = (int)(atof(fi->second.c_str()) * 5 + 0.5);
			std::string stars;
			for (int i = 0; i < 5; i++) stars += (i < n) ? "\xE2\x98\x85" : "\xE2\x98\x86";
			vars["game.stars"] = stars;
		}
	}

	for (int t = 0; t < MEDIA_TYPES; t++) vars[std::string("media.") + media_types[t]] = media_path(s, sys, lkey, t, g);
}

/////////////////////////////////////////////////////////////////////////////
// decoding

static int read_file(const std::string &path, std::vector<uint8_t> &data)
{
	FILE *fp = fopen(path.c_str(), "rb");
	if (!fp) return 0;
	fseek(fp, 0, SEEK_END);
	long size = ftell(fp);
	fseek(fp, 0, SEEK_SET);
	if (size <= 0 || size > MAX_FILE)
	{
		fclose(fp);
		return 0;
	}
	data.resize(size);
	int ok = fread(data.data(), 1, size, fp) == (size_t)size;
	fclose(fp);
	return ok;
}

#ifndef FE_PREVIEW

// libpng 1.6 "simplified API" (the library is linked for Imlib2)
extern "C"
{
	struct png_control;
	typedef struct
	{
		png_control *opaque;
		uint32_t version, width, height, format, flags, colormap_entries, warning_or_error;
		char message[64];
	} png_image;

	int png_image_begin_read_from_memory(png_image *image, const void *memory, size_t size);
	int png_image_finish_read(png_image *image, const void *background, void *buffer, int32_t row_stride, void *colormap);
	void png_image_free(png_image *image);
}
#define PNG_IMAGE_VERSION 1
#define PNG_FORMAT_BGRA   0x13  // COLOR | ALPHA | BGR: 0xAARRGGBB in memory

static int decode_png(const std::vector<uint8_t> &data, int &w, int &h, std::vector<uint32_t> &px)
{
	png_image img;
	memset(&img, 0, sizeof(img));
	img.version = PNG_IMAGE_VERSION;
	if (!png_image_begin_read_from_memory(&img, data.data(), data.size())) return 0;

	if (!img.width || !img.height || img.width * img.height > MAX_PIXELS)
	{
		png_image_free(&img);
		return 0;
	}

	img.format = PNG_FORMAT_BGRA;
	px.resize(img.width * img.height);
	if (!png_image_finish_read(&img, 0, px.data(), 0, 0))
	{
		png_image_free(&img);
		return 0;
	}

	w = img.width;
	h = img.height;
	return 1;
}

// libturbojpeg, loaded at run time
typedef void *tjhandle;
static tjhandle (*tj_init)(void);
static int (*tj_header)(tjhandle, const unsigned char *, unsigned long, int *, int *, int *, int *);
static int (*tj_decompress)(tjhandle, const unsigned char *, unsigned long, unsigned char *, int, int, int, int, int);
static int (*tj_destroy)(tjhandle);
#define TJPF_BGRA          8
#define TJFLAG_FASTUPSAMPLE 256
#define TJFLAG_FASTDCT     2048

static int tj_load()
{
	static int state = 0;
	if (state) return state > 0;

	void *lib = dlopen("libturbojpeg.so.0", RTLD_NOW);
	if (lib)
	{
		tj_init = (tjhandle (*)(void))dlsym(lib, "tjInitDecompress");
		tj_header = (int (*)(tjhandle, const unsigned char *, unsigned long, int *, int *, int *, int *))dlsym(lib, "tjDecompressHeader3");
		tj_decompress = (int (*)(tjhandle, const unsigned char *, unsigned long, unsigned char *, int, int, int, int, int))dlsym(lib, "tjDecompress2");
		tj_destroy = (int (*)(tjhandle))dlsym(lib, "tjDestroy");
	}

	state = (tj_init && tj_header && tj_decompress && tj_destroy) ? 1 : -1;
	if (state < 0) fprintf(stderr, "frontier: libturbojpeg not available, no JPEG images\n");
	return state > 0;
}

// decodes at 1/2, 1/4 or 1/8 when the image is much bigger than needed
static int decode_jpeg(const std::vector<uint8_t> &data, int need_w, int need_h, int &w, int &h, std::vector<uint32_t> &px)
{
	if (!tj_load()) return 0;

	static thread_local tjhandle tj = 0;  // media and video threads
	if (!tj) tj = tj_init();
	if (!tj) return 0;

	int jw, jh, sub, cs;
	if (tj_header(tj, data.data(), data.size(), &jw, &jh, &sub, &cs) || jw <= 0 || jh <= 0 || jw * jh > MAX_PIXELS) return 0;

	int d = 1;
	while (d < 8 && (jw + 2 * d - 1) / (2 * d) >= need_w && (jh + 2 * d - 1) / (2 * d) >= need_h) d *= 2;
	w = (jw + d - 1) / d;
	h = (jh + d - 1) / d;

	px.resize(w * h);
	return !tj_decompress(tj, data.data(), data.size(), (unsigned char *)px.data(), w, w * 4, h, TJPF_BGRA, TJFLAG_FASTUPSAMPLE | TJFLAG_FASTDCT);
}

static int decode(const std::string &path, int need_w, int need_h, int &w, int &h, std::vector<uint32_t> &px)
{
	std::vector<uint8_t> data;
	if (!read_file(path, data) || data.size() < 8) return 0;

	if (data[0] == 0x89 && data[1] == 'P' && data[2] == 'N' && data[3] == 'G') return decode_png(data, w, h, px);
	if (data[0] == 0xFF && data[1] == 0xD8) return decode_jpeg(data, need_w, need_h, w, h, px);
	return 0;
}

#else

// PC preview: single thread, Imlib2 is fine
static int decode(const std::string &path, int, int, int &w, int &h, std::vector<uint32_t> &px)
{
	Imlib_Image img = imlib_load_image_immediately_without_cache(path.c_str());
	if (!img) return 0;
	imlib_context_set_image(img);
	w = imlib_image_get_width();
	h = imlib_image_get_height();
	DATA32 *d = imlib_image_get_data_for_reading_only();
	int alpha = imlib_image_has_alpha();
	px.resize(w * h);
	for (int i = 0; i < w * h; i++) px[i] = alpha ? d[i] : (d[i] | 0xFF000000);
	imlib_free_image();
	return 1;
}

#endif

static void halve(std::vector<uint32_t> &px, int &w, int &h)
{
	int nw = w / 2, nh = h / 2;
	for (int y = 0; y < nh; y++)
	{
		const uint32_t *a = px.data() + (2 * y) * w;
		const uint32_t *b = a + w;
		uint32_t *d = px.data() + y * nw;
		for (int x = 0; x < nw; x++)
		{
			uint32_t p0 = a[2 * x], p1 = a[2 * x + 1], p2 = b[2 * x], p3 = b[2 * x + 1];
			uint32_t rb = ((p0 & 0x00FF00FF) + (p1 & 0x00FF00FF) + (p2 & 0x00FF00FF) + (p3 & 0x00FF00FF)) >> 2;
			uint32_t ag = (((p0 >> 8) & 0x00FF00FF) + ((p1 >> 8) & 0x00FF00FF) + ((p2 >> 8) & 0x00FF00FF) + ((p3 >> 8) & 0x00FF00FF)) >> 2;
			d[x] = (rb & 0x00FF00FF) | ((ag & 0x00FF00FF) << 8);
		}
	}
	w = nw;
	h = nh;
	px.resize(w * h);
}

static inline uint32_t lerp(uint32_t a, uint32_t b, int t) // t = 0..256
{
	uint32_t rb = ((a & 0x00FF00FF) * (256 - t) + (b & 0x00FF00FF) * t) >> 8;
	uint32_t ag = (((a >> 8) & 0x00FF00FF) * (256 - t) + ((b >> 8) & 0x00FF00FF) * t) >> 8;
	return (rb & 0x00FF00FF) | ((ag & 0x00FF00FF) << 8);
}

static void resize(const std::vector<uint32_t> &src, int sw, int sh, std::vector<uint32_t> &dst, int dw, int dh)
{
	dst.resize(dw * dh);
	std::vector<int> xs(dw), xw(dw);
	for (int x = 0; x < dw; x++)
	{
		int fx = (int)(((int64_t)(2 * x + 1) * sw * 128) / dw) - 128;
		if (fx < 0) fx = 0;
		xs[x] = std::min(fx >> 8, sw - 1);
		xw[x] = (xs[x] < sw - 1) ? (fx & 255) : 0;
	}

	for (int y = 0; y < dh; y++)
	{
		int fy = (int)(((int64_t)(2 * y + 1) * sh * 128) / dh) - 128;
		if (fy < 0) fy = 0;
		int y0 = std::min(fy >> 8, sh - 1);
		int y1 = std::min(y0 + 1, sh - 1);
		int wy = fy & 255;
		const uint32_t *r0 = src.data() + y0 * sw;
		const uint32_t *r1 = src.data() + y1 * sw;
		uint32_t *d = dst.data() + y * dw;
		for (int x = 0; x < dw; x++)
		{
			int x0 = xs[x], x1 = std::min(x0 + 1, sw - 1);
			d[x] = lerp(lerp(r0[x0], r0[x1], xw[x]), lerp(r1[x0], r1[x1], xw[x]), wy);
		}
	}
}

// decoded image (sw x sh) -> bitmap for w x h with the fit mode
static std::shared_ptr<fe_bitmap> fit_bitmap(std::vector<uint32_t> &px, int sw, int sh, int w, int h, int fit)
{
	// area of the source to use and size of the result
	int cx = 0, cy = 0, cw = sw, ch = sh, dw = w, dh = h;
	if (fit == FE_FIT_CONTAIN)
	{
		if ((int64_t)sw * h > (int64_t)sh * w) dh = std::max(1, (int)((int64_t)sh * w / sw));
		else dw = std::max(1, (int)((int64_t)sw * h / sh));
	}
	else if (fit == FE_FIT_COVER)
	{
		if ((int64_t)sw * h > (int64_t)sh * w)
		{
			cw = std::max(1, (int)((int64_t)w * sh / h));
			cx = (sw - cw) / 2;
		}
		else
		{
			ch = std::max(1, (int)((int64_t)h * sw / w));
			cy = (sh - ch) / 2;
		}
	}

	if (cw != sw || ch != sh)
	{
		std::vector<uint32_t> crop(cw * ch);
		for (int y = 0; y < ch; y++) memcpy(crop.data() + y * cw, px.data() + (cy + y) * sw + cx, cw * 4);
		px.swap(crop);
	}

	while (cw >= 2 * dw && ch >= 2 * dh) halve(px, cw, ch);

	auto bm = std::make_shared<fe_bitmap>();
	bm->w = dw;
	bm->h = dh;
	if (cw == dw && ch == dh) bm->px.swap(px);
	else resize(px, cw, ch, bm->px, dw, dh);
	return bm;
}

std::shared_ptr<fe_bitmap> fe_bitmap_scale(const fe_bitmap &bm, int w, int h)
{
	if (w <= 0 || h <= 0 || bm.w <= 0 || bm.h <= 0) return nullptr;
	std::vector<uint32_t> px = bm.px;
	return fit_bitmap(px, bm.w, bm.h, w, h, FE_FIT_STRETCH);
}

static std::shared_ptr<fe_bitmap> load_bitmap(const std::string &path, int w, int h, int fit)
{
	uint64_t t0 = now_ms();
	int sw = 0, sh = 0;
	std::vector<uint32_t> px;
	if (!decode(path, w, h, sw, sh, px))
	{
		fprintf(stderr, "frontier: can't decode %s\n", path.c_str());
		return 0;
	}

	std::shared_ptr<fe_bitmap> bm = fit_bitmap(px, sw, sh, w, h, fit);
	fprintf(stderr, "frontier: image %s %dx%d -> %dx%d, %d ms\n", path.c_str(), sw, sh, bm->w, bm->h, (int)(now_ms() - t0));
	return bm;
}

/////////////////////////////////////////////////////////////////////////////
// cache (under mtx in threaded mode)

static void cache_put(const std::string &id, std::shared_ptr<fe_bitmap> bm)
{
	cache_item it;
	it.bm = bm;
	it.used = ++use_counter;
	it.bytes = bm ? bm->px.size() * 4 : 0;

	auto old = cache.find(id);
	if (old != cache.end()) cache_bytes -= old->second.bytes;
	cache[id] = it;
	cache_bytes += it.bytes;

	while (cache_bytes > CACHE_BYTES && cache.size() > 1)
	{
		auto lru = cache.end();
		for (auto c = cache.begin(); c != cache.end(); ++c)
		{
			if (c->first != id && (lru == cache.end() || c->second.used < lru->second.used)) lru = c;
		}
		if (lru == cache.end()) break;
		cache_bytes -= lru->second.bytes;
		cache.erase(lru);
	}
}

/////////////////////////////////////////////////////////////////////////////
// worker

static void *worker(void *)
{
	pthread_mutex_lock(&mtx);
	while (1)
	{
		if (reset_req)
		{
			reset_req = 0;
			systems.clear();
		}

		if (info_gen != sel_gen)
		{
			int gen = sel_gen;
			std::string sys = sel_sys, key = sel_key;
			pthread_mutex_unlock(&mtx);

			std::map<std::string, std::string> vars;
			if (!sys.empty()) make_vars(sys, key, vars);

			pthread_mutex_lock(&mtx);
			if (gen == sel_gen)
			{
				info_vars.swap(vars);
				info_gen = gen;
				changed_flag = 1;
			}
			continue;
		}

		if (!pending.empty())
		{
			img_req r = pending.back();
			uint64_t age = now_ms() - r.time;
			if (age < IMAGE_DELAY_MS)
			{
				struct timespec ts;
				clock_gettime(CLOCK_REALTIME, &ts);
				uint64_t ns = ts.tv_nsec + (IMAGE_DELAY_MS - age) * 1000000ULL;
				ts.tv_sec += ns / 1000000000ULL;
				ts.tv_nsec = ns % 1000000000ULL;
				pthread_cond_timedwait(&cond, &mtx, &ts);
				continue;
			}

			pending.pop_back();
			pthread_mutex_unlock(&mtx);

			std::shared_ptr<fe_bitmap> bm = load_bitmap(r.path, r.w, r.h, r.fit);

			pthread_mutex_lock(&mtx);
			cache_put(r.id, bm);
			changed_flag = 1;
			continue;
		}

		pthread_cond_wait(&cond, &mtx);
	}
	return 0;
}

/////////////////////////////////////////////////////////////////////////////
// video
//
// .mjv: "MJV1", uint32 frames, uint16 width, uint16 height, uint16 fps * 100,
// uint16 flags (0), uint32 offsets[frames + 1] (from the file start, the last
// one is the end of the data), then the frames as JPEG. Little endian.
// Made from mp4 files on the PC by frontier/scraper/fe_scrape.py (ffmpeg).
//
// Any other file (mp4 from the scraper): decoded by frontier/lib/fe_av.so
// (tools/fe/fe_av) with its sound, pictures shown at their timestamps following
// the sound heard, decoded without converting them while late. Both loop.
// A second size of the same video (the CRT pages in the dual mode, "view 2")
// is made from the same decoded pictures.

static pthread_t vthread;
static int vstarted = 0;
static pthread_cond_t vcond = PTHREAD_COND_INITIALIZER;

// under mtx
static std::string vid_path;
static int vid_w = 0, vid_h = 0, vid_fit = 0, vid_gen = 0, vid_idx = -1;
static uint64_t vid_t0 = 0, vid_req = 0;
static std::shared_ptr<fe_bitmap> vid_bm;
// view 2 (vid2_w = 0: none)
static int vid2_w = 0, vid2_h = 0, vid2_fit = 0, vid2_gen = 0;
static uint64_t vid2_req = 0;
static std::shared_ptr<fe_bitmap> vid2_bm;

#define VIDEO_IDLE_MS 500  // stops when nobody asks for frames
#define VIDEO_SHOW_MS 250  // even when late, a picture at least this often
#define VIDEO_SYNC_MS 30   // the pictures move to the sound beyond this

static int vid_volume = 40; // video_volume in frontier.ini

#ifndef FE_PREVIEW

// under mtx
static int vid2_on(uint64_t t)
{
	return vid2_w > 0 && t - vid2_req <= VIDEO_IDLE_MS;
}

// nobody asks for frames any more (under mtx)
static int video_idle(uint64_t t)
{
	return t - vid_req > VIDEO_IDLE_MS && !vid2_on(t);
}

// fe_av.so, loaded at run time (interface in tools/fe/fe_av/fe_av.h)
typedef struct fev fev;
static fev *(*fev_open)(const char *, int, int, int, int, int *, int *);
static int (*fev_next)(fev *, uint32_t *, int64_t *);
static int (*fev_view)(fev *, int, int, int, int, int *, int *);
static int (*fev_picture)(fev *, int, uint32_t *);
static int (*fev_rewind)(fev *, int64_t *);
static int64_t (*fev_clock)(fev *);
static void (*fev_close)(fev *);
static pthread_once_t fev_once = PTHREAD_ONCE_INIT;
static int fev_state = 0;

static void fev_init()
{
	std::string path = root + "/lib/fe_av.so";
	void *lib = dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
	if (lib)
	{
		fev_open = (fev *(*)(const char *, int, int, int, int, int *, int *))dlsym(lib, "fev_open");
		fev_next = (int (*)(fev *, uint32_t *, int64_t *))dlsym(lib, "fev_next");
		fev_view = (int (*)(fev *, int, int, int, int, int *, int *))dlsym(lib, "fev_view");
		fev_picture = (int (*)(fev *, int, uint32_t *))dlsym(lib, "fev_picture");
		fev_rewind = (int (*)(fev *, int64_t *))dlsym(lib, "fev_rewind");
		fev_clock = (int64_t (*)(fev *))dlsym(lib, "fev_clock");
		fev_close = (void (*)(fev *))dlsym(lib, "fev_close");
	}

	fev_state = (fev_open && fev_next && fev_view && fev_picture && fev_rewind && fev_clock && fev_close) ? 1 : -1;
	if (fev_state < 0) fprintf(stderr, "frontier: %s not available, only .mjv videos\n", path.c_str());
}

// media thread and video thread
static int fev_load()
{
	if (root.empty()) return 0;
	pthread_once(&fev_once, fev_init);
	return fev_state > 0;
}

static uint32_t rd32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }
static uint16_t rd16(const uint8_t *p) { return p[0] | (p[1] << 8); }

// video thread only
struct vstate
{
	int gen = -1;
	int gen2 = -1;             // vid2_gen view 2 is set up for
	int count = 0;             // pictures shown (frame number for the renderer)
	// .mjv
	FILE *fp = 0;
	std::vector<uint32_t> offs;
	int fps100 = 1500;
	// fe_av
	fev *av = 0;
	int aw = 0, ah = 0;        // size of the pictures from fe_av
	int aw2 = 0, ah2 = 0;      // the same for view 2 (0: none)
	int64_t base = -1;         // ms from vid_t0 where the current loop starts (-1: first picture not decoded)
	int64_t loop_start = 0;    // ms of the current loop on fe_av's timeline (sum of the loops)
	int64_t last_pts = 0, frame_ms = 33;
	int64_t shown = 0;         // ms from vid_t0 of the last picture converted
	int decoded = 0;           // pictures decoded in this loop
	int converted = 0;         // pictures converted in this loop
	int syncs = 0;             // moves of the clock to the sound in this loop
	double t_dec = 0, t_fit = 0; // ms spent in this loop (log at the end)
};

static void video_close(vstate &v)
{
	if (v.fp) fclose(v.fp);
	v.fp = 0;
	v.offs.clear();
	if (v.av) fev_close(v.av);
	v.av = 0;
}

static int video_open(vstate &v, const std::string &path, int w, int h, int fit)
{
	video_close(v);
	v.count = 0;
	v.gen2 = -1;
	v.aw2 = v.ah2 = 0;

	if (path.size() < 4 || strcasecmp(path.c_str() + path.size() - 4, ".mjv"))
	{
		if (!fev_load()) return 0;
		v.av = fev_open(path.c_str(), w, h, fit, vid_volume, &v.aw, &v.ah);  // fit: FE_FIT_* = FEV_* of fe_av.h
		v.base = -1;
		v.loop_start = 0;
		v.last_pts = 0;
		v.frame_ms = 33;
		v.shown = 0;
		v.decoded = 0;
		v.converted = 0;
		v.syncs = 0;
		v.t_dec = v.t_fit = 0;
		return v.av != 0;
	}

	v.fp = fopen(path.c_str(), "rb");
	uint8_t hdr[16];
	if (v.fp && fread(hdr, 1, 16, v.fp) == 16 && !memcmp(hdr, "MJV1", 4))
	{
		uint32_t n = rd32(hdr + 4);
		v.fps100 = rd16(hdr + 12);
		if (n > 0 && n < 100000 && v.fps100 > 0)
		{
			std::vector<uint8_t> idx((n + 1) * 4);
			if (fread(idx.data(), 1, idx.size(), v.fp) == idx.size())
			{
				v.offs.resize(n + 1);
				for (uint32_t i = 0; i <= n; i++) v.offs[i] = rd32(idx.data() + i * 4);
				return 1;
			}
		}
	}
	video_close(v);
	return 0;
}

// waits on vcond (under mtx) at most ms
static void video_wait(uint64_t ms)
{
	struct timespec ts;
	clock_gettime(CLOCK_REALTIME, &ts);
	uint64_t ns = ts.tv_nsec + ms * 1000000ULL;
	ts.tv_sec += ns / 1000000000ULL;
	ts.tv_nsec = ns % 1000000000ULL;
	pthread_cond_timedwait(&vcond, &mtx, &ts);
}

static int video_wanted(int gen)
{
	return gen == vid_gen && !vid_path.empty() && !video_idle(now_ms());
}

// view 2 asked by the renderer: its size for this video (under mtx)
struct view2
{
	int on, w, h, fit, gen;
};

static view2 video_view2(vstate &v)
{
	view2 r = { vid2_on(now_ms()), vid2_w, vid2_h, vid2_fit, vid2_gen };
	if (r.on && v.av && v.gen2 != r.gen)
	{
		v.gen2 = r.gen;
		if (!fev_view(v.av, 1, r.w, r.h, r.fit, &v.aw2, &v.ah2)) v.aw2 = v.ah2 = 0;
	}
	return r;
}

// next mjv frame when its time comes (under mtx)
static void video_step_mjv(vstate &v)
{
	uint64_t t = now_ms() - vid_t0;
	uint64_t n = t * v.fps100 / 100000;  // frames since the start
	int frames = v.offs.size() - 1;
	int idx = (int)(n % frames);
	if (idx != vid_idx)
	{
		int w = vid_w, h = vid_h, fit = vid_fit, g = vid_gen;
		view2 v2 = video_view2(v);
		pthread_mutex_unlock(&mtx);

		std::shared_ptr<fe_bitmap> bm, bm2;
		uint32_t size = v.offs[idx + 1] - v.offs[idx];
		std::vector<uint8_t> data(size);
		int sw, sh;
		std::vector<uint32_t> px;
		if (size && size < MAX_FILE && !fseek(v.fp, v.offs[idx], SEEK_SET) && fread(data.data(), 1, size, v.fp) == size &&
			decode_jpeg(data, v2.on ? std::max(w, v2.w) : w, v2.on ? std::max(h, v2.h) : h, sw, sh, px))
		{
			if (v2.on)
			{
				std::vector<uint32_t> px2 = px;
				bm2 = fit_bitmap(px2, sw, sh, v2.w, v2.h, v2.fit);
			}
			bm = fit_bitmap(px, sw, sh, w, h, fit);
		}

		pthread_mutex_lock(&mtx);
		if (g == vid_gen)
		{
			vid_idx = idx;
			if (bm) vid_bm = bm;
			if (bm2 && v2.gen == vid2_gen) vid2_bm = bm2;
			changed_flag = 1;
		}
		return;
	}

	// until the next frame
	uint64_t next = ((n + 1) * 100000 + v.fps100 - 1) / v.fps100;
	video_wait(std::min<uint64_t>(100, next > t ? next - t : 1));
}

// next fe_av picture, shown at its time (under mtx)
static void video_step_av(vstate &v)
{
	int w = vid_w, h = vid_h, fit = vid_fit, g = vid_gen;
	view2 v2 = video_view2(v);
	int64_t t = (int64_t)(now_ms() - vid_t0);
	// with sound the pictures follow it: their clock moves to the sound heard
	int64_t a = v.base >= 0 ? fev_clock(v.av) : -1;
	if (a >= 0)
	{
		int64_t p = t - v.base + v.loop_start;
		if (p - a > VIDEO_SYNC_MS || a - p > VIDEO_SYNC_MS)
		{
			v.base += p - a;
			v.syncs++;
		}
	}
	// late (the next picture was due two pictures ago): decode it without converting
	int late = v.base >= 0 && v.base + v.last_pts + 2 * v.frame_ms < t && t - v.shown < VIDEO_SHOW_MS;
	pthread_mutex_unlock(&mtx);

	std::vector<uint32_t> px;
	if (!late) px.resize(v.aw * v.ah);
	int64_t pts = 0;
	uint64_t t0 = now_us();
	int r = fev_next(v.av, late ? 0 : px.data(), &pts);
	v.t_dec += (now_us() - t0) / 1000.0;
	int64_t loop = 0;
	if (!r && v.decoded && fev_rewind(v.av, &loop))
	{
		// loop: the file restarts one picture after its last one
		fprintf(stderr, "frontier: video loop, %d pictures, %d shown, decoding %.1f ms, scaling %.1f ms, %d moves to the sound\n",
			v.decoded, v.converted, v.t_dec / v.decoded, v.converted ? v.t_fit / v.converted : 0.0, v.syncs);
		v.base += loop;
		v.loop_start += loop;
		v.last_pts = -v.frame_ms;
		v.decoded = 0;
		v.converted = 0;
		v.syncs = 0;
		v.t_dec = v.t_fit = 0;
		pthread_mutex_lock(&mtx);
		return;
	}
	if (r <= 0)
	{
		fprintf(stderr, "frontier: video decoding stopped (%d)\n", r);
		video_close(v);
		pthread_mutex_lock(&mtx);
		if (g == vid_gen) vid_path.clear();
		return;
	}

	if (v.base < 0) v.base = (int64_t)(now_ms() - vid_t0) - pts;  // the first picture at once
	if (v.decoded && pts > v.last_pts && pts - v.last_pts < 1000) v.frame_ms = pts - v.last_pts;
	v.last_pts = pts;
	v.decoded++;

	std::shared_ptr<fe_bitmap> bm, bm2;
	if (!late)
	{
		t0 = now_us();
		bm = fit_bitmap(px, v.aw, v.ah, w, h, fit);
		if (v2.on && v.aw2)
		{
			std::vector<uint32_t> px2(v.aw2 * v.ah2);
			if (fev_picture(v.av, 1, px2.data())) bm2 = fit_bitmap(px2, v.aw2, v.ah2, v2.w, v2.h, v2.fit);
		}
		v.t_fit += (now_us() - t0) / 1000.0;
		v.converted++;
	}

	pthread_mutex_lock(&mtx);
	int64_t due = v.base + pts;
	while (bm && video_wanted(g))
	{
		int64_t left = due - (int64_t)(now_ms() - vid_t0);
		if (left <= 0) break;
		video_wait(std::min<int64_t>(left, 100));
	}
	if (bm && g == vid_gen)
	{
		vid_idx = v.count++;
		vid_bm = bm;
		if (bm2 && v2.gen == vid2_gen) vid2_bm = bm2;
		changed_flag = 1;
		v.shown = (int64_t)(now_ms() - vid_t0);
	}
}

static void *video_worker(void *)
{
	// on the core Main does not use (main.cpp pins Main to core 1)
	cpu_set_t set;
	CPU_ZERO(&set);
	CPU_SET(0, &set);
	pthread_setaffinity_np(pthread_self(), sizeof(set), &set);

	vstate v;
	pthread_mutex_lock(&mtx);
	while (1)
	{
		if (vid_path.empty() || video_idle(now_ms()))
		{
			video_close(v);
			vid_path.clear();
			vid_bm.reset();
			vid2_bm.reset();
			vid2_w = 0;
			vid_idx = -1;
			v.gen = -1;
			pthread_cond_wait(&vcond, &mtx);
			continue;
		}

		if (v.gen != vid_gen)
		{
			// new video (or new size)
			v.gen = vid_gen;
			std::string path = vid_path;
			int w = vid_w, h = vid_h, fit = vid_fit;
			pthread_mutex_unlock(&mtx);

			uint64_t t0 = now_ms();
			int ok = video_open(v, path, w, h, fit);
			if (!ok) fprintf(stderr, "frontier: bad video %s\n", path.c_str());
			else if (v.av) fprintf(stderr, "frontier: video %s, box %dx%d -> %dx%d, %d ms\n", path.c_str(), w, h, v.aw, v.ah, (int)(now_ms() - t0));

			pthread_mutex_lock(&mtx);
			if (!ok && v.gen == vid_gen) vid_path.clear();
			continue;
		}

		if (v.av) video_step_av(v);
		else if (v.fp) video_step_mjv(v);
		else video_wait(100);
	}
	return 0;
}

std::shared_ptr<fe_bitmap> fe_video_frame(const std::string &path, int w, int h, int fit, int *frame)
{
	*frame = -1;
	if (!started || !threaded || path.empty() || w <= 0 || h <= 0) return 0;

	pthread_mutex_lock(&mtx);
	uint64_t t = now_ms();
	int wake = vid_path.empty() || video_idle(t);
	int second = 0;
	if (path == vid_path && w == vid_w && h == vid_h && fit == vid_fit) {}
	else if (path == vid_path && w == vid2_w && h == vid2_h && fit == vid2_fit) second = 1;
	else if (path == vid_path && !wake && !vid2_on(t))
	{
		// another size of the playing video: view 2
		vid2_w = w;
		vid2_h = h;
		vid2_fit = fit;
		vid2_gen++;
		vid2_bm.reset();
		second = 1;
	}
	else
	{
		vid_path = path;
		vid_w = w;
		vid_h = h;
		vid_fit = fit;
		vid_t0 = t;
		vid_gen++;
		vid_idx = -1;
		vid_bm.reset();
		vid2_w = 0;
		vid2_bm.reset();
		wake = 1;
	}
	if (second) vid2_req = t;
	else vid_req = t;

	if (!vstarted)
	{
		vstarted = !pthread_create(&vthread, 0, video_worker, 0);
		if (!vstarted) fprintf(stderr, "frontier: can't start the video thread\n");
	}
	if (wake) pthread_cond_signal(&vcond);

	std::shared_ptr<fe_bitmap> bm = second ? vid2_bm : vid_bm;
	*frame = bm ? vid_idx : -1;
	pthread_mutex_unlock(&mtx);
	return bm;
}

#else

static int fev_load()
{
	return 0;
}

std::shared_ptr<fe_bitmap> fe_video_frame(const std::string &, int, int, int, int *frame)
{
	*frame = -1;
	return 0;
}

#endif

void fe_video_volume(int volume)
{
	vid_volume = std::max(0, std::min(100, volume));
}

void fe_video_stop()
{
	pthread_mutex_lock(&mtx);
	vid_path.clear();
	vid_bm.reset();
	vid2_w = 0;
	vid2_bm.reset();
	vid_idx = -1;
	pthread_cond_signal(&vcond);
	pthread_mutex_unlock(&mtx);
}

/////////////////////////////////////////////////////////////////////////////
// public interface

std::shared_ptr<fe_bitmap> fe_media_load(const std::string &path, int w, int h, int fit)
{
	if (path.empty() || w <= 0 || h <= 0) return 0;
	return load_bitmap(path, w, h, fit);
}

void fe_media_init(const std::string &dir, int thr)
{
	if (started) return;
	root = dir;
	threaded = thr;
	started = 1;

	if (threaded && pthread_create(&thread, 0, worker, 0))
	{
		fprintf(stderr, "frontier: can't start the media thread\n");
		threaded = 0;
	}
}

void fe_media_reset()
{
	pthread_mutex_lock(&mtx);
	if (threaded) reset_req = 1;
	else systems.clear();
	cache.clear();
	cache_bytes = 0;
	pending.clear();
	sel_sys.clear();
	sel_key.clear();
	sel_gen++;
	info_vars.clear();
	info_gen = sel_gen;
	pthread_cond_signal(&cond);
	pthread_mutex_unlock(&mtx);
}

void fe_media_select(const std::string &system, const std::string &key)
{
	if (!started) return;

	pthread_mutex_lock(&mtx);
	if (system == sel_sys && key == sel_key)
	{
		pthread_mutex_unlock(&mtx);
		return;
	}

	sel_sys = system;
	sel_key = key;
	sel_gen++;
	pending.clear();
	if (system.empty())
	{
		info_vars.clear();
		info_gen = sel_gen;
	}
	else if (!threaded)
	{
		info_vars.clear();
		make_vars(system, key, info_vars);
		info_gen = sel_gen;
	}
	pthread_cond_signal(&cond);
	pthread_mutex_unlock(&mtx);
}

int fe_media_vars(std::map<std::string, std::string> &vars)
{
	pthread_mutex_lock(&mtx);
	int ready = (info_gen == sel_gen);
	if (ready)
	{
		for (auto &v : info_vars) vars[v.first] = v.second;
	}
	pthread_mutex_unlock(&mtx);
	return ready;
}

std::shared_ptr<fe_bitmap> fe_media_image(const std::string &path, int w, int h, int fit, int *loading)
{
	if (loading) *loading = 0;
	if (!started || path.empty() || w <= 0 || h <= 0) return 0;

	char sz[48];
	snprintf(sz, sizeof(sz), "|%d|%d|%d", w, h, fit);
	std::string id = path + sz;

	std::shared_ptr<fe_bitmap> bm;
	pthread_mutex_lock(&mtx);
	auto it = cache.find(id);
	if (it != cache.end())
	{
		it->second.used = ++use_counter;
		bm = it->second.bm;
	}
	else if (!threaded)
	{
		bm = load_bitmap(path, w, h, fit);
		cache_put(id, bm);
	}
	else
	{
		if (loading) *loading = 1;
		int queued = 0;
		for (auto &r : pending) queued |= (r.id == id);
		if (!queued)
		{
			pending.push_back({ id, path, w, h, fit, now_ms() });
			pthread_cond_signal(&cond);
		}
	}
	pthread_mutex_unlock(&mtx);
	return bm;
}

int fe_media_changed()
{
	pthread_mutex_lock(&mtx);
	int c = changed_flag;
	changed_flag = 0;
	pthread_mutex_unlock(&mtx);
	return c;
}
