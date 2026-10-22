// Theme file parser for Frontier.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <strings.h>
#include <unistd.h>

#include "fe_theme.h"

const char *fe_section::get(const char *key, const char *def) const
{
	auto it = props.find(key);
	return (it == props.end()) ? def : it->second.c_str();
}

int fe_section::get_int(const char *key, int def) const
{
	auto it = props.find(key);
	return (it == props.end() || it->second.empty()) ? def : atoi(it->second.c_str());
}

int fe_section::has(const char *key) const
{
	return props.find(key) != props.end();
}

static std::string trim(const std::string &s)
{
	size_t b = 0, e = s.size();
	while (b < e && isspace((unsigned char)s[b])) b++;
	while (e > b && isspace((unsigned char)s[e - 1])) e--;
	return s.substr(b, e - b);
}

// calls cb(section, key, value) for every key; returns 0 if the file can't be read
template <typename F>
static int parse_ini(const std::string &path, F cb)
{
	FILE *fp = fopen(path.c_str(), "r");
	if (!fp) return 0;

	std::string section;
	char buf[1024];
	while (fgets(buf, sizeof(buf), fp))
	{
		std::string line = buf;

		// inline comment: " ;" (a bare ';' or '#' may be part of a value)
		size_t c = line.find(" ;");
		if (c == std::string::npos) c = line.find("\t;");
		if (c != std::string::npos) line.erase(c);

		line = trim(line);
		if (line.empty() || line[0] == ';' || line[0] == '#') continue;

		if (line[0] == '[')
		{
			size_t e = line.find(']');
			section = trim(line.substr(1, (e == std::string::npos) ? std::string::npos : e - 1));
			cb(section, std::string(), std::string());
			continue;
		}

		size_t eq = line.find('=');
		if (eq == std::string::npos) continue;

		std::string key = trim(line.substr(0, eq));
		for (auto &ch : key) ch = tolower((unsigned char)ch);
		cb(section, key, trim(line.substr(eq + 1)));
	}

	fclose(fp);
	return 1;
}

int fe_theme_load(fe_theme &theme, const std::string &dir, const char *file)
{
	theme = fe_theme();
	theme.dir = dir;
	theme.global.name = "theme";

	return parse_ini(dir + "/" + file, [&](const std::string &section, const std::string &key, const std::string &val)
	{
		if (!strcasecmp(section.c_str(), "theme") || section.empty())
		{
			if (!key.empty()) theme.global.props[key] = val;
			return;
		}

		if (key.empty())
		{
			fe_section s;
			s.name = section;
			theme.elements.push_back(s);
		}
		else
		{
			theme.elements.back().props[key] = val;
		}
	});
}

int fe_read_sections(const std::string &path, std::vector<fe_section> &out)
{
	out.clear();
	return parse_ini(path, [&](const std::string &section, const std::string &key, const std::string &val)
	{
		if (key.empty())
		{
			fe_section s;
			s.name = section;
			out.push_back(s);
		}
		else if (!out.empty())
		{
			out.back().props[key] = val;
		}
	});
}

std::map<std::string, std::string> fe_read_ini(const std::string &path)
{
	std::map<std::string, std::string> out;
	parse_ini(path, [&](const std::string &, const std::string &key, const std::string &val)
	{
		if (!key.empty()) out[key] = val;
	});
	return out;
}

int fe_write_ini_key(const std::string &path, const std::string &key, const std::string &value)
{
	std::vector<std::string> lines;
	FILE *fp = fopen(path.c_str(), "r");
	if (fp)
	{
		char buf[1024];
		while (fgets(buf, sizeof(buf), fp))
		{
			buf[strcspn(buf, "\r\n")] = 0;
			lines.push_back(buf);
		}
		fclose(fp);
	}

	int found = 0;
	for (auto &l : lines)
	{
		size_t b = l.find_first_not_of(" \t");
		if (b == std::string::npos || l.compare(b, key.size(), key)) continue;
		size_t e = l.find_first_not_of(" \t", b + key.size());
		if (e == std::string::npos || l[e] != '=') continue;
		l = key + "=" + value;
		found = 1;
		break;
	}
	if (!found) lines.push_back(key + "=" + value);

	std::string tmp = path + ".tmp";
	fp = fopen(tmp.c_str(), "w");
	if (!fp) return 0;
	for (auto &l : lines) fprintf(fp, "%s\n", l.c_str());
	fflush(fp);
	fsync(fileno(fp));
	fclose(fp);
	return !rename(tmp.c_str(), path.c_str());
}

uint32_t fe_parse_color(const char *str, uint32_t def)
{
	if (!str) return def;
	while (isspace((unsigned char)*str)) str++;
	if (*str == '#') str++;

	size_t len = 0;
	while (isxdigit((unsigned char)str[len])) len++;

	uint32_t v = strtoul(std::string(str, len).c_str(), 0, 16);
	if (len == 6) return 0xFF000000 | v;
	if (len == 8) return (v >> 8) | (v << 24);  // RRGGBBAA -> AARRGGBB
	return def;
}

int fe_parse_ints(const char *str, int *out, int max)
{
	int n = 0;
	while (str && *str && n < max)
	{
		char *end;
		long v = strtol(str, &end, 10);
		if (end == str) break;
		out[n++] = (int)v;
		str = end;
		while (*str == ',' || isspace((unsigned char)*str)) str++;
	}
	return n;
}
