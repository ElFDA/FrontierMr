// fe_av.so: mp4 video and audio decoding for the video thread of Frontier (fe_media.cpp).
//
// FFmpeg (LGPL 2.1 or later) is linked in statically with only what the
// Frontier needs (H.264 and MPEG-4 video, MP3 and AAC audio, mp4/mov demuxer,
// swscale, swresample). The library exports only the fev_* functions and Main
// loads it with dlopen, like libturbojpeg, so Main's Makefile does not change.
// Built by build.sh here.
//
// Pictures come out as 0xFFRRGGBB already at the size of the caller's box, with
// Frontier's fit modes (fit_bitmap() in fe_media.cpp), sampled straight from
// the YUV planes: each output pixel averages a block of luma (up to 4x4, when
// the picture is reduced) and takes the chroma at its centre. Converting the
// whole picture to RGB first and scaling it after costs more, mostly in memory
// traffic. At the picture's own size 4:2:0 (ScreenScraper) goes through the
// NEON converter of swscale. Two views (two sizes: HDMI and CRT pages of
// Frontier) can be made from the same decoded picture. Measures: ffmpeg 7.1.1 minimal build, ~15-20 ms per frame on the ARM core 0.
//
// Audio: converted to 48 kHz stereo 16 bit with the volume applied, kept in a
// ring and played by a thread of the library through ALSA (libasound loaded
// with dlopen; the MiSTer's default device goes to the core's audio, the menu
// core included). The file is read ahead (video packets wait in a queue) so
// that the ring always holds half a second: in the mp4 files the audio comes
// up to 0.3 s after the video. Positions are counted on one timeline that goes
// on across the loops; the caller syncs the pictures to fev_clock().

#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <time.h>
#include <unistd.h>

#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/channel_layout.h>
#include <libswresample/swresample.h>
#include <libswscale/swscale.h>

#include "fe_av.h"

#define EXPORT __attribute__((visibility("default")))

#define RATE        48000
#define RING_FRAMES (RATE * 2)    // audio ring: 2 s
#define AHEAD       (RATE / 2)    // read ahead until the ring holds 0.5 s
#define LATENCY_US  100000        // ALSA buffer
#define VQ_MAX      256           // video packets read ahead at most
#define CHUNK       1024          // frames per ALSA write
#define FADE        (RATE / 100)  // fade out when stopping: 10 ms

/////////////////////////////////////////////////////////////////////////////
// ALSA, loaded at run time

typedef struct _snd_pcm snd_pcm_t;
typedef struct _snd_config snd_config_t;
typedef struct _snd_input snd_input_t;
static int (*pcm_open)(snd_pcm_t **, const char *, int, int);
static int (*pcm_set_params)(snd_pcm_t *, int, int, unsigned, unsigned, int, unsigned);
static long (*pcm_writei)(snd_pcm_t *, const void *, unsigned long);
static int (*pcm_recover)(snd_pcm_t *, int, int);
static int (*pcm_delay)(snd_pcm_t *, long *);
static int (*pcm_state)(snd_pcm_t *);
static int (*pcm_drain)(snd_pcm_t *);
static int (*pcm_close)(snd_pcm_t *);
static int (*cfg_top)(snd_config_t **);
static int (*cfg_load)(snd_config_t *, snd_input_t *);
static int (*input_buffer_open)(snd_input_t **, const char *, ssize_t);
static int (*input_close)(snd_input_t *);
static int (*pcm_open_lconf)(snd_pcm_t **, const char *, int, int, snd_config_t *);
#define SND_PCM_STREAM_PLAYBACK       0
#define SND_PCM_FORMAT_S16_LE         2
#define SND_PCM_ACCESS_RW_INTERLEAVED 3
#define SND_PCM_STATE_RUNNING         3

static pthread_once_t alsa_once = PTHREAD_ONCE_INIT;
static int alsa_ok = 0;

