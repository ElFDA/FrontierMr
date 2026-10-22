#!/usr/bin/env python3
# Pictures of the example themes "citypop", "citypop_dark" and "citypop_blue"
# (Japanese pop of the bubble era, after bubblism.jp: dashed grid, mint and blue,
# pink bubble, dot patterns, offset shadows) and the ini files of the two variants,
# made from those of citypop with other colours.
# The positions match the rect= of the ini files (1280x720 for 16:9, 960x720
# for 4:3; 3 units of height = 1 line of the CRT): change both together.
# Usage: tools/fe/themegen/citypop_assets.py
import os
import numpy as np
from PIL import Image, ImageDraw

THEMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'frontier', 'themes')
ROOT = None                                 # img/ folder of the theme being made

MINT, BLUE, PINK, LIGHT = (105, 210, 186), (60, 107, 177), (255, 163, 217), (122, 161, 219)
YELLOW, NAVY = (255, 221, 51), (0, 41, 103)
SS = 3                                      # supersampling of the drawings

# BG background, GRID dashed lines, PAPER panels, SHADOW offset shadows on the
# background, EDGE blue edge of the slab in the header, CARDS backgrounds of the
# cards, CARD_DOTS dots on the cards
PALETTES = {
    'citypop': dict(BG=(244, 213, 213), GRID=(255, 227, 249), PAPER=(250, 242, 241), SHADOW=LIGHT, EDGE=BLUE,
                    CARDS=[(255, 214, 236), (255, 236, 160), (205, 222, 250), (255, 200, 220), (200, 240, 228),
                           (236, 220, 250), (250, 228, 210), (214, 240, 250)], CARD_DOTS=(255, 255, 255)),
    # the dark mode of bubblism.jp
    'citypop_dark': dict(BG=(33, 33, 33), GRID=(85, 60, 80), PAPER=(43, 43, 43), SHADOW=LIGHT, EDGE=BLUE,
                         CARDS=[(58, 38, 54), (56, 50, 34), (34, 44, 62), (62, 36, 48), (30, 54, 50),
                                (48, 40, 64), (60, 44, 38), (32, 50, 60)], CARD_DOTS=(85, 60, 80)),
    # the blue of the titles as background, panels of the light accent colour of the site
    'citypop_blue': dict(BG=BLUE, GRID=(86, 130, 196), PAPER=(245, 247, 255), SHADOW=NAVY, EDGE=NAVY,
                         CARDS=[(255, 214, 236), (255, 236, 160), (205, 222, 250), (255, 200, 220), (200, 240, 228),
                                (236, 220, 250), (250, 228, 210), (214, 240, 250)], CARD_DOTS=(255, 255, 255)),
}
P = None                                    # palette of the theme being made

def save(im, name):
    os.makedirs(ROOT, exist_ok=True)
    p = os.path.join(ROOT, name)
    im.save(p)
    print(os.path.normpath(p))

def grid(w, h):
    im = Image.new('RGB', (w, h), P['BG'])
    d = ImageDraw.Draw(im)
    for x in range(48, w, 96):              # dashes 18 on, 3 off
        for y in range(0, h, 21):
            d.rectangle([x - 1, y, x + 1, y + 17], fill=P['GRID'])
    for y in range(30, h, 60):
        for x in range(0, w, 21):
            d.rectangle([x, y, x + 17, y + 2], fill=P['GRID'])
    return im

def dots(d, x0, y0, x1, y1, step, r, color):
    for y in range(y0, y1, step):
        for x in range(x0, x1, step):
            d.ellipse([x - r, y - r, x + r, y + r], fill=color)

def panel(d, box, border_left):
    """Paper panel with a mint border on one side and an offset shadow."""
    x0, y0, x1, y1 = box
    d.rectangle([x0 + 6, y0 + 6, x1 + 6, y1 + 6], fill=P['SHADOW'])
    d.rectangle(box, fill=P['PAPER'])
    if border_left:
        d.rectangle([x0, y0, x0 + 15, y1], fill=MINT)
    else:
        d.rectangle([x1 - 15, y0, x1, y1], fill=MINT)

