#ifndef FE_LISTS_H
#define FE_LISTS_H

// Games by their data (system, arcade core, publisher, developer, genre, subgenre,
// decade, year, series, players) for "+ New list from filter..." of My Lists: the user
// chooses one or more values for each data (one of them must match, and all the data),
// then the games are copied into a new list or added to one. From
// frontier/.cache/meta.tsv written by the scraper (fe_scrape.py --index, also at the
// end of every run), one line per rom or .mra:
//   <system>\t<file>\t<core>\t<publisher>\t<developer>\t<genre>\t<subgenre>\t<year>\t<series>\t<players>
// The filter is kept in frontier/.cache/filter.txt.
//
// Folders:
//   @lists                     a line for each data with what is chosen ("Capcom, Konami", "any")
//   @lists/v/<data>            its values: "[x] Capcom  104" (games with the other choices);
//                              entries "@lists/v/<data>/<value>" ("" = Any) are chosen with A
//   @lists/games               the games of the filter
//   @lists/add                 the lists to add them to (made by frontier.cpp)
//   @lists/new                 the name of a new list: suggested or typed (made by frontier.cpp)
// '/' and '%' in the values are written %2F and %25. The games are named by their
// key (fe_fav.h): "@sys/SNES/Super Mario World", "_Arcade/1942.mra".

#include <string>
#include <vector>

#include "fe_render.h"

#define FE_LISTS "@lists"

// the index and the games are read again when needed (F5)
void fe_lists_reset();

// the games of a games/ folder are known or changed (fe_group_poll): made again
void fe_lists_group_changed();

// entries of "@lists", "@lists/v/<data>", "@lists/games" with ".." first; 0 for the others
int fe_lists_entries(const std::string &path, std::vector<fe_entry> &out);

// A on a value "@lists/v/<data>/<value>": chosen or not ("Any": none); 0 if it isn't one
int fe_lists_toggle(const std::string &name);

// nothing chosen
void fe_lists_clear();
int fe_lists_has_filter();

// games of the filter: how many, their keys and names (by name)
int fe_lists_count();
void fe_lists_games(std::vector<std::pair<std::string, std::string>> &out);

// the folder above ("" = above "@lists") and the entry to select there
std::string fe_lists_parent(const std::string &path, std::string &select);

// "Publisher", "SNES - Capcom, Konami - Platform", "New list from filter"
std::string fe_lists_title(const std::string &path);

// name for a list of the filter: "SNES - Capcom, Konami - Platform"
std::string fe_lists_name();

// a value "@lists/v/system/<folder>": its games/ folder as on disk, "@arcade"; "" for the others
std::string fe_lists_system(const std::string &name);

#endif
