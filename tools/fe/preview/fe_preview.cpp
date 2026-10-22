// Preview of a theme on a PC: uses the same renderer as the MiSTer
// (fe_render.cpp, fe_theme.cpp) with sample data and saves a PNG.
// Build and usage: tools/fe/preview/preview.sh <theme folder> <out.png> [width height] [sel] [detail|screensaver|loading]

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "lib/imlib2/Imlib2.h"
#include "fe_render.h"
#include "fe_media.h"

int main(int argc, char **argv)
{
	if (argc < 3)
	{
		fprintf(stderr, "usage: %s <theme folder> <out.png> [width height] [sel] [detail|screensaver|loading]\n", argv[0]);
		return 1;
	}

	int w = (argc > 4) ? atoi(argv[3]) : 1280;
	int h = (argc > 4) ? atoi(argv[4]) : 720;

	static const char *names[] = {
		"1942 (Revision B)", "1943 Kai Midway Kaisen (Japan)", "Bubble Bobble", "Cadillacs and Dinosaurs (World 930201)",
		"Donkey Kong (US set 1)", "Final Fight (World, set 1)", "Galaga (Namco rev. B)", "Ghosts'n Goblins (World? set 1)",
		"Metal Slug - Super Vehicle-001", "Out Run (sitdown/upright, Rev B)", "Pac-Man (Midway)", "R-Type (World)",
		"Street Fighter II': Champion Edition (World 920513)", "Tetris (set 1)", "The King of Fighters '98 - The Slugfest", "Xevious (Namco)",
	};

	std::vector<fe_entry> entries;
	entries.push_back({ "..", "..", "", "", 1 });
	entries.push_back({ "_Alternatives", "Alternatives", "", "", 1 });
	entries.push_back({ "_Cave CV1000", "Cave CV1000", "", "", 1 });
	for (auto n : names) entries.push_back({ std::string(n) + ".mra", n, "", "", 0 });
	entries.push_back({ "jt1942.rbf", "jt1942", "24.08.15", "", 0 });

	fe_view v;
	v.entries = &entries;
	v.sel = (argc > 5) ? atoi(argv[5]) : 7;
	v.vars["title"] = "Arcade";
	v.vars["folder"] = "Arcade";
	char str[32];
	snprintf(str, sizeof(str), "%d/%d", v.sel + 1, (int)entries.size());
	v.vars["pos"] = str;
	v.vars["count"] = std::to_string(entries.size());
	v.vars["game.name"] = entries[v.sel].label;
	v.vars["game.title"] = entries[v.sel].label;
	v.vars["game.file"] = entries[v.sel].name;
	v.vars["game.favorite"] = "1"; // shows the mark of the favorites

	// media from the Frontier folder which contains the theme (themes/<name>)
	std::string theme = argv[1];
	while (!theme.empty() && theme.back() == '/') theme.pop_back();
	std::string root = theme.substr(0, theme.rfind('/'));
	root = root.substr(0, root.rfind('/'));
	fe_media_init(root, 0);
	const fe_entry &cur = entries[v.sel];
	if (cur.dir) fe_media_select(cur.name == ".." ? "" : "folders", cur.label);
	else fe_media_select("arcade", cur.name.substr(0, cur.name.rfind('.')));
	fe_media_vars(v.vars);
	v.vars["system"] = cur.dir ? "folders" : "arcade";

	// detail screen: detail.ini, with a sample description and versions;
	// screensaver: screensaver.ini, the same game alone
	bool saver = (argc > 6) && !strcmp(argv[6], "screensaver");
	bool loading = (argc > 6) && !strcmp(argv[6], "loading");
	if (loading)
	{
		// loading screen: loading.ini, the game being loaded at 63%
		v.vars["progress"] = "63";
		v.vars["loading.file"] = "games/NEOGEO/" + entries[v.sel].label + ".neo";
		v.vars["system.name"] = "Neo Geo";
	}
	bool detail = saver || ((argc > 6) && !strcmp(argv[6], "detail"));
	std::vector<fe_entry> one(1, entries[v.sel]);
	if (saver)
	{
		one[0].tag = "Arcade";
		v.entries = &one;
		v.sel = 0;
		v.vars["system.name"] = "Arcade";
		v.vars["pos"] = "1/1";
	}
	// sample game data (the list keeps what the gamelist has)
	auto sample = [&](const char *k, const char *val) { if (detail || v.vars[k].empty()) v.vars[k] = val; };
	sample("game.desc", "A sample description of the game, long enough to be wrapped on more lines: "
		"the detail screen shows it next to the pictures and scrolls it when it does not fit. "
		"With the text layout (FE_LAYOUT=text) it takes the place of the pictures of the game, "
		"for those who scrape only the texts: the player flies over the Pacific shooting down "
		"waves of enemy planes, collecting power-ups and looping to avoid the bullets.");
	sample("game.year", "1984");
	sample("game.developer", "Capcom");
	sample("game.genre", "Shooter");
	sample("game.players", "2");
	sample("game.stars", "\u2605\u2605\u2605\u2605\u2606");
	if (detail && !saver) v.vars["pos"] = "1/3";
	// FE_LAYOUT=text: the text layout of the theme (layout=text instead of layout=media)
	const char *lay = getenv("FE_LAYOUT");
	fe_render_text_layout(lay && !strcmp(lay, "text"));
	if (!fe_render_load(argv[1], loading ? "loading" : saver ? "screensaver" : detail ? "detail" : "theme")) return 1;

	std::vector<uint32_t> buf(w * h);
	std::vector<fe_rect> dirty;
	// a second frame after 1 s: fades done, scrolling texts not started yet
	fe_render_draw(v, buf.data(), w, h, 1, dirty);
	v.time_ms = 1000;
	fe_render_draw(v, buf.data(), w, h, 1, dirty);

	// 240p: lines doubled, as seen on a CRT
	int dh = (w >= 2 * h) ? 2 * h : h;
	Imlib_Image img = imlib_create_image(w, dh);
	imlib_context_set_image(img);
	uint32_t *d = imlib_image_get_data();
	for (int y = 0; y < dh; y++)
		for (int x = 0; x < w; x++) d[y * w + x] = buf[(y * h / dh) * w + x] | 0xFF000000;
	imlib_image_put_back_data(d);
	imlib_image_set_format("png");
	imlib_save_image(argv[2]);
	imlib_free_image();
	printf("%s (%dx%d%s)\n", argv[2], w, h, dh != h ? ", lines doubled" : "");
	return 0;
}
