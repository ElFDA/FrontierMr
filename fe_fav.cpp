// Favorites and recent games of Frontier (see fe_fav.h).

#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include <string>

#include "fe_fav.h"

static std::string fav_file, recent_file;
static std::vector<fe_fav> favs, recent;

static int has(const std::vector<fe_fav> &list, const std::string &key)
{
	for (auto &f : list) if (f.key == key) return 1;
	return 0;
}

static void load(const std::string &file, std::vector<fe_fav> &list)
{
	list.clear();
	FILE *fp = fopen(file.c_str(), "r");
	if (!fp) return;
	char line[2048];
	while (fgets(line, sizeof(line), fp))
	{
		line[strcspn(line, "\r\n")] = 0;
		char *tab = strchr(line, '\t');
		if (tab) *tab = 0;
		if (!line[0] || has(list, line)) continue;
		fe_fav f;
		f.key = line;
		f.label = (tab && tab[1]) ? tab + 1 : line;
		list.push_back(f);
	}
	fclose(fp);
}

static void save(const std::string &file, const std::vector<fe_fav> &list)
{
	std::string tmp = file + ".tmp";
	FILE *fp = fopen(tmp.c_str(), "w");
	if (!fp)
	{
		printf("frontier: can't write %s\n", tmp.c_str());
		return;
	}
	for (auto &f : list) fprintf(fp, "%s\t%s\n", f.key.c_str(), f.label.c_str());
	fflush(fp);
	fsync(fileno(fp)); // the MiSTer is often switched off without a shutdown
	fclose(fp);
	rename(tmp.c_str(), file.c_str());
}

void fe_fav_load(const std::string &file)
{
	fav_file = file;
	load(file, favs);
}

const std::vector<fe_fav> &fe_fav_list()
{
	return favs;
}

int fe_fav_has(const std::string &key)
{
	return has(favs, key);
}

int fe_fav_toggle(const std::string &key, const std::string &label)
{
	for (size_t i = 0; i < favs.size(); i++)
	{
		if (favs[i].key != key) continue;
		favs.erase(favs.begin() + i);
		save(fav_file, favs);
		return 0;
	}

	fe_fav f;
	f.key = key;
	f.label = label.empty() ? key : label;
	favs.push_back(f);
	save(fav_file, favs);
	return 1;
}

void fe_recent_load(const std::string &file)
{
	recent_file = file;
	load(file, recent);
}

const std::vector<fe_fav> &fe_recent_list()
{
	return recent;
}

void fe_recent_add(const std::string &key, const std::string &label, int max)
{
	if (key.empty() || recent_file.empty() || max <= 0) return;
	for (size_t i = 0; i < recent.size(); i++)
	{
		if (recent[i].key != key) continue;
		recent.erase(recent.begin() + i);
		break;
	}
	fe_fav f;
	f.key = key;
	f.label = label.empty() ? key : label;
	recent.insert(recent.begin(), f);
	if ((int)recent.size() > max) recent.resize(max);
	save(recent_file, recent);
}

/////////////////////////////////////////////////////////////////////////////
// My Lists

static std::string mylists_file;
static std::vector<fe_mylist> mylists;

void fe_mylists_load(const std::string &file)
{
	mylists_file = file;
	mylists.clear();
	FILE *fp = fopen(file.c_str(), "r");
	if (!fp) return;
	char line[2048];
	while (fgets(line, sizeof(line), fp))
	{
		line[strcspn(line, "\r\n")] = 0;
		if (!line[0] || line[0] == ';' || line[0] == '#') continue;
		size_t len = strlen(line);
		if (line[0] == '[' && line[len - 1] == ']')
		{
			fe_mylist l;
			l.name = std::string(line + 1, len - 2);
			if (!l.name.empty() && fe_mylists_find(l.name) < 0) mylists.push_back(l);
			continue;
		}
		if (mylists.empty()) continue;
		char *tab = strchr(line, '\t');
		if (tab) *tab = 0;
		if (!line[0] || has(mylists.back().games, line)) continue;
		fe_fav f;
		f.key = line;
		f.label = (tab && tab[1]) ? tab + 1 : line;
		mylists.back().games.push_back(f);
	}
	fclose(fp);
}

static void mylists_save()
{
	std::string tmp = mylists_file + ".tmp";
	FILE *fp = fopen(tmp.c_str(), "w");
	if (!fp)
	{
		printf("frontier: can't write %s\n", tmp.c_str());
		return;
	}
	fprintf(fp, "; My Lists of Frontier: a section per list, its name in brackets (it can be\n"
		"; changed here, then F5), then one line per game: <key><TAB><name> as in favorites.txt\n");
	for (auto &l : mylists)
	{
		fprintf(fp, "\n[%s]\n", l.name.c_str());
		for (auto &f : l.games) fprintf(fp, "%s\t%s\n", f.key.c_str(), f.label.c_str());
	}
	fflush(fp);
	fsync(fileno(fp));
	fclose(fp);
	rename(tmp.c_str(), mylists_file.c_str());
}

const std::vector<fe_mylist> &fe_mylists()
{
	return mylists;
}

int fe_mylists_find(const std::string &name)
{
	for (size_t i = 0; i < mylists.size(); i++) if (mylists[i].name == name) return i;
	return -1;
}

int fe_mylists_has(int list, const std::string &key)
{
	return list >= 0 && list < (int)mylists.size() && has(mylists[list].games, key);
}

int fe_mylists_toggle(int list, const std::string &key, const std::string &label)
{
	if (list < 0 || list >= (int)mylists.size() || key.empty()) return 0;
	std::vector<fe_fav> &games = mylists[list].games;
	for (size_t i = 0; i < games.size(); i++)
	{
		if (games[i].key != key) continue;
		games.erase(games.begin() + i);
		mylists_save();
		return 0;
	}
	fe_fav f;
	f.key = key;
	f.label = label.empty() ? key : label;
	games.push_back(f);
	mylists_save();
	return 1;
}

int fe_mylists_new(const std::string &key, const std::string &label)
{
	fe_mylist l;
	for (int n = mylists.size() + 1;; n++)
	{
		l.name = "List " + std::to_string(n);
		if (fe_mylists_find(l.name) < 0) break;
	}
	mylists.push_back(l);
	fe_mylists_toggle(mylists.size() - 1, key, label);
	return mylists.size() - 1;
}

int fe_mylists_add(const std::string &name, const std::vector<fe_fav> &games)
{
	fe_mylist l;
	l.name = name.empty() ? std::string("List") : name;
	for (int n = 2; fe_mylists_find(l.name) >= 0; n++) l.name = (name.empty() ? std::string("List") : name) + " " + std::to_string(n);
	l.games = games;
	mylists.push_back(l);
	mylists_save();
	return mylists.size() - 1;
}

int fe_mylists_append(int list, const std::vector<fe_fav> &games)
{
	if (list < 0 || list >= (int)mylists.size()) return 0;
	int n = 0;
	for (auto &f : games)
	{
		if (has(mylists[list].games, f.key)) continue;
		mylists[list].games.push_back(f);
		n++;
	}
	if (n) mylists_save();
	return n;
}

int fe_mylists_rename(int list, const std::string &name)
{
	if (list < 0 || list >= (int)mylists.size() || name.empty()) return 0;
	int other = fe_mylists_find(name);
	if (other >= 0 && other != list) return 0;
	mylists[list].name = name;
	mylists_save();
	return 1;
}

void fe_mylists_remove(int list)
{
	if (list < 0 || list >= (int)mylists.size()) return;
	mylists.erase(mylists.begin() + list);
	mylists_save();
}
