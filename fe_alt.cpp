// Index of the arcade alternatives for Frontier (see fe_alt.h).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include <dirent.h>
#include <pthread.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/resource.h>
#include <sys/syscall.h>

#include <algorithm>
#include <map>
#include <unordered_map>

#include "fe_alt.h"

#define ALT_DIR   "_Arcade/_alternatives"
#define ALT_CACHE "frontier/.cache/alternatives.txt"

struct alt_file
{
	std::string path;              // relative to the root
	long mtime = 0;
	std::vector<std::string> keys; // setname, parent and zip names, lowercase
};

static pthread_mutex_t mtx = PTHREAD_MUTEX_INITIALIZER;
static int started = 0, ready = 0;
static int running = 0;        // a worker is reading the folder (under mtx)
static int check_saved = 0;    // the saved index is checked for changes (rescan=auto)
static std::string root;
static std::vector<alt_file> files;
static std::unordered_multimap<std::string, int> by_key;

static std::string lower(std::string s)
{
	for (auto &c : s) c = tolower((unsigned char)c);
	return s;
}

static int ends_with_mra(const char *name)
{
	size_t len = strlen(name);
	return len > 4 && !strcasecmp(name + len - 4, ".mra");
}

// "<tag>value</tag>" -> value, "" if missing
static std::string tag_value(const std::string &t, const char *tag)
{
	std::string open = std::string("<") + tag + ">";
	size_t b = t.find(open);
	if (b == std::string::npos) return "";
	b += open.size();
	size_t e = t.find('<', b);
	if (e == std::string::npos) return "";
	std::string v = t.substr(b, e - b);
	while (!v.empty() && isspace((unsigned char)v.back())) v.pop_back();
	while (!v.empty() && isspace((unsigned char)v[0])) v.erase(0, 1);
	return lower(v);
}

static void add_key(std::vector<std::string> &keys, std::string k)
{
	if (k.empty()) return;
	if (std::find(keys.begin(), keys.end(), k) == keys.end()) keys.push_back(k);
}

// setname, parent and the names of the zip files of an .mra
static std::vector<std::string> mra_keys(const std::string &path, std::string *setname = 0, std::string *parent_out = 0)
{
	std::vector<std::string> keys;
	FILE *fp = fopen(path.c_str(), "rb");
	if (!fp) return keys;
	std::string t;
	char buf[4096];
	size_t n;
	while ((n = fread(buf, 1, sizeof(buf), fp)) > 0 && t.size() < 256 * 1024) t.append(buf, n);
	fclose(fp);

	std::string set = tag_value(t, "setname");
	if (setname) *setname = set;
	std::string parent = tag_value(t, "parent");
	if (parent_out) *parent_out = parent;
	add_key(keys, set);
	add_key(keys, parent);

	size_t pos = 0;
	while ((pos = t.find("zip=\"", pos)) != std::string::npos)
	{
		pos += 5;
		size_t e = t.find('"', pos);
		if (e == std::string::npos) break;
		std::string list = t.substr(pos, e - pos);
		size_t s = 0;
		while (s <= list.size())
		{
			size_t bar = list.find('|', s);
			if (bar == std::string::npos) bar = list.size();
			std::string z = lower(list.substr(s, bar - s));
			size_t slash = z.find_last_of('/');
			if (slash != std::string::npos) z.erase(0, slash + 1);
			if (z.size() > 4 && z.compare(z.size() - 4, 4, ".zip") == 0) add_key(keys, z.substr(0, z.size() - 4));
			s = bar + 1;
		}
		pos = e + 1;
	}
	return keys;
}

static void load_cache(std::map<std::string, alt_file> &old)
{
	FILE *fp = fopen((root + "/" ALT_CACHE).c_str(), "r");
	if (!fp) return;
	char line[4096];
	while (fgets(line, sizeof(line), fp))
	{
		line[strcspn(line, "\r\n")] = 0;
		char *t1 = strchr(line, '\t');
		if (!t1) continue;
		*t1++ = 0;
		char *t2 = strchr(t1, '\t');
		if (!t2) continue;
		*t2++ = 0;

		alt_file f;
		f.path = line;
		f.mtime = atol(t1);
		for (char *k = strtok(t2, " "); k; k = strtok(0, " ")) f.keys.push_back(k);
		old[f.path] = f;
	}
	fclose(fp);
}

static void save_cache(const std::vector<alt_file> &list)
{
	mkdir((root + "/frontier/.cache").c_str(), 0755);
	std::string name = root + "/" ALT_CACHE;
	FILE *fp = fopen((name + ".tmp").c_str(), "w");
	if (!fp) return;
	for (auto &f : list)
	{
		fprintf(fp, "%s\t%ld\t", f.path.c_str(), f.mtime);
		for (size_t i = 0; i < f.keys.size(); i++) fprintf(fp, "%s%s", i ? " " : "", f.keys[i].c_str());
		fprintf(fp, "\n");
	}
	fclose(fp);
	rename((name + ".tmp").c_str(), name.c_str());
}

