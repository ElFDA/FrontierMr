#ifndef FE_FAV_H
#define FE_FAV_H

// Favorites of Frontier, kept in frontier/favorites.txt, and the games
// played last, in frontier/recent.txt: one line per game, "<key>\t<label>". The key is what Frontier remembers of a title:
// "@sys/SNES/Super Mario World" (a game by title), "games/NES/Game.nes",
// "_Arcade/1942.mra", "_Console/SNES_20240101.rbf".

#include <string>
#include <vector>

struct fe_fav
{
	std::string key;
	std::string label;
};

// reads the file (again)
void fe_fav_load(const std::string &file);

// in the order they were added
const std::vector<fe_fav> &fe_fav_list();

int fe_fav_has(const std::string &key);

// adds or removes a game and writes the file; returns 1 if it was added
int fe_fav_toggle(const std::string &key, const std::string &label);

// recent games: the last one first, at most max (more lines in the file are
// kept until the next game is added)
void fe_recent_load(const std::string &file);
const std::vector<fe_fav> &fe_recent_list();

// puts a game first (moved there if it is already in the list) and writes the file
void fe_recent_add(const std::string &key, const std::string &label, int max);

// lists made by the user ("My Lists"), kept in frontier/mylists.ini: a section per
// list with its name in brackets, then one line per game as in favorites.txt
//   [List 1]
//   @sys/SNES/Super Mario World<TAB>Super Mario World
// The names can be changed in Frontier (keyboard) or by hand (then F5).
struct fe_mylist
{
	std::string name;
	std::vector<fe_fav> games;  // in the order they were added
};

void fe_mylists_load(const std::string &file);
const std::vector<fe_mylist> &fe_mylists();
// index of a list by name, -1 if there is none
int fe_mylists_find(const std::string &name);
int fe_mylists_has(int list, const std::string &key);
// adds or removes a game and writes the file; returns 1 if it was added
int fe_mylists_toggle(int list, const std::string &key, const std::string &label);
// a new list "List N" with a game in it; returns its index
int fe_mylists_new(const std::string &key, const std::string &label);
// a new list with these games, named name (name 2, name 3... if it is there); returns its index
int fe_mylists_add(const std::string &name, const std::vector<fe_fav> &games);
// adds the games which aren't there yet to a list; returns how many were added
int fe_mylists_append(int list, const std::vector<fe_fav> &games);
// a new name for a list; 0 if it is empty or another list has it
int fe_mylists_rename(int list, const std::string &name);
// removes a list
void fe_mylists_remove(int list);

#endif
