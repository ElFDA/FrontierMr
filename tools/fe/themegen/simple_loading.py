#!/usr/bin/env python3
# Spinner of the loading screen of the simple theme (themes/simple/anim/spinner_*.png),
# also used by the themes without their own loading.ini.
# Usage: tools/fe/themegen/simple_loading.py
import os, math
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'frontier', 'themes', 'default', 'anim')
N, SIZE, SS = 12, 96, 4                    # frames, pixels (base 1280x720 x 1.5), supersampling
GOLD, DIM = (255, 192, 64), (58, 74, 102)

os.makedirs(OUT, exist_ok=True)
for i in range(N):
    im = Image.new('RGBA', (SIZE * SS, SIZE * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, r, dot = SIZE * SS / 2, SIZE * SS * 0.38, SIZE * SS * 0.075
    for k in range(N):
        # 12 dots on a ring, the bright one turns, the ones behind it fade
        age = (i - k) % N
        t = max(0.0, 1 - age / 6.0)
        col = tuple(int(DIM[j] + (GOLD[j] - DIM[j]) * t) for j in range(3)) + (255,)
        a = 2 * math.pi * k / N - math.pi / 2
        x, y = c + r * math.cos(a), c + r * math.sin(a)
        rr = dot * (0.7 + 0.3 * t)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=col)
    im = im.resize((SIZE, SIZE), Image.LANCZOS)
    p = os.path.join(OUT, 'spinner_%02d.png' % i)
    im.save(p)
    print(os.path.normpath(p))