static void scan(const std::string &rel, std::map<std::string, alt_file> &old, std::vector<alt_file> &out, int &changed)
{
	DIR *d = opendir((root + "/" + rel).c_str());
	if (!d) return;
	std::vector<std::string> subdirs;
	struct dirent *de;
	while ((de = readdir(d)))
	{
		if (de->d_name[0] == '.') continue;
		std::string p = rel + "/" + de->d_name;
		int is_mra = ends_with_mra(de->d_name);
		if (de->d_type != DT_DIR && de->d_type != DT_LNK && de->d_type != DT_UNKNOWN && !is_mra) continue;

		struct stat st;
		if (stat((root + "/" + p).c_str(), &st)) continue; // broken links
		if (S_ISDIR(st.st_mode))
		{
			if (subdirs.size() < 10000 && rel.size() < 512) subdirs.push_back(p); // links to folders too
			continue;
		}
		if (!is_mra || !S_ISREG(st.st_mode)) continue;

		auto it = old.find(p);
		if (it != old.end() && it->second.mtime == (long)st.st_mtime)
		{
			out.push_back(it->second);
			continue;
		}

		alt_file f;
		f.path = p;
		f.mtime = st.st_mtime;
		f.keys = mra_keys(root + "/" + p);
		out.push_back(f);
		changed = 1;
	}
	closedir(d);
	for (auto &s : subdirs) scan(s, old, out, changed);
}

static void publish(std::vector<alt_file> &list)
{
	std::unordered_multimap<std::string, int> keys;
	for (size_t i = 0; i < list.size(); i++)
		for (auto &k : list[i].keys) keys.emplace(k, (int)i);

	pthread_mutex_lock(&mtx);
	files.swap(list);
	by_key.swap(keys);
	ready = 1;
	pthread_mutex_unlock(&mtx);
}

static void *worker(void *arg)
{
	int force = arg != 0;
	// below the menu: the index can wait
	setpriority(PRIO_PROCESS, syscall(SYS_gettid), 15);

	// the saved index is used at once, then the folder is checked for changes
	// (rescan=auto or fe_alt_rescan(); rescan=manual: only if there is none)
	std::map<std::string, alt_file> old;
	load_cache(old);
	size_t old_count = old.size();
	if (old_count && !force)
	{
		std::vector<alt_file> saved;
		for (auto &f : old) saved.push_back(f.second);
		publish(saved);
		if (!check_saved)
		{
			fprintf(stderr, "frontier: %d alternatives from the saved index\n", (int)old_count);
			pthread_mutex_lock(&mtx);
			running = 0;
			pthread_mutex_unlock(&mtx);
			return 0;
		}
	}

	std::vector<alt_file> list;
	int changed = 0;
	scan(ALT_DIR, old, list, changed);
	changed |= (list.size() != old_count);
	if (changed) save_cache(list);
	size_t count = list.size();
	if (changed || !old_count || force) publish(list);
	fprintf(stderr, "frontier: %d alternatives indexed%s\n", (int)count, changed ? " (updated)" : "");
	pthread_mutex_lock(&mtx);
	running = 0;
	pthread_mutex_unlock(&mtx);
	return 0;
}

static void start_worker(int force)
{
	pthread_mutex_lock(&mtx);
	int busy = running;
	running = 1;
	pthread_mutex_unlock(&mtx);
	if (busy) return;

	pthread_t th;
	if (pthread_create(&th, 0, worker, force ? (void *)1 : 0))
	{
		pthread_mutex_lock(&mtx);
		running = 0;
		ready = 1;
		pthread_mutex_unlock(&mtx);
	}
	else pthread_detach(th);
}

void fe_alt_start(const std::string &dir, int check)
{
	if (started) return;
	started = 1;
	root = dir;
	check_saved = check;
	start_worker(0);
}

void fe_alt_rescan()
{
	if (!started) return;
	start_worker(1);
}

int fe_alt_busy()
{
	pthread_mutex_lock(&mtx);
	int busy = running;
	pthread_mutex_unlock(&mtx);
	return busy;
}

int fe_alt_count()
{
	pthread_mutex_lock(&mtx);
	int n = files.size();
	pthread_mutex_unlock(&mtx);
	return n;
}

void fe_alt_mra_keys(const std::string &path, std::string &setname, std::string &parent, std::vector<std::string> &keys)
{
	setname.clear();
	parent.clear();
	keys = mra_keys(path, &setname, &parent);
}

int fe_alt_versions(const std::string &mra, std::vector<fe_version> &out)
{
	out.clear();
	pthread_mutex_lock(&mtx);
	int ok = ready;
	pthread_mutex_unlock(&mtx);
	if (!ok) return 0;

	// the main game's romset: its setname, or its first zip
	std::string set;
	std::vector<std::string> keys = mra_keys(root + "/" + mra, &set);
	if (set.empty() && !keys.empty()) set = keys[0];
	if (set.empty()) return 1;

	pthread_mutex_lock(&mtx);
	auto range = by_key.equal_range(set);
	for (auto it = range.first; it != range.second; ++it)
	{
		const alt_file &f = files[it->second];
		fe_version v;
		v.path = f.path;
		size_t slash = f.path.find_last_of('/');
		v.label = f.path.substr(slash + 1, f.path.size() - slash - 1 - 4);
		out.push_back(v);
	}
	pthread_mutex_unlock(&mtx);
	std::sort(out.begin(), out.end(), [](const fe_version &a, const fe_version &b) { return strcasecmp(a.label.c_str(), b.label.c_str()) < 0; });
	return 1;
}
