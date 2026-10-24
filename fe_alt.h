#ifndef FE_ALT_H
#define FE_ALT_H

// Versions of an arcade game for Frontier's detail view: the .mra files of
// _Arcade/_alternatives which use the main game's romset (its setname among
// their zip files or as <parent>). Reading all of them takes ~40 s with a cold
// SD card, so a low priority thread builds an index once and keeps it in
// frontier/.cache/alternatives.txt (then only new or changed files are read).
// With rescan=manual (default) the saved index is used as it is: the folder is
// read again only by fe_alt_rescan().

#include <string>
#include <vector>

struct fe_version
{
	std::string path;   // relative to the root dir, e.g. "_Arcade/_alternatives/_1942/1942 (Revision A).mra"
	std::string label;  // file name without .mra
};

// starts the index thread (once); root = MiSTer root dir; check = the saved index
// is checked for changes too (rescan=auto)
void fe_alt_start(const std::string &root, int check);
// reads the folder again (new or changed .mra files), unless it is being read
void fe_alt_rescan();
// 1 while the folder is being read
int fe_alt_busy();
// alternatives in the index
int fe_alt_count();

// alternatives of the main .mra (path relative to the root), sorted by name;
// returns 0 while the index is being built (call again later)
int fe_alt_versions(const std::string &mra, std::vector<fe_version> &out);

// setname, parent and the names of the zip files of an .mra (full path), lowercase, as the
// index uses them (for the games grouped in "#Newest", see fe_newest.h)
void fe_alt_mra_keys(const std::string &path, std::string &setname, std::string &parent, std::vector<std::string> &keys);

#endif
