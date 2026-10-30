// Games by system for Frontier (see fe_games.h).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include <dirent.h>
#include <limits.h>
#include <sys/stat.h>
#include <time.h>

#include <algorithm>
#include <map>
#include <set>

#include "fe_games.h"
#include "fe_theme.h"
#include "file_io.h"

#define FE_LAUNCH_DIR "frontier/launch"

struct slot
{
	char type;   // 'f' file, 's' disk image
	int index;
	int delay;
	std::vector<std::string> exts;  // lowercase, '?' = any char
};

struct sysdef
{
	std::string id, name, category, rbf, setname;
	int same_dir = 0;
	std::string autorun; // a PRG of frontier/ loaded after a disk image (C64: types LOAD and RUN), with the first 'f' slot of prg
	int reset = 0;     // seconds: <reset> after the disk image is mounted (the disk boots at the reset)
	int romsets = 0;   // Neo Geo: zip files and folders are romsets (romsets.xml), loaded by the first slot
	int view = -1;     // view=: 1 folders, 0 by title, -1 by the category (the computers in folders)
	std::vector<std::string> folders;
	std::vector<std::string> launchers; // MGLs of the root which start a configuration of the core by themselves
	std::vector<slot> slots;
};

static std::vector<sysdef> systems;
static std::vector<fe_games_folder> folders;
static int scanned = 0;
static int manual = 1;          // rescan=manual: the saved list of folders is enough
static int wait_s = 0;          // games_wait: seconds in which an empty games/ is read again
static time_t start_t = time(0);
static int force_scan = 0;      // fe_games_rescan()
static std::string ini_stamp;   // size and time of systems.ini: the saved list belongs to it

#define FE_FOLDERS_CACHE "frontier/.cache/folders.txt"
static std::map<std::string, std::vector<std::string>> rbf_dirs; // folder -> lowercase file names

static std::string lower(std::string s)
{
	for (auto &c : s) c = tolower((unsigned char)c);
	return s;
}

static std::vector<std::string> split(const std::string &s, const char *sep)
{
	std::vector<std::string> out;
	size_t pos = 0;
	while (pos <= s.size())
	{
		size_t end = s.find_first_of(sep, pos);
		if (end == std::string::npos) end = s.size();
		if (end > pos) out.push_back(s.substr(pos, end - pos));
		pos = end + 1;
	}
	return out;
}

/////////////////////////////////////////////////////////////////////////////
// roots of the games: the SD card (or the disk games/ links to), the other USB disks, the
// network shares (see fe_games.h)

#ifndef FE_MEDIA
#define FE_MEDIA "/media"   // where the USB disks and the network share are mounted
#endif
static int merge_on = 1;

static std::string real_path(const std::string &p)
{
	char buf[PATH_MAX];
	return realpath(p.c_str(), buf) ? std::string(buf) : p;
}

static int is_directory(const std::string &p)
{
	struct stat st;
	return !stat(p.c_str(), &st) && S_ISDIR(st.st_mode);
}

// parent/name, whatever the case of name in parent ("" if it isn't there)
static std::string find_ci(const std::string &parent, const std::string &name)
{
	struct stat st;
	std::string exact = parent + "/" + name;
	if (!stat(exact.c_str(), &st)) return exact;
	DIR *d = opendir(parent.c_str());
	if (!d) return "";
	std::string found;
	while (struct dirent *de = readdir(d))
	{
		if (!strcasecmp(de->d_name, name.c_str()))
		{
			found = parent + "/" + de->d_name;
			break;
		}
	}
	closedir(d);
	return found;
}

// the roots are looked for at every call (a disk or a share can come at any time; the lists are made by a
// thread, so nothing is kept)
static std::vector<std::string> game_roots()
{
	std::string root = getRootDir();
	std::vector<std::string> roots = { root + "/games" };
	if (!merge_on) return roots;

	std::vector<std::string> seen = { real_path(roots[0]) };
	std::vector<std::string> candidates;
	for (int i = 0; i < 8; i++)
	{
		std::string usb = FE_MEDIA "/usb" + std::to_string(i);
		candidates.push_back(usb + "/games");
		candidates.push_back(usb); // the system folders right on the disk (/media/usb0/SNES)
	}
	candidates.push_back(FE_MEDIA "/network/games");
	candidates.push_back(FE_MEDIA "/network");
	candidates.push_back(root + "/cifs/games");
	candidates.push_back(root + "/cifs");
	candidates.push_back(root);
	// "Storage: USB": the SD card too
	std::string sd = getStorageDir(0);
	if (real_path(sd) != real_path(root))
	{
		candidates.push_back(sd + "/games");
		candidates.push_back(sd);
	}
	for (auto &c : candidates)
	{
		if (!is_directory(c)) continue;
		std::string r = real_path(c);
		if (std::find(seen.begin(), seen.end(), r) != seen.end()) continue;
		seen.push_back(r);
		roots.push_back(c);
	}
	return roots;
}

