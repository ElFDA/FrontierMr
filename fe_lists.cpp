// Games by their data and the filter of "+ New list from filter..." of My Lists (see fe_lists.h).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include <time.h>
#include <unistd.h>
#include <sys/stat.h>

#include <algorithm>
#include <map>

#include "fe_lists.h"
#include "fe_group.h"
#include "fe_games.h"
#include "file_io.h"

#define INDEX_FILE "frontier/.cache/meta.tsv"
#define FILTER_FILE "frontier/.cache/filter.txt"

enum { A_SYSTEM, A_CORE, A_PUBLISHER, A_DEVELOPER, A_GENRE, A_SUBGENRE, A_YEAR, A_SERIES, A_PLAYERS, A_DECADE, A_COUNT };
// names in the paths, labels shown
static const char *attr_names[A_COUNT] = { "system", "core", "publisher", "developer", "genre", "subgenre", "year", "series", "players", "decade" };
static const char *attr_labels[A_COUNT] = { "System", "Core", "Publisher", "Developer", "Genre", "Subgenre", "Year", "Series", "Players", "Decade" };
// columns of meta.tsv (-1: the file)
static const int columns[] = { A_SYSTEM, -1, A_CORE, A_PUBLISHER, A_DEVELOPER, A_GENRE, A_SUBGENRE, A_YEAR, A_SERIES, A_PLAYERS };
// lines of the filter, in this order
static const int filter_rows[] = { A_SYSTEM, A_CORE, A_PUBLISHER, A_DEVELOPER, A_GENRE, A_SUBGENRE, A_DECADE, A_YEAR, A_SERIES, A_PLAYERS };

typedef std::pair<int, int> fe_lval; // attribute, value id

struct fe_lrow
{
	int sys = -1;             // value id of A_SYSTEM
	std::string file;         // key of the gamelist, .mra file
	std::vector<fe_lval> v;
};

struct fe_lgame
{
	std::string key, label;
	std::string sys_label;    // shown on the right
	int def;                  // the data come from the version launched
	std::vector<fe_lval> v;
};

static int loaded = 0;       // index read (0: again at the next use)
static int games_dirty = 1;  // the games are made again from the rows
static size_t games_folders = 0;
static std::vector<std::string> values[A_COUNT];
static std::map<std::string, int> value_ids[A_COUNT]; // lowercase value -> id
static std::vector<fe_lrow> rows;
static std::vector<fe_lgame> games;

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
	while (1)
	{
		size_t end = s.find(sep, pos);
		out.push_back(s.substr(pos, end == std::string::npos ? std::string::npos : end - pos));
		if (end == std::string::npos) break;
		pos = end + 1;
	}
	return out;
}

// '/' and '%' of a name or value in a path
static std::string enc(const std::string &s)
{
	std::string out;
	for (char c : s)
	{
		if (c == '%') out += "%25";
		else if (c == '/') out += "%2F";
		else out += c;
	}
	return out;
}

static std::string dec(const std::string &s)
{
	std::string out;
	for (size_t i = 0; i < s.size(); i++)
	{
		if (s[i] == '%' && !s.compare(i, 3, "%2F")) { out += '/'; i += 2; }
		else if (s[i] == '%' && !s.compare(i, 3, "%25")) { out += '%'; i += 2; }
		else out += s[i];
	}
	return out;
}

static int attr_of(const std::string &name)
{
	for (int a = 0; a < A_COUNT; a++) if (!strcasecmp(name.c_str(), attr_names[a])) return a;
	return -1;
}

static int intern(int a, const std::string &v)
{
	std::string k = lower(v);
	auto it = value_ids[a].find(k);
	if (it != value_ids[a].end()) return it->second;
	value_ids[a][k] = values[a].size();
	values[a].push_back(v);
	return values[a].size() - 1;
}

static int value_id(int a, const std::string &v)
{
	auto it = value_ids[a].find(lower(trim(v)));
	return (it == value_ids[a].end()) ? -1 : it->second;
}

/////////////////////////////////////////////////////////////////////////////
// systems