def bubble(r):
    """Glossy pink bubble (RGBA, 2r x 2r)."""
    n = 2 * r * SS
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / (n - 1) * 2 - 1
    dist = np.sqrt(xx * xx + yy * yy)
    inside = dist <= 1
    # pink, a lilac haze on the upper left, lighter on the rim at the bottom
    lil = np.clip(1 - np.sqrt((xx + 0.35) ** 2 + (yy + 0.35) ** 2) / 0.9, 0, 1) ** 1.5
    rim = np.clip((dist - 0.75) / 0.25, 0, 1) * np.clip(yy + 0.3, 0, 1)
    base = np.array([248, 170, 220], np.float32)
    lilac = np.array([200, 150, 215], np.float32)
    c = base * (1 - lil[..., None] * 0.7) + lilac * (lil[..., None] * 0.7)
    c = c * (1 - rim[..., None] * 0.5) + 255 * rim[..., None] * 0.5
    # highlight: a white arc on the upper left
    hl = np.clip(1 - np.abs(np.sqrt((xx + 0.05) ** 2 + (yy + 0.05) ** 2) - 0.8) / 0.06, 0, 1)
    hl *= ((xx < -0.15) & (yy < -0.15)).astype(np.float32)
    c = c * (1 - hl[..., None] * 0.8) + 255 * hl[..., None] * 0.8
    a = inside.astype(np.float32) * 255
    im = Image.fromarray(np.dstack([c, a]).clip(0, 255).astype(np.uint8), 'RGBA')
    return im.resize((2 * r, 2 * r), Image.LANCZOS)

def header(im, d):
    # mint slab with a blue edge behind the bubble, as on the logo
    d.polygon([(26, 92), (40, 30), (176, 4), (160, 70)], fill=P['EDGE'])
    d.polygon([(20, 88), (34, 26), (170, 0), (154, 66)], fill=MINT)
    b = bubble(42)
    im.paste(b, (36, 8), b)

def help_bar(d, w):
    d.rectangle([40 + 6, 648 + 6, w - 40 + 6, 699 + 6], fill=P['SHADOW'])
    d.rectangle([40, 648, w - 40, 699], fill=MINT)

def list_bg(w, list_x1, pic_x0):
    im = grid(w, 720)
    d = ImageDraw.Draw(im)
    dots(d, 14, 104, 150, 240, 12, 3, PINK)                 # pink dots behind the list
    dots(d, w - 130, 86, w - 6, 206, 12, 3, MINT)           # mint dots behind the picture
    header(im, d)
    panel(d, [26, 114, list_x1, 632], True)
    panel(d, [pic_x0, 114, w - 26, 443], False)
    help_bar(d, w)
    return im

def detail_bg(w, pic_x1, text_x0):
    im = grid(w, 720)
    d = ImageDraw.Draw(im)
    dots(d, 14, 104, 150, 240, 12, 3, PINK)
    dots(d, w - 130, 86, w - 6, 206, 12, 3, MINT)
    header(im, d)
    panel(d, [26, 114, pic_x1, 443], True)
    panel(d, [text_x0, 114, w - 26, 632], False)
    help_bar(d, w)
    return im

def sel(w, h):
    """Mint bar with a light blue offset shadow (the buttons of bubblism.jp)."""
    im = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([5 * SS, 6 * SS, w * SS - 1, (h - 3) * SS - 1], fill=LIGHT + (255,))
    d.rectangle([0, 3 * SS, (w - 6) * SS - 1, (h - 6) * SS - 1], fill=MINT + (255,))
    return im.resize((w, h), Image.LANCZOS)

def tag():
    """Pink slanted tag for the year and the position, shadow on the left."""
    w, h = 132, 60
    im = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    def poly(dx, dy, c):
        pts = [(12 + dx, 0 + dy), (132 + dx, 0 + dy), (132 + dx, 52 + dy), (26 + dx, 43 + dy)]
        d.polygon([(x * SS, y * SS) for x, y in pts], fill=c + (255,))
    poly(-6, 6, P['SHADOW'])
    poly(0, 0, PINK)
    return im.resize((w, h), Image.LANCZOS)

# ---------------------------------------------------------------------------
# cards of the main screen (media/systems/<key>.png): Memphis shapes and the name
from PIL import ImageFont
import math, random
BEBAS = os.path.join(THEMES, 'default', 'fonts', 'BebasNeue-Regular.ttf')

