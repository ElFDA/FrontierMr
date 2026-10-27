#ifndef FE_GAMES_H
#define FE_GAMES_H

// Games by system for Frontier: frontier/systems.ini says which core and
// which MGL parameters load the files of each folder in games/.

#include <string>
#include <vector>

struct fe_games_folder
{
	std::string dir;       // folder in games/, as on disk
	std::string name;      // display name
	std::string id;        // systems.ini section of the best system
	std::string category;  // Console, Handheld, Computer, Other
};

// reads systems.ini (again) and forgets the scanned folders
void fe_games_load(const std::string &ini);

// folders in games/ with files and an installed core, sorted by name; with
// rescan=manual the list of the last time (frontier/.cache/folders.txt, made
// again if systems.ini changes or by fe_games_rescan())
const std::vector<fe_games_folder> &fe_games_folders();
void fe_games_manual(int on);
// games_wait=N in frontier.ini: for N seconds after the start an empty games/ is read
// again (a USB disk mounted after MiSTer starts), 0 = read once
void fe_games_wait(int seconds);
// the folders are read again at the next fe_games_folders()
void fe_games_rescan();

// merge_games=1 (default): the games of the same system on more storages are one list.
// The roots, in this order (the first one wins when a file is in two): /media/fat/games
// (or the USB disk it links to), /media/usb0..7/games, /media/network/games and /media/network,
// /media/fat/cifs/games and /media/fat/cifs (CIFS shares). A system folder is found in each root
// whatever its case ("PSX" and "psx"). The roots are looked for at every call.
void fe_games_merge(int on);
// the existing folders (absolute paths, the first root first) of a path "games/<folder>[/sub]",
// empty if none; without merge_games only the first root
std::vector<std::string> fe_games_dirs(const std::string &rel);
// absolute path of a file "games/<folder>/..." (also "...zip/inside"): in the first root which
// has it; <root>/<rel> if none. Other paths: <root>/<rel>
std::string fe_games_file(const std::string &rel);
const fe_games_folder *fe_games_find(const std::string &dir);

// extensions for ScanDirectory ("NESMGL") of a games/ folder
std::string fe_games_exts(const std::string &dir);

// all the extensions (lowercase, also the long ones) of a games/ folder; with
// romsets also "zip"
std::vector<std::string> fe_games_ext_list(const std::string &dir);

// MGLs (paths relative to the root) of the systems of a games/ folder which start a
// configuration of the core without a file (systems.ini launchers=), only those which
// exist
std::vector<std::string> fe_games_launchers(const std::string &dir);

// 1 if a system of the folder loads romsets (systems.ini romsets=1, Neo Geo):
// zip files and folders listed in its romsets.xml, browsed like the core does
// (ScanDirectory with SCANO_NEOGEO)
int fe_games_romsets(const std::string &dir);

// writes frontier/launch/<dir>/<name>.mgl for a file (path relative to the
// root, e.g. "games/NES/Game.nes"); returns the MGL path relative to the
// root, "" if no system can load the file
std::string fe_games_mgl(const std::string &rom);

#endif
