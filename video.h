#ifndef VIDEO_H
#define VIDEO_H

#define VFILTER_HORZ  0
#define VFILTER_VERT  1
#define VFILTER_SCAN  2
#define VFILTER_ILACE 3

struct VideoInfo
{
	uint32_t width;
	uint32_t height;
	uint32_t htime;
	uint32_t vtime;
	uint32_t ptime;
	uint32_t ctime;
	uint32_t vtimeh;
	uint32_t frame_clocks;
	uint32_t arx;
	uint32_t ary;
	uint32_t arxy;
	uint32_t fb_en;
	uint32_t fb_fmt;
	uint32_t fb_width;
	uint32_t fb_height;
	uint32_t pixrep;
	uint32_t de_h;
	uint32_t de_v;

	bool interlaced;
	bool rotated;
};

// expose video timings for timerfd-based frame timer
extern VideoInfo current_video_info;

bool  video_is_direct();

void  video_init();
void  video_poll();

int   video_get_edid(uint8_t **buf, int *size);
void  video_hdmi_power(int on);

int   video_get_scaler_flt(int type);
void  video_set_scaler_flt(int type, int n);
char* video_get_scaler_coeff(int type, int only_name = 1);
void  video_set_scaler_coeff(int type, const char *name);

int   video_get_gamma_en();
void  video_set_gamma_en(int n);
char* video_get_gamma_curve(int only_name = 1);
void  video_set_gamma_curve(const char *name);

int   video_get_shadow_mask_mode();
void  video_set_shadow_mask_mode(int n);
char* video_get_shadow_mask(int only_name = 1);
void  video_set_shadow_mask(const char *name);
void  video_loadPreset(char *name, bool save);

int   video_get_rotated();

void video_cfg_reset();

void  video_mode_adjust(bool force = false);

int   hasAPI1_5();

void video_fb_enable(int enable, int n = 0);
int video_fb_state();
void video_menu_bg(int n, int idle = 0);
int video_bg_has_picture();
int video_chvt(int num);
void video_cmd(char *cmd);
void video_mode_cmd(char *cmd);

void video_core_description(char *str, size_t len);
void video_scaler_description(char *str, size_t len);
char* video_get_core_mode_name(int with_vrefresh = 1);

void dbg_draw_cursor(int x, int y);

// FRONTIER
volatile uint32_t *video_fe_page(int page, int *w, int *h);
int video_fe_cur_page();
void video_fe_show(int page);
int video_fe_bg_gen();
void video_fe_crt(int on);
void video_fe_interlace(int on);   // CRT pages 640x480 interlaced (with the "fi" menu.rbf)
// picture on the CRT moved right by px: done by Frontier's menu.rbf in steps
// of 4 (-32..28); returns the pixels it moves (0 with another menu.rbf)
int video_fe_hpos(int px);
int video_fe_main_crt();           // the menu pages are the 15 kHz picture (direct_video, crt=1)
// with Frontier's menu.rbf: pages 0/1 for the CRT (0 if not available)
volatile uint32_t *video_fe_crt_page(int page, int *w, int *h);
int video_fe_crt_cur_page();
void video_fe_crt_show(int page);

#endif // VIDEO_H
