#!/usr/bin/env python3
# Blocks of keys of THEME_GUIDE.txt / GUIDA_TEMA_ita.txt, made from the ini files of
# themes/citypop (fonts in fonts/ instead of ../simple/fonts/). Run it again and
# paste the output into both guides when the ini files of citypop change.
# Usage: guide_blocks.py full theme.ini|detail.ini
#        guide_blocks.py diff43 theme.ini theme_43.ini   (keys to change after "Make 4:3")
#        guide_blocks.py diff43 detail.ini detail_43.ini
import math, os, sys

T = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'frontier', 'themes', 'citypop')

def parse(f):
    g, els, sec = {}, [], None
    for l in open(os.path.join(T, f), encoding='utf-8'):
        t = l.strip()
        if not t or t.startswith(';'):
            continue
        if t.startswith('['):
            sec = t[1:-1]
            if sec != 'theme':
                els.append((sec, {}))
            continue
        k, v = t.split('=', 1)
        v = v.replace('../simple/fonts/', 'fonts/')
        (g if sec == 'theme' else els[-1][1])[k] = v
    return g, els

def block(name, props):
    return '\n'.join([f'  [{name}]'] + [f'    {k}={v}' for k, v in props.items()])

def full(f):
    g, els = parse(f)
    print('\n\n'.join([block('theme', g)] + [block(n, p) for n, p in els]))

def make43(p):
    """What "Make 4:3" of the theme editor does: x and width * 0.75 (Math.round)."""
    p = dict(p)
    if 'rect' in p:
        x, y, w, h = [int(v) for v in p['rect'].split(',')]
        p['rect'] = f'{math.floor(x * 0.75 + 0.5)},{y},{math.floor(w * 0.75 + 0.5)},{h}'
    return p

def diff43(src, dst):
    g1, e1 = parse(src)
    g2, e2 = parse(dst)
    out = []
    gd = {k: v for k, v in g2.items() if g1.get(k) != v and k != 'base'}
    if gd:
        out.append(block('theme', gd))
    m1 = dict(e1)
    for n, p in e2:
        a = make43(m1.get(n, {}))
        d = {k: v for k, v in p.items() if a.get(k) != v}
        gone = [k for k in a if k not in p]
        if d or gone:
            out.append(block(n, d) + ''.join(f'\n    {k}=   (empty)' for k in gone))
    names = [n for n, _ in e2]
    out += [f'  [{n}]  delete' for n in m1 if n not in names]
    print('\n'.join(out))

{'full': full, 'diff43': diff43}[sys.argv[1]](*sys.argv[2:])