static void alsa_init(void)
{
	void *lib = dlopen("libasound.so.2", RTLD_NOW | RTLD_LOCAL);
	if (!lib) return;
	pcm_open = (int (*)(snd_pcm_t **, const char *, int, int))dlsym(lib, "snd_pcm_open");
	pcm_set_params = (int (*)(snd_pcm_t *, int, int, unsigned, unsigned, int, unsigned))dlsym(lib, "snd_pcm_set_params");
	pcm_writei = (long (*)(snd_pcm_t *, const void *, unsigned long))dlsym(lib, "snd_pcm_writei");
	pcm_recover = (int (*)(snd_pcm_t *, int, int))dlsym(lib, "snd_pcm_recover");
	pcm_delay = (int (*)(snd_pcm_t *, long *))dlsym(lib, "snd_pcm_delay");
	pcm_state = (int (*)(snd_pcm_t *))dlsym(lib, "snd_pcm_state");
	pcm_drain = (int (*)(snd_pcm_t *))dlsym(lib, "snd_pcm_drain");
	pcm_close = (int (*)(snd_pcm_t *))dlsym(lib, "snd_pcm_close");
	alsa_ok = pcm_open && pcm_set_params && pcm_writei && pcm_recover && pcm_delay && pcm_state && pcm_drain && pcm_close;
	cfg_top = (int (*)(snd_config_t **))dlsym(lib, "snd_config_top");
	cfg_load = (int (*)(snd_config_t *, snd_input_t *))dlsym(lib, "snd_config_load");
	input_buffer_open = (int (*)(snd_input_t **, const char *, ssize_t))dlsym(lib, "snd_input_buffer_open");
	input_close = (int (*)(snd_input_t *))dlsym(lib, "snd_input_close");
	pcm_open_lconf = (int (*)(snd_pcm_t **, const char *, int, int, snd_config_t *))dlsym(lib, "snd_pcm_open_lconf");
}

// The "default" device of the MiSTer is plug -> rate (48000 Hz) -> file /dev/MrAudio ->
// hw:0 (Dummy). Its rate plugin (linear converter of alsa-lib) writes past the end of
// its buffer, also from 48000 to 48000 Hz: it overwrote the thread-local memory of
// Main (crashes in malloc/sscanf during the screensaver with videos). The audio here is
// already 48000 Hz, S16, stereo: the same chain without plug and rate.
static const char *direct_conf =
	"pcm.frontier { type file file \"/dev/MrAudio\" format \"raw\" slave.pcm { type hw card 0 } }";

static int pcm_open_direct(snd_pcm_t **pcm)
{
	static snd_config_t *cfg = NULL;  // kept: the plugins may refer to it
	if (access("/dev/MrAudio", W_OK) || !cfg_top || !cfg_load || !input_buffer_open || !input_close || !pcm_open_lconf)
		return -1;
	if (!cfg)
	{
		snd_input_t *in = NULL;
		snd_config_t *c = NULL;
		if (cfg_top(&c) < 0) return -1;
		if (input_buffer_open(&in, direct_conf, -1) < 0) return -1;
		int r = cfg_load(c, in);
		input_close(in);
		if (r < 0) return -1;
		cfg = c;
	}
	return pcm_open_lconf(pcm, "frontier", SND_PCM_STREAM_PLAYBACK, 0, cfg);
}

