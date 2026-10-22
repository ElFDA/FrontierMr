#ifndef FE_GROUP_H
#define FE_GROUP_H

// Games of a system grouped by title: a games/ folder and all its subfolders
// ("1 US - A-F", "2 Japan - A-Z", ...) become one list with an entry for each
// title, and the versions (regions, revisions) of the game in the detail view.
// Only the files with a No-Intro region in the name are listed:
// "Title (USA, Europe) (Rev 1).md"; the other files are in the folders.
// Titles of the same game with different names (Thunder Force IV and
// Lightening Force) are linked by frontier/gamelists/<folder>/groups.txt,
// written by the scraper from the MAME software lists: "<group>\t<title>".
// Folders with romsets (Neo Geo, fe_games_romsets()) have no regions: their
// games are "Title (tags) (setname).neo" and the zip files in romsets.xml
// ("3countb.zip" -> "3 Count Bout"), versions of the same title.

#include <string>
#include <vector>
#include <map>

struct fe_grom
{
	std::string path;   // relative to the root: games/<folder>/.../<file>
	std::string name;   // file name without extension
	int rank = 0;       // position of its best region in the preferred order
	int pre = 0;        // beta, prototype, demo...
	int rerel = 0;      // re-release (Virtual Console, Sega Ages, collections)
	int rev = 0;        // revision (Rev 1, Rev A, v1.1)
	int alt = 0;        // (Alt), romsets: (set 2)...
	int order = 0;      // romsets: zip after .neo, .neo without setname last
	std::string label;  // shown in the detail view if not empty (romsets: "3 Count Bout (3countb.zip)")
};

struct fe_gtitle
{
	std::string title;  // as in the file name
	int group;          // index in groups
	int def;            // rom launched by the entry
};

struct fe_gsystem
{
	std::vector<fe_grom> roms;
	std::vector<fe_gtitle> titles;           // sorted by name
	std::vector<std::vector<int>> groups;    // roms of each game, best first
	std::map<std::string, int> title_index;  // title -> index in titles
	std::map<std::string, int> rom_title;    // rom name (fe_grom.name) -> index in titles (Lists, fe_lists.cpp)
};

// preferred regions, e.g. "USA,World,Europe,Japan"; forgets the scans if they change
void fe_group_regions(const std::string &csv);
// folders left out of the lists, e.g. "Extra" (default); forgets the scans if they change
void fe_group_exclude(const std::string &csv);
// forgets the scans (F5)
void fe_group_reset();

// asks for the games of a folder: the list of the last time comes at once from
// frontier/.cache/games_<folder>.txt; without it a thread reads the folders.
// Automatic mode: with the cache too, once per session (MiSTer restarts at every
// core load, also coming back to the menu), at low priority (~4 s for 25000
// files with a cold SD card)
void fe_group_request(const std::string &dir);
// 1 = the folders are read again only by fe_group_rescan() (rescan=manual, default)
void fe_group_manual(int on);
// reads the folders again now (the list shown stays until the new one is there)
void fe_group_rescan(const std::string &dir);
// 1 while a fe_group_rescan() of the folder isn't finished (its result not polled yet)
int fe_group_busy(const std::string &dir);
// main thread, at every poll: 1 if the list of a folder is new or changed, *dir = which
int fe_group_poll(std::string &dir);

// the games of a folder, null if they are not known yet
const fe_gsystem *fe_group_get(const std::string &dir);

const fe_gtitle *fe_group_title(const fe_gsystem *s, const std::string &title);

#endif
