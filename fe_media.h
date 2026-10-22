#ifndef FE_MEDIA_H
#define FE_MEDIA_H

// Game metadata and images for Frontier, loaded by a worker thread so the
// menu never waits for the SD card. Files in /media/fat/frontier:
//   gamelists/<system>/gamelist.xml          EmulationStation format
//   media/<system>/<type>/<key>.png|.jpg     type: box snap title marquee fanart video
// <key> is the file name without extension (e.g. the .mra name).

#include <inttypes.h>
#include <string>
#include <vector>
#include <map>
#include <memory>

struct fe_bitmap
{
	int w = 0, h = 0;
	std::vector<uint32_t> px; // 0xAARRGGBB
	mutable int opaque = -1;  // all alpha 0xFF (-1 = not checked yet)
};

enum { FE_FIT_CONTAIN, FE_FIT_COVER, FE_FIT_STRETCH };

// root = Frontier's folder; threaded = 0 does everything in the caller (PC preview)
void fe_media_init(const std::string &root, int threaded = 1);
// forget gamelists, file lists and images (they are read again when needed)
void fe_media_reset();

// current game; system "" = none
// key: the name of the game, or more names separated by "\n": the data of the first
// one which has them
void fe_media_select(const std::string &system, const std::string &key);
// adds game.* and media.* of the current game; 0 if not loaded yet
int  fe_media_vars(std::map<std::string, std::string> &vars);

// image file decoded and scaled for w x h; null while it is loading (*loading = 1)
// or if it can't be read
std::shared_ptr<fe_bitmap> fe_media_image(const std::string &path, int w, int h, int fit, int *loading = 0);

// the same, decoded now in the calling thread (theme images)
std::shared_ptr<fe_bitmap> fe_media_load(const std::string &path, int w, int h, int fit);

// a copy of a bitmap scaled to w x h (stretched)
std::shared_ptr<fe_bitmap> fe_bitmap_scale(const fe_bitmap &bm, int w, int h);

// video (.mjv, or mp4 with its sound) played by its own thread, scaled for
// w x h: the current frame (null while starting), *frame = frame number. Keep
// calling it while the video is shown: it stops by itself when nobody asks for
// frames (after 500 ms; fe_video_stop() at once).
std::shared_ptr<fe_bitmap> fe_video_frame(const std::string &path, int w, int h, int fit, int *frame);
void fe_video_stop();
// sound of the videos 0-100 (0 = none), for the next video
void fe_video_volume(int volume);

// 1 if something was loaded since the last call (the view must be redrawn)
int  fe_media_changed();

#endif