std::string fe_root()
{
	std::string root = getRootDir(), sd = getStorageDir(0);
	if (!is_directory(root + "/frontier") && is_directory(sd + "/frontier")) return sd;
	return root;
}

void fe_games_merge(int on)
{
	merge_on = on;
}

// "games/<folder>/sub" -> folder, "/sub" (or ""); 0 if it isn't such a path
static int games_split(const std::string &rel, std::string &folder, std::string &sub)
{
	if (strncasecmp(rel.c_str(), "games/", 6)) return 0;
	size_t sl = rel.find('/', 6);
	folder = rel.substr(6, sl == std::string::npos ? std::string::npos : sl - 6);
	sub = (sl == std::string::npos) ? std::string() : rel.substr(sl);
	return !folder.empty();
}

std::vector<std::string> fe_games_dirs(const std::string &rel)
{
	std::vector<std::string> out;
	std::string folder, sub;
	if (!games_split(rel, folder, sub))
	{
		std::string p = std::string(getRootDir()) + "/" + rel;
		if (is_directory(p)) out.push_back(p);
		return out;
	}
	for (auto &r : game_roots())
	{
		std::string f = find_ci(r, folder);
		if (f.empty()) continue;
		std::string p = f + sub;
		if (is_directory(p)) out.push_back(p);
	}
	return out;
}

std::string fe_games_file(const std::string &rel)
{
	std::string folder, sub;
	if (games_split(rel, folder, sub))
	{
		// inside a zip file the path goes on after ".zip/": the zip is what must be there
		std::string test = sub;
		for (size_t i = 0; i + 5 <= sub.size(); i++)
		{
			if (!strncasecmp(sub.c_str() + i, ".zip/", 5))
			{
				test = sub.substr(0, i + 4);
				break;
			}
		}
		struct stat st;
		for (auto &r : game_roots())
		{
			std::string f = find_ci(r, folder);
			if (!f.empty() && !stat((f + test).c_str(), &st)) return f + sub;
		}
	}
	return std::string(getRootDir()) + "/" + rel;
}

static int has_folder(const sysdef &s, const std::string &dir)
{
	for (auto &f : s.folders) if (!strcasecmp(f.c_str(), dir.c_str())) return 1;
	return 0;
}

// systems which use a games/ folder, best match first: same name as the
// folder, then only this folder, then this as first folder, then the others
static std::vector<const sysdef *> systems_of(const std::string &dir)
{
	std::vector<std::pair<int, const sysdef *>> list;
	for (auto &s : systems)
	{
		if (!has_folder(s, dir)) continue;
		int rank = 3;
		if (!strcasecmp(s.id.c_str(), dir.c_str())) rank = 0;
		else if (!strcasecmp(s.folders[0].c_str(), dir.c_str())) rank = (s.folders.size() == 1) ? 1 : 2;
		list.push_back({ rank, &s });
	}

	// same rank: the system with more file types (TurboGrafx16 before SuperGrafx)
	auto exts = [](const sysdef *s) { size_t n = 0; for (auto &sl : s->slots) n += sl.exts.size(); return n; };
	std::stable_sort(list.begin(), list.end(), [&](const std::pair<int, const sysdef *> &a, const std::pair<int, const sysdef *> &b)
	{
		return (a.first != b.first) ? a.first < b.first : exts(a.second) > exts(b.second);
	});

	std::vector<const sysdef *> out;
	for (auto &l : list) out.push_back(l.second);
	return out;
}