static int64_t now_us(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (int64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000;
}

/////////////////////////////////////////////////////////////////////////////

// one output size of the pictures
typedef struct
{
	struct SwsContext *sws;
	int w, h;        // output size (0: view not used)
	int fit;         // FEV_CONTAIN, FEV_COVER, FEV_STRETCH
	int box_w, box_h;
	int sw, sh;      // source size the tables are for
	int *xs, *ys;    // first source column / row of each output pixel
	int bx, by;      // luma block averaged for each output pixel
} view;

struct fev
{
	AVFormatContext *fc;
	AVCodecContext *cc;
	AVPacket *pkt;
	AVFrame *frm;    // last picture, kept for the other view until the next one
	int have_frm;
	view vw[FEV_VIEWS];
	int si;          // video stream
	int eof;         // no more packets in the file
	int flushed;     // end of the file sent to the decoder
	int64_t start;   // timestamp of the first picture
	double tb;       // video time base in ms
	int64_t last_pts, frame_ms; // last picture and picture length (ms)

	AVPacket *vq[VQ_MAX]; // video packets read ahead
	int vq_head, vq_n;

	// audio (ai < 0: none)
	int ai;
	AVCodecContext *ac;
	AVFrame *afrm;
	SwrContext *swr;
	double atb;      // audio time base in s
	double vstart;   // start of the video stream in s (timeline 0)
	int gain;        // volume * 256 / 100
	int16_t *conv;   // swresample output
	int conv_frames;
	snd_pcm_t *pcm;
	pthread_t thread;
	int thread_on;
	pthread_mutex_t mtx;
	pthread_cond_t cond;
	// under mtx; frame numbers on the timeline (48 kHz)
	int16_t *ring;   // stereo frames, RING_FRAMES
	int64_t head;    // next frame to write in the ring
	int64_t tail;    // next frame the audio thread takes
	int64_t loop0;   // timeline frame of the start of the current loop
	int64_t pos;     // timeline frame heard at pos_time (-1: not playing)
	int64_t pos_time;
	int stop;
};

/////////////////////////////////////////////////////////////////////////////
// pictures

static inline uint8_t clip8(int v)
{
	return v < 0 ? 0 : v > 255 ? 255 : v;
}

static inline uint32_t yuv_px(int Y, int U, int V)
{
	int c = 298 * (Y - 16) + 128;
	U -= 128;
	V -= 128;
	return 0xFF000000u | (clip8((c + 409 * V) >> 8) << 16) | (clip8((c - 100 * U - 208 * V) >> 8) << 8) | clip8((c + 516 * U) >> 8);
}

// output size and source area for a source picture (same as fit_bitmap)
static int setup(view *v, int sw, int sh)
{
	int cx = 0, cy = 0, cw = sw, ch = sh, dw = v->box_w, dh = v->box_h;
	if (dw <= 0 || dh <= 0)
	{
		dw = sw;
		dh = sh;
	}
	else if (v->fit == FEV_CONTAIN)
	{
		if ((int64_t)sw * dh > (int64_t)sh * dw) dh = (int)((int64_t)sh * dw / sw);
		else dw = (int)((int64_t)sw * dh / sh);
	}
	else if (v->fit == FEV_COVER)
	{
		if ((int64_t)sw * dh > (int64_t)sh * dw)
		{
			cw = (int)((int64_t)dw * sh / dh);
			cx = (sw - cw) / 2;
		}
		else
		{
			ch = (int)((int64_t)dh * sw / dw);
			cy = (sh - ch) / 2;
		}
	}
	if (dw < 1) dw = 1;
	if (dh < 1) dh = 1;
	if (cw < 1) cw = 1;
	if (ch < 1) ch = 1;

	free(v->xs);
	free(v->ys);
	v->xs = (int *)malloc(dw * sizeof(int));
	v->ys = (int *)malloc(dh * sizeof(int));
	if (!v->xs || !v->ys) return 0;

	v->bx = cw / dw;
	v->by = ch / dh;
	if (v->bx < 1) v->bx = 1;
	if (v->bx > 4) v->bx = 4;
	if (v->by < 1) v->by = 1;
	if (v->by > 4) v->by = 4;
	// block centred on the output pixel's centre in the source
	for (int x = 0; x < dw; x++)
	{
		int c = cx + (int)(((int64_t)(2 * x + 1) * cw) / (2 * dw)) - v->bx / 2;
		v->xs[x] = c < 0 ? 0 : c > sw - v->bx ? sw - v->bx : c;
	}
	for (int y = 0; y < dh; y++)
	{
		int c = cy + (int)(((int64_t)(2 * y + 1) * ch) / (2 * dh)) - v->by / 2;
		v->ys[y] = c < 0 ? 0 : c > sh - v->by ? sh - v->by : c;
	}
	v->sw = sw;
	v->sh = sh;
	v->w = dw;
	v->h = dh;
	return 1;
}

// chroma shift of the formats sampled here, -1 for the others
static int chroma_shift(int fmt)
{
	if (fmt == AV_PIX_FMT_YUV420P || fmt == AV_PIX_FMT_YUVJ420P) return 1;
	if (fmt == AV_PIX_FMT_YUV444P || fmt == AV_PIX_FMT_YUVJ444P) return 0;
	return -1;
}

// BT.601 limited range; cs: chroma shift (1 for 4:2:0, 0 for 4:4:4)
static void sample(const view *v, const AVFrame *f, uint32_t *out, int cs)
{
	const int bx = v->bx, by = v->by, ls = f->linesize[0];
	const int inv = 65536 / (bx * by);
	for (int y = 0; y < v->h; y++)
	{
		const uint8_t *ly = f->data[0] + (size_t)v->ys[y] * ls;
		int cy = (v->ys[y] + by / 2) >> cs;
		const uint8_t *u = f->data[1] + (size_t)cy * f->linesize[1];
		const uint8_t *vv = f->data[2] + (size_t)cy * f->linesize[2];
		uint32_t *o = out + (size_t)y * v->w;
		const int *xs = v->xs;
		if (bx == 1 && by == 1)
		{
			for (int x = 0; x < v->w; x++)
			{
				int sx = xs[x], c = sx >> cs;
				o[x] = yuv_px(ly[sx], u[c], vv[c]);
			}
		}
		else if (bx == 2 && by == 2)
		{
			for (int x = 0; x < v->w; x++)
			{
				const uint8_t *p = ly + xs[x];
				int c = (xs[x] + 1) >> cs;
				o[x] = yuv_px((p[0] + p[1] + p[ls] + p[ls + 1] + 2) >> 2, u[c], vv[c]);
			}
		}
		else
		{
			for (int x = 0; x < v->w; x++)
			{
				const uint8_t *p = ly + xs[x];
				int sum = 0;
				for (int j = 0; j < by; j++, p += ls)
					for (int i = 0; i < bx; i++) sum += p[i];
				int c = (xs[x] + bx / 2) >> cs;
				o[x] = yuv_px((sum * inv) >> 16, u[c], vv[c]);
			}
		}
	}
}

static int convert(view *v, const AVFrame *f, uint32_t *px)
{
	// a picture of another size than the first one: the output size stays
	if ((f->width != v->sw || f->height != v->sh) && v->xs)
	{
		int w = v->w, h = v->h;
		if (!setup(v, f->width, f->height)) return 0;
		if (v->w != w || v->h != h) return 0;
	}

	int cs = chroma_shift(f->format);
	int same = v->w == f->width && v->h == f->height;
	if (cs >= 0 && !(same && cs == 1))
	{
		sample(v, f, px, cs);
		return 1;
	}

	// 4:2:0 at its own size (NEON path of swscale) or anything else
	v->sws = sws_getCachedContext(v->sws, f->width, f->height, (enum AVPixelFormat)f->format,
		v->w, v->h, AV_PIX_FMT_BGRA, SWS_FAST_BILINEAR, NULL, NULL, NULL);
	if (!v->sws) return 0;
	uint8_t *dst[4] = { (uint8_t *)px };
	int stride[4] = { v->w * 4 };
	// the NEON converters of swscale return 0 lines even when they work
	return sws_scale(v->sws, (const uint8_t *const *)f->data, f->linesize, 0, f->height, dst, stride) >= 0;
}

/////////////////////////////////////////////////////////////////////////////
// audio

// copies n frames to the ring (under mtx; data NULL = silence)
static void ring_put(fev *v, const int16_t *data, int n)
{
	if (v->head - v->tail + n > RING_FRAMES) return; // nobody plays: dropped
	for (int i = 0; i < n; i++)
	{
		int16_t *d = v->ring + 2 * ((v->head + i) % RING_FRAMES);
		d[0] = data ? data[2 * i] : 0;
		d[1] = data ? data[2 * i + 1] : 0;
	}
	v->head += n;
	pthread_cond_signal(&v->cond);
}

static void *audio_thread(void *arg)
{
	fev *v = (fev *)arg;
	int16_t buf[2 * CHUNK];

	pthread_mutex_lock(&v->mtx);
	while (!v->stop)
	{
		int n = (int)(v->head - v->tail);
		if (n <= 0)
		{
			// nothing to play: ALSA runs dry and starts again at the next write
			v->pos = -1;
			struct timespec ts;
			clock_gettime(CLOCK_REALTIME, &ts);
			ts.tv_nsec += 10000000;
			if (ts.tv_nsec >= 1000000000)
			{
				ts.tv_sec++;
				ts.tv_nsec -= 1000000000;
			}
			pthread_cond_timedwait(&v->cond, &v->mtx, &ts);
			continue;
		}
		if (n > CHUNK) n = CHUNK;
		for (int i = 0; i < n; i++) memcpy(buf + 2 * i, v->ring + 2 * ((v->tail + i) % RING_FRAMES), 4);
		v->tail += n;
		int64_t written = v->tail;
		pthread_mutex_unlock(&v->mtx);

		long r = pcm_writei(v->pcm, buf, n);
		if (r < 0) pcm_recover(v->pcm, (int)r, 1);
		long delay = 0;
		int running = pcm_state(v->pcm) == SND_PCM_STATE_RUNNING && !pcm_delay(v->pcm, &delay);

		pthread_mutex_lock(&v->mtx);
		v->pos = running ? written - delay : -1;
		v->pos_time = now_us();
	}

	// what is in the ALSA buffer plays, then a short fade: no click
	int n = (int)(v->head - v->tail);
	if (n > FADE) n = FADE;
	for (int i = 0; i < FADE; i++)
	{
		const int16_t *s = v->ring + 2 * ((v->tail + i) % RING_FRAMES);
		int g = FADE - i;
		buf[2 * i] = i < n ? s[0] * g / FADE : 0;
		buf[2 * i + 1] = i < n ? s[1] * g / FADE : 0;
	}
	v->pos = -1;
	pthread_mutex_unlock(&v->mtx);
	if (pcm_writei(v->pcm, buf, FADE) >= 0) pcm_drain(v->pcm);
	return 0;
}

static int audio_open(fev *v, int volume)
{
	if (volume <= 0) return 0;
	pthread_once(&alsa_once, alsa_init);
	if (!alsa_ok) return 0;

	int ai = av_find_best_stream(v->fc, AVMEDIA_TYPE_AUDIO, -1, v->si, NULL, 0);
	if (ai < 0) return 0;
	AVStream *st = v->fc->streams[ai];
	const AVCodec *codec = avcodec_find_decoder(st->codecpar->codec_id);
	if (!codec) return 0;
	v->ac = avcodec_alloc_context3(codec);
	if (!v->ac || avcodec_parameters_to_context(v->ac, st->codecpar) < 0) return 0;
	v->ac->pkt_timebase = st->time_base;
	v->ac->thread_count = 1;
	if (avcodec_open2(v->ac, codec, NULL) < 0) return 0;

	v->afrm = av_frame_alloc();
	v->ring = (int16_t *)malloc(RING_FRAMES * 4);
	if (!v->afrm || !v->ring) return 0;
	// the chain of the MiSTer without its rate plugin, otherwise "default"
	int direct = pcm_open_direct(&v->pcm) >= 0;
	if (direct && pcm_set_params(v->pcm, SND_PCM_FORMAT_S16_LE, SND_PCM_ACCESS_RW_INTERLEAVED, 2, RATE, 0, LATENCY_US) < 0)
	{
		pcm_close(v->pcm);
		direct = 0;
	}
	if (!direct)
	{
		if (pcm_open(&v->pcm, "default", SND_PCM_STREAM_PLAYBACK, 0) < 0)
		{
			v->pcm = NULL;
			return 0;
		}
		if (pcm_set_params(v->pcm, SND_PCM_FORMAT_S16_LE, SND_PCM_ACCESS_RW_INTERLEAVED, 2, RATE, 1, LATENCY_US) < 0) return 0;
	}

	v->atb = av_q2d(st->time_base);
	AVStream *vs = v->fc->streams[v->si];
	v->vstart = vs->start_time == AV_NOPTS_VALUE ? 0 : vs->start_time * av_q2d(vs->time_base);
	v->gain = volume > 100 ? 256 : volume * 256 / 100;
	v->pos = -1;
	pthread_mutex_init(&v->mtx, NULL);
	pthread_cond_init(&v->cond, NULL);
	if (pthread_create(&v->thread, NULL, audio_thread, v))
	{
		pthread_mutex_destroy(&v->mtx);
		pthread_cond_destroy(&v->cond);
		return 0;
	}
	v->thread_on = 1;
	st->discard = AVDISCARD_DEFAULT;
	v->ai = ai;
	return 1;
}

static void audio_close(fev *v)
{
	if (v->thread_on)
	{
		pthread_mutex_lock(&v->mtx);
		v->stop = 1;
		pthread_cond_signal(&v->cond);
		pthread_mutex_unlock(&v->mtx);
		pthread_join(v->thread, NULL);
		pthread_mutex_destroy(&v->mtx);
		pthread_cond_destroy(&v->cond);
		v->thread_on = 0;
	}
	if (v->pcm) pcm_close(v->pcm);
	v->pcm = NULL;
	swr_free(&v->swr);
	av_frame_free(&v->afrm);
	avcodec_free_context(&v->ac);
	free(v->ring);
	free(v->conv);
	v->ring = NULL;
	v->conv = NULL;
	v->conv_frames = 0;
	v->ai = -1;
}

// decoded audio to the ring, at its place on the timeline
static void audio_frame(fev *v, AVFrame *f)
{
	if (!v->swr)
	{
		AVChannelLayout stereo = AV_CHANNEL_LAYOUT_STEREO, in = f->ch_layout;
		if (!in.nb_channels) av_channel_layout_default(&in, 2);
		if (swr_alloc_set_opts2(&v->swr, &stereo, AV_SAMPLE_FMT_S16, RATE, &in, (enum AVSampleFormat)f->format,
			f->sample_rate, 0, NULL) < 0 || swr_init(v->swr) < 0)
		{
			swr_free(&v->swr);
			return;
		}
	}

	int max = swr_get_out_samples(v->swr, f->nb_samples);
	if (max <= 0) return;
	if (max > v->conv_frames)
	{
		free(v->conv);
		v->conv = (int16_t *)malloc(max * 4);
		v->conv_frames = v->conv ? max : 0;
		if (!v->conv) return;
	}
	uint8_t *out = (uint8_t *)v->conv;
	int n = swr_convert(v->swr, &out, max, (const uint8_t **)f->extended_data, f->nb_samples);
	if (n <= 0) return;
	for (int i = 0; i < 2 * n; i++) v->conv[i] = (int16_t)((v->conv[i] * v->gain) >> 8);

	pthread_mutex_lock(&v->mtx);
	const int16_t *d = v->conv;
	if (f->pts != AV_NOPTS_VALUE)
	{
		// where it belongs: a gap is filled with silence, an overlap cut
		int64_t at = v->loop0 + (int64_t)((f->pts * v->atb - v->vstart) * RATE);
		int64_t diff = at - v->head;
		if (diff > RATE / 50 && diff < RATE) ring_put(v, NULL, (int)diff);
		else if (diff < -RATE / 50)
		{
			int cut = (int)(-diff < n ? -diff : n);
			d += 2 * cut;
			n -= cut;
		}
	}
	if (n > 0) ring_put(v, d, n);
	pthread_mutex_unlock(&v->mtx);
}

static void audio_packet(fev *v, AVPacket *p)
{
	if (avcodec_send_packet(v->ac, p) < 0) return;
	while (!avcodec_receive_frame(v->ac, v->afrm))
	{
		audio_frame(v, v->afrm);
		av_frame_unref(v->afrm);
	}
}

static int audio_level(fev *v)
{
	pthread_mutex_lock(&v->mtx);
	int n = (int)(v->head - v->tail);
	pthread_mutex_unlock(&v->mtx);
	return n;
}

/////////////////////////////////////////////////////////////////////////////
// reading

// next packet of the file: audio is decoded, video queued; 0 at the end
static int read_packet(fev *v)
{
	if (v->eof || v->vq_n == VQ_MAX) return 0;
	while (1)
	{
		if (av_read_frame(v->fc, v->pkt) < 0)
		{
			v->eof = 1;
			return 0;
		}
		if (v->pkt->stream_index == v->si)
		{
			AVPacket *p = av_packet_clone(v->pkt);
			av_packet_unref(v->pkt);
			if (!p) continue;
			v->vq[(v->vq_head + v->vq_n) % VQ_MAX] = p;
			v->vq_n++;
			return 1;
		}
		if (v->pkt->stream_index == v->ai) audio_packet(v, v->pkt);
		av_packet_unref(v->pkt);
	}
}

static void vq_clear(fev *v)
{
	while (v->vq_n)
	{
		av_packet_free(&v->vq[v->vq_head]);
		v->vq_head = (v->vq_head + 1) % VQ_MAX;
		v->vq_n--;
	}
	v->vq_head = 0;
}

/////////////////////////////////////////////////////////////////////////////

EXPORT fev *fev_open(const char *path, int box_w, int box_h, int fit, int volume, int *out_w, int *out_h)
{
	av_log_set_level(AV_LOG_QUIET);

	fev *v = (fev *)calloc(1, sizeof(fev));
	if (!v) return NULL;
	v->start = AV_NOPTS_VALUE;
	v->ai = -1;
	v->frame_ms = 33;

	if (avformat_open_input(&v->fc, path, NULL, NULL) < 0) goto fail;
	v->si = av_find_best_stream(v->fc, AVMEDIA_TYPE_VIDEO, -1, -1, NULL, 0);
	if (v->si < 0) goto fail;

	// the mp4 header has what the decoders need: probing the streams would
	// decode pictures for nothing
	AVStream *st = v->fc->streams[v->si];
	if (st->codecpar->width <= 0 || st->codecpar->format < 0)
	{
		if (avformat_find_stream_info(v->fc, NULL) < 0) goto fail;
	}
	for (unsigned i = 0; i < v->fc->nb_streams; i++)
	{
		if ((int)i != v->si) v->fc->streams[i]->discard = AVDISCARD_ALL;
	}

	const AVCodec *codec = avcodec_find_decoder(st->codecpar->codec_id);
	if (!codec) goto fail;
	v->cc = avcodec_alloc_context3(codec);
	if (!v->cc || avcodec_parameters_to_context(v->cc, st->codecpar) < 0) goto fail;
	v->cc->pkt_timebase = st->time_base;
	v->cc->thread_count = 1; // the caller's core: Main keeps the other one busy
	v->cc->flags2 |= AV_CODEC_FLAG2_FAST;
	// beyond DVD size the deblocking filter costs too much (not visible in a small box)
	if (st->codecpar->width * st->codecpar->height > 720 * 576) v->cc->skip_loop_filter = AVDISCARD_ALL;
	if (avcodec_open2(v->cc, codec, NULL) < 0) goto fail;

	v->pkt = av_packet_alloc();
	v->frm = av_frame_alloc();
	if (!v->pkt || !v->frm) goto fail;

	int sw = st->codecpar->width, sh = st->codecpar->height;
	if (sw <= 0 || sh <= 0) goto fail;
	v->tb = av_q2d(st->time_base) * 1000.0;
	view *v0 = &v->vw[0];
	v0->fit = fit;
	v0->box_w = box_w;
	v0->box_h = box_h;
	if (!setup(v0, sw, sh)) goto fail;
	// shown at half the area or less: the blocks the deblocking filter smooths
	// can't be seen, and it is about a quarter of the decoding time
	if ((int64_t)v0->w * v0->h * 2 <= (int64_t)sw * sh) v->cc->skip_loop_filter = AVDISCARD_ALL;

	if (!audio_open(v, volume)) audio_close(v); // no sound: the video plays anyway

	*out_w = v0->w;
	*out_h = v0->h;
	return v;

fail:
	fev_close(v);
	return NULL;
}

EXPORT int fev_next(fev *v, uint32_t *px, int64_t *pts_ms)
{
	// the audio ahead of the pictures
	if (v->ai >= 0)
	{
		while (audio_level(v) < AHEAD && read_packet(v)) {}
	}

	if (v->have_frm) av_frame_unref(v->frm);
	v->have_frm = 0;
	while (1)
	{
		int r = avcodec_receive_frame(v->cc, v->frm);
		if (!r)
		{
			v->have_frm = 1;
			int64_t ts = v->frm->best_effort_timestamp;
			if (ts == AV_NOPTS_VALUE) ts = v->frm->pts;
			if (ts == AV_NOPTS_VALUE) ts = 0;
			if (v->start == AV_NOPTS_VALUE) v->start = ts;
			*pts_ms = (int64_t)((ts - v->start) * v->tb);
			if (*pts_ms > v->last_pts && *pts_ms - v->last_pts < 1000) v->frame_ms = *pts_ms - v->last_pts;
			v->last_pts = *pts_ms;
			return (!px || convert(&v->vw[0], v->frm, px)) ? 1 : -1;
		}
		if (r == AVERROR_EOF) return 0;
		if (r != AVERROR(EAGAIN)) return -1;

		if (!v->vq_n) read_packet(v);
		if (!v->vq_n)
		{
			// end of the file: the decoder still holds some pictures
			if (v->flushed) return 0;
			v->flushed = 1;
			avcodec_send_packet(v->cc, NULL);
			continue;
		}
		AVPacket *p = v->vq[v->vq_head];
		v->vq_head = (v->vq_head + 1) % VQ_MAX;
		v->vq_n--;
		avcodec_send_packet(v->cc, p);
		av_packet_free(&p);
	}
}

EXPORT int fev_rewind(fev *v, int64_t *loop_ms)
{
	// the loop lasts up to the end of its last picture; the audio of the next
	// one starts there (silence added or audio cut to get there)
	int64_t len = v->last_pts + v->frame_ms;
	*loop_ms = len;
	if (v->ai >= 0)
	{
		pthread_mutex_lock(&v->mtx);
		int64_t end = v->loop0 + len * RATE / 1000;
		if (v->head < end) ring_put(v, NULL, (int)(end - v->head < RATE ? end - v->head : RATE));
		else if (v->head > end) v->head = end > v->tail ? end : v->tail;
		v->loop0 = end;
		pthread_mutex_unlock(&v->mtx);
		avcodec_flush_buffers(v->ac);
		swr_free(&v->swr);
	}

	if (av_seek_frame(v->fc, v->si, v->start == AV_NOPTS_VALUE ? 0 : v->start, AVSEEK_FLAG_BACKWARD) < 0 &&
		avformat_seek_file(v->fc, -1, INT64_MIN, 0, INT64_MAX, 0) < 0) return 0;
	avcodec_flush_buffers(v->cc);
	vq_clear(v);
	v->eof = 0;
	v->flushed = 0;
	v->last_pts = -v->frame_ms;
	return 1;
}

EXPORT int fev_view(fev *v, int n, int box_w, int box_h, int fit, int *out_w, int *out_h)
{
	if (n <= 0 || n >= FEV_VIEWS) return 0;
	view *w = &v->vw[n];
	w->fit = fit;
	w->box_w = box_w;
	w->box_h = box_h;
	if (!setup(w, v->vw[0].sw, v->vw[0].sh))
	{
		w->w = w->h = 0;
		return 0;
	}
	*out_w = w->w;
	*out_h = w->h;
	return 1;
}

EXPORT int fev_picture(fev *v, int n, uint32_t *px)
{
	if (n < 0 || n >= FEV_VIEWS || !v->vw[n].w || !v->have_frm) return 0;
	return convert(&v->vw[n], v->frm, px);
}

EXPORT int64_t fev_clock(fev *v)
{
	if (v->ai < 0) return -1;
	pthread_mutex_lock(&v->mtx);
	int64_t pos = v->pos, t = v->pos_time;
	pthread_mutex_unlock(&v->mtx);
	if (pos < 0) return -1;
	int64_t el = now_us() - t;
	if (el > 200000) return -1; // the audio thread is stuck: don't follow it
	return pos * 1000 / RATE + el / 1000;
}

EXPORT void fev_close(fev *v)
{
	if (!v) return;
	audio_close(v);
	vq_clear(v);
	for (int i = 0; i < FEV_VIEWS; i++)
	{
		sws_freeContext(v->vw[i].sws);
		free(v->vw[i].xs);
		free(v->vw[i].ys);
	}
	av_frame_free(&v->frm);
	av_packet_free(&v->pkt);
	avcodec_free_context(&v->cc);
	avformat_close_input(&v->fc);
	free(v);
}
