// "#Newest" of the Arcade folder, see fe_newest.h

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/stat.h>
#include <map>
#include <algorithm>

#include "fe_newest.h"
#include "fe_alt.h"

#define FE_NEW_CLOCK_OK 1748736000 // 2025-06-01: before that the clock isn't set
#define FE_NEW_DEPTH    4

struct known
{
	time_t seen;
	time_t mtime;
};

static std::map<std::string, known> seen_map;   // the file
static std::map<std::string, time_t> present;    // .mra of the last scan: mtime
static std::string base_root, base_file;         // of the last scan

struct mra_meta
{
	long mtime = 0;
	std::string set, parent;
	std::vector<std::string> keys;
};
static std::map<std::string, mra_meta> metas;    // frontier/.cache/newest_keys.txt
static int metas_loaded = 0, metas_changed = 0;
static std::map<std::string, std::vector<std::string>> group_others; // last list: entry -> the other .mra

static void walk(const std::string &root, const std::string &rel, int depth)
{
	DIR *d = opendir((root + "/" + rel).c_str());
	if (!d) return;
	while (struct dirent *de = readdir(d))
	{
		const char *n = de->d_name;
		if (n[0] == '.') continue;
		std::string sub = rel + "/" + n;
		struct stat st;
		if (stat((root + "/" + sub).c_str(), &st)) continue;
		if (S_ISDIR(st.st_mode))
		{
			if (depth < FE_NEW_DEPTH && strcasecmp(n, "_alternatives")) walk(root, sub, depth + 1);
			continue;
		}
		size_t len = strlen(n);
		if (len > 4 && !strcasecmp(n + len - 4, ".mra")) present[sub] = st.st_mtime;
	}
	closedir(d);
}

static void read_file(const std::string &file)
{
	seen_map.clear();
	FILE *fp = fopen(file.c_str(), "r");
	if (!fp) return;
	char line[2048];
	while (fgets(line, sizeof(line), fp))
	{
		line[strcspn(line, "\r\n")] = 0;
		char *t1 = strchr(line, '\t');
		char *t2 = t1 ? strchr(t1 + 1, '\t') : 0;
		if (!t2) continue;
		*t1 = 0;
		*t2 = 0;
		known k;
		k.seen = atol(line);
		k.mtime = atol(t1 + 1);
		seen_map[t2 + 1] = k;
	}
	fclose(fp);
}

static void write_file(const std::string &file)
{
	std::string tmp = file + ".tmp";
	FILE *fp = fopen(tmp.c_str(), "w");
	if (!fp) return;
	for (auto &k : seen_map) fprintf(fp, "%ld\t%ld\t%s\n", (long)k.second.seen, (long)k.second.mtime, k.first.c_str());
	fflush(fp);
	fsync(fileno(fp));
	fclose(fp);
	rename(tmp.c_str(), file.c_str());
}

void fe_newest_scan(const std::string &root, const std::string &file)
{
	// the clock isn't set for the first seconds after the power on (no RTC): what is known
	// is read all the same, only the new games wait to be told the day
	time_t now = time(0);
	int clock_ok = now >= FE_NEW_CLOCK_OK;
	base_root = root;
	base_file = file;

	present.clear();
	walk(root, "_Arcade", 0);
	if (present.empty()) return; // nothing read (not there yet): don't take it for a baseline

	int first = access(file.c_str(), F_OK) != 0;
	if (!first) read_file(file);
	else seen_map.clear();
	if (first && !clock_ok) return; // the baseline waits for the clock too

	int changed = first;
	for (auto &p : present)
	{
		auto it = seen_map.find(p.first);
		if (it != seen_map.end()) continue;
		if (!clock_ok) continue;
		known k;
		k.seen = first ? 0 : now;
		k.mtime = p.second;
		seen_map[p.first] = k;
		changed = 1;
	}
	if (changed) write_file(file);
	printf("frontier: newest: %d arcade games, %s\n", (int)present.size(), !clock_ok ? "clock not set, only the known ones" : first ? "all known (first time)" : changed ? "new ones found" : "nothing new");
}

static std::string keys_file()
{
	size_t slash = base_file.find_last_of('/');
	return (slash == std::string::npos ? std::string() : base_file.substr(0, slash)) + "/.cache/newest_keys.txt";
}

