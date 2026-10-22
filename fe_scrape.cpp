// The scraper started from Frontier, in the background: see fe_scrape.h.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <signal.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/resource.h>

#include <map>

#include "fe_scrape.h"
#include "fe_theme.h"

static std::string root_dir, fe;
static fe_scrape_state cur;
static time_t last_read = 0;

static std::string status_file() { return fe + "/.cache/scrape_status.txt"; }

static uint64_t ms_now()
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

// the process is there and is the scraper (a pid can be used again after a restart)
static int alive(int pid)
{
	if (pid <= 0) return 0;
	char path[64], buf[512];
	snprintf(path, sizeof(path), "/proc/%d/cmdline", pid);
	int fd = open(path, O_RDONLY);
	if (fd < 0) return 0;
	int len = read(fd, buf, sizeof(buf) - 1);
	close(fd);
	if (len <= 0) return 0;
	for (int i = 0; i < len; i++) if (!buf[i]) buf[i] = ' ';
	buf[len] = 0;
	return strstr(buf, "fe_scrape.py") != 0;
}

static void read_status(fe_scrape_state &st)
{
	std::map<std::string, std::string> s = fe_read_ini(status_file());
	st.state = s.count("state") ? s["state"] : "";
	st.system = s["system"];
	st.step = s["step"];
	st.game = s["game"];
	st.error = s["error"];
	st.n = atoi(s["n"].c_str());
	st.total = atoi(s["total"].c_str());
	st.done = atoi(s["done"].c_str());
	st.systems = atoi(s["systems"].c_str());
	st.running = st.state == "running" && alive(atoi(s["pid"].c_str()));
	// running in the file but the process is gone: power off, killed
	if (st.state == "running" && !st.running) st.state = "stopped";
}

void fe_scrape_init(const std::string &root, const std::string &fe_dir)
{
	root_dir = root;
	fe = fe_dir;
	read_status(cur);
	last_read = time(0);
}

