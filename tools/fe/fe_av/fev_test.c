// Test of fe_av.so on the MiSTer: decodes a video like Frontier does and
// prints the time per picture. Usage (core 0, like the video thread of Frontier):
//   taskset 1 ./fev_test /media/fat/frontier/lib/fe_av.so video.mp4 [box_w box_h [pic.ppm]]
// box: shown whole (contain). pic.ppm: picture 150 (5 s at 30 fps), to check the colours.
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#include "fe_av.h"

static double now_ms(void)
{
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return t.tv_sec * 1e3 + t.tv_nsec * 1e-6;
}

int main(int argc, char **argv)
{
	if (argc < 3)
	{
		fprintf(stderr, "usage: %s fe_av.so video.mp4 [box_w box_h [pic.ppm]]\n", argv[0]);
		return 1;
	}

	void *lib = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
	if (!lib)
	{
		fprintf(stderr, "%s\n", dlerror());
		return 1;
	}
	fev *(*open)(const char *, int, int, int, int, int *, int *) = dlsym(lib, "fev_open");
	int (*next)(fev *, uint32_t *, int64_t *) = dlsym(lib, "fev_next");
	int (*rewind)(fev *, int64_t *) = dlsym(lib, "fev_rewind");
	int64_t (*clock)(fev *) = dlsym(lib, "fev_clock");
	void (*close)(fev *) = dlsym(lib, "fev_close");
	if (!open || !next || !rewind || !clock || !close) return 1;

	int nw = argc > 4 ? atoi(argv[3]) : 0, nh = argc > 4 ? atoi(argv[4]) : 0;
	int w, h;
	double t0 = now_ms();
	int vol = getenv("FEV_VOLUME") ? atoi(getenv("FEV_VOLUME")) : 0;
	fev *v = open(argv[2], nw, nh, FEV_CONTAIN, vol, &w, &h);
	if (!v)
	{
		fprintf(stderr, "can't open %s\n", argv[2]);
		return 1;
	}
	double t_open = now_ms() - t0;

	uint32_t *px = malloc((size_t)w * h * 4);
	int64_t pts = 0, last = 0;
	int n = 0, r;
	t0 = now_ms();
	double first = 0;
	int play = getenv("FEV_PLAY") != NULL;
	while ((r = next(v, px, &pts)) > 0)
	{
		if (!n)
		{
			first = now_ms() - t0;
			t0 = now_ms();
		}
		if (play)
		{
			double due = t0 + pts;
			if (due > now_ms()) usleep((useconds_t)((due - now_ms()) * 1000));
			if (n % 30 == 0) printf("picture %lld ms, sound %lld ms\n", (long long)pts, (long long)clock(v));
		}
		FILE *fp = (n == 150 && argc > 5) ? fopen(argv[5], "wb") : NULL;
		if (fp)
		{
			fprintf(fp, "P6 %d %d 255\n", w, h);
			for (int i = 0; i < w * h; i++) fputc(px[i] >> 16, fp), fputc(px[i] >> 8, fp), fputc(px[i], fp);
			fclose(fp);
		}
		last = pts;
		n++;
	}
	double t = now_ms() - t0;
	int alpha = n && (px[0] >> 24) == 0xFF && (px[w * h - 1] >> 24) == 0xFF;
	printf("%s: out %dx%d, open %.1f ms, first picture %.1f ms, %d pictures, %.2f ms each after it, last pts %lld ms, end %d, alpha %s\n",
		argv[2], w, h, t_open, first, n, n > 1 ? t / (n - 1) : 0, (long long)last, r, alpha ? "ok" : "NO");

	// loop: the first picture after the rewind must be at pts 0
	int64_t loop = 0;
	if (rewind(v, &loop) && next(v, px, &pts) > 0) printf("rewind: loop %lld ms, first pts %lld ms\n", (long long)loop, (long long)pts);
	else printf("rewind failed\n");
	close(v);
	return 0;
}