// "_Console/NES" -> is there a _Console/NES_*.rbf or NES.rbf?
static int rbf_installed(const std::string &rbf)
{
	size_t p = rbf.rfind('/');
	std::string dir = (p == std::string::npos) ? "" : rbf.substr(0, p);
	std::string name = lower((p == std::string::npos) ? rbf : rbf.substr(p + 1));

	auto it = rbf_dirs.find(dir);
	if (it == rbf_dirs.end())
	{
		std::vector<std::string> files;
		std::string path = std::string(getRootDir()) + "/" + dir;
		DIR *d = opendir(path.c_str());
		if (d)
		{
			while (struct dirent *de = readdir(d)) files.push_back(lower(de->d_name));
			closedir(d);
		}
		it = rbf_dirs.insert({ dir, files }).first;
	}

	for (auto &f : it->second)
	{
		if (f.size() < 4 || f.compare(f.size() - 4, 4, ".rbf")) continue;
		if (f == name + ".rbf" || !f.compare(0, name.size() + 1, name + "_")) return 1;
	}
	return 0;
}

static int dir_has_files(const std::string &path)
{
	DIR *d = opendir(path.c_str());
	if (!d) return 0;
	int found = 0;
	while (struct dirent *de = readdir(d))
	{
		if (de->d_name[0] != '.')
		{
			found = 1;
			break;
		}
	}
	closedir(d);
	return found;
}

static int ext_match(const std::string &pattern, const std::string &ext)
{
	if (pattern.size() != ext.size()) return 0;
	for (size_t i = 0; i < ext.size(); i++)
	{
		if (pattern[i] != '?' && pattern[i] != ext[i]) return 0;
	}
	return 1;
}

static std::string xml_escape(const std::string &s)
{
	std::string out;
	for (char c : s)
	{
		if (c == '&') out += "&amp;";
		else if (c == '<') out += "&lt;";
		else if (c == '>') out += "&gt;";
		else if (c == '"') out += "&quot;";
		else out += c;
	}
	return out;
}

/////////////////////////////////////////////////////////////////////////////

void fe_games_load(const std::string &ini)
{
	systems.clear();
	folders.clear();
	rbf_dirs.clear();
	scanned = 0;
	struct stat st;
	ini_stamp = stat(ini.c_str(), &st) ? std::string() : std::to_string((long long)st.st_size) + "-" + std::to_string((long long)st.st_mtime);

	std::vector<fe_section> secs;
	if (!fe_read_sections(ini, secs))
	{
		fprintf(stderr, "frontier: %s not found, no games by system\n", ini.c_str());
		return;
	}

	for (auto &s : secs)
	{
		sysdef d;
		d.id = s.name;
		d.name = s.get("name", s.name.c_str());
		d.category = s.get("category", "Other");
		d.rbf = s.get("rbf");
		d.setname = s.get("setname");
		d.same_dir = s.get_int("setname_same_dir", 0);
		d.romsets = s.get_int("romsets", 0);
		d.reset = s.get_int("reset", 0);
		d.autorun = s.get("autorun");
		std::string view = lower(s.get("view"));
		d.view = view == "folders" ? 1 : view == "titles" ? 0 : -1;
		d.folders = split(s.get("folders"), "|");
		d.launchers = split(s.get("launchers"), "|");

		for (int i = 1; i < 32; i++)
		{
			char key[16];
			snprintf(key, sizeof(key), "slot%d", i);
			if (!s.has(key)) break;

			slot sl;
			int n = 0;
			if (sscanf(s.get(key), " %c , %d , %d ,%n", &sl.type, &sl.index, &sl.delay, &n) < 3 || !n) continue;
			sl.type = tolower(sl.type);
			for (auto &e : split(lower(s.get(key) + n), " \t")) sl.exts.push_back(e[0] == '.' ? e.substr(1) : e);
			if (!sl.exts.empty()) d.slots.push_back(sl);
		}

		if (!d.rbf.empty() && !d.folders.empty() && !d.slots.empty()) systems.push_back(d);
	}

	fprintf(stderr, "frontier: %d systems in %s\n", (int)systems.size(), ini.c_str());
}

// files in a folder and its subfolders (up to 4 levels)
static int count_files(const std::string &path, int depth)
{
	DIR *d = opendir(path.c_str());
	if (!d) return 0;
	int n = 0;
	while (struct dirent *de = readdir(d))
	{
		if (de->d_name[0] == '.') continue;
		std::string sub = path + "/" + de->d_name;
		int dir = de->d_type == DT_DIR;
		struct stat st;
		if (de->d_type == DT_UNKNOWN || de->d_type == DT_LNK) dir = !stat(sub.c_str(), &st) && S_ISDIR(st.st_mode);
		if (dir) n += (depth < 4) ? count_files(sub, depth + 1) : 0;
		else n++;
	}
	closedir(d);
	return n;
}

