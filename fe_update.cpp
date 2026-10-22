// Frontier's firmware next to the official one (see fe_update.h).
//
// U-Boot loads the official menu.rbf at power on: the first start of Frontier
// loads frontier/bin/menu.rbf instead. FE_MENU_TRY holds the size and time of
// the file being tried and the attempts, and is removed when it has started.
// After two power ons where it did not start (a damaged file leaves the FPGA
// without a core) FE_MENU_BAD keeps the official menu until the file changes.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/resource.h>

#include <string>

#include "fe_update.h"
#include "frontier.h"
#include "file_io.h"
#include "fpga_io.h"
#include "osd.h"
#include "user_io.h"

#define FE_MENU_RBF  "frontier/bin/menu.rbf"
#define FE_MENU_TRY  "frontier/bin/.menu_try"
#define FE_MENU_BAD  "frontier/bin/.menu_bad"
#define FE_PROTECT   "frontier/protect_updates.py"
#define FE_BOOT_DONE "/tmp/frontier_update_check"  // tmpfs: once per power on
#define FE_PROTECT_LOG "/tmp/frontier_protect.log"

static std::string storage_file(const char *name)
{
	return std::string(getStorageDir(0)) + "/" + name;
}

// "size mtime" of a file, "" if missing or empty
static std::string file_id(const std::string &path)
{
	struct stat st;
	if (stat(path.c_str(), &st) || st.st_size <= 0) return "";
	char id[64];
	snprintf(id, sizeof(id), "%lld %lld", (long long)st.st_size, (long long)st.st_mtime);
	return id;
}

static std::string read_line(const std::string &path)
{
	char line[256] = {};
	FILE *fp = fopen(path.c_str(), "r");
	if (!fp) return "";
	if (!fgets(line, sizeof(line), fp)) line[0] = 0;
	fclose(fp);
	line[strcspn(line, "\r\n")] = 0;
	return line;
}

// Frontier's menu.rbf ends its version with "fe" ("fi" = also interlaced)
static int menu_is_ours()
{
	const char *name = OsdCoreNameGet();
	size_t len = strlen(name);
	return is_menu() && len >= 2 && name[len - 2] == 'f' && (name[len - 1] == 'e' || name[len - 1] == 'i');
}

const char *fe_update_menu_rbf()
{
	static std::string path;
	if (!frontier_enabled()) return 0;
	path = storage_file(FE_MENU_RBF);
	std::string id = file_id(path);
	if (id.empty() || read_line(storage_file(FE_MENU_BAD)) == id) return 0;
	return path.c_str();
}

// protect_updates.py --repair in the background: it puts back what an updater or
// another tool may have removed (filter, guard line, Downloader drop-in) and
// writes nothing when all is in place
static void protect_check()
{
	std::string script = storage_file(FE_PROTECT);
	if (access(script.c_str(), R_OK)) return;
	pid_t pid = fork();
	if (pid == 0)
	{
		setsid();
		if (fork() == 0)
		{
			int out = open(FE_PROTECT_LOG, O_WRONLY | O_CREAT | O_TRUNC, 0644);
			int in = open("/dev/null", O_RDONLY);
			dup2(in, 0);
			if (out >= 0)
			{
				dup2(out, 1);
				dup2(out, 2);
			}
			for (int fd = 3; fd < 1024; fd++) close(fd);
			sigset_t set;
			sigemptyset(&set);
			sigprocmask(SIG_SETMASK, &set, 0);
			for (int s = 1; s < 32; s++) signal(s, SIG_DFL);
			setpriority(PRIO_PROCESS, 0, 15);
			// sh at once: no second process named MiSTer (pidof MiSTer, killall MiSTer);
			// the check waits until Frontier and the network have started
			execl("/bin/sh", "sh", "-c", "sleep 20; exec python3 \"$0\" --root \"$1\" --repair",
				script.c_str(), getStorageDir(0), (char *)0);
			_exit(127);
		}
		_exit(0);
	}
	if (pid > 0) waitpid(pid, 0, 0);
}

// MiSTer on the SD is no longer the running one (an updater replaced it): the
// guard puts Frontier's back before MiSTer is started again for a core, or
// before a reset from the OSD (which does not run the shutdown scripts)
const char *fe_update_guard()
{
	static std::string exe;
	struct stat run, disk;
	exe = storage_file("MiSTer");
	if (!stat("/proc/self/exe", &run) && !stat(exe.c_str(), &disk) &&
		run.st_dev == disk.st_dev && run.st_ino == disk.st_ino) return 0;
	std::string guard = storage_file("frontier/guard.sh");
	if (access(guard.c_str(), R_OK)) return exe.c_str();
	printf("frontier: %s changed, running %s\n", exe.c_str(), guard.c_str());
	pid_t pid = fork();
	if (pid == 0)
	{
		for (int fd = 3; fd < 1024; fd++) close(fd);
		execl("/bin/sh", "sh", guard.c_str(), "exec", (char *)0);
		_exit(127);
	}
	if (pid > 0) waitpid(pid, 0, 0);
	return exe.c_str();
}

static void write_line(const std::string &path, const std::string &text)
{
	FILE *fp = fopen(path.c_str(), "w");
	if (!fp) return;
	fprintf(fp, "%s\n", text.c_str());
	fflush(fp);
	fsync(fileno(fp));
	fclose(fp);
}

void fe_update_boot()
{
	std::string tried = storage_file(FE_MENU_TRY), bad = storage_file(FE_MENU_BAD);
	if (menu_is_ours())
	{
		if (!access(tried.c_str(), F_OK) || !access(bad.c_str(), F_OK))
		{
			unlink(tried.c_str());
			unlink(bad.c_str());
			sync();
		}
	}
	else if (is_menu() && fe_update_menu_rbf())
	{
		// "size mtime attempts"
		std::string id = file_id(storage_file(FE_MENU_RBF)), line = read_line(tried);
		int attempts = 0;
		if (!line.compare(0, id.size() + 1, id + " ")) attempts = atoi(line.c_str() + id.size() + 1);
		if (attempts >= 2)
		{
			printf("frontier: %s did not start, the official menu.rbf is used\n", FE_MENU_RBF);
			write_line(bad, id);
			unlink(tried.c_str());
			sync();
		}
		else
		{
			write_line(tried, id + " " + std::to_string(attempts + 1));
			printf("frontier: loading %s\n", FE_MENU_RBF);
			fpga_load_rbf("menu.rbf"); // restarts MiSTer, back only if it cannot be read
		}
	}

	if (access(FE_BOOT_DONE, F_OK))
	{
		close(open(FE_BOOT_DONE, O_WRONLY | O_CREAT, 0644));
		protect_check();
	}
}
