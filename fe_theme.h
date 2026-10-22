#ifndef FE_THEME_H
#define FE_THEME_H

// Theme description for Frontier: an INI file (theme.ini) where every
// section is an element drawn in file order. The [theme] section holds the
// global settings. See tools/fe/sd/frontier/themes/simple/theme.ini.

#include <inttypes.h>
#include <string>
#include <vector>
#include <map>

struct fe_section
{
	std::string name;
	std::map<std::string, std::string> props;

	const char *get(const char *key, const char *def = "") const;
	int get_int(const char *key, int def) const;
	int has(const char *key) const;
};

struct fe_theme
{
	std::string dir;                 // theme folder, absolute
	fe_section global;               // [theme]
	std::vector<fe_section> elements; // other sections, in file order
};

// 0 if dir/file can't be read
int fe_theme_load(fe_theme &theme, const std::string &dir, const char *file = "theme.ini");

// "#RRGGBB" or "#RRGGBBAA" -> 0xAARRGGBB
uint32_t fe_parse_color(const char *str, uint32_t def);

// "1,2,3" -> number of values read
int fe_parse_ints(const char *str, int *out, int max);

// all the sections of an ini file, in order
int fe_read_sections(const std::string &path, std::vector<fe_section> &out);

// simple ini key=value file, for frontier.ini
std::map<std::string, std::string> fe_read_ini(const std::string &path);
// sets key=value in an ini file (the first line with the key, or a new line at the end),
// comments and the other lines stay; 0 if it can't be written
int fe_write_ini_key(const std::string &path, const std::string &key, const std::string &value);

#endif
