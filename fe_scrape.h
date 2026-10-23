#ifndef FE_SCRAPE_H
#define FE_SCRAPE_H

// The scraper (frontier/scraper/fe_scrape.py) started from "#Frontier Settings" >
// "Scraper": it runs in the background, also while a game is played (MiSTer is
// started again when a core loads: the scraper is not its child), and writes its
// progress in frontier/.cache/scrape_status.txt; its output goes to
// frontier/.cache/scrape.log.

#include <string>
#include <vector>

struct fe_scrape_state
{
	int running = 0;         // the scraper process is there
	std::string state;       // running, done, stopped, error, "" (never run)
	std::string system;      // gamelist name of the system being done ("snes", "arcade")
	std::string step;        // list (reading the games), scrape, index
	std::string game;        // last game done
	std::string error;
	int n = 0, total = 0;    // games of the system
	int done = 0;            // systems finished
	int systems = 0;         // systems to do
	int updated = -1;        // games with new data or pictures in this run (-1: not written)
	int notfound = 0;        // games no source has (skipped or tried in vain)
};

// fe_dir = absolute path of the frontier folder
void fe_scrape_init(const std::string &root, const std::string &fe_dir);

// starts the scraper with these arguments (after the script); 0 if it can't start
// or one is already running
int fe_scrape_start(const std::vector<std::string> &args);
// asks the running scraper to stop (it saves what it has)
void fe_scrape_stop();

// reads the progress again (at most once a second); returns 1 when something
// changed, and sets finished_system/finished when a system or the whole run ended
int fe_scrape_poll(fe_scrape_state &st, int &finished_system, int &finished);
const fe_scrape_state &fe_scrape_get();

// ScreenScraper account in scraper.ini ([screenscraper] user/password), read as the
// scraper reads it: frontier/scraper.ini, then frontier/scraper/scraper.ini (wins)
std::string fe_scrape_cred(const char *key);
// written in the file which wins (scraper/scraper.ini if it is there); 0 on error
int fe_scrape_set_cred(const char *key, const std::string &value);

#endif