int fe_scrape_start(const std::vector<std::string> &args)
{
	read_status(cur);
	if (cur.running) return 0;

	std::string script = fe + "/scraper/fe_scrape.py";
	struct stat st;
	if (stat(script.c_str(), &st)) return 0;
	mkdir((fe + "/.cache").c_str(), 0755);
	std::string log = fe + "/.cache/scrape.log";

	std::vector<std::string> av = { "python3", "-u", script, "--root", root_dir, "--status", status_file() };
	av.insert(av.end(), args.begin(), args.end());
	std::vector<char *> argv;
	for (auto &a : av) argv.push_back((char *)a.c_str());
	argv.push_back(0);

	// two forks: the scraper is not a child of MiSTer (no zombie, it goes on when
	// MiSTer is started again); its pid comes back through a pipe
	int fds[2];
	if (pipe(fds)) return 0;
	pid_t pid = fork();
	if (pid == 0)
	{
		setsid();
		pid_t gc = fork();
		if (gc == 0)
		{
			int out = open(log.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
			int in = open("/dev/null", O_RDONLY);
			dup2(in, 0);
			if (out >= 0)
			{
				dup2(out, 1);
				dup2(out, 2);
			}
			for (int fd = 3; fd < 1024; fd++) close(fd);
			// default signals: SIGTERM/SIGINT must stop it
			sigset_t set;
			sigemptyset(&set);
			sigprocmask(SIG_SETMASK, &set, 0);
			for (int s = 1; s < 32; s++) signal(s, SIG_DFL);
			setpriority(PRIO_PROCESS, 0, 10); // games and Frontier first
			execvp("python3", argv.data());
			_exit(127);
		}
		write(fds[1], &gc, sizeof(gc));
		_exit(0);
	}
	close(fds[1]);
	pid_t gc = -1;
	if (pid > 0)
	{
		if (read(fds[0], &gc, sizeof(gc)) != sizeof(gc)) gc = -1;
		waitpid(pid, 0, 0);
	}
	close(fds[0]);
	if (gc <= 0) return 0;

	// running at once (the scraper writes the file itself soon)
	FILE *fp = fopen(status_file().c_str(), "w");
	if (fp)
	{
		fprintf(fp, "state=running\npid=%d\nstep=list\n", gc);
		fclose(fp);
	}
	printf("frontier: scraper started (pid %d)\n", gc);
	read_status(cur);
	last_read = time(0);
	return 1;
}

void fe_scrape_stop()
{
	std::map<std::string, std::string> s = fe_read_ini(status_file());
	int pid = atoi(s["pid"].c_str());
	if (alive(pid))
	{
		kill(pid, SIGTERM);
		printf("frontier: scraper %d stopped\n", pid);
	}
}

int fe_scrape_poll(fe_scrape_state &st, int &finished_system, int &finished)
{
	finished_system = finished = 0;
	static uint64_t last = 0;
	if (ms_now() - last < 1000)
	{
		st = cur;
		return 0;
	}
	last = ms_now();

	fe_scrape_state old = cur;
	read_status(cur);
	st = cur;
	if (old.running && (cur.done != old.done || cur.system != old.system)) finished_system = 1;
	if (old.running && !cur.running) finished = finished_system = 1;
	return cur.state != old.state || cur.running != old.running || cur.system != old.system ||
		cur.step != old.step || cur.n != old.n || cur.total != old.total || cur.done != old.done;
}

const fe_scrape_state &fe_scrape_get()
{
	return cur;
}

/////////////////////////////////////////////////////////////////////////////
// scraper.ini

static std::string trim(const std::string &s)
{
	size_t b = s.find_first_not_of(" \t");
	if (b == std::string::npos) return "";
	size_t e = s.find_last_not_of(" \t");
	return s.substr(b, e - b + 1);
}

static int read_lines(const std::string &path, std::vector<std::string> &lines)
{
	FILE *fp = fopen(path.c_str(), "r");
	if (!fp) return 0;
	char buf[1024];
	while (fgets(buf, sizeof(buf), fp))
	{
		buf[strcspn(buf, "\r\n")] = 0;
		lines.push_back(buf);
	}
	fclose(fp);
	return 1;
}

// line of key in [section], -1 if not there; end = line after the section (-1: no section)
static int find_key(const std::vector<std::string> &lines, const char *section, const char *key, int &end)
{
	int in = 0, at = -1;
	end = -1;
	for (int i = 0; i < (int)lines.size(); i++)
	{
		std::string l = trim(lines[i]);
		if (!l.empty() && l[0] == '[')
		{
			if (in) return at;
			in = !strcasecmp(l.c_str(), (std::string("[") + section + "]").c_str());
			if (in) end = i + 1;
			continue;
		}
		if (!in) continue;
		if (!l.empty() && l[0] != ';' && l[0] != '#') end = i + 1;
		size_t eq = l.find_first_of("=:");
		if (eq != std::string::npos && !strcasecmp(trim(l.substr(0, eq)).c_str(), key)) at = i;
	}
	return at;
}

// 1 if the file has the key (also empty)
static int value_in(const std::string &path, const char *key, std::string &value)
{
	std::vector<std::string> lines;
	if (!read_lines(path, lines)) return 0;
	int end;
	int at = find_key(lines, "screenscraper", key, end);
	if (at < 0) return 0;
	std::string l = lines[at];
	value = trim(l.substr(l.find_first_of("=:") + 1));
	return 1;
}

std::string fe_scrape_cred(const char *key)
{
	// as configparser.read([...]): the last file with the key wins
	std::string v;
	if (!value_in(fe + "/scraper/scraper.ini", key, v)) value_in(fe + "/scraper.ini", key, v);
	return v;
}

int fe_scrape_set_cred(const char *key, const std::string &value)
{
	struct stat st;
	std::string path = !stat((fe + "/scraper/scraper.ini").c_str(), &st) ? fe + "/scraper/scraper.ini" : fe + "/scraper.ini";
	std::vector<std::string> lines;
	read_lines(path, lines);
	int end;
	int at = find_key(lines, "screenscraper", key, end);
	std::string line = std::string(key) + " = " + value;
	if (at >= 0) lines[at] = line;
	else if (end >= 0) lines.insert(lines.begin() + end, line);
	else
	{
		if (!lines.empty() && !trim(lines.back()).empty()) lines.push_back("");
		lines.push_back("[screenscraper]");
		lines.push_back(line);
	}

	std::string tmp = path + ".tmp";
	FILE *fp = fopen(tmp.c_str(), "w");
	if (!fp) return 0;
	for (auto &l : lines) fprintf(fp, "%s\n", l.c_str());
	fflush(fp);
	fsync(fileno(fp));
	fclose(fp);
	int ok = !rename(tmp.c_str(), path.c_str());
	sync();
	return ok;
}
