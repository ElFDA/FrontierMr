// Games of a system grouped by title (see fe_group.h).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include <dirent.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <pthread.h>

#include <algorithm>
#include <set>

#include "fe_group.h"
#include "fe_games.h"
#include "file_io.h"
#include "lib/miniz/miniz.h"

static std::vector<std::string> regions = { "usa", "world", "europe", "japan" };
// folders left out of the lists by title (exclude_dirs= in frontier.ini): unlicensed,
// prototypes, hacks... are in games/<system>/Extra, still in "Folders"
static std::set<std::string> exclude = { "extra" };
static std::map<std::string, fe_gsystem> scanned; // by folder name, case sensitive
static int manual = 1;                 // rescan=manual: the cache is enough
static std::set<std::string> rescans;  // fe_group_rescan() not finished (main thread)

// No-Intro region names: the first tag after the title is made of them
static const char *region_names[] = {
	"world", "usa", "europe", "japan", "asia", "australia", "brazil", "canada", "china", "france",
	"germany", "hong kong", "italy", "korea", "netherlands", "spain", "sweden", "taiwan", "uk",
	"russia", "scandinavia", "greece", "finland", "norway", "denmark", "portugal", "poland",
	"belgium", "austria", "switzerland", "latin america", "mexico", "argentina", "india",
	"south africa", "new zealand", "ireland", "israel", "croatia", "turkey", "czech", "hungary",
	"slovakia", "uae", "chile", "colombia", "peru", "thailand", "indonesia", "singapore",
	"malaysia", "philippines", "vietnam", "unknown"
};

static std::string lower(std::string s)
{
	for (auto &c : s) c = tolower((unsigned char)c);
	return s;
}

static std::string trim(const std::string &s)
{
	size_t a = s.find_first_not_of(" \t"), b = s.find_last_not_of(" \t");
	return (a == std::string::npos) ? std::string() : s.substr(a, b - a + 1);
}

static std::vector<std::string> split(const std::string &s, char sep)
{
	std::vector<std::string> out;
	size_t pos = 0;
	while (pos <= s.size())
	{
		size_t end = s.find(sep, pos);
		if (end == std::string::npos) end = s.size();
		std::string t = trim(s.substr(pos, end - pos));
		if (!t.empty()) out.push_back(t);
		pos = end + 1;
	}
	return out;
}

static int is_region(const std::string &r)
{
	for (auto n : region_names) if (r == n) return 1;
	return 0;
}

// "1991-08-23 F-Zero (USA)": release date in front (collections sorted by date)
static size_t date_len(const std::string &n)
{
	if (n.size() < 12) return 0;
	for (int i = 0; i < 10; i++)
	{
		char c = n[i];
		if ((i == 4 || i == 7) ? c != '-' : !isdigit((unsigned char)c)) return 0;
	}
	size_t j = 10;
	while (j < n.size() && strchr(" _-", n[j])) j++;
	return (j > 10) ? j : 0;
}

static int has_word(const std::string &tag, const char *const *words, int n)
{
	for (int i = 0; i < n; i++) if (strstr(tag.c_str(), words[i])) return 1;
	return 0;
}