static void load_metas()
{
	metas_loaded = 1;
	metas.clear();
	FILE *fp = fopen(keys_file().c_str(), "r");
	if (!fp) return;
	char line[8192];
	while (fgets(line, sizeof(line), fp))
	{
		line[strcspn(line, "\r\n")] = 0;
		// path \t mtime \t setname \t parent \t key key key
		char *f[5];
		char *p = line;
		int n = 0;
		for (; n < 5; n++)
		{
			f[n] = p;
			char *t = strchr(p, '\t');
			if (!t) { n++; break; }
			*t = 0;
			p = t + 1;
		}
		if (n < 5) continue;
		mra_meta m;
		m.mtime = atol(f[1]);
		m.set = f[2];
		m.parent = f[3];
		for (char *k = strtok(f[4], " "); k; k = strtok(0, " ")) m.keys.push_back(k);
		metas[f[0]] = m;
	}
	fclose(fp);
}

static void save_metas()
{
	std::string name = keys_file(), tmp = name + ".tmp";
	std::string dir = name.substr(0, name.find_last_of('/'));
	mkdir(dir.c_str(), 0755);
	FILE *fp = fopen(tmp.c_str(), "w");
	if (!fp) return;
	for (auto &m : metas)
	{
		if (!present.count(m.first)) continue; // the .mra which are gone
		fprintf(fp, "%s\t%ld\t%s\t%s\t", m.first.c_str(), m.second.mtime, m.second.set.c_str(), m.second.parent.c_str());
		for (size_t i = 0; i < m.second.keys.size(); i++) fprintf(fp, "%s%s", i ? " " : "", m.second.keys[i].c_str());
		fprintf(fp, "\n");
	}
	fflush(fp);
	fsync(fileno(fp));
	fclose(fp);
	rename(tmp.c_str(), name.c_str());
}

static const mra_meta &meta_of(const std::string &key)
{
	if (!metas_loaded) load_metas();
	mra_meta &m = metas[key];
	long mtime = present.count(key) ? (long)present[key] : 0;
	if (m.mtime != mtime || (m.set.empty() && m.keys.empty()))
	{
		m = mra_meta();
		m.mtime = mtime;
		fe_alt_mra_keys(base_root + "/" + key, m.set, m.parent, m.keys);
		metas_changed = 1;
	}
	return m;
}

static std::string file_label(const std::string &key)
{
	return key.substr(key.rfind('/') + 1);
}

// the words of a file name without the parts in () and []: "Heavy Unit (World).mra" -> heavy unit
static std::vector<std::string> title_words(const std::string &key)
{
	std::string t = file_label(key);
	if (t.size() > 4) t.erase(t.size() - 4);
	std::vector<std::string> w;
	std::string cur;
	int depth = 0;
	for (unsigned char c : t)
	{
		if (c == '(' || c == '[') depth++;
		else if ((c == ')' || c == ']') && depth) depth--;
		else if (!depth && (isalnum(c) || c == '\'')) cur += tolower(c);
		else if (!depth && !cur.empty()) { w.push_back(cur); cur.clear(); }
		else if (depth) { if (!cur.empty()) { w.push_back(cur); cur.clear(); } }
	}
	if (!cur.empty()) w.push_back(cur);
	return w;
}

// one title starts or ends with the other: the clones of a romset can be other games
// (Space Invaders / Balloon Bomber, Pac-Man / Ms. Pac-Man)
static int same_title(const std::string &a, const std::string &b)
{
	std::vector<std::string> x = title_words(a), y = title_words(b);
	if (x.empty() || y.empty()) return 0;
	if (x.size() > y.size()) x.swap(y);
	return std::equal(x.begin(), x.end(), y.begin()) || std::equal(x.begin(), x.end(), y.end() - x.size());
}

static std::vector<int> uf;
static int uf_find(int a) { return uf[a] == a ? a : uf[a] = uf_find(uf[a]); }
static void uf_join(int a, int b) { uf[uf_find(a)] = uf_find(b); }