// games/ folders of a system of the index: gamelists/<system> is lowercase, the folders
// can be MegaDrive and Megadrive
static std::vector<std::string> sys_dirs(const std::string &sys)
{
	std::vector<std::string> out;
	for (auto &f : fe_games_folders()) if (lower(f.dir) == sys) out.push_back(f.dir);
	return out;
}

// "Mega Drive / Genesis" -> "Mega Drive"
static std::string sys_label(const std::string &sys)
{
	if (sys == "arcade") return "Arcade";
	for (auto &d : sys_dirs(sys))
	{
		const fe_games_folder *f = fe_games_find(d);
		if (f) return f->name.substr(0, f->name.find(" / "));
	}
	return sys;
}

static std::string value_label(int a, const std::string &v)
{
	if (a == A_SYSTEM) return sys_label(lower(v));
	if (a == A_PLAYERS) return v + (v == "1" ? " player" : " players");
	return v;
}

/////////////////////////////////////////////////////////////////////////////
// files

static void read_index()
{
	for (int a = 0; a < A_COUNT; a++)
	{
		values[a].clear();
		value_ids[a].clear();
	}
	rows.clear();

	struct timespec t0, t1;
	clock_gettime(CLOCK_MONOTONIC, &t0);
	FILE *fp = fopen((std::string(getRootDir()) + "/" INDEX_FILE).c_str(), "r");
	if (!fp) return;
	char *line = 0;
	size_t size = 0;
	ssize_t len;
	int first = 1;
	while ((len = getline(&line, &size, fp)) >= 0)
	{
		line[strcspn(line, "\r\n")] = 0;
		if (first)
		{
			first = 0;
			if (strncmp(line, "FEM1", 4))
			{
				fprintf(stderr, "frontier: lists: %s of another version, run the scraper again\n", INDEX_FILE);
				break;
			}
			continue;
		}
		std::vector<std::string> f = split(line, '\t');
		if (f.size() < 2 || f[0].empty() || f[1].empty()) continue;
		fe_lrow r;
		r.file = f[1];
		for (size_t c = 0; c < f.size() && c < sizeof(columns) / sizeof(columns[0]); c++)
		{
			int a = columns[c];
			if (a < 0 || f[c].empty()) continue;
			for (auto &v : split(f[c], '|'))
			{
				if (v.empty()) continue;
				int id = intern(a, v);
				r.v.push_back({ a, id });
				if (a == A_SYSTEM) r.sys = id;
				if (a == A_YEAR) r.v.push_back({ A_DECADE, intern(A_DECADE, v.substr(0, 3) + "0s") });
			}
		}
		rows.push_back(r);
	}
	free(line);
	fclose(fp);
	clock_gettime(CLOCK_MONOTONIC, &t1);
	fprintf(stderr, "frontier: lists: %d games in %s, %.0f ms\n", (int)rows.size(), INDEX_FILE,
		(t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6);
}

/////////////////////////////////////////////////////////////////////////////
// games

static int has_attr(const fe_lgame &g, int a)
{
	for (auto &p : g.v) if (p.first == a) return 1;
	return 0;
}

// a game for each title: the rows of all the versions of a game by title become one
static void make_games()
{
	struct timespec t0, t1;
	clock_gettime(CLOCK_MONOTONIC, &t0);
	games.clear();
	std::map<std::string, int> index;            // key -> game
	std::map<int, std::vector<std::string>> dirs; // system -> games/ folders
	std::map<int, std::string> labels;            // system -> name shown
	int arcade = value_id(A_SYSTEM, "arcade");
	int unknown = 0;
	for (auto &r : rows)
	{
		fe_lgame g;
		g.def = 1;
		if (r.sys == arcade)
		{
			g.key = std::string("_Arcade/") + r.file;
			g.label = r.file.substr(0, r.file.rfind('.'));
			g.sys_label = "Arcade";
		}
		else
		{
			auto d = dirs.find(r.sys);
			if (d == dirs.end())
			{
				d = dirs.emplace(r.sys, sys_dirs(values[A_SYSTEM][r.sys])).first;
				for (auto &x : d->second) fe_group_request(x); // from the cache at once
				labels[r.sys] = sys_label(values[A_SYSTEM][r.sys]);
			}
			for (auto &dir : d->second)
			{
				const fe_gsystem *s = fe_group_get(dir);
				if (!s) continue;
				auto it = s->rom_title.find(r.file);
				if (it == s->rom_title.end()) continue;
				const fe_gtitle &t = s->titles[it->second];
				g.key = "@sys/" + dir + "/" + t.title;
				g.label = t.title;
				g.def = s->roms[t.def].name == r.file;
				g.sys_label = labels[r.sys];
				break;
			}
			if (g.key.empty())
			{
				unknown++; // a file not there any more, not listed by title, or a folder not read yet
				continue;
			}
		}

		auto it = index.find(g.key);
		if (it == index.end())
		{
			index[g.key] = games.size();
			g.v = r.v;
			games.push_back(g);
			continue;
		}
		fe_lgame &x = games[it->second];
		if (g.def && !x.def)
		{
			// the data of the version launched
			x.def = 1;
			x.v = r.v;
			continue;
		}
		// the other versions: only the data missing
		std::vector<fe_lval> add;
		for (auto &p : r.v) if (!has_attr(x, p.first)) add.push_back(p);
		x.v.insert(x.v.end(), add.begin(), add.end());
	}
	games_dirty = 0;
	games_folders = fe_games_folders().size();
	clock_gettime(CLOCK_MONOTONIC, &t1);
	fprintf(stderr, "frontier: lists: %d games (%d files not found), %.0f ms\n", (int)games.size(), unknown,
		(t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6);
}

static void ready()
{
	if (!loaded)
	{
		loaded = 1;
		read_index();
		games_dirty = 1;
	}
	// games/ on a USB disk mounted later: its folders are there now
	if (games_dirty || games_folders != fe_games_folders().size()) make_games();
}

void fe_lists_reset()
{
	loaded = 0;
	games_dirty = 1;
}

void fe_lists_group_changed()
{
	games_dirty = 1;
}

/////////////////////////////////////////////////////////////////////////////
// filter: values chosen for each data, one of them (OR), all the data (AND); kept in
// frontier/.cache/filter.txt ("<data>\t<value>" lines), also after a game

static std::vector<std::string> chosen[A_COUNT];
static int filter_read = 0;

static std::string filter_file()
{
	return std::string(getRootDir()) + "/" FILTER_FILE;
}

static void read_filter()
{
	filter_read = 1;
	for (auto &c : chosen) c.clear();
	FILE *fp = fopen(filter_file().c_str(), "r");
	if (!fp) return;
	char line[1024];
	while (fgets(line, sizeof(line), fp))
	{
		line[strcspn(line, "\r\n")] = 0;
		char *tab = strchr(line, '\t');
		if (!tab) continue;
		*tab = 0;
		int a = attr_of(line);
		if (a >= 0 && tab[1]) chosen[a].push_back(tab + 1);
	}
	fclose(fp);
}

static void write_filter()
{
	std::string path = filter_file(), tmp = path + ".tmp";
	FILE *fp = fopen(tmp.c_str(), "w");
	if (!fp) return;
	for (int a = 0; a < A_COUNT; a++) for (auto &v : chosen[a]) fprintf(fp, "%s\t%s\n", attr_names[a], v.c_str());
	fclose(fp);
	rename(tmp.c_str(), path.c_str());
}

static int is_chosen(int a, const std::string &v)
{
	for (auto &c : chosen[a]) if (!strcasecmp(c.c_str(), v.c_str())) return 1;
	return 0;
}

struct fe_lcond
{
	int a;
	std::vector<int> ids;     // empty: no value known, no games
};

// the conditions of the filter, without those of one data (skip)
static std::vector<fe_lcond> conditions(int skip = -1)
{
	std::vector<fe_lcond> out;
	for (int a = 0; a < A_COUNT; a++)
	{
		if (a == skip || chosen[a].empty()) continue;
		fe_lcond c;
		c.a = a;
		for (auto &v : chosen[a])
		{
			int id = value_id(a, v);
			if (id >= 0) c.ids.push_back(id);
		}
		out.push_back(c);
	}
	return out;
}

static int match(const fe_lgame &g, const std::vector<fe_lcond> &conds)
{
	for (auto &c : conds)
	{
		int ok = 0;
		for (auto &p : g.v)
		{
			if (p.first != c.a) continue;
			for (int id : c.ids) if (id == p.second) ok = 1;
			if (ok) break;
		}
		if (!ok) return 0;
	}
	return 1;
}

// values of a data among the games of the filter without its own choice: value id -> games
static std::map<int, int> count_values(int a)
{
	std::vector<fe_lcond> conds = conditions(a);
	std::map<int, int> out;
	for (auto &g : games)
	{
		if (!match(g, conds)) continue;
		int last = -1;
		for (auto &p : g.v) if (p.first == a && p.second != last) out[last = p.second]++;
	}
	return out;
}

static void add(std::vector<fe_entry> &out, const std::string &name, const std::string &label, const std::string &tag, int dir)
{
	fe_entry e;
	e.name = name;
	e.label = label;
	e.tag = tag;
	e.dir = dir;
	out.push_back(e);
}

// "Capcom, Konami", "Capcom +2", "any"
static std::string chosen_text(int a)
{
	if (chosen[a].empty()) return "any";
	std::string out = value_label(a, chosen[a][0]);
	if (chosen[a].size() == 2) out += ", " + value_label(a, chosen[a][1]);
	else if (chosen[a].size() > 2) out += " +" + std::to_string(chosen[a].size() - 1);
	return out;
}

static void ready_filter()
{
	ready();
	if (!filter_read) read_filter();
}

int fe_lists_entries(const std::string &path, std::vector<fe_entry> &out)
{
	ready_filter();
	out.clear();
	add(out, "..", "..", "", 1);

	if (path == FE_LISTS)
	{
		// a line for each data with values, what is chosen on the right
		if (games.empty()) add(out, "", rows.empty() ? "No data: run the scraper (or fe_scrape.py --index)" : "No games found", "", 0);
		for (int a : filter_rows)
		{
			int any = 0;
			for (auto &g : games) if ((any = has_attr(g, a))) break;
			if (any || !chosen[a].empty()) add(out, std::string(FE_LISTS "/v/") + attr_names[a], attr_labels[a], chosen_text(a), 1);
		}
		return 1;
	}

	if (!path.compare(0, strlen(FE_LISTS "/v/"), FE_LISTS "/v/"))
	{
		// the values of a data: [x] chosen, with the number of games
		int a = attr_of(path.substr(strlen(FE_LISTS "/v/")));
		if (a < 0) return 0;
		std::string base = path + "/";
		add(out, base, std::string(chosen[a].empty() ? "[x]" : "[ ]") + " Any", "", 0);
		std::map<int, int> count = count_values(a);
		for (auto &v : chosen[a])
		{
			int id = value_id(a, v);
			if (id >= 0 && !count.count(id)) count[id] = 0; // chosen, no games with the other choices
		}
		std::vector<fe_entry> list;
		for (auto &c : count)
		{
			const std::string &v = values[a][c.first];
			add(list, base + enc(v), std::string(is_chosen(a, v) ? "[x] " : "[ ] ") + value_label(a, v), std::to_string(c.second), 0);
		}
		std::sort(list.begin(), list.end(), [a](const fe_entry &x, const fe_entry &y) {
			if (a == A_YEAR || a == A_DECADE || a == A_PLAYERS) return x.label.substr(4) < y.label.substr(4);
			return strcasecmp(x.label.c_str() + 4, y.label.c_str() + 4) < 0;
		});
		out.insert(out.end(), list.begin(), list.end());
		return 1;
	}

	if (path == FE_LISTS "/games")
	{
		// the games of the filter, the system on the right if they are of more systems
		std::vector<fe_lcond> conds = conditions();
		std::vector<fe_entry> list;
		std::string sys;
		int systems = 0;
		for (auto &g : games)
		{
			if (!match(g, conds)) continue;
			if (g.sys_label != sys && systems < 2)
			{
				systems++;
				sys = g.sys_label;
			}
			add(list, g.key, g.label, g.sys_label, 0);
		}
		if (systems < 2) for (auto &e : list) e.tag.clear();
		std::stable_sort(list.begin(), list.end(), [](const fe_entry &x, const fe_entry &y) {
			int c = strcasecmp(x.label.c_str(), y.label.c_str());
			return c ? c < 0 : strcasecmp(x.tag.c_str(), y.tag.c_str()) < 0;
		});
		out.insert(out.end(), list.begin(), list.end());
		if (list.empty()) add(out, "", "No games", "", 0);
		return 1;
	}
	return 0;
}

int fe_lists_toggle(const std::string &name)
{
	const char *prefix = FE_LISTS "/v/";
	if (name.compare(0, strlen(prefix), prefix)) return 0;
	size_t slash = name.find('/', strlen(prefix));
	if (slash == std::string::npos) return 0;
	int a = attr_of(name.substr(strlen(prefix), slash - strlen(prefix)));
	if (a < 0) return 0;
	ready_filter();
	std::string v = dec(name.substr(slash + 1));
	if (v.empty()) chosen[a].clear(); // "Any"
	else if (is_chosen(a, v))
	{
		for (size_t i = 0; i < chosen[a].size(); i++)
			if (!strcasecmp(chosen[a][i].c_str(), v.c_str())) chosen[a].erase(chosen[a].begin() + i--);
	}
	else chosen[a].push_back(v);
	write_filter();
	return 1;
}

void fe_lists_clear()
{
	ready_filter();
	for (auto &c : chosen) c.clear();
	write_filter();
}

int fe_lists_has_filter()
{
	ready_filter();
	for (auto &c : chosen) if (!c.empty()) return 1;
	return 0;
}

int fe_lists_count()
{
	ready_filter();
	std::vector<fe_lcond> conds = conditions();
	int n = 0;
	for (auto &g : games) n += match(g, conds);
	return n;
}

void fe_lists_games(std::vector<std::pair<std::string, std::string>> &out)
{
	std::vector<fe_entry> list;
	fe_lists_entries(FE_LISTS "/games", list);
	out.clear();
	for (auto &e : list) if (!e.dir && !e.name.empty()) out.push_back({ e.name, e.label });
}

std::string fe_lists_parent(const std::string &path, std::string &select)
{
	select = path;
	return (path == FE_LISTS) ? std::string() : std::string(FE_LISTS);
}

std::string fe_lists_name()
{
	ready_filter();
	std::string name;
	for (int a : filter_rows)
	{
		if (chosen[a].empty()) continue;
		std::string part;
		for (auto &v : chosen[a]) part += (part.empty() ? "" : ", ") + value_label(a, v);
		name += (name.empty() ? "" : " - ") + part;
	}
	return name.empty() ? std::string("All games") : name;
}

std::string fe_lists_title(const std::string &path)
{
	if (path == FE_LISTS "/games") return fe_lists_name();
	if (path == FE_LISTS "/add") return "Add to a list";
	if (path == FE_LISTS "/new") return "Name of the new list";
	if (!path.compare(0, strlen(FE_LISTS "/v/"), FE_LISTS "/v/"))
	{
		int a = attr_of(path.substr(strlen(FE_LISTS "/v/")));
		if (a >= 0) return attr_labels[a];
	}
	return "New list from filter";
}

std::string fe_lists_system(const std::string &name)
{
	const char *prefix = FE_LISTS "/v/system/";
	if (name.compare(0, strlen(prefix), prefix) || name.size() == strlen(prefix)) return "";
	std::string sys = lower(dec(name.substr(strlen(prefix))));
	if (sys == "arcade") return "@arcade";
	std::vector<std::string> dirs = sys_dirs(sys);
	return dirs.empty() ? std::string() : dirs[0];
}