def card(key, label, bg, seed):
    w, h = 640, 480
    rnd = random.Random(seed)
    im = Image.new('RGB', (w * SS, h * SS), bg)
    d = ImageDraw.Draw(im)
    s = lambda v: int(v * SS)
    # dot block, slab, triangle, squiggle and dashes
    for y in range(s(40), s(200), s(22)):
        for x in range(s(420), s(610), s(22)):
            d.ellipse([x - s(4), y - s(4), x + s(4), y + s(4)], fill=P['CARD_DOTS'])
    x0, y0 = rnd.randint(30, 90), rnd.randint(250, 300)
    d.polygon([(s(x0 + 8), s(y0 + 8)), (s(x0 + 228), s(y0 - 52)), (s(x0 + 268), s(y0 + 88)), (s(x0 + 48), s(y0 + 148))], fill=LIGHT)
    d.polygon([(s(x0), s(y0)), (s(x0 + 220), s(y0 - 60)), (s(x0 + 260), s(y0 + 80)), (s(x0 + 40), s(y0 + 140))], fill=MINT if bg != MINT else PINK)
    tx, ty = rnd.randint(470, 540), rnd.randint(300, 360)
    d.polygon([(s(tx + 6), s(ty + 6)), (s(tx + 96), s(ty + 26)), (s(tx + 36), s(ty + 106))], fill=NAVY)
    d.polygon([(s(tx), s(ty)), (s(tx + 90), s(ty + 20)), (s(tx + 30), s(ty + 100))], fill=YELLOW)
    pts = [(s(60 + i * 4), s(70 + 22 * math.sin(i / 7.0))) for i in range(70)]
    d.line(pts, fill=BLUE, width=s(9), joint='curve')
    for _ in range(9):
        cx, cy, a = rnd.randint(20, 620), rnd.randint(20, 460), rnd.random() * math.pi
        dx, dy = 16 * math.cos(a), 16 * math.sin(a)
        d.line([(s(cx - dx), s(cy - dy)), (s(cx + dx), s(cy + dy))], fill=rnd.choice([BLUE, PINK, NAVY, YELLOW]), width=s(6))
    im = im.resize((w, h), Image.LANCZOS)
    b = bubble(70)
    im.paste(b, (rnd.randint(380, 470), rnd.randint(170, 230)), b)
    # the name, mint with a blue offset shadow as the titles
    f = ImageFont.truetype(BEBAS, 150 if len(label) < 9 else 120)
    d = ImageDraw.Draw(im)
    d.text((w // 2 + 7, h // 2 + 7), label, font=f, fill=BLUE, anchor='mm')
    d.text((w // 2, h // 2), label, font=f, fill=(255, 255, 255) if bg == MINT else MINT, anchor='mm')
    if key == 'favorites':
        g = ImageFont.truetype(os.path.join(os.path.dirname(BEBAS), 'DejaVuSans-Bold.ttf'), 110)
        d.text((560 + 5, 400 + 5), '★', font=g, fill=BLUE, anchor='mm')
        d.text((560, 400), '★', font=g, fill=PINK, anchor='mm')
    if key == 'recent':
        # a clock, as the star of the favorites
        for o, c in ((5, BLUE), (0, PINK)):
            cx, cy = 560 + o, 400 + o
            d.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], fill=c)
            if o:
                continue
            d.ellipse([cx - 34, cy - 34, cx + 34, cy + 34], fill=(255, 255, 255))
            d.line([(cx, cy), (cx, cy - 24)], fill=NAVY, width=8)
            d.line([(cx, cy), (cx + 18, cy + 8)], fill=NAVY, width=8)
            d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=NAVY)
    return im

CARDS = [('favorites', 'Favorites'), ('arcade', 'Arcade'), ('computer', 'Computer'), ('console', 'Console'),
         ('handheld', 'Handheld'), ('other', 'Other'), ('mister', 'MiSTer'), ('recent', 'Recent')]

# ---------------------------------------------------------------------------
# loading screen (loading.ini): an album sleeve (the box of the game) with a
# spinning record coming out of it, "NOW LOADING" with bouncing bubbles, the bar.
# LOAD[file] = sleeve box, record centre and radius, part of the record shown
# (right of the sleeve, the anim element), bar box: base units of the ini.
LOAD = {
    'loading.png':    dict(w=1280, sleeve=(96, 150, 456, 510), rec=(500, 330, 170), crop=(456, 160, 670, 500),
                           bar=(700, 450, 1220, 490)),
    'loading_43.png': dict(w=960, sleeve=(60, 150, 380, 470), rec=(420, 310, 150), crop=(380, 160, 570, 460),
                           bar=(600, 462, 920, 498)),
}
RECORD_FRAMES, BUBBLE_FRAMES = 24, 12

def loading_bg(L):
    w = L['w']
    im = grid(w, 720)
    d = ImageDraw.Draw(im)
    dots(d, 14, 104, 150, 240, 12, 3, PINK)
    dots(d, w - 130, 560, w - 6, 640, 12, 3, MINT)
    header(im, d)
    panel(d, list(L['sleeve']), True)                   # the sleeve, the box of the game on it
    x0, y0, x1, y1 = L['bar']
    d.rectangle([x0 + 6, y0 + 6, x1 + 6, y1 + 6], fill=P['SHADOW'])
    d.rectangle([x0, y0, x1, y1], fill=P['PAPER'])    # the empty bar (type=bar draws the mint part)
    help_bar(d, w)
    return im

def record(r, angle):
    """Vinyl record of radius r (RGBA 2r x 2r) turned by angle degrees: black
    grooves, pink label with a mint segment and the name, a fixed sheen."""
    n = 2 * r * SS
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / (n - 1) * 2 - 1
    dist = np.sqrt(xx * xx + yy * yy)
    grooves = 22 + 10 * (np.sin(dist * 260) > 0.6) + 6 * (np.sin(dist * 37) > 0.9)
    c = np.dstack([grooves] * 3).astype(np.float32)
    # sheen: two light wedges which don't turn (the light of the room)
    ang = np.arctan2(yy, xx)
    sheen = (np.clip(np.cos(2 * (ang + 0.8)), 0, 1) ** 6) * np.clip((dist - 0.38) / 0.1, 0, 1)
    c += sheen[..., None] * 70
    a = (dist <= 1).astype(np.float32) * 255
    im = Image.fromarray(np.dstack([c, a]).clip(0, 255).astype(np.uint8), 'RGBA')
    # label (turns): pink, mint segment, yellow dot, the name
    lr = int(0.36 * r * SS)
    lab = Image.new('RGBA', (2 * lr, 2 * lr), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lab)
    ld.ellipse([0, 0, 2 * lr - 1, 2 * lr - 1], fill=PINK + (255,))
    ld.pieslice([0, 0, 2 * lr - 1, 2 * lr - 1], 200, 290, fill=MINT + (255,))
    ld.ellipse([lr + lr // 3, lr // 3, lr + lr // 3 + lr // 4, lr // 3 + lr // 4], fill=YELLOW + (255,))
    f = ImageFont.truetype(BEBAS, int(lr * 0.42))
    ld.text((lr, lr + lr * 0.45), 'FRONTIER', font=f, fill=NAVY + (255,), anchor='mm')
    ld.ellipse([lr - lr // 9, lr - lr // 9, lr + lr // 9, lr + lr // 9], fill=(20, 20, 20, 255))  # the hole
    lab = lab.rotate(-angle, resample=Image.BICUBIC)
    im.paste(lab, (n // 2 - lr, n // 2 - lr), lab)
    return im.resize((2 * r, 2 * r), Image.LANCZOS)

def record_frame(L, i, scale=2):
    """Frame i of the record: the part right of the sleeve (crop), with the
    shadow of the sleeve on it; scale = pixels per base unit (sharp at 1080p)."""
    cx, cy, r = L['rec']
    x0, y0, x1, y1 = L['crop']
    rec = record(r * scale, i * 360 / RECORD_FRAMES)
    im = Image.new('RGBA', ((x1 - x0) * scale, (y1 - y0) * scale), (0, 0, 0, 0))
    im.paste(rec, ((cx - r - x0) * scale, (cy - r - y0) * scale), rec)
    px = np.array(im).astype(np.float32)
    sh = 6 * scale                                      # offset shadow of the sleeve
    sy0, sy1 = (L['sleeve'][1] + 6 - y0) * scale, (L['sleeve'][3] + 6 - y0) * scale
    strip = px[max(0, sy0):max(0, sy1), :sh]
    strip[..., :3] = strip[..., :3] * 0.3 + np.array(P['SHADOW'], np.float32) * 0.7
    return Image.fromarray(px.clip(0, 255).astype(np.uint8), 'RGBA')

def bubbles_frame(i, scale=2):
    """Three pink bubbles jumping one after the other (140 x 56 base units)."""
    w, h, r = 140, 56, 14
    im = Image.new('RGBA', (w * scale, h * scale), (0, 0, 0, 0))
    b = bubble(r * scale)
    for k in range(3):
        ph = (i / BUBBLE_FRAMES - k / 6.0) % 1.0
        jump = math.sin(ph * 2 * math.pi) if ph < 0.5 else 0.0
        x = (14 + k * 42) * scale
        y = int((h - 2 * r - 2 - jump * 24) * scale)
        im.paste(b, (x, y), b)
    return im

# ---------------------------------------------------------------------------
# ini files of the variants: those of citypop with other colours. recolor(section,
# key, value) returns the new value; the elements on the background (title, name,
# data under the picture) and those on the panels can have different colours.
ON_BG = {'title', 'position', 'name', 'maker', 'genre', 'players', 'stars', 'loading', 'game', 'system', 'percent'}

def dark(sec, key, val):
    if key == 'background_color': return '#212121'
    if sec == 'year' or key in ('sel_color', 'sel_image'): return val       # on the pink tag, on the mint bar
    if sec in ('help',): return val
    m = {'#212121': '#DCDCDC', '#585858': '#A8A8A8', '#747474': '#8F8F8F', '#E2CACA': '#3A3A3A',
         '#EAD9D9': '#3A3A3A', '#3C6BB1': '#7AA1DB'}
    if key == 'shadow' and val == '#7AA1DB': return '#3C6BB1'
    if key == 'shadow' or key.startswith('scrollbar_knob'): return val
    return m.get(val, val)

def blue(sec, key, val):
    if key == 'background_color': return '#3C6BB1'
    if key == 'scrollbar_color' or (key == 'color' and val == '#E2CACA'): return '#D8DAE1'
    if sec not in ON_BG: return val
    if key == 'shadow': return '#002967'
    m = {'#3C6BB1': '#F5F7FF', '#585858': '#DCE6F7', '#747474': '#B4C8EA', '#EC76B2': '#FFA3D9'}
    return m.get(val, val)

VARIANTS = {'citypop_dark': ('City Pop Dark', 'dark background (the dark mode of bubblism.jp)', dark),
            'citypop_blue': ('City Pop Blue', 'background of the blue of the titles', blue)}

def variant_ini(src, name, what, recolor):
    out, sec = [], ''
    for line in open(src, encoding='utf-8').read().split('\n'):
        t = line.strip()
        if t.startswith('[') and t.endswith(']'):
            sec = t[1:-1]
        elif '=' in t and not t.startswith(';'):
            k, v = t.split('=', 1)
            if k == 'name': v = name
            elif v.startswith('#'): v = recolor(sec, k, v)
            line = k + '=' + v
        elif t.startswith('; Theme "City Pop"'):
            line = line.replace('"City Pop"', '"%s"' % name)
        elif t.startswith('; Pale pink with a dashed grid'):
            line = '; Variant of citypop: %s.\n; Its ini files are made from those of citypop by citypop_assets.py.' % what
        out.append(line)
    return '\n'.join(out)

for theme, pal in PALETTES.items():
    P = pal
    ROOT = os.path.join(THEMES, theme, 'img')
    save(list_bg(1280, 616, 652), 'bg.png')
    save(list_bg(960, 466, 494), 'bg_43.png')
    save(detail_bg(1280, 616, 652), 'detail.png')
    save(detail_bg(960, 466, 494), 'detail_43.png')
    save(sel(574, 51), 'sel.png')
    save(sel(424, 51), 'sel_43.png')
    save(tag(), 'tag.png')
    for f, L in LOAD.items():
        save(loading_bg(L), f)
    ROOT = os.path.join(THEMES, theme, 'anim')
    for i in range(RECORD_FRAMES):
        save(record_frame(LOAD['loading.png'], i), 'record_%02d.png' % i)
        save(record_frame(LOAD['loading_43.png'], i), 'record43_%02d.png' % i)
    for i in range(BUBBLE_FRAMES):
        save(bubbles_frame(i), 'bubbles_%02d.png' % i)
    ROOT = os.path.join(THEMES, theme, 'media', 'systems')
    for i, (key, label) in enumerate(CARDS):
        save(card(key, label, P['CARDS'][i], i), key + '.png')
    if theme in VARIANTS:
        name, what, recolor = VARIANTS[theme]
        for f in ('theme.ini', 'theme_43.ini', 'detail.ini', 'detail_43.ini', 'screensaver.ini', 'screensaver_43.ini',
                  'loading.ini', 'loading_43.ini'):
            with open(os.path.join(THEMES, theme, f), 'w', encoding='utf-8') as o:
                o.write(variant_ini(os.path.join(THEMES, 'citypop', f), name, what, recolor))
            print(os.path.normpath(os.path.join(THEMES, theme, f)))
