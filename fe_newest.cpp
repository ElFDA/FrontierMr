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

#define FE_NEW_CLOCK_OK 1748736000 // 2025-06-01: before that the clock isn't set
#define FE_NEW_DEPTH    4

struct known
{
	time_t seen;
	time_t mtime;
};

static std::map<std::string, known> seen_map;   // the file
static std::map<std::string, time_t> present;    // .mra of the last scan: mtime

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

std::vector<fe_new> fe_newest_list(int days)
{
	std::vector<fe_new> out;
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
	for (auto &e : v)
	{
		fe_new n;
		n.key = e.second;
		n.seen = e.first.first;
		out.push_back(n);
	}
	return out;
}
