#ifndef FE_NEWEST_H
#define FE_NEWEST_H

// "#Newest" of the Arcade folder: the arcade games (.mra) which appeared on the SD card,
// the newest first. What is new is told by Frontier, not by the date of the files (an
// update rewrites them): frontier/arcade_seen.txt has a line "<seen>\t<mtime>\t<key>" for
// every .mra it has met; the first time all of them are written with seen 0 (known), after
// that the ones not in the file get the time of that scan.

#include <string>
#include <vector>
#include <time.h>

struct fe_new
{
	std::string key;   // "_Arcade/1942.mra", "_Arcade/_MeatCores/x.mra"
	time_t seen;       // when Frontier saw it first
};

// reads _Arcade (the folders too, not _alternatives) and updates the file; does nothing
// while the clock of the MiSTer isn't set (no RTC: 1970 until the network sets it)
void fe_newest_scan(const std::string &root, const std::string &file);

// the .mra still there seen in the last days, the newest first
std::vector<fe_new> fe_newest_list(int days);

#endif