std::vector<fe_new> fe_newest_list(int days)
{
	std::vector<fe_new> out;
	group_others.clear();
	time_t from = time(0) - (time_t)days * 86400;
	std::vector<std::pair<std::pair<time_t, time_t>, std::string>> v;
	for (auto &k : seen_map)
	{
		if (k.second.seen <= 0 || k.second.seen < from || !present.count(k.first)) continue;
		v.push_back({{k.second.seen, present[k.first]}, k.first});
	}
	std::sort(v.begin(), v.end(), [](const std::pair<std::pair<time_t, time_t>, std::string> &a, const std::pair<std::pair<time_t, time_t>, std::string> &b) {
		return a.first != b.first ? a.first > b.first : a.second < b.second;
	});

	// one game = the .mra which use the same romset: the setname of one is the setname, the
	// parent or a zip of the other, or they have the same parent (as the alternatives)
	int n = v.size();
	uf.resize(n);
	std::map<std::string, int> by_set, by_parent;
	for (int i = 0; i < n; i++)
	{
		uf[i] = i;
		const mra_meta &m = meta_of(v[i].second);
		if (!m.set.empty()) by_set.emplace(m.set, i);
	}
	for (int i = 0; i < n; i++)
	{
		const mra_meta &m = meta_of(v[i].second);
		for (auto &k : m.keys)
		{
			auto it = by_set.find(k);
			if (it != by_set.end()) uf_join(i, it->second);
		}
		if (!m.parent.empty())
		{
			auto it = by_parent.emplace(m.parent, i);
			if (!it.second) uf_join(i, it.first->second);
		}
	}
	if (metas_changed)
	{
		save_metas();
		metas_changed = 0;
	}

	// the games in the order of their newest .mra; the shown one = the main one of the group
	// (the setname the others use), then the shortest name; the ones of the romset which have
	// another title are games of their own
	std::vector<int> gid(n);
	std::map<int, std::vector<int>> comp; // root -> members (in list order)
	for (int i = 0; i < n; i++) comp[uf_find(i)].push_back(i);
	std::map<int, int> best_of;           // root -> the shown one
	for (auto &c : comp)
	{
		std::vector<int> &mem = c.second;
		int best = mem[0], best_score = -1;
		for (int i : mem)
		{
			const mra_meta &mi = meta_of(v[i].second);
			int score = 0;
			for (int j : mem)
				if (j != i && !mi.set.empty() && std::find(meta_of(v[j].second).keys.begin(), meta_of(v[j].second).keys.end(), mi.set) != meta_of(v[j].second).keys.end()) score++;
			std::string a = file_label(v[i].second), b = file_label(v[best].second);
			if (score > best_score || (score == best_score && (a.size() < b.size() || (a.size() == b.size() && strcasecmp(a.c_str(), b.c_str()) < 0))))
			{
				best = i;
				best_score = score;
			}
		}
		best_of[c.first] = best;
	}
	for (int i = 0; i < n; i++)
	{
		int r = uf_find(i), b = best_of[r];
		gid[i] = (i == b || same_title(v[i].second, v[b].second)) ? r : n + i;
	}
	std::map<int, std::vector<int>> groups; // group -> members (in list order)
	std::vector<int> roots;
	for (int i = 0; i < n; i++)
	{
		if (!groups.count(gid[i])) roots.push_back(gid[i]);
		groups[gid[i]].push_back(i);
	}
	for (int r : roots)
	{
		std::vector<int> &mem = groups[r];
		int best = r < n ? best_of[r] : mem[0];
		fe_new e;
		e.key = v[best].second;
		e.seen = v[mem[0]].first.first;
		e.versions = (int)mem.size() - 1;
		out.push_back(e);
		if (mem.size() > 1)
		{
			std::vector<std::string> others;
			for (int i : mem)
				if (i != best) others.push_back(v[i].second);
			std::sort(others.begin(), others.end(), [](const std::string &a, const std::string &b) { return strcasecmp(file_label(a).c_str(), file_label(b).c_str()) < 0; });
			group_others[e.key] = others;
		}
	}
	return out;
}

std::vector<std::string> fe_newest_versions(const std::string &key)
{
	auto it = group_others.find(key);
	return it == group_others.end() ? std::vector<std::string>() : it->second;
}