// "Title (USA, Europe) (Rev 1)" -> title and rom info; 0 if it isn't a No-Intro
// name with a region: only "(...)" tags after the title, the first one made of
// regions, no hacks, translations or pirate copies ("[FastROM hack]", "T+Eng v2", "(Hack)", "(Pirate)")
static int parse_name(const std::string &full, std::string &title, fe_grom &r, const std::vector<std::string> &prefs)
{
	std::string name = full.substr(date_len(full));
	if (name.empty() || name[0] == '[') return 0; // [BIOS] ...
	size_t p = name.find(" (");
	if (p == std::string::npos || name.find('[') < p) return 0;
	title = trim(name.substr(0, p));
	if (title.empty()) return 0;

	static const char *excluded[] = { "hack", "t+", "t-", "translat", "patch", "trainer", "cracked", "pirate" };
	static const char *prerelease[] = { "beta", "proto", "sample", "demo", "kiosk", "debug", "program", "test" };
	static const char *rereleases[] = { "virtual console", "switch online", "classic mini", "mini", "sega ages", "3d classics",
		"collection", "evercade", "retro-bit", "limited run", "arcade archives", "steam", "gog" };

	r.rank = prefs.size();
	int first = 1;
	size_t pos = p;
	while (1)
	{
		while (pos < name.size() && name[pos] == ' ') pos++;
		if (pos >= name.size()) break;
		if (name[pos] != '(' && name[pos] != '[') return 0; // free text after the tags
		char close = (name[pos] == '(') ? ')' : ']';
		size_t end = name.find(close, pos);
		if (end == std::string::npos) return 0;
		std::string tag = lower(name.substr(pos + 1, end - pos - 1));
		int square = (close == ']');
		pos = end + 1;

		if (square)
		{
			// GoodTools flags: only [!] (verified dump) is a plain game
			if (tag != "!") return 0;
			continue;
		}

		if (first)
		{
			first = 0;
			std::vector<std::string> list = split(tag, ',');
			if (list.empty()) return 0;
			for (auto &x : list)
			{
				if (!is_region(x)) return 0;
				for (size_t i = 0; i < prefs.size(); i++) if (prefs[i] == x && (int)i < r.rank) r.rank = i;
			}
			continue;
		}

		if (has_word(tag, excluded, sizeof(excluded) / sizeof(excluded[0]))) return 0;
		if (has_word(tag, prerelease, sizeof(prerelease) / sizeof(prerelease[0]))) r.pre = 1;
		if (has_word(tag, rereleases, sizeof(rereleases) / sizeof(rereleases[0]))) r.rerel = 1;
		if (!strncmp(tag.c_str(), "rev ", 4))
		{
			const char *v = tag.c_str() + 4;
			r.rev = isdigit((unsigned char)*v) ? atoi(v) : (isalpha((unsigned char)*v) ? *v - 'a' + 1 : 0);
		}
		else if (tag[0] == 'v' && isdigit((unsigned char)tag[1]))
		{
			int major = atoi(tag.c_str() + 1), minor = 0;
			const char *dot = strchr(tag.c_str(), '.');
			if (dot) minor = atoi(dot + 1);
			r.rev = major * 100 + minor;
		}
		else if (!strncmp(tag.c_str(), "alt", 3)) r.alt = 1;
	}
	return !first;
}

// the better version first: released (a prototype of the preferred region comes
// after the release of another one), preferred region, latest revision
static bool better(const fe_grom &a, const fe_grom &b)
{
	if (a.pre != b.pre) return a.pre < b.pre;
	if (a.rank != b.rank) return a.rank < b.rank;
	if (a.rerel != b.rerel) return a.rerel < b.rerel;
	if (a.rev != b.rev) return a.rev > b.rev;
	if (a.alt != b.alt) return a.alt < b.alt;
	if (a.order != b.order) return a.order < b.order;
	return strcasecmp(a.name.c_str(), b.name.c_str()) < 0;
}

/////////////////////////////////////////////////////////////////////////////
// romsets (Neo Geo)

static std::string xml_attr(const std::string &tag, const char *name)
{
	std::string key = std::string(" ") + name + "=\"";
	size_t p = tag.find(key);
	if (p == std::string::npos) return "";
	p += key.size();
	size_t e = tag.find('"', p);
	if (e == std::string::npos) return "";
	std::string v = tag.substr(p, e - p), out;
	static const char *ent[][2] = { { "&amp;", "&" }, { "&apos;", "'" }, { "&quot;", "\"" }, { "&lt;", "<" }, { "&gt;", ">" } };
	for (size_t i = 0; i < v.size(); i++)
	{
		int done = 0;
		for (auto &x : ent)
		{
			if (v.compare(i, strlen(x[0]), x[0])) continue;
			out += x[1];
			i += strlen(x[0]) - 1;
			done = 1;
			break;
		}
		if (!done) out += v[i];
	}
	return out;
}