void fe_games_manual(int on)
{
	manual = on;
}

void fe_games_wait(int seconds)
{
	wait_s = seconds;
}

void fe_games_rescan()
{
	scanned = 0;
	force_scan = 1;
}

// frontier/.cache/folders.txt: "FEF1\t<systems.ini stamp>", then "<dir>\t<name>\t<id>\t<category>"
static int read_folders_cache()
{
	FILE *fp = fopen((fe_root() + "/" FE_FOLDERS_CACHE).c_str(), "r");
	if (!fp) return 0;
	char line[1024];
	int ok = fgets(line, sizeof(line), fp) && std::string(line, strcspn(line, "\r\n")) == "FEF1\t" + ini_stamp;
	while (ok && fgets(line, sizeof(line), fp))
	{
		line[strcspn(line, "\r\n")] = 0;
		std::vector<std::string> p = split(line, "\t");
		if (p.size() < 4) continue;
		fe_games_folder f;
		f.dir = p[0];
		f.name = p[1];
		f.id = p[2];
		f.category = p[3];
		folders.push_back(f);
	}
	fclose(fp);
	if (!ok || folders.empty())
	{
		folders.clear();
		return 0;
	}
	fprintf(stderr, "frontier: %d game folders from the saved list\n", (int)folders.size());
	return 1;
}

static void write_folders_cache()
{
	std::string path = fe_root() + "/" FE_FOLDERS_CACHE;
	mkdir((fe_root() + "/frontier/.cache").c_str(), 0755);
	FILE *fp = fopen((path + ".tmp").c_str(), "w");
	if (!fp) return;
	fprintf(fp, "FEF1\t%s\n", ini_stamp.c_str());
	for (auto &f : folders) fprintf(fp, "%s\t%s\t%s\t%s\n", f.dir.c_str(), f.name.c_str(), f.id.c_str(), f.category.c_str());
	fclose(fp);
	rename((path + ".tmp").c_str(), path.c_str());
}

