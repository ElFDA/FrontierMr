#ifndef FE_UPDATE_H
#define FE_UPDATE_H

// Frontier keeps its own firmware in frontier/bin (updated by its Downloader
// database): MiSTer and menu.rbf in the root stay the official ones' paths.
// frontier/guard.sh (from linux/user-startup.sh) copies frontier/bin/MiSTer to
// the root at shutdown and at boot; menu.rbf is loaded from frontier/bin.

// the menu.rbf to load for "menu.rbf" (fpga_io.cpp): Frontier's, or 0 = the
// official one in the root (Frontier off, missing, or it did not start)
const char *fe_update_menu_rbf();

// start of Frontier: after power on loads Frontier's menu.rbf (MiSTer restarts),
// once per power on checks the update protection in the background
void fe_update_boot();

// before MiSTer restarts itself or resets (fpga_io.cpp): if an updater has
// replaced MiSTer, frontier/guard.sh puts Frontier's back first; returns the
// path to start then (/proc/self/exe names the deleted file), else 0
const char *fe_update_guard();

#endif
