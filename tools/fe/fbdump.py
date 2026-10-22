#!/usr/bin/env python3
# Runs on the MiSTer: saves a page of the HPS framebuffer (0,1,2) as PPM.
# CRT pages (Frontier's menu.rbf): c0, c1 (640 x 240/288).
# Usage: python3 fbdump.py <page> <width> <height> <out.ppm>
import mmap, os, sys
FB_ADDR = 0x22000000
FB_SIZE = 1920 * 1080 * 4
FE_CRT_ADDR = 0x23800000
FE_CRT_PAGE = 2 * 1024 * 1024
page, w, h, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
addr = FE_CRT_ADDR + FE_CRT_PAGE * int(page[1:]) if page[0] == 'c' else FB_ADDR + FB_SIZE * int(page)
fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
m = mmap.mmap(fd, FB_SIZE, mmap.MAP_SHARED, mmap.PROT_READ, offset=addr)
data = m[:w * h * 4]
rgb = bytearray(w * h * 3)
rgb[0::3] = data[2::4]
rgb[1::3] = data[1::4]
rgb[2::3] = data[0::4]
with open(out, 'wb') as f:
    f.write(b'P6 %d %d 255\n' % (w, h))
    f.write(rgb)