const std::vector<fe_games_folder> &fe_games_folders()
{
	// games/ can be a link to a USB disk mounted after MiSTer starts: while
	// there is nothing, it is read again at most every 2 s for games_wait seconds
	static time_t last_try = 0;
	if (scanned && (!folders.empty() || time(0) - last_try < 2 || time(0) - start_t > wait_s)) return folders;
	int first = !scanned;
	scanned = 1;
	last_try = time(0);
	folders.clear();

	// rescan=manual: the list of the last time (systems with games and core)
	if (first && manual && !force_scan && read_folders_cache()) return folders;
	force_scan = 0;
	struct timespec t0, t1;
	clock_gettime(CLOCK_MONOTONIC, &t0);

	std::string games = std::string(getRootDir()) + "/games";
	DIR *d = opendir(games.c_str());
	if (!d && game_roots().size() < 2) return folders;

	while (d)
	{
		struct dirent *de = readdir(d);
		if (!de) break;
		if (de->d_name[0] == '.') continue;

		std::vector<const sysdef *> sys = systems_of(de->d_name);
		if (sys.empty()) continue;

		int core = 0;
		for (auto s : sys) core |= rbf_installed(s->rbf);
		if (!core) continue;

		std::string path = games + "/" + de->d_name;
		struct stat st;
		if (stat(path.c_str(), &st) || !S_ISDIR(st.st_mode) || !dir_has_files(path)) continue;

		fe_games_folder f;
		f.dir = de->d_name;
		f.name = sys[0]->name;
		f.id = sys[0]->id;
		f.category = sys[0]->category;
		folders.push_back(f);
	}
	if (d) closedir(d);

	// the same name in other case (MegaDrive with the games, Megadrive with only
	// the 240p Test Suite): only the folder with more files, the other one is in
	// the MiSTer view
	std::map<std::string, std::vector<std::string>> same; // lowercase name -> folders
	for (auto &f : folders) same[lower(f.dir)].push_back(f.dir);
	std::set<std::string> hidden;
	for (auto &g : same)
	{
		if (g.second.size() < 2) continue;
		std::string best;
		int most = -1;
		for (auto &dir : g.second)
		{
			int n = count_files(games + "/" + dir, 0);
			if (n > most) { most = n; best = dir; }
		}
		for (auto &dir : g.second) if (dir != best)
		{
			hidden.insert(dir);
			fprintf(stderr, "frontier: games/%s hidden, games/%s has more files\n", dir.c_str(), best.c_str());
		}
	}
	folders.erase(std::remove_if(folders.begin(), folders.end(), [&](const fe_games_folder &f) { return hidden.count(f.dir) > 0; }), folders.end());

	// the same system on the other storages: its games join those already there; a system only
	// there is a folder of its own
	const std::vector<std::string> roots = game_roots();
	for (size_t i = 1; i < roots.size(); i++) fprintf(stderr, "frontier: games also in %s\n", roots[i].c_str());
	for (size_t i = 1; i < roots.size(); i++)
	{
		DIR *rd = opendir(roots[i].c_str());
		if (!rd) continue;
		while (struct dirent *de = readdir(rd))
		{
			if (de->d_name[0] == '.') continue;
			std::vector<const sysdef *> sys = systems_of(de->d_name);
			if (sys.empty()) continue;
			int core = 0;
			for (auto s : sys) core |= rbf_installed(s->rbf);
			if (!core) continue;
			int known = 0;
			for (auto &f : folders) if (!strcasecmp(f.dir.c_str(), de->d_name)) known = 1;
			std::string path = roots[i] + "/" + de->d_name;
			if (known || !is_directory(path) || !dir_has_files(path)) continue;
			fe_games_folder f;
			f.dir = de->d_name;
			f.name = sys[0]->name;
			f.id = sys[0]->id;
			f.category = sys[0]->category;
			folders.push_back(f);
		}
		closedir(rd);
	}

	// folders of the same system (e.g. MegaDrive and Genesis): show the folder name too
	std::map<std::string, int> count;
	for (auto &f : folders) count[f.name]++;
	for (auto &f : folders) if (count[f.name] > 1) f.name += " (" + f.dir + ")";

	std::sort(folders.begin(), folders.end(), [](const fe_games_folder &a, const fe_games_folder &b)
	{
		return strcasecmp(a.name.c_str(), b.name.c_str()) < 0;
	});

	if (!folders.empty()) write_folders_cache();
	clock_gettime(CLOCK_MONOTONIC, &t1);
	fprintf(stderr, "frontier: %d game folders, %.0f ms\n", (int)folders.size(), (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6);
	return folders;
}

const fe_games_folder *fe_games_find(const std::string &dir)
{
	// the exact name first: MegaDrive and Megadrive can both be there
	for (auto &f : fe_games_folders()) if (f.dir == dir) return &f;
	for (auto &f : fe_games_folders()) if (!strcasecmp(f.dir.c_str(), dir.c_str())) return &f;
	return 0;
}

int fe_games_view_folders(const std::string &dir)
{
	std::vector<const sysdef *> sys = systems_of(dir);
	if (sys.empty()) return 0;
	if (sys[0]->view >= 0) return sys[0]->view;
	return sys[0]->category == "Computer";
}

std::string fe_games_exts(const std::string &dir)
{
	std::vector<std::string> list;
	for (auto s : systems_of(dir))
	{
		for (auto &sl : s->slots)
		{
			for (auto &e : sl.exts)
			{
				if (e.empty() || e.size() > 3) continue;  // ScanDirectory compares 3 chars
				std::string x = e;
				for (auto &c : x) c = toupper((unsigned char)c);
				x.resize(3, ' ');
				if (std::find(list.begin(), list.end(), x) == list.end()) list.push_back(x);
			}
		}
	}
	list.push_back("MGL");

	std::string out;
	for (auto &e : list) out += e;
	return out;
}

std::vector<std::string> fe_games_ext_list(const std::string &dir)
{
	std::vector<std::string> list;
	for (auto s : systems_of(dir))
		for (auto &sl : s->slots)
			for (auto &e : sl.exts)
				if (!e.empty() && std::find(list.begin(), list.end(), e) == list.end()) list.push_back(e);
	if (fe_games_romsets(dir) && std::find(list.begin(), list.end(), "zip") == list.end()) list.push_back("zip");
	return list;
}

std::vector<std::string> fe_games_launchers(const std::string &dir)
{
	std::vector<std::string> out;
	for (auto s : systems_of(dir))
	{
		for (auto &l : s->launchers)
		{
			if (l.back() == '/')
			{
				// a folder: all its MGLs by name (_Computer/_X68000 Games/)
				std::vector<std::string> names;
				DIR *d = opendir((std::string(getRootDir()) + "/" + l).c_str());
				if (!d) continue;
				while (struct dirent *de = readdir(d))
				{
					size_t n = strlen(de->d_name);
					if (de->d_name[0] != '.' && n > 4 && !strcasecmp(de->d_name + n - 4, ".mgl")) names.push_back(de->d_name);
				}
				closedir(d);
				std::sort(names.begin(), names.end(), [](const std::string &a, const std::string &b) { return strcasecmp(a.c_str(), b.c_str()) < 0; });
				for (auto &n : names) out.push_back(l + n);
				continue;
			}
			struct stat st;
			if (!stat((std::string(getRootDir()) + "/" + l).c_str(), &st) && std::find(out.begin(), out.end(), l) == out.end()) out.push_back(l);
		}
	}
	return out;
}

int fe_games_romsets(const std::string &dir)
{
	for (auto s : systems_of(dir)) if (s->romsets) return 1;
	return 0;
}

std::string fe_games_mgl(const std::string &rom)
{
	// games/<dir>/.../<file>
	std::vector<std::string> parts = split(rom, "/");
	if (parts.size() < 3 || strcasecmp(parts[0].c_str(), "games")) return "";
	std::string dir = parts[1];
	std::string file = parts.back();
	size_t dot = file.rfind('.');
	std::string ext = (dot == std::string::npos) ? std::string() : lower(file.substr(dot + 1));

	const sysdef *sys = 0;
	const slot *sl = 0;
	for (auto s : systems_of(dir))
	{
		for (auto &x : s->slots)
		{
			for (auto &e : x.exts)
			{
				// a romset (zip or folder) goes to the first slot of its system
				if ((!ext.empty() && ext_match(e, ext)) || (s->romsets && (ext == "zip" || ext.empty())))
				{
					sys = s;
					sl = &x;
					break;
				}
			}
			if (sl) break;
		}
		if (sl) break;
	}

	if (!sl)
	{
		fprintf(stderr, "frontier: no system for %s\n", rom.c_str());
		return "";
	}

	std::string rel = std::string(FE_LAUNCH_DIR) + "/" + dir;
	std::string path = fe_root() + "/" + rel;
	mkdir((fe_root() + "/" FE_LAUNCH_DIR).c_str(), 0777);
	mkdir(path.c_str(), 0777);

	rel += "/" + file.substr(0, dot) + ".mgl";
	path = fe_root() + "/" + rel;

	FILE *fp = fopen(path.c_str(), "w");
	if (!fp)
	{
		fprintf(stderr, "frontier: can't write %s\n", path.c_str());
		return "";
	}

	fprintf(fp, "<mistergamedescription>\n");
	fprintf(fp, "\t<rbf>%s</rbf>\n", xml_escape(sys->rbf).c_str());
	if (!sys->setname.empty()) fprintf(fp, "\t<setname%s>%s</setname>\n", sys->same_dir ? " same_dir=\"1\"" : "", xml_escape(sys->setname).c_str());
	fprintf(fp, "\t<file delay=\"%d\" type=\"%c\" index=\"%d\" path=\"%s\"/>\n", sl->delay, sl->type, sl->index,
		xml_escape(fe_games_file(rom)).c_str());
	if (sl->type == 's' && !sys->autorun.empty() && sl->index == sys->slots[0].index) // the first drive: LOAD ...,8
	{
		// MeGaLoSorTer's way: after the disk the core loads a small PRG which types LOAD"*",8,1 and RUN
		for (auto &x : sys->slots)
		{
			if (x.type != 'f' || std::find(x.exts.begin(), x.exts.end(), "prg") == x.exts.end()) continue;
			fprintf(fp, "\t<file delay=\"0\" type=\"f\" index=\"%d\" path=\"%s\"/>\n", x.index,
				xml_escape(fe_root() + "/" + sys->autorun).c_str());
			break;
		}
	}
	if (sys->reset > 0 && sl->type == 's') fprintf(fp, "\t<reset delay=\"%d\"/>\n", sys->reset);
	fprintf(fp, "</mistergamedescription>\n");
	fclose(fp);

	fprintf(stderr, "frontier: %s -> %s (%s)\n", rom.c_str(), rel.c_str(), sys->id.c_str());
	return fe_root() == getRootDir() ? rel : path; // "Storage: USB": the MGL is on the SD card
}