// games/<dir>/romsets.xml: setname (lowercase) -> name; the hidden ones are left out
static std::map<std::string, std::string> read_romsets(const std::string &dir)
{
	std::map<std::string, std::string> out;
	std::string path = std::string(getRootDir()) + "/games/" + dir + "/romsets.xml";
	FILE *fp = fopen(path.c_str(), "r");
	if (!fp) return out;
	std::string text;
	char buf[8192];
	size_t n;
	while ((n = fread(buf, 1, sizeof(buf), fp)) > 0) text.append(buf, n);
	fclose(fp);

	for (size_t p = text.find("<romset "); p != std::string::npos; p = text.find("<romset ", p + 1))
	{
		size_t e = text.find('>', p);
		if (e == std::string::npos) break;
		std::string tag = text.substr(p, e - p);
		if (tag.find(" hide=") != std::string::npos) continue;
		std::string alt = xml_attr(tag, "altname");
		for (auto &name : split(xml_attr(tag, "name"), ',')) out[lower(name)] = alt.empty() ? name : alt;
	}
	return out;
}

// a romset: "Title (tags) (setname).neo", or a zip file of romsets.xml (name =
// "2020 Super Baseball (set 2)"); 0 if it isn't one
static int parse_romset(const std::string &stem, const std::string &ext, const std::map<std::string, std::string> &names,
	std::string &title, fe_grom &r, const std::vector<std::string> &prefs, std::string *setname = 0)
{
	std::string full, set;
	if (ext == "neo")
	{
		// the last tag is the setname: lowercase letters, digits, _; without it the
		// name of the file is the title ("BeatEmUp/Burning Fight.neo" of a zip of .neo files)
		size_t open = stem.rfind(" (");
		if (open != std::string::npos && stem.back() == ')') set = stem.substr(open + 2, stem.size() - open - 3);
		if (!set.empty() && set.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_") == std::string::npos) full = stem.substr(0, open);
		else
		{
			set.clear();
			full = stem;
			r.order = 2; // after the romsets with a setname (and their data)
		}
	}
	else
	{
		auto it = names.find(lower(stem));
		if (it == names.end()) return 0;
		full = it->second;
		set = lower(stem);
		r.order = 1;
		r.label = full + " (" + stem + "." + ext + ")";
	}

	static const char *excluded[] = { "hack", "translat", "patch", "trainer", "cracked", "pirate" };
	static const char *prerelease[] = { "beta", "proto", "sample", "demo", "debug", "test", "bootleg" };
	size_t p = full.find(" (");
	title = trim(full.substr(0, p));
	if (title.empty()) return 0;
	r.rank = prefs.size();
	while (p != std::string::npos)
	{
		size_t open = full.find('(', p), close = (open == std::string::npos) ? open : full.find(')', open);
		if (close == std::string::npos) break;
		std::string tag = lower(full.substr(open + 1, close - open - 1));
		p = close + 1;
		if (has_word(tag, excluded, sizeof(excluded) / sizeof(excluded[0]))) return 0;
		if (has_word(tag, prerelease, sizeof(prerelease) / sizeof(prerelease[0]))) r.pre = 1;
		if (tag == "aes") r.rerel = 1; // the home version after the arcade one
		if (!strncmp(tag.c_str(), "set ", 4)) r.alt = atoi(tag.c_str() + 4) - 1; // (set 1) is the main one
		else if (!strncmp(tag.c_str(), "alt", 3)) r.alt = 1;
		for (auto &x : split(tag, ','))
			for (size_t i = 0; i < prefs.size(); i++) if (prefs[i] == x && (int)i < r.rank) r.rank = i;
	}
	if (setname) *setname = set;
	return 1;
}

static std::string file_ext(const std::string &name)
{
	size_t dot = name.rfind('.');
	return (dot == std::string::npos || dot == 0) ? std::string() : lower(name.substr(dot + 1));
}

// title key: case and repeated spaces don't count
static std::string title_key(const std::string &t)
{
	std::string out;
	for (char c : t)
	{
		if (c == ' ' && (out.empty() || out.back() == ' ')) continue;
		out += tolower((unsigned char)c);
	}
	return out;
}

struct found
{
	std::string path, name;
	int depth;
};

static void add_found(std::map<std::string, found> &files, const std::string &key, const std::string &path, const std::string &name, int rank)
{
	// the same file in more places: the lower rank (no date in front, not in a zip,
	// shallower), then the first path
	auto it = files.find(key);
	if (it != files.end() && (it->second.depth < rank || (it->second.depth == rank && strcasecmp(it->second.path.c_str(), path.c_str()) <= 0))) return;
	files[key] = { path, name, rank };
}

// "Altered Beast (USA, Europe).zip" or a whole collection ("SNES.zip", also with
// folders inside): the roms inside named like a game (only the central directory is read)
// romsets (Neo Geo): a zip which isn't a romset of romsets.xml, its .neo files
static void zip_roms(const std::string &root, const std::string &rel, const std::string &zip, int depth,
	const std::set<std::string> &exts, const std::set<std::string> &excl, std::map<std::string, found> &files,
	const std::map<std::string, std::string> *romsets)
{
	static const std::vector<std::string> none;
	std::string title;
	fe_grom r;

	mz_zip_archive za;
	memset(&za, 0, sizeof(za));
	if (!mz_zip_reader_init_file(&za, (root + "/" + rel + "/" + zip).c_str(), 0)) return;
	int n = mz_zip_reader_get_num_files(&za);
	for (int i = 0; i < n; i++)
	{
		mz_zip_archive_file_stat st;
		if (!mz_zip_reader_file_stat(&za, i, &st) || mz_zip_reader_is_file_a_directory(&za, i)) continue;
		std::string m = st.m_filename;
		size_t sl = m.rfind('/');
		std::string b = (sl == std::string::npos) ? m : m.substr(sl + 1);
		int skip = 0; // folders of exclude_dirs inside the zip too
		for (size_t a = 0, e; !skip && (e = m.find('/', a)) != std::string::npos; a = e + 1) skip = excl.count(lower(m.substr(a, e - a)));
		if (skip) continue;
		size_t dot = b.rfind('.');
		if (dot == std::string::npos || dot == 0 || !exts.count(lower(b.substr(dot + 1)))) continue;
		std::string stem = b.substr(0, dot);
		if (romsets ? lower(b.substr(dot + 1)) != "neo" || !parse_romset(stem, "neo", *romsets, title, r, none) : !parse_name(stem, title, r, none)) continue;
		int sub = (sl == std::string::npos) ? 0 : (int)std::count(m.begin(), m.end(), '/');
		add_found(files, lower(b.substr(date_len(b))), rel + "/" + zip + "/" + m, stem, depth + sub + 50 + (date_len(b) ? 100 : 0));
	}
	mz_zip_reader_end(&za);
}

static volatile int urgent = 0; // an awaited list is queued: the check of a cache stops

static void walk(const std::string &root, const std::string &rel, int depth, const std::set<std::string> &exts, const std::set<std::string> &excl, std::map<std::string, found> &files, int stoppable,
	const std::map<std::string, std::string> *romsets)
{
	if (depth > 8 || (stoppable && urgent)) return;
	DIR *d = opendir((root + "/" + rel).c_str());
	if (!d) return;

	std::vector<std::string> dirs;
	while (struct dirent *de = readdir(d))
	{
		if (de->d_name[0] == '.') continue;
		std::string name = de->d_name;
		int type = de->d_type;
		if (type == DT_UNKNOWN || type == DT_LNK)
		{
			struct stat st;
			if (stat((root + "/" + rel + "/" + name).c_str(), &st)) continue;
			type = S_ISDIR(st.st_mode) ? DT_DIR : DT_REG;
		}

		if (type == DT_DIR)
		{
			if (!excl.count(lower(name))) dirs.push_back(name);
			continue;
		}

		size_t dot = name.rfind('.');
		if (dot == std::string::npos || dot == 0) continue;
		std::string ext = lower(name.substr(dot + 1));
		if (ext == "zip" && (!exts.count(ext) || (romsets && !romsets->count(lower(name.substr(0, dot))))))
		{
			zip_roms(root, rel, name, depth, exts, excl, files, romsets);
			continue;
		}
		if (!exts.count(ext)) continue;

		// the same file in more folders (collections): the one without a date in
		// front ("1991-08-23 F-Zero (USA).sfc"), then the shallowest one
		size_t dl = date_len(name);
		add_found(files, lower(name.substr(dl)), rel + "/" + name, name.substr(0, dot), depth + (dl ? 100 : 0));
	}
	closedir(d);

	for (auto &n : dirs) walk(root, rel + "/" + n, depth + 1, exts, excl, files, stoppable, romsets);
}

// groups.txt of the scraper: title key -> group id
static std::map<std::string, std::string> read_groups(const std::string &dir)
{
	std::map<std::string, std::string> out;
	std::string path = std::string(getRootDir()) + "/frontier/gamelists/" + lower(dir) + "/groups.txt";
	FILE *fp = fopen(path.c_str(), "r");
	if (!fp) return out;
	char line[1024];
	while (fgets(line, sizeof(line), fp))
	{
		line[strcspn(line, "\r\n")] = 0;
		if (line[0] == '#') continue;
		char *tab = strchr(line, '\t');
		if (!tab) continue;
		*tab = 0;
		out[title_key(tab + 1)] = line;
	}
	fclose(fp);
	return out;
}

static int find_root(std::vector<int> &parent, int i)
{
	while (parent[i] != i) i = parent[i] = parent[parent[i]];
	return i;
}

// files with a region of a folder, relative to the root (worker thread)
static std::vector<std::string> scan_files(const std::string &dir, const std::set<std::string> &exts, const std::set<std::string> &excl, int romsets, int stoppable, int &ok)
{
	struct stat st;
	ok = !stat((std::string(getRootDir()) + "/games/" + dir).c_str(), &st) && S_ISDIR(st.st_mode);
	std::map<std::string, found> files;
	std::map<std::string, std::string> names;
	if (romsets) names = read_romsets(dir);
	walk(getRootDir(), "games/" + dir, 0, exts, excl, files, stoppable, romsets ? &names : 0);

	if (romsets)
	{
		std::vector<std::string> out;
		static const std::vector<std::string> none;
		for (auto &f : files)
		{
			fe_grom r;
			std::string title;
			if (parse_romset(f.second.name, file_ext(f.second.path), names, title, r, none)) out.push_back(f.second.path);
		}
		return out;
	}

	// copies with a number in front in the lists of the collections ("006 Lightening
	// Force (USA).md", "057 - Wonder Boy (Japan).sg"): dropped if the title without
	// the number is the title of another file
	static const std::vector<std::string> none;
	std::set<std::string> titles;
	for (auto &f : files)
	{
		fe_grom r;
		std::string title;
		if (parse_name(f.second.name, title, r, none)) titles.insert(lower(title));
	}
	for (auto it = files.begin(); it != files.end();)
	{
		const std::string &k = it->first;
		size_t i = 0, j;
		while (i < k.size() && isdigit((unsigned char)k[i])) i++;
		for (j = i; j < k.size() && strchr(" ._-", k[j]); j++);
		// k: lowercase file name without the date, name: the same without the extension
		std::string name = it->second.name.substr(date_len(it->second.name));
		fe_grom r;
		std::string title;
		if (i && j > i && j < name.size() && (files.count(k.substr(j)) ||
			(parse_name(name.substr(j), title, r, none) && titles.count(lower(title))))) it = files.erase(it);
		else ++it;
	}

	std::vector<std::string> out;
	for (auto &f : files)
	{
		fe_grom r;
		std::string title;
		if (parse_name(f.second.name, title, r, none)) out.push_back(f.second.path);
	}
	return out;
}

// list of games from the files (main thread)
static void build(fe_gsystem &s, const std::string &dir, const std::vector<std::string> &paths)
{
	s = fe_gsystem();
	int romsets = fe_games_romsets(dir);
	std::map<std::string, std::string> names;
	if (romsets) names = read_romsets(dir);

	// roms by title
	std::map<std::string, std::vector<int>> by_title;
	std::map<std::string, std::string> shown; // title key -> title as in the first file
	std::vector<std::pair<std::string, std::string>> links; // title key -> group id (groups.txt, romsets: setname)
	for (auto &p : paths)
	{
		fe_grom r;
		std::string title, set;
		std::string name = p.substr(p.rfind('/') + 1);
		std::string ext = file_ext(name);
		size_t dot = name.rfind('.');
		if (dot != std::string::npos && dot > 0) name.erase(dot);
		if (romsets ? !parse_romset(name, ext, names, title, r, regions, &set) : !parse_name(name, title, r, regions)) continue;
		r.path = p;
		r.name = name;
		std::string key = title_key(title);
		if (!set.empty()) links.push_back({ key, "set:" + set }); // titles with the same romset are linked
		by_title[key].push_back(s.roms.size());
		if (!shown.count(key)) shown[key] = title;
		s.roms.push_back(r);
	}

	// titles linked by groups.txt or by a romset
	std::vector<std::string> keys;
	std::map<std::string, int> key_index;
	for (auto &t : by_title)
	{
		key_index[t.first] = keys.size();
		keys.push_back(t.first);
	}
	std::vector<int> parent(keys.size());
	for (size_t i = 0; i < parent.size(); i++) parent[i] = i;
	std::map<std::string, int> group_first;
	for (auto &g : read_groups(dir)) links.push_back(g);
	for (auto &g : links)
	{
		auto k = key_index.find(g.first);
		if (k == key_index.end()) continue;
		auto f = group_first.find(g.second);
		if (f == group_first.end()) group_first[g.second] = k->second;
		else parent[find_root(parent, k->second)] = find_root(parent, f->second);
	}

	std::map<int, int> group_of_root;
	for (size_t i = 0; i < keys.size(); i++)
	{
		int root = find_root(parent, i);
		if (!group_of_root.count(root))
		{
			group_of_root[root] = s.groups.size();
			s.groups.emplace_back();
		}
		int g = group_of_root[root];
		std::vector<int> &roms = by_title[keys[i]];
		s.groups[g].insert(s.groups[g].end(), roms.begin(), roms.end());

		fe_gtitle t;
		t.title = shown[keys[i]];
		t.group = g;
		t.def = roms[0];
		for (int r : roms) if (better(s.roms[r], s.roms[t.def])) t.def = r;
		s.titles.push_back(t);
	}

	for (auto &g : s.groups) std::sort(g.begin(), g.end(), [&](int a, int b) { return better(s.roms[a], s.roms[b]); });
	std::sort(s.titles.begin(), s.titles.end(), [](const fe_gtitle &a, const fe_gtitle &b) { return strcasecmp(a.title.c_str(), b.title.c_str()) < 0; });
	for (size_t i = 0; i < s.titles.size(); i++) s.title_index[s.titles[i].title] = i;
	for (auto &t : by_title)
	{
		int ti = s.title_index[shown[t.first]];
		for (int r : t.second) s.rom_title[s.roms[r].name] = ti;
	}
}

/////////////////////////////////////////////////////////////////////////////
// cache (frontier/.cache/games_<folder>.txt: the files with a region) and the
// thread which reads the folders again

struct folder_state
{
	std::vector<std::string> paths; // files of the list in memory
	int checked = 0;                // read again by the thread in this session
	int built = 0;
};

static std::map<std::string, folder_state> folders; // by folder name, case sensitive (MegaDrive and Megadrive can both be there)

static pthread_mutex_t mtx = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cond = PTHREAD_COND_INITIALIZER;
static int thread_started = 0;
struct job
{
	std::string dir;
	std::set<std::string> exts;
	std::set<std::string> excl;
	int romsets;
	int nice;  // 0 if the list is awaited ("Reading the games..."), 15 to check the cache
};
static std::vector<job> queue;
struct result
{
	std::string dir;
	std::vector<std::string> paths;
	int ok;  // 0: the folder is not there (USB disk not mounted yet)
	int nice;
};
static std::vector<result> done;

static std::string cache_path(const std::string &dir)
{
	return std::string(getRootDir()) + "/frontier/.cache/games_" + dir + ".txt";
}

// first line of the cache: format (N: romsets with the .neo files without setname and
// those in zip files) and excluded folders (other ones: the cache is not used)
static std::string cache_header(const std::string &dir)
{
	std::string h = fe_games_romsets(dir) ? "FEG2N" : "FEG2";
	for (auto &e : exclude) h += "\t" + e;
	return h;
}

static int read_cache(const std::string &dir, std::vector<std::string> &paths)
{
	FILE *fp = fopen(cache_path(dir).c_str(), "r");
	if (!fp) return 0;
	char line[2048];
	int ok = fgets(line, sizeof(line), fp) && std::string(line, strcspn(line, "\r\n")) == cache_header(dir);
	while (ok && fgets(line, sizeof(line), fp))
	{
		line[strcspn(line, "\r\n")] = 0;
		if (line[0]) paths.push_back(line);
	}
	fclose(fp);
	return ok;
}

static void write_cache(const std::string &dir, const std::vector<std::string> &paths)
{
	std::string path = cache_path(dir);
	mkdir((std::string(getRootDir()) + "/frontier/.cache").c_str(), 0755);
	std::string tmp = path + ".tmp";
	FILE *fp = fopen(tmp.c_str(), "w");
	if (!fp) return;
	fprintf(fp, "%s\n", cache_header(dir).c_str());
	for (auto &p : paths) fprintf(fp, "%s\n", p.c_str());
	fclose(fp);
	rename(tmp.c_str(), path.c_str());
}

static void *worker(void *)
{
	pthread_mutex_lock(&mtx);
	while (1)
	{
		while (queue.empty()) pthread_cond_wait(&cond, &mtx);
		// awaited lists first
		auto it = std::min_element(queue.begin(), queue.end(), [](const job &a, const job &b) { return a.nice < b.nice; });
		job j = *it;
		queue.erase(it);
		urgent = 0;
		for (auto &q : queue) if (!q.nice) urgent = 1;
		pthread_mutex_unlock(&mtx);

		setpriority(PRIO_PROCESS, syscall(SYS_gettid), j.nice);
		struct timespec t0, t1;
		clock_gettime(CLOCK_MONOTONIC, &t0);
		int ok = 0;
		std::vector<std::string> paths = scan_files(j.dir, j.exts, j.excl, j.romsets, j.nice > 0, ok);
		clock_gettime(CLOCK_MONOTONIC, &t1);
		if (j.nice > 0 && urgent)
		{
			// stopped for an awaited list: again later
			pthread_mutex_lock(&mtx);
			queue.push_back(j);
			continue;
		}
		fprintf(stderr, "frontier: games/%s read (nice %d): %d files with a region, %.0f ms\n", j.dir.c_str(), j.nice, (int)paths.size(),
			(t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6);

		pthread_mutex_lock(&mtx);
		done.push_back({ j.dir, paths, ok, j.nice });
	}
	return 0;
}

void fe_group_regions(const std::string &csv)
{
	std::vector<std::string> list = split(lower(csv), ',');
	if (list.empty()) list = { "usa", "world", "europe", "japan" };
	if (list != regions)
	{
		regions = list;
		// the same files, other default versions
		for (auto &f : folders) f.second.built = 0;
		scanned.clear();
	}
}

void fe_group_exclude(const std::string &csv)
{
	std::set<std::string> list;
	for (auto &e : split(lower(csv), ','))
		if (!e.empty()) list.insert(e);
	if (list != exclude)
	{
		exclude = list;
		fe_group_reset();
	}
}

void fe_group_reset()
{
	scanned.clear();
	folders.clear();
	rescans.clear();
}

void fe_group_manual(int on)
{
	manual = on;
}

static void queue_job(const std::string &dir, int nice)
{
	std::set<std::string> exts;
	for (auto &e : fe_games_ext_list(dir)) exts.insert(e);
	pthread_mutex_lock(&mtx);
	queue.push_back({ dir, exts, exclude, fe_games_romsets(dir), nice });
	if (!nice) urgent = 1;
	if (!thread_started)
	{
		pthread_t th;
		if (!pthread_create(&th, 0, worker, 0))
		{
			pthread_detach(th);
			thread_started = 1;
		}
	}
	pthread_cond_signal(&cond);
	pthread_mutex_unlock(&mtx);
}

const fe_gsystem *fe_group_get(const std::string &dir)
{
	const std::string &key = dir;
	auto it = scanned.find(key);
	if (it != scanned.end()) return &it->second;

	// files known (cache or thread) but not built yet (regions or groups changed)
	auto f = folders.find(key);
	if (f == folders.end() || (f->second.paths.empty() && !f->second.checked)) return 0;
	build(scanned[key], dir, f->second.paths);
	f->second.built = 1;
	return &scanned[key];
}

void fe_group_request(const std::string &dir)
{
	const std::string &key = dir;
	if (folders.count(key)) return;
	folder_state &f = folders[key];

	// the list of the last time, at once
	// an empty list is not trusted: the folder is read at once (it was empty or
	// not mounted, or the cache belongs to a folder with the same name in other
	// case, the SD card is FAT)
	int cached = read_cache(dir, f.paths) && !f.paths.empty();
	if (cached)
	{
		build(scanned[key], dir, f.paths);
		f.built = 1;
		if (manual) return; // read again only when asked (fe_group_rescan)
	}

	// then the folders are read again
	queue_job(dir, cached ? 15 : 0);
}

void fe_group_rescan(const std::string &dir)
{
	if (rescans.count(dir)) return;
	int known = folders.count(dir);
	fe_group_request(dir);
	rescans.insert(dir);
	// a new folder without the cache is being read already
	if (known || folders[dir].built) queue_job(dir, 0);
}

int fe_group_busy(const std::string &dir)
{
	return rescans.count(dir) > 0;
}

int fe_group_poll(std::string &dir)
{
	result res;
	pthread_mutex_lock(&mtx);
	int got = !done.empty();
	if (got)
	{
		res = done.front();
		done.erase(done.begin());
	}
	pthread_mutex_unlock(&mtx);
	if (!got) return 0;

	const std::string &key = res.dir;
	if (!res.nice) rescans.erase(key); // an awaited list (also a fe_group_rescan()) is there
	auto f = folders.find(key);
	if (f == folders.end()) return 0; // F5 in the meantime
	if (!res.ok)
	{
		// folder not there (yet): the cache stays, asked again next time
		if (!f->second.built) scanned.erase(key);
		folders.erase(f);
		return 0;
	}
	f->second.checked = 1;
	if (f->second.built && res.paths == f->second.paths) return 0; // nothing changed

	f->second.paths = res.paths;
	write_cache(res.dir, res.paths);
	build(scanned[key], res.dir, res.paths);
	f->second.built = 1;
	dir = res.dir;
	return 1;
}

const fe_gtitle *fe_group_title(const fe_gsystem *s, const std::string &title)
{
	if (!s) return 0;
	auto it = s->title_index.find(title);
	return (it == s->title_index.end()) ? 0 : &s->titles[it->second];
}
