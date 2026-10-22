#ifndef FRONTIER_H
#define FRONTIER_H

#include <inttypes.h>

// Frontier: graphical game selection frontend for the menu core.
// Drawn on the HPS framebuffer; loading is done by menu.cpp through the
// same states used by the original file browser.

enum fe_action
{
	FE_NONE = 0,
	FE_LAUNCH,       // frontier_selected_path() must be loaded
	FE_OPEN_OSD,     // open the original OSD (System menu)
	FE_OPEN_BROWSER  // open the original core browser
};

int frontier_enabled();
void frontier_start();
fe_action frontier_poll(uint32_t key, int menu);

const char *frontier_selected_path();  // relative to root dir, e.g. "_Console/SNES_20240101.rbf"
const char *frontier_selected_label();

// L+R+Select+Start held in a game: back to the menu (from input.cpp).
// bit: 1 L, 2 R, 4 Select, 8 Start of the joypad's menu mapping, 0 another key
void frontier_panic_key(int dev, int bit, int value);
// main loop (input_poll): the combo above and the end of the loading screen
void frontier_panic_poll();

// ProgressMessage() of menu.cpp while a core loads a game: the loading screen
// of the theme on HDMI, the OSD bar only on the CRT (fe_loading); 1 = no OSD
int frontier_progress(const char *title, const char *text, int current, int max);

#endif
