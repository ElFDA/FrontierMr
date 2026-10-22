#!/bin/bash
# Builds fe_av.so (mp4 videos for Frontier) with the project toolchain:
# downloads FFmpeg, compiles a minimal static FFmpeg for the DE10-Nano
# (Cortex-A9, NEON) and links it with fe_av.c into one shared library.
# Output: tools/fe/sd/frontier/lib/fe_av.so (+ FFmpeg licence), copied to the
# MiSTer by deploy.sh; tools/fe/fe_av/fev_test (speed test, see fev_test.c).
# Usage: tools/fe/fe_av/build.sh   (work folder: FE_AV_WORK, default $HOME/.frontier/fe_av)
set -e
cd "$(dirname "$0")"
HERE=$(pwd)
[ -f ../env.local.sh ] && . ../env.local.sh  # local paths, not in git
OUT=$HERE/../sd/frontier/lib
W=${FE_AV_WORK:-$HOME/.frontier/fe_av}
FFV=7.1.1
export PATH=${MISTER_GCC_INSTALL_DIR:-$HOME/toolchain}/gcc-arm-10.2-2020.11-x86_64-arm-none-linux-gnueabihf/bin:$PATH
CC=arm-none-linux-gnueabihf-gcc
CFLAGS="-O2 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard"

mkdir -p "$W" "$OUT"
cd "$W"
CONF="--prefix=$W/install --enable-cross-compile \
	--cross-prefix=arm-none-linux-gnueabihf- --arch=arm --target-os=linux --cpu=cortex-a9 \
	--extra-cflags=-mfpu=neon\ -mfloat-abi=hard --enable-pic --enable-static --disable-shared \
	--disable-programs --disable-doc --disable-debug --disable-network --disable-autodetect \
	--disable-iconv --disable-everything --disable-avdevice --disable-avfilter \
	--enable-avcodec --enable-avformat --enable-swscale --enable-swresample \
	--enable-decoder=h264,mpeg4,h263,mp3,mp3float,aac --enable-parser=h264,mpeg4video,mpegaudio,aac \
	--enable-demuxer=mov --enable-protocol=file --enable-neon"
# FFmpeg built again only when the configuration changes
if [ "$(cat install/conf 2>/dev/null)" != "$CONF" ]; then
	[ -d ffmpeg-$FFV ] || { curl -sSfLO https://ffmpeg.org/releases/ffmpeg-$FFV.tar.xz; tar xf ffmpeg-$FFV.tar.xz; }
	# 7.1.1 does not link with h264 alone: aom_film_grain.o is only built for HEVC
	sed -i 's/^OBJS-$(CONFIG_H264_SEI)                += h264_sei.o h2645_sei.o$/& aom_film_grain.o/' ffmpeg-$FFV/libavcodec/Makefile
	rm -rf build install && mkdir build && cd build
	eval ../ffmpeg-$FFV/configure $CONF >/dev/null
	make -j"$(nproc)" >/dev/null
	make install >/dev/null
	cd "$W"
	echo "$CONF" > install/conf
fi

I=$W/install
$CC $CFLAGS -shared -fPIC -fvisibility=hidden -I"$I/include" "$HERE/fe_av.c" \
	"$I/lib/libavformat.a" "$I/lib/libavcodec.a" "$I/lib/libswscale.a" "$I/lib/libswresample.a" "$I/lib/libavutil.a" \
	-Wl,--exclude-libs,ALL -Wl,-Bsymbolic -Wl,-z,noexecstack -lm -lpthread -ldl -s -o "$OUT/fe_av.so"
cp "$W/ffmpeg-$FFV/COPYING.LGPLv2.1" "$OUT/FFMPEG_LICENSE.txt"
$CC $CFLAGS -I"$HERE" "$HERE/fev_test.c" -ldl -o "$HERE/fev_test"
arm-none-linux-gnueabihf-nm -D --defined-only "$OUT/fe_av.so" | grep ' T ' | grep -v ' T _'
ls -la "$OUT/fe_av.so"
