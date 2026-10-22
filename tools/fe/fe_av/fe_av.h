// fe_av.so interface (fe_av.c). Main does not include this file: fe_media.cpp
// declares the same functions as pointers filled with dlsym.
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct fev fev;

// fit modes, the same values as FE_FIT_* in fe_media.h
enum { FEV_CONTAIN, FEV_COVER, FEV_STRETCH };

// Opens a video. box_w/box_h: box it is shown in (0: own size), fit: how it
// goes in the box. The pictures come out at the final size, out_w x out_h
// (contain: smaller than the box on one side). volume: 0-100 for the sound
// (0 = none; also none without libasound or an audio track). NULL on error.
fev *fev_open(const char *path, int box_w, int box_h, int fit, int volume, int *out_w, int *out_h);

// Decodes the next picture in display order and, if px is not NULL, converts it
// into px (out_w * out_h, 0xFFRRGGBB). pts_ms: time from the first picture.
// Returns 1 with a picture, 0 at the end of the file, -1 on error.
int fev_next(fev *v, uint32_t *px, int64_t *pts_ms);

// Back to the start of the file (pictures restart from pts 0). loop_ms: length
// of the loop just ended; the sound goes on from there. 1 = done.
int fev_rewind(fev *v, int64_t *loop_ms);

// Second view (n = 1) of the same video: the pictures also at another size
// (the CRT pages of Frontier), made with fev_picture. 1 = done.
#define FEV_VIEWS 2
int fev_view(fev *v, int n, int box_w, int box_h, int fit, int *out_w, int *out_h);

// The last picture of fev_next converted for view n into px (its out_w * out_h).
int fev_picture(fev *v, int n, uint32_t *px);

// Time of the sound being heard, in ms on a timeline that starts with the first
// picture and goes on across the loops (sum of the loop_ms); -1 without sound or
// while it does not play. The pictures follow it.
int64_t fev_clock(fev *v);

// Stops the sound (after a 10 ms fade) and frees everything.
void fev_close(fev *v);

#ifdef __cplusplus
}
#endif
