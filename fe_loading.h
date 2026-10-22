#ifndef FE_LOADING_H
#define FE_LOADING_H

// Loading screen of Frontier: while a core loads a game (the ProgressMessage()
// bar of the OSD) HDMI shows the theme's loading.ini on the HPS framebuffer
// (the LFB of sys_top, there in every core), then the core again; the bar of
// the OSD stays only on the CRT (VGA OSD), where the core's picture is.

#include <string>
#include <map>

// the game launched by Frontier (title, system, media...): kept in /tmp for the
// next MiSTer process, which loads the core and then the game
void fe_loading_save(const std::map<std::string, std::string> &vars);

// a ProgressMessage(); 1 if it must not go on to the OSD: the end of a file
// while the loading screen is on (the OSD bar is sent only to the VGA output)
int fe_loading_progress(const char *title, const char *text, int current, int max);

// 1 while the loading screen has the framebuffer (vga_nag() of menu.cpp must stay quiet)
int fe_loading_active();

// main loop: the core comes back when nothing was loaded for a while
void fe_loading_poll();

#endif
