#!/usr/bin/env python3
"""Scraper for Frontier, the MiSTer frontend: writes gamelists/<system>/gamelist.xml and
media/<system>/<type>/<game>.<ext> in Frontier's folder.

Runs on the MiSTer (python 3.9, standard library only) and on a PC (with Pillow
the pictures are also resized). Sources, in order (each data from the first one which has it):
  ss        ScreenScraper (screenscraper.fr): all systems, credentials needed; first, so
            arcade and consoles have the same genres, descriptions and videos
  adb       ArcadeDB (adb.arcadeitalia.net): arcade (and Neo Geo) by setname, data, pictures
            and videos, for what ScreenScraper hasn't (or first without its credentials)
  libretro  libretro-thumbnails: pictures only (box, snap, title), by exact No-Intro/MAME name
The data of the systems (description, maker, year, hardware) come from Wikipedia: the
article in wiki= of systems.ini, the description in the language of --lang.

Examples (on the MiSTer):
  python3 /media/fat/frontier/scraper/fe_scrape.py --arcade   # all the .mra files of _Arcade
  python3 fe_scrape.py --system NES --system SNES  # folders of games/
  python3 fe_scrape.py --all-systems --limit 20    # quick test
  python3 fe_scrape.py --groups --system MegaDrive  # different titles of the same game (MAME lists)
  python3 fe_scrape.py --category Console --video  # all the consoles, one game per title
  python3 fe_scrape.py --index                     # only the data of Frontier's "Lists" (no network)
  python3 fe_scrape.py --systems-info --all-systems --lang it  # only the data of the systems (Wikipedia)
On a PC with the SD card mounted or shared:  --root /path/of/the/sd

The ScreenScraper credentials go in <frontier>/scraper.ini or scraper/scraper.ini
or on the command line. Without credentials the ss source is skipped.
"""

import argparse
import base64
import configparser
import datetime
import hashlib
import html
import html.parser
import json
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib

try:
    from PIL import Image
except ImportError:
    Image = None

UA = 'MiSTerFrontier-scraper/1.0'
# Wikimedia limits the requests of programs which don't say what they are and where they come from
WIKI_UA = UA + ' (MiSTer FPGA frontend; https://github.com/ElFDA/FrontierMr)'
MEDIA_TYPES = ('box', 'snap', 'title', 'marquee', 'fanart', 'video')
OPTIONAL_TYPES = ('fanart', 'video')  # downloaded only with --fanart / --video
GAMELIST_MEDIA = {'snap': 'image', 'box': 'thumbnail', 'marquee': 'marquee', 'video': 'video', 'fanart': 'fanart', 'title': 'titleshot'}
FIELDS = ('name', 'desc', 'releasedate', 'developer', 'publisher', 'genre', 'players', 'rating')

# folder of games/ (lowercase) -> (ScreenScraper id, libretro-thumbnails name)
# ids from Skyscraper platforms_idmap.csv, names from the libretro-thumbnails repositories
SYSTEMS = {
    'nes': (3, 'Nintendo - Nintendo Entertainment System'),
    'fds': (106, 'Nintendo - Family Computer Disk System'),
    'snes': (4, 'Nintendo - Super Nintendo Entertainment System'),
    'gameboy': (9, 'Nintendo - Game Boy'),
    'gbc': (10, 'Nintendo - Game Boy Color'),
    'gba': (12, 'Nintendo - Game Boy Advance'),
    'n64': (14, 'Nintendo - Nintendo 64'),
    'virtualboy': (11, 'Nintendo - Virtual Boy'),
    'pokemonmini': (211, 'Nintendo - Pokemon Mini'),
    'megadrive': (1, 'Sega - Mega Drive - Genesis'),
    'genesis': (1, 'Sega - Mega Drive - Genesis'),
    'sms': (2, 'Sega - Master System - Mark III'),
    'gamegear': (21, 'Sega - Game Gear'),
    'sg1000': (109, 'Sega - SG-1000'),
    'megacd': (20, 'Sega - Mega-CD - Sega CD'),
    's32x': (19, 'Sega - 32X'),
    'saturn': (22, 'Sega - Saturn'),
    'tgfx16': (31, 'NEC - PC Engine - TurboGrafx 16'),
    'tgfx16-cd': (114, 'NEC - PC Engine CD - TurboGrafx-CD'),
    'pcfx': (72, 'NEC - PC-FX'),
    'psx': (57, 'Sony - PlayStation'),
    'atari2600': (26, 'Atari - 2600'),
    'atari5200': (40, 'Atari - 5200'),
    'atari7800': (41, 'Atari - 7800'),
    'atari800': (43, None),
    'atarilynx': (28, 'Atari - Lynx'),
    'jaguar': (27, 'Atari - Jaguar'),
    'atarist': (42, 'Atari - ST'),
    'neogeo': (142, 'SNK - Neo Geo'),
    'neogeo-cd': (70, 'SNK - Neo Geo CD'),
    'ngp': (25, 'SNK - Neo Geo Pocket'),
    'ngpc': (82, 'SNK - Neo Geo Pocket Color'),
    'wonderswan': (45, 'Bandai - WonderSwan'),
    'wonderswancolor': (46, 'Bandai - WonderSwan Color'),
    'coleco': (48, 'Coleco - ColecoVision'),
    'intellivision': (115, 'Mattel - Intellivision'),
    'vectrex': (102, 'GCE - Vectrex'),
    'odyssey2': (104, 'Magnavox - Odyssey2'),
    'channelf': (80, 'Fairchild - Channel F'),
    'arcadia': (94, 'Emerson - Arcadia 2001'),
    'astrocade': (44, 'Bally - Astrocade'),
    'c64': (66, 'Commodore - 64'),
    'amiga': (64, 'Commodore - Amiga'),
    'vic20': (73, 'Commodore - VIC-20'),
    'msx': (113, 'Microsoft - MSX'),
    'msx1': (113, 'Microsoft - MSX'),
    'spectrum': (76, 'Sinclair - ZX Spectrum'),
    'zxspectrum': (76, 'Sinclair - ZX Spectrum'),
    'amstrad': (65, 'Amstrad - CPC'),
    'x68000': (79, 'Sharp - X68000'),
    '3do': (29, 'The 3DO Company - 3DO'),
    'apple-ii': (86, None),
}
# extensions which in a shared folder belong to another system
EXT_SYSTEM = {'fds': 'fds', 'gbc': 'gbc', 'gg': 'gamegear', 'sg': 'sg1000', 'a26': 'atari2600'}
ARCADE = (75, 'MAME')
# folder of games/ (lowercase) -> MAME software lists (hash/<list>.xml) for --groups
SOFTLISTS = {
    'nes': ['nes'], 'fds': ['famicom_flop'], 'snes': ['snes'], 'gameboy': ['gameboy'], 'gbc': ['gbcolor'],
    'gba': ['gba'], 'n64': ['n64'], 'virtualboy': ['vboy'], 'pokemonmini': ['pokemini'],
    'megadrive': ['megadriv'], 'genesis': ['megadriv'], 'sms': ['sms'], 'gamegear': ['gamegear'],
    'sg1000': ['sg1000'], 's32x': ['32x'], 'tgfx16': ['pce', 'tg16', 'sgx'], 'atari2600': ['a2600'],
    'atari5200': ['a5200'], 'atari7800': ['a7800'], 'atarilynx': ['lynx'], 'jaguar': ['jaguar'],
    'ngp': ['ngp'], 'ngpc': ['ngpc'], 'wonderswan': ['wswan'], 'wonderswancolor': ['wscolor'],
    'coleco': ['coleco'], 'intellivision': ['intv'], 'vectrex': ['vectrex'], 'odyssey2': ['videopac'],
    'channelf': ['channelf'],
}
MAME_HASH = 'https://raw.githubusercontent.com/mamedev/mame/master/hash/%s.xml'
# No-Intro regions: the first tag after the title (as fe_group.cpp)
REGIONS = {
    'world', 'usa', 'europe', 'japan', 'asia', 'australia', 'brazil', 'canada', 'china', 'france',
    'germany', 'hong kong', 'italy', 'korea', 'netherlands', 'spain', 'sweden', 'taiwan', 'uk',
    'russia', 'scandinavia', 'greece', 'finland', 'norway', 'denmark', 'portugal', 'poland',
    'belgium', 'austria', 'switzerland', 'latin america', 'mexico', 'argentina', 'india',
    'south africa', 'new zealand', 'ireland', 'israel', 'croatia', 'turkey', 'czech', 'hungary',
    'slovakia', 'uae', 'chile', 'colombia', 'peru', 'thailand', 'indonesia', 'singapore',
    'malaysia', 'philippines', 'vietnam', 'unknown',
}


def log(*a):
    print(*a, flush=True)


class Status:
    """--status FILE: progress for Frontier ("Frontier Settings" > "Scraper"), key=value
    lines written again at most once a second (always with force)"""

    def __init__(self, path):
        self.path = path
        self.data = {'state': 'running', 'pid': str(os.getpid())}
        self.last = 0

    def set(self, force=False, **kw):
        self.data.update({k: str(v) for k, v in kw.items()})
        if not self.path or (not force and time.time() - self.last < 1):
            return
        self.last = time.time()
        try:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(''.join('%s=%s\n' % (k, v) for k, v in self.data.items()))
            os.replace(tmp, self.path)
        except OSError:
            pass


STATUS = Status(None)


#############################################################################
# network

class Http:
    def __init__(self, delay):
        self.delay = delay
        self.last = 0
        # set when an answer is not a real one (network, server, quota): the game is not
        # remembered as "not found" (see NotFound); the caller clears it
        self.trouble = False

    def get(self, url, tries=3, ua=UA):
        """bytes, None if not found; self.status = HTTP code (None on network errors)"""
        self.status = None
        for t in range(tries):
            wait = self.last + self.delay - time.time()
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            try:
                req = urllib.request.Request(url, headers={'User-Agent': ua})
                with urllib.request.urlopen(req, timeout=60) as r:
                    self.status = r.status
                    return r.read()
            except urllib.error.HTTPError as e:
                self.status = e.code
                if e.code in (400, 401, 403, 404, 410):
                    if e.code != 404:
                        self.trouble = True
                    return None
                if e.code == 429 or e.code >= 500:
                    time.sleep(2 + 3 * t)
                    continue
                self.trouble = True
                return None
            except Exception as e:
                log('   network:', e)
                time.sleep(2 + 3 * t)
        self.trouble = True
        return None


def write_file(path, data):
    """the whole file with one write() through a .tmp: the SD of the MiSTer is mounted with
    "sync", every write() waits for the card (a gamelist written in 8 KB pieces took a minute)"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    tmp = path + '.tmp'
    with open(tmp, 'wb', buffering=0) as f:
        view = memoryview(data)
        while view:
            view = view[f.write(view):]
    os.replace(tmp, path)


def cache_json(cache, name, fetch, fresh=False):
    """API answers saved on disk, so the requests are not repeated; fresh: a "not found"
    saved ({}) is asked again, fresh='all': any answer is asked again (the saved one
    stays if there is no new answer)"""
    path = os.path.join(cache, re.sub(r'[^\w.()+-]', '_', name)[:150] + '.json')
    old = None
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                old = json.load(f)
            if (old and fresh != 'all') or not fresh:
                return old
        except Exception:
            pass
    data = fetch()
    if data is None:
        return old
    os.makedirs(cache, exist_ok=True)
    write_file(path, json.dumps(data))
    return data


#############################################################################
# list of the games

class Game:
    def __init__(self, system, key, path, title=None):
        self.system = system  # folder in gamelists/ and media/
        self.key = key        # file name without extension
        self.path = path      # <path> in the gamelist
        self.title = title or key
        self.setname = None
        self.ext = ''
        self.crc = None
        self.size = None
        self.ids = None       # (ScreenScraper id, libretro name)
        self.getcrc = None
        self.alt = False      # .mra of _Arcade/_alternatives
        self.main = None      # key of the main .mra of an alternative or of another version (list_arcade)
        self.parent = ''      # <parent> of an .mra
        self.keys = []


MRA_TAGS = ('rbf', 'manufacturer', 'year', 'players', 'category', 'parent')
MRA_CACHE = 'MRA1'  # format of .scrape_cache/mra_info.tsv


def mra_read(path):
    """what the scraper uses of an .mra, read once (regular expressions: much faster than
    the XML parser): setname, name, the tags of MRA_TAGS and keys = setname, parent and the
    names of the zip files, lowercase (as fe_alt.cpp)"""
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            text = f.read(65536)
    except Exception:
        return {}
    out = {}
    m = re.search(r'<setname[^>]*>\s*([^<]+?)\s*</setname>', text)
    setname = m.group(1) if m else None
    zips = []
    for m in re.finditer(r'\bzip="([^"]*)"', text):
        for z in m.group(1).split('|'):
            z = z.strip().rsplit('/', 1)[-1]
            if z.lower().endswith('.zip') and len(z) > 4:
                zips.append(z[:-4])
    if not setname:
        m = re.search(r'<rom[^>]*\bzip="([^"|]+)', text)
        if m:
            setname = m.group(1).strip()
            if setname.lower().endswith('.zip'):
                setname = setname[:-4]
    if setname:
        out['setname'] = setname
    m = re.search(r'<name>\s*([^<]+?)\s*</name>', text)
    if m:
        out['name'] = m.group(1).replace('&amp;', '&').replace('&apos;', "'").replace('&quot;', '"')
    for tag in MRA_TAGS:
        m = re.search(r'<%s[^>]*>\s*([^<]*?)\s*</%s>' % (tag, tag), text)
        if m and m.group(1):
            out[tag] = html.unescape(m.group(1))
    out['keys'] = list(dict.fromkeys(k.lower() for k in [setname or '', out.get('parent', '')] + zips if k))
    return out


class MraCache:
    """mra_read() of the .mra files in .scrape_cache/mra_info.tsv: an .mra is read again
    only when new or changed (mtime, size); thousands of files on the SD take long"""

    def __init__(self, cache):
        self.path = os.path.join(cache, 'mra_info.tsv')
        self.items = {}   # path relative to the root -> (mtime, size, info)
        self.seen = set()
        self.changed = False
        self.read = 0
        try:
            with open(self.path, encoding='utf-8') as f:
                if f.readline().rstrip('\n') == MRA_CACHE:
                    for line in f:
                        rel, mtime, size, info = line.rstrip('\n').split('\t', 3)
                        self.items[rel] = (int(mtime), int(size), json.loads(info))
        except (OSError, ValueError):
            self.items = {}

    def get(self, root, rel, st=None):
        full = os.path.join(root, rel)
        try:
            st = st or os.stat(full)
        except OSError:
            return {}
        self.seen.add(rel)
        old = self.items.get(rel)
        if old and old[0] == int(st.st_mtime) and old[1] == st.st_size:
            return old[2]
        info = mra_read(full)
        self.items[rel] = (int(st.st_mtime), st.st_size, info)
        self.changed = True
        self.read += 1
        return info

    def save(self, prune=False):
        """prune: also forget the files not asked in this run (after reading all of _Arcade)"""
        if prune and set(self.items) - self.seen:
            self.items = {k: v for k, v in self.items.items() if k in self.seen}
            self.changed = True
        if not self.changed:
            return
        text = MRA_CACHE + '\n' + ''.join('%s\t%d\t%d\t%s\n' % (k, v[0], v[1], json.dumps(v[2], ensure_ascii=False))
                                          for k, v in sorted(self.items.items()))
        try:
            write_file(self.path, text)
            self.changed = False
        except OSError as ex:
            log('   cache of the .mra files not written:', ex)


MRA = {}  # root -> MraCache, see mra_cache()


def mra_cache(root, cache):
    if root not in MRA:
        MRA[root] = MraCache(cache)
    return MRA[root]


ALT_DIR = '_alternatives'


def list_arcade(root, cache):
    """the .mra files of _Arcade; those of _alternatives have alt = True and main = the key of
    the .mra outside _alternatives of the same game, when there is one (main_of())"""
    games = {}
    base = os.path.join(root, '_Arcade')
    mc = mra_cache(root, cache)
    for d, dirs, files in os.walk(base):
        dirs[:] = [x for x in dirs if x.lower() not in ('cores', '_organized', 'mame', 'hbmame') and not x.startswith('.')]
        rel = os.path.relpath(d, root)
        alt = rel.replace('\\', '/').split('/')[1:2] == [ALT_DIR]
        for f in sorted(files):
            if not f.lower().endswith('.mra'):
                continue
            key = f[:-4]
            if key in games and (alt or not games[key].alt):
                continue  # the first one, but an .mra outside _alternatives wins
            info = mc.get(root, os.path.join(rel, f))
            g = Game('arcade', key, './' + f)
            g.setname = info.get('setname')
            g.title = info.get('name') or key
            g.ext = 'mra'
            g.ids = ARCADE
            g.alt = alt
            g.keys = info.get('keys', [])
            g.parent = (info.get('parent') or '').lower()
            g.altdir = os.path.basename(d).lstrip('_').lower() if alt else ''
            games[key] = g
    mc.save(prune=True)
    out = list(games.values())
    main_of(out)
    group_versions(out)
    return out


def title_words(title):
    """the words of a title without the parts in () and []: "Heavy Unit (World)" -> heavy unit"""
    return re.findall(r"[a-z0-9']+", re.sub(r'\([^)]*\)|\[[^\]]*\]', ' ', title.lower()))


def same_title(a, b):
    """one title starts or ends with the other ("Jackal" / "Tokushu Butai Jackal"): clones of a
    romset can be other games (Space Invaders / Balloon Bomber, Pac-Man / Ms. Pac-Man)"""
    a, b = title_words(a), title_words(b)
    if not a or not b:
        return False
    if len(a) > len(b):
        a, b = b, a
    return b[:len(a)] == a or b[-len(a):] == a


def group_versions(games):
    """the .mra outside _alternatives of the same game (the regions and revisions of a core:
    Heavy Unit World / Japan / US in _Decoryah/_HeavyUnit) are one game for the scraper: the
    main one (the setname the others use, then the shortest title) is scraped, the others take
    from it as the alternatives do (g.main). Same romset as fe_newest.cpp: the setname of one is the
    setname, parent or zip of the other, or they have the same parent; the others must have a
    title like the main one (same_title)"""
    mains = [g for g in games if not g.alt and not g.main and 'bios' not in g.title.lower()]
    by_set = {}
    uses = {}  # zip names which are not the setname or the parent: used by how many .mra
    for g in mains:
        if g.setname:
            by_set.setdefault(g.setname.lower(), []).append(g)
        for k in g.keys:
            if k != (g.setname or '').lower() and k != g.parent:
                uses[k] = uses.get(k, 0) + 1
    root = {g.key: g.key for g in mains}

    def find(k):
        while root[k] != k:
            root[k] = root[root[k]]
            k = root[k]
        return k

    def join(a, b):
        root[find(a.key)] = find(b.key)

    by_parent = {}
    for g in mains:
        # its parent is the setname of another; a zip of the other game counts unless many
        # .mra use it (the BIOS: pgm, playch10, neogeo)
        for k in g.keys:
            if k != g.parent and uses.get(k, 0) > 3:
                continue
            for h in by_set.get(k, []):
                join(g, h)
        if g.parent:
            if g.parent in by_parent:
                join(g, by_parent[g.parent])
            else:
                by_parent[g.parent] = g
    groups = {}
    for g in mains:
        groups.setdefault(find(g.key), []).append(g)
    moved = {}
    for members in groups.values():
        if len(members) < 2:
            continue

        def score(g):
            s = (g.setname or '').lower()
            return (-sum(1 for h in members if h is not g and s and s in h.keys), len(g.title), g.key.lower())
        best = min(members, key=score)
        for g in members:
            if g is not best and same_title(g.key, best.key):
                g.main = best.key
                moved[g.key] = best.key
    for g in games:  # an alternative of a game which now takes from another
        if g.main in moved:
            g.main = moved[g.main]


def main_of(games):
    """g.main of the alternatives: the .mra outside _alternatives with (in order) the same
    setname, the setname among its parent/zip names, its setname among the parent/zip names of
    the alternative, a parent/zip name in common; zip names of more than 3 .mra (BIOS: neogeo,
    qsound...) do not count. More of them: the name closest to the alternative's folder"""
    mains = [g for g in games if not g.alt]
    by_set, by_other = {}, {}
    for g in mains:
        s = (g.setname or '').lower()
        if s:
            by_set.setdefault(s, []).append(g)
        for k in g.keys:
            if k != s:
                by_other.setdefault(k, []).append(g)
    common = {k for k, v in by_other.items() if len(v) > 3}

    def closest(alt, cands):
        def score(g):
            a, b = alt.altdir or alt.title.lower(), g.title.lower()
            n = 0
            while n < min(len(a), len(b)) and a[n] == b[n]:
                n += 1
            return (-n, g.key.lower())
        return min(cands, key=score).key

    for g in games:
        g.main = None
        if not g.alt:
            continue
        s = (g.setname or '').lower()
        others = [k for k in g.keys if k != s]
        steps = [by_set.get(s) if s else None,
                 by_other.get(s) if s and s not in common else None,
                 [m for k in others for m in by_set.get(k, [])],
                 [m for k in others if k not in common for m in by_other.get(k, [])]]
        for cands in steps:
            if cands:
                g.main = closest(g, cands)
                break


# Italian names accepted too (Portatili, Altro)
CATEGORY_NAMES = {'console': 'console', 'handheld': 'handheld', 'portatili': 'handheld', 'computer': 'computer',
                  'other': 'other', 'altro': 'other'}


# folders (lowercase) of the systems with romsets=1 in systems.ini (Neo Geo), from read_systems_ini()
ROMSET_DIRS = set()
# folder (lowercase) -> English Wikipedia article (wiki= in systems.ini) and name of the system
SYSTEM_WIKI = {}
SYSTEM_NAMES = {}


def read_systems_ini(path, categories=None):
    """folder (lowercase) -> extensions, from systems.ini; categories: folder -> {categories}"""
    exts = {}
    cp = configparser.ConfigParser(interpolation=None, strict=False, comment_prefixes=(';',))
    cp.optionxform = str
    try:
        cp.read(path, encoding='utf-8')
    except Exception as e:
        log('systems.ini:', e)
        return exts
    for s in cp.sections():
        sec = cp[s]
        e = set()
        for k, v in sec.items():
            if k.startswith('slot'):
                parts = v.split(',', 3)
                if len(parts) == 4:
                    e.update(x.lower().lstrip('.') for x in parts[3].split())
        for folder in sec.get('folders', '').split('|'):
            if folder:
                exts.setdefault(folder.lower(), set()).update(e)
                if sec.get('romsets', '0').strip() == '1':
                    ROMSET_DIRS.add(folder.lower())
                # a folder of more systems (NES, FDS, NESMusic): the one of the same name,
                # otherwise the first one with an article
                if sec.get('wiki', '').strip() and (folder.lower() not in SYSTEM_WIKI or folder.lower() == s.lower()):
                    SYSTEM_WIKI[folder.lower()] = sec['wiki'].strip()
                    SYSTEM_NAMES[folder.lower()] = sec.get('name', s)
                if categories is not None:
                    categories.setdefault(folder.lower(), set()).add(sec.get('category', 'Other').lower())
    return exts


def ext_ok(ext, patterns):
    return any(len(p) == len(ext) and all(a == '?' or a == b for a, b in zip(p, ext)) for p in patterns)


def list_system(root, folder, patterns, crc):
    games = {}
    base = os.path.join(root, 'games', folder)
    sysname = folder.lower()

    def add(name, size, crcval, getcrc=None):
        key, ext = os.path.splitext(name)
        ext = ext[1:].lower()
        if ext == 'mgl' or not ext_ok(ext, patterns) or key in games:
            return
        g = Game(sysname, key, './' + name)
        g.ext = ext
        g.size = size
        g.crc = crcval
        g.getcrc = getcrc if crc else None  # computed only if needed (ScreenScraper)
        g.ids = SYSTEMS.get(EXT_SYSTEM.get(ext, sysname)) or SYSTEMS.get(sysname)
        games[key] = g

    for d, dirs, files in os.walk(base):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.'))
        for f in sorted(files):
            p = os.path.join(d, f)
            if f.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(p) as z:
                        for i in z.infolist():
                            if not i.is_dir():
                                add(os.path.basename(i.filename), i.file_size, '%08x' % i.CRC)
                except Exception as e:
                    log('   zip:', f, e)
            else:
                size = os.path.getsize(p)

                def getcrc(p=p, size=size):
                    if size > 64 * 1024 * 1024:
                        return None
                    c = 0
                    with open(p, 'rb') as fh:
                        for chunk in iter(lambda: fh.read(1 << 20), b''):
                            c = zlib.crc32(chunk, c)
                    return '%08x' % (c & 0xFFFFFFFF)
                add(f, size, None, getcrc)
    return list(games.values())


def rom_order(stem, regions):
    """sort key of the version to start (as better() in fe_group.cpp)"""
    name = stem[date_len(stem):]
    tags = [t.lower() for t in re.findall(r'\(([^)]*)\)', name)]
    rank = len(regions)
    if tags:
        for r in (x.strip() for x in tags[0].split(',')):
            if r in regions:
                rank = min(rank, regions.index(r))
    rest = tags[1:]
    pre = any(w in t for t in rest for w in ('beta', 'proto', 'sample', 'demo', 'kiosk', 'debug', 'program', 'test'))
    rerel = any(w in t for t in rest for w in ('virtual console', 'switch online', 'classic mini', 'mini', 'sega ages',
                                                 '3d classics', 'collection', 'evercade', 'retro-bit', 'limited run',
                                                 'arcade archives', 'steam', 'gog'))
    rev = 0
    for t in rest:
        m = re.match(r'rev (\w)', t)
        if m:
            rev = int(m.group(1)) if m.group(1).isdigit() else ord(m.group(1)) - ord('a') + 1
        m = re.match(r'v(\d+)(?:\.(\d+))?', t)
        if m:
            rev = int(m.group(1)) * 100 + int(m.group(2) or 0)
    alt = any(t.startswith('alt') for t in rest)
    return (pre, rank, rerel, -rev, alt, stem.lower())


def list_titles(root, folder, patterns, crc, regions):
    """as the list of Frontier (fe_group.cpp): only No-Intro names with a region (also
    inside zip files with the region in the name), one game per title (the preferred version);
    g.versions = [(key, path)] of all the versions"""
    base = os.path.join(root, 'games', folder)
    sysname = folder.lower()
    found = {}  # name without date (lowercase) -> (file, zip member or None, size, crc, rank)

    def add(name, path, member, size, crcval, rank):
        key = name[date_len(name):].lower()
        if key not in found or rank < found[key][4]:
            found[key] = (path, member, size, crcval, rank)

    for d, dirs, files in os.walk(base):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.') and x.lower() not in EXCLUDE_DIRS)
        depth = d.count(os.sep)
        for f in sorted(files):
            stem, ext = os.path.splitext(f)
            ext = ext[1:].lower()
            p = os.path.join(d, f)
            if not os.path.exists(p):
                continue  # broken link (the file was moved)
            if ext == 'zip' and not ext_ok(ext, patterns):
                # one game per zip or a whole collection (also with folders inside)
                try:
                    with zipfile.ZipFile(p) as z:
                        for i in z.infolist():
                            m = i.filename
                            if i.is_dir() or any(x.lower() in EXCLUDE_DIRS for x in m.split('/')[:-1]):
                                continue
                            b = m.rsplit('/', 1)[-1]
                            ms, me = os.path.splitext(b)
                            if ext_ok(me[1:].lower(), patterns) and title_region(ms):
                                add(b, p, m, i.file_size, '%08x' % i.CRC, (bool(date_len(b)), 1, depth + m.count('/')))
                except Exception as e:
                    log('   zip:', f, e)
                continue
            if ext == 'mgl' or not ext_ok(ext, patterns) or not title_region(stem):
                continue
            add(f, p, None, None, None, (bool(date_len(f)), 0, depth))
    drop_numbered(found)

    by_title = {}
    for v in found.values():
        name = os.path.basename(v[1] or v[0])
        by_title.setdefault(norm(title_region(os.path.splitext(name)[0])), []).append(v)

    games = []
    for t in sorted(by_title):
        vers = sorted(by_title[t], key=lambda v: rom_order(os.path.splitext(os.path.basename(v[1] or v[0]))[0], regions))
        path, member, size, crcval, _ = vers[0]
        name = os.path.basename(member or path)
        key, ext = os.path.splitext(name)
        g = Game(sysname, key, './' + name, title_region(key))
        g.ext = ext[1:].lower()
        if member:
            g.size, g.crc = size, crcval
        else:
            g.size = os.path.getsize(path)

            def getcrc(p=path, size=g.size):
                if size > 64 * 1024 * 1024:
                    return None
                c = 0
                with open(p, 'rb') as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b''):
                        c = zlib.crc32(chunk, c)
                return '%08x' % (c & 0xFFFFFFFF)
            g.getcrc = getcrc if crc else None
        g.ids = SYSTEMS.get(EXT_SYSTEM.get(g.ext, sysname)) or SYSTEMS.get(sysname)
        g.versions = []
        for v in vers:
            n = os.path.basename(v[1] or v[0])
            g.versions.append((os.path.splitext(n)[0], './' + n))
        games.append(g)
    return games


ROMSET_EXCLUDED = ('hack', 'translat', 'patch', 'trainer', 'cracked', 'pirate')
ROMSET_PRE = ('beta', 'proto', 'sample', 'demo', 'debug', 'test', 'bootleg')


def read_romsets(path):
    """romsets.xml of the Neo Geo: setname (lowercase) -> name; without the hidden ones (hide)"""
    names = {}
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            text = f.read()
    except OSError:
        return names
    for m in re.finditer(r'<romset\s([^>]*)>', text):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        if 'hide' in a:
            continue
        alt = html.unescape(a.get('altname', ''))
        for n in a.get('name', '').split(','):
            if n.strip():
                names[n.strip().lower()] = alt or n.strip()
    return names


def romset_key(name):
    """name for comparisons: lowercase letters and digits, "Super Spy, The" = "The Super Spy",
    "OverTop" = "Over Top", "Neo Drift Out: New Technology" = "Neo Drift Out - New Technology"
    """
    name = name.strip()
    m = re.match(r'^(.*), (the|a|an)$', name, re.I)
    if m:
        name = m.group(2) + ' ' + m.group(1)
    return re.sub(r'[^a-z0-9]', '', name.lower())


def romset_name(stem, ext, names, regions, by_name=None):
    """(title, setname, order) of a romset as parse_romset() of fe_group.cpp:
    'Title (tags) (setname).neo' or a zip file of romsets.xml; None if it isn't one.
    A .neo file without setname: the name of the file is the title, the setname that of
    romsets.xml with the same name (by_name: romset_key(name) -> setname), for ArcadeDB"""
    if ext == 'neo':
        m = re.match(r'^(.*) \(([a-z0-9_]+)\)$', stem)
        # without setname in the name: after the others, as in fe_group.cpp
        full, setname, zipped = (m.group(1), m.group(2), 0) if m else (stem, (by_name or {}).get(romset_key(stem)), 2)
    else:
        full = names.get(stem.lower())
        if not full:
            return None
        setname, zipped = stem.lower(), 1
    p = full.find(' (')
    title = (full if p < 0 else full[:p]).strip()
    tags = [t.lower() for t in re.findall(r'\(([^)]*)\)', full[p:] if p >= 0 else '')]
    if not title or any(w in t for t in tags for w in ROMSET_EXCLUDED):
        return None
    pre = any(w in t for t in tags for w in ROMSET_PRE)
    rank = min([regions.index(x.strip()) for t in tags for x in t.split(',') if x.strip() in regions] or [len(regions)])
    alt = 0
    for t in tags:
        m = re.match(r'set (\d+)', t)
        if m:
            alt = int(m.group(1)) - 1  # (set 1) = the main one
        elif t.startswith('alt'):
            alt = 1
    return title, setname, (pre, rank, 'aes' in tags, 0, alt, zipped, stem.lower())


def list_romsets(root, folder, regions):
    """games of a folder of romsets (Neo Geo) as the list of Frontier: .neo files with the
    setname in the name and zip files of romsets.xml, one game per title; media key = file
    name of the version to start, setname for ArcadeDB and ScreenScraper"""
    base = os.path.join(root, 'games', folder)
    names = read_romsets(os.path.join(base, 'romsets.xml'))
    sysname = folder.lower()
    found = {}  # file name (lowercase) -> (path, depth, zip member info or None): the shallowest one
    for d, dirs, files in os.walk(base):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.') and x.lower() not in EXCLUDE_DIRS)
        depth = d.count(os.sep)
        for f in sorted(files):
            p = os.path.join(d, f)
            stem, ext = os.path.splitext(f)
            if ext.lower() not in ('.neo', '.zip') or not os.path.exists(p):
                continue
            if ext.lower() == '.zip' and stem.lower() not in names:
                # not a romset: the .neo files inside it (a collection of .neo files)
                try:
                    with zipfile.ZipFile(p) as z:
                        for i in z.infolist():
                            b = i.filename.rsplit('/', 1)[-1]
                            if i.is_dir() or not b.lower().endswith('.neo') or \
                                    any(x.lower() in EXCLUDE_DIRS for x in i.filename.split('/')[:-1]):
                                continue
                            dz = depth + i.filename.count('/') + 1
                            if b.lower() not in found or dz < found[b.lower()][1]:
                                found[b.lower()] = (p + '/' + i.filename, dz, i)
                except Exception as e:
                    log('   zip:', f, e)
                continue
            if f.lower() not in found or depth < found[f.lower()][1]:
                found[f.lower()] = (p, depth, None)

    # setname of a name of romsets.xml: the main romset (the one without tags) first
    by_name = {}
    for setname, name in sorted(names.items(), key=lambda x: ('(' in x[1], x[0])):
        by_name.setdefault(romset_key(name), setname)
    by_title = {}
    for p, _, member in found.values():
        stem, ext = os.path.splitext(os.path.basename(p))
        r = romset_name(stem, ext[1:].lower(), names, regions, by_name)
        if r:
            by_title.setdefault(norm(r[0]), []).append((r, p, member))

    games = []
    for t in sorted(by_title):
        vers = sorted(by_title[t], key=lambda v: v[0][2])
        (title, setname, _), path, member = vers[0]
        name = os.path.basename(path)
        g = Game(sysname, os.path.splitext(name)[0], './' + name, title)
        g.ext = os.path.splitext(name)[1][1:].lower()
        g.setname = setname
        if member:
            g.size, g.crc = member.file_size, '%08x' % member.CRC
        else:
            g.size = os.path.getsize(path)
        g.ids = SYSTEMS.get(sysname)
        g.versions = [(os.path.splitext(os.path.basename(v[1]))[0], './' + os.path.basename(v[1])) for v in vers]
        games.append(g)
    return games


#############################################################################
# gamelist.xml

GAMELISTS = {}  # gamelist.xml -> entries, of the systems scraped in this run (for build_index)


def read_gamelist(path):
    out = {}
    if not os.path.exists(path):
        return out
    try:
        root = ET.parse(path).getroot()
    except Exception as e:
        log('gamelist unreadable, it is written again:', path, e)
        return out
    for g in root.iter('game'):
        p = g.findtext('path') or ''
        key = os.path.splitext(os.path.basename(p))[0]
        if key:
            out[key] = {c.tag: (c.text or '') for c in g}
    return out


def xml_text(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def write_gamelist(path, entries):
    """the same text as ElementTree with ET.indent(root, '  '), made directly: ElementTree
    takes many seconds on the MiSTer for thousands of games"""
    order = ['path'] + list(FIELDS) + list(GAMELIST_MEDIA.values())
    out = ["<?xml version='1.0' encoding='utf-8'?>\n"]
    for key in sorted(entries, key=str.lower):
        e = entries[key]
        tags = [t for t in order + [t for t in e if t not in order] if e.get(t)]
        if not tags:
            out.append('\n  <game />')
            continue
        out.append('\n  <game>')
        for tag in tags:
            text = e[tag]
            if tag == 'desc':
                # some sources give HTML entities ("&quot;") and CR LF
                text = html.unescape(text).replace('\r\n', '\n').replace('\r', '\n')
            out.append('\n    <%s>%s</%s>' % (tag, xml_text(text), tag))
        out.append('\n  </game>')
    out[1:1] = ['<gameList>'] if entries else ['<gameList />']
    if entries:
        out.append('\n</gameList>')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_file(path, ''.join(out))


#############################################################################
# sources

def adb_cache(lang):
    """folder of .scrape_cache with the answers of ArcadeDB: one per language (texts and
    genres are in the language asked); adb/ = before, language not known"""
    return 'adb_' + re.sub(r'[^a-z]', '', lang.lower())


def adb_fetch(http, cache, games, lang, failed=None, fresh=(), again=()):
    """ArcadeDB, in batches of 25 names not in the cache: setname -> info; failed: set of the
    names without an answer (network or service error); fresh: names whose "not found"
    saved ({}) is asked again; again: names asked again whatever was saved"""
    out = {}
    names = sorted({g.setname for g in games if g.setname})
    todo = []
    for n in names:
        path = os.path.join(cache, n + '.json')
        try:
            with open(path, encoding='utf-8') as f:
                out[n] = json.load(f)
            if (not out[n] and n in fresh) or n in again:
                todo.append(n)
        except (OSError, ValueError):
            todo.append(n)
    for i in range(0, len(todo), 25):
        batch = todo[i:i + 25]
        url = 'https://adb.arcadeitalia.net/service_scraper.php?ajax=query_mame&lang=%s&use_parent=1&game_name=%s' % (
            lang, urllib.parse.quote(';'.join(batch)))
        data = http.get(url)
        try:
            res = json.loads(data.decode('utf-8'))['result']
        except Exception:
            log('   ArcadeDB: no answer, trying again next run')
            if failed is not None:
                failed.update(batch)
            continue  # network or service error: nothing in the cache
        found = {r.get('game_name'): r for r in res}
        os.makedirs(cache, exist_ok=True)
        for n in batch:
            r = found.get(n, {})
            out[n] = r
            write_file(os.path.join(cache, n + '.json'), json.dumps(r))
        log('   ArcadeDB: %d/%d new' % (min(i + 25, len(todo)), len(todo)))
    return out


def adb_desc(text):
    """text of history.dat without the heading ("Arcade Video game published...", "(c) year") and the technical sections"""
    text = re.split(r'\n\s*- [A-Z][A-Z ]+ -', text)[0]
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    while paras and (re.match(r'^(Arcade )?Video game published', paras[0], re.I) or re.search(r'\(c\) ?\d{4}', paras[0]) and len(paras[0]) < 120):
        paras.pop(0)
    return '\n\n'.join(paras)


def adb_info(r, small):
    if not r or not r.get('title'):
        return None, {}
    year = (r.get('year') or '')[:4]
    info = {
        'name': r.get('title', ''),
        'desc': adb_desc(r.get('history') or ''),
        'releasedate': (year + '0101T000000') if year.isdigit() else '',
        'developer': r.get('manufacturer', ''),
        'publisher': r.get('manufacturer', ''),
        'genre': r.get('genre', ''),
        'players': r.get('players', ''),
        'rating': '%.2f' % (int(r['rate']) / 100.0) if str(r.get('rate', '')).isdigit() else '',
    }
    flyer = r.get('url_image_flyer') or ''
    if small:
        flyer = flyer.replace('resize=0', 'resize=1')  # 151x200 instead of the original (up to 2 MB)
    media = {'snap': r.get('url_image_ingame'), 'title': r.get('url_image_title'),
             'marquee': r.get('url_image_marquee'), 'box': flyer,
             'video': r.get('url_video_shortplay')}
    return {k: str(v) for k, v in info.items()}, {k: v for k, v in media.items() if v}


def libretro_name(name):
    return re.sub(r'[&*/:`<>?\\|"]', '_', name)


def libretro_media(g):
    if not g.ids or not g.ids[1]:
        return {}
    base = 'https://thumbnails.libretro.com/' + urllib.parse.quote(g.ids[1]) + '/'
    names = [g.title, g.key] if g.ids is ARCADE or g.setname else [g.key]
    out = {}
    for t, folder in (('box', 'Named_Boxarts'), ('snap', 'Named_Snaps'), ('title', 'Named_Titles')):
        out[t] = [base + folder + '/' + urllib.parse.quote(libretro_name(n)) + '.png' for n in dict.fromkeys(names)]
    return out


def ss_fetch(http, cache, g, cred, lang, fresh=False):
    if not cred or not g.ids:
        return None, {}
    params = {
        'devid': cred['devid'], 'devpassword': cred['devpassword'], 'softname': 'MiSTerFrontier',
        'ssid': cred['user'], 'sspassword': cred['password'], 'output': 'json',
        'systemeid': g.ids[0], 'romtype': 'rom', 'romnom': g.path[2:],
    }
    if g.crc is None and g.getcrc:
        g.crc = g.getcrc()
    if g.crc:
        params['crc'] = g.crc
    if g.size:
        params['romtaille'] = g.size
    if g.setname:
        params['romnom'] = g.setname + '.zip'
    url = 'https://api.screenscraper.fr/api2/jeuInfos.php?' + urllib.parse.urlencode(params)

    def fetch():
        # only valid answers and "not found" (404) go in the cache: credential, quota or
        # network errors are tried again in the next run
        data = http.get(url)
        if not data:
            return {} if http.status == 404 else None
        try:
            d = json.loads(data.decode('utf-8'))
        except Exception:
            http.trouble = True
            return None  # error answers in plain text
        # no credentials on the SD card: the request URL and the account data are removed,
        # also from the media URLs (they are added back when downloading)
        d.pop('header', None)
        (d.get('response') or {}).pop('ssuser', None)
        for m in ((d.get('response') or {}).get('jeu') or {}).get('medias') or []:
            if m.get('url'):
                m['url'] = ss_strip_cred(m['url'])
        return d
    d = cache_json(cache, '%s_%s' % (g.system, g.key), fetch, fresh)
    jeu = (d or {}).get('response', {}).get('jeu')
    if not jeu:
        return None, {}

    def pick(items, keyname, prefs):
        items = items or []
        for p in prefs:
            for it in items:
                if it.get(keyname) == p:
                    return it.get('text', '')
        return items[0].get('text', '') if items else ''

    regions = ss_regions(g)
    langs = [lang, 'en']
    genres = []
    for gen in jeu.get('genres', []) or []:
        n = pick(gen.get('noms'), 'langue', langs)
        if n:
            genres.append(n)
    date = pick(jeu.get('dates'), 'region', regions)
    note = (jeu.get('note') or {}).get('text', '')
    info = {
        'name': pick(jeu.get('noms'), 'region', regions),
        'desc': pick(jeu.get('synopsis'), 'langue', langs),
        'releasedate': (date[:4] + (date[5:7] if len(date) >= 7 else '01') + (date[8:10] if len(date) >= 10 else '01') + 'T000000') if date[:4].isdigit() else '',
        'developer': (jeu.get('developpeur') or {}).get('text', ''),
        'publisher': (jeu.get('editeur') or {}).get('text', ''),
        'genre': ' / '.join(genres[:2]),
        'players': (jeu.get('joueurs') or {}).get('text', ''),
        'rating': '%.2f' % (int(note) / 20.0) if note.isdigit() else '',
    }
    want = {'snap': ['ss'], 'title': ['sstitle'], 'box': ['box-2D'], 'marquee': ['wheel', 'wheel-hd', 'screenmarqueesmall'],
            'fanart': ['fanart'], 'video': ['video-normalized', 'video']}
    media = {}
    for t, types in want.items():
        for ty in types:
            cands = [m for m in jeu.get('medias', []) or [] if m.get('type') == ty]
            if not cands:
                continue
            order = (SS_BOX + [r for r in regions if r not in SS_BOX]) if t == 'box' else regions
            cands.sort(key=lambda m: order.index(m.get('region')) if m.get('region') in order else 99)
            media[t] = ss_add_cred(cands[0].get('url'), cred)
            break
    return info, media


SS_KEY_FILE = 'ss_dev.key'  # Frontier's ScreenScraper developer key, next to this script


def ss_keystream(n):
    """Mask of the developer key (tools/fe/ss_key.py writes ss_dev.key with it)"""
    ks = b''
    for c in range(n // 32 + 1):
        ks += hashlib.sha256(b'MiSTerFrontier/ScreenScraper' + bytes([c])).digest()
    return ks


def ss_dev():
    """Frontier's key for ScreenScraper as [devid, devpassword], ['', ''] without ss_dev.key.
    It names the program, not the user: it is not in the source code, only in the
    packages; please do not reuse it in other programs."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), SS_KEY_FILE)) as fh:
            raw = base64.a85decode(fh.read().strip())
        return (bytes(a ^ b for a, b in zip(raw, ss_keystream(len(raw)))).decode().split(':', 1) + [''])[:2]
    except (OSError, ValueError, UnicodeDecodeError):
        return ['', '']
SS_CRED = ('devid', 'devpassword', 'ssid', 'sspassword')
# No-Intro regions -> ScreenScraper codes
SS_REGION = {'usa': 'us', 'europe': 'eu', 'japan': 'jp', 'world': 'wor', 'france': 'fr', 'germany': 'de',
             'spain': 'sp', 'italy': 'it', 'korea': 'kr', 'brazil': 'br', 'australia': 'au', 'asia': 'asi',
             'china': 'cn', 'taiwan': 'tw', 'uk': 'uk', 'canada': 'ca', 'netherlands': 'nl', 'sweden': 'se'}
SS_PREF = ['us', 'wor', 'eu', 'jp']  # from regions= of frontier.ini (main)
# folders skipped by the lists by title and by the groups (exclude_dirs= of frontier.ini, as
# fe_group.cpp): unlicensed games, prototypes, hacks... are in games/<system>/Extra
EXCLUDE_DIRS = {'extra'}
SS_BOX = []  # preferred regions for the box art (--box-regions / scraper.ini), e.g. ['jp']


def ss_regions(g):
    """regions of names and media: those of the ROM, then the preferred order"""
    m = re.search(r'\(([^)]*)\)', g.key[date_len(g.key):])
    own = [SS_REGION[x.strip().lower()] for x in (m.group(1).split(',') if m else []) if x.strip().lower() in SS_REGION]
    out = []
    for r in own + SS_PREF + ['ss', 'eu', 'wor', 'us', 'jp']:
        if r not in out:
            out.append(r)
    return out


def ss_strip_cred(url):
    u = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True) if k not in SS_CRED]
    return urllib.parse.urlunsplit(u._replace(query=urllib.parse.urlencode(q)))


def ss_add_cred(url, cred):
    if not url or 'devid=' in url:
        return url
    add = {'devid': cred['devid'], 'devpassword': cred['devpassword'], 'ssid': cred['user'], 'sspassword': cred['password']}
    return url + ('&' if '?' in url else '?') + urllib.parse.urlencode(add)


#############################################################################
# data of the systems: Wikipedia, in gamelists/systems/gamelist.xml (path ./<games folder>.sys)
# as the games: Frontier shows them on the systems (description, maker, year, type); the
# hardware is at the end of the description and in tags of its own (${game.cpu}...)

WIKI_API = 'https://%s.wikipedia.org/w/api.php?'
# infobox label (lowercase, English Wikipedia) -> tag of the gamelist, label in the description
WIKI_FIELDS = [
    ('manufacturer', 'developer', None), ('developer', 'developer', None), ('type', 'genre', None),
    ('generation', 'generation', 'Generation'), ('released', 'released', 'Released'),
    ('release date', 'released', 'Released'),
    ('lifespan', 'lifespan', 'Lifespan'), ('discontinued', 'discontinued', 'Discontinued'),
    ('introductory price', 'price', 'Price'), ('units sold', 'units', 'Units sold'),
    ('cpu', 'cpu', 'CPU'), ('processor', 'cpu', 'CPU'), ('memory', 'memory', 'Memory'),
    ('storage', 'storage', 'Storage'), ('removable storage', 'storage', 'Storage'),
    ('graphics', 'graphics', 'Graphics'), ('sound', 'sound', 'Sound'), ('display', 'display', 'Display'),
    ('media', 'media', 'Media'), ('controller input', 'input', 'Controllers'), ('input', 'input', 'Controllers'),
    ('operating system', 'os', 'Operating system'), ('predecessor', 'predecessor', 'Predecessor'),
    ('best-selling game', 'bestseller', 'Best-selling game'), ('successor', 'successor', 'Successor'),
]


class Infobox(html.parser.HTMLParser):
    """label -> text of the rows of the first infobox table"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.depth, self.done = {}, 0, False
        self.cell, self.label, self.text, self.skip = None, '', [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get('class') or ''
        if self.done:
            return
        if tag == 'table':
            if self.depth or 'infobox' in cls:
                self.depth += 1
            return
        if not self.depth:
            return
        if self.skip:
            if tag not in ('br', 'img', 'wbr', 'hr', 'meta', 'link'):
                self.skip += 1
            return
        if tag in ('sup', 'style', 'script') or 'reference' in cls or 'noprint' in cls or \
                (a.get('style') or '').replace(' ', '').startswith('display:none'):
            self.skip = 1
        elif tag in ('th', 'td'):
            self.cell, self.text = tag, []
        elif tag in ('br', 'li') and self.cell:
            self.text.append('; ')

    def handle_endtag(self, tag):
        if self.done or not self.depth:
            return
        if self.skip:
            self.skip -= 1
            return
        if tag == 'table':
            self.depth -= 1
            self.done = self.depth == 0
        elif tag == 'th' and self.cell == 'th':
            self.label, self.cell = clean_value(''.join(self.text)).lower(), None
        elif tag == 'td' and self.cell == 'td':
            if self.label and self.label not in self.rows:
                self.rows[self.label] = ''.join(self.text)
            self.label, self.cell = '', None
        elif tag == 'tr':
            self.label = ''

    def handle_data(self, data):
        if self.depth and not self.skip and self.cell:
            self.text.append(data)


def wiki_text(t):
    """one line: "; " between the items of a list, no empty items"""
    t = re.sub(r'\s+', ' ', t.replace('\xa0', ' '))
    parts = [p.strip(' ,') for p in t.split(';')]
    return '; '.join(p for p in parts if p)


def wiki_get(http, cache, lang, params):
    params = dict(params, format='json', formatversion=2, redirects=1)
    name = 'wiki_%s_%s' % (lang, '_'.join('%s=%s' % kv for kv in sorted(params.items())
                                          if kv[0] not in ('format', 'formatversion', 'redirects')))

    def fetch():
        data = http.get(WIKI_API % lang + urllib.parse.urlencode(params), ua=WIKI_UA)
        try:
            return json.loads(data) if data else None
        except ValueError:
            return None
    return cache_json(cache, name, fetch)


def wiki_extract(http, cache, lang, title):
    """plain text of the introduction of an article (at most ~2500 characters)"""
    d = wiki_get(http, cache, lang, {'action': 'query', 'prop': 'extracts', 'exintro': 1, 'explaintext': 1, 'titles': title})
    pages = (d or {}).get('query', {}).get('pages', [])
    text = pages[0].get('extract', '') if pages and not pages[0].get('missing') else ''
    out = ''
    for p in (p.strip() for p in text.split('\n')):
        if not p:
            continue
        if out and len(out) + len(p) > 2500:
            break
        out += ('\n' if out else '') + p
    return out


def system_info(args, http, folder):
    """gamelist entry of a system from Wikipedia, None without wiki= in systems.ini"""
    title = SYSTEM_WIKI.get(folder.lower())
    if not title:
        return None
    cache = os.path.join(args.frontier, '.scrape_cache', 'wikipedia')
    lang = (args.lang or 'en').split('-')[0].lower()
    d = wiki_get(http, cache, 'en', {'action': 'parse', 'page': title, 'prop': 'text', 'section': 0})
    box = Infobox()
    if d and 'parse' in d:
        box.feed(d['parse'].get('text', ''))
    rows = {k: wiki_text(v) for k, v in box.rows.items() if wiki_text(v)}
    desc = ''
    if lang != 'en':
        d = wiki_get(http, cache, 'en', {'action': 'query', 'prop': 'langlinks', 'lllang': lang, 'titles': title})
        pages = (d or {}).get('query', {}).get('pages', [])
        links = pages[0].get('langlinks', []) if pages else []
        if links:
            desc = wiki_extract(http, cache, lang, links[0].get('title', ''))
    desc = desc or wiki_extract(http, cache, 'en', title)
    if not desc and not rows:
        log('%s: nothing on Wikipedia (%s)' % (folder, title))
        return None
    e = {'path': './%s.sys' % folder, 'name': SYSTEM_NAMES.get(folder.lower(), folder)}
    hw = []
    for label, tag, shown in WIKI_FIELDS:
        v = rows.get(label)
        if not v or e.get(tag):
            continue
        e[tag] = v
        if shown:
            hw.append('%s: %s' % (shown, v))
    year = re.search(r'\b(19[4-9]\d|20[0-4]\d)\b', e.get('released', ''))
    if year:
        e['releasedate'] = year.group(1)
    e['desc'] = desc + ('\n\n' + '\n'.join(hw) if hw else '')
    e['source'] = 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_'))
    return e


def scrape_systems(args, http, folders):
    """data of the systems in gamelists/systems/gamelist.xml (once; again with --force or
    --refresh-data, e.g. in another language)"""
    path = os.path.join(args.frontier, 'gamelists', 'systems', 'gamelist.xml')
    entries = read_gamelist(path)
    n = 0
    for i, folder in enumerate(folders):
        old = [k for k in entries if k.lower() == folder.lower()]
        if old and not args.force and not args.refresh_data:
            continue
        STATUS.set(system=folder.lower(), step='system', n=0, total=0, systems=len(folders), done=i)
        e = system_info(args, http, folder)
        if e:
            for k in old:
                del entries[k]
            entries[folder] = e
            n += 1
            write_gamelist(path, entries)  # after each system: nothing lost if stopped
    if n:
        log('systems: data of %d systems from Wikipedia -> %s' % (n, path))


#############################################################################
# video: Frontier plays the mp4 files (frontier/lib/fe_av.so); optionally
# mp4 -> .mjv (sequence of JPEGs, lighter to play: decoded with libturbojpeg)

def jpeg_size(data):
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            return None
        m = data[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            return struct.unpack('>HH', data[i + 5:i + 9])[::-1]
        i += 2 + struct.unpack('>H', data[i + 2:i + 4])[0]
    return None


def make_mjv(src, dst, fps, width, seconds, quality=5):
    """converts a video with ffmpeg; format in fe_media.cpp (video section)"""
    cmd = ['ffmpeg', '-v', 'error', '-i', src, '-an', '-t', str(seconds),
           '-vf', 'fps=%g,scale=%d:-2' % (fps, width), '-q:v', str(quality),
           '-f', 'image2pipe', '-c:v', 'mjpeg', '-']
    try:
        data = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
    except Exception as e:
        log('   ffmpeg:', e)
        return False
    frames = [b'\xff\xd8\xff' + f for f in data.split(b'\xff\xd8\xff')[1:]]
    if not frames:
        return False
    size = jpeg_size(frames[0]) or (width, 0)
    head = b'MJV1' + struct.pack('<IHHHH', len(frames), size[0], size[1], int(round(fps * 100)), 0)
    off = len(head) + 4 * (len(frames) + 1)
    offsets = []
    for f in frames:
        offsets.append(off)
        off += len(f)
    offsets.append(off)
    tmp = dst + '.tmp'
    with open(tmp, 'wb') as fh:
        fh.write(head + struct.pack('<%dI' % len(offsets), *offsets) + b''.join(frames))
    os.replace(tmp, dst)
    return True


def convert_videos(args, folder):
    """mp4 -> mjv in a media/<system>/video folder"""
    if not shutil.which('ffmpeg'):
        return
    for f in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not f.lower().endswith('.mp4'):
            continue
        src = os.path.join(folder, f)
        dst = os.path.join(folder, f[:-4] + '.mjv')
        if os.path.exists(dst) and not args.force:
            continue
        if make_mjv(src, dst, args.video_fps, args.video_width, args.video_seconds):
            log('   video: %s (%d KB)' % (os.path.basename(dst), os.path.getsize(dst) // 1024))
            if not args.keep_mp4:
                os.remove(src)


#############################################################################
# pictures

MEDIA_EXT = ('.png', '.jpg', '.jpeg', '.mjv', '.mp4')
_media_index = {}  # folder -> {file name without extension: path}


def _media_add(index, dirpath, name):
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext in MEDIA_EXT:
        # lowercase, as Frontier looks for them: on the SD (exFAT) "Revision 1" and "revision 1"
        # are the same file
        old = index.get(stem.lower())
        if not old or MEDIA_EXT.index(ext) < MEDIA_EXT.index(os.path.splitext(old)[1].lower()):
            index[stem.lower()] = os.path.join(dirpath, name)


def find_media(dirpath, key):
    """media file of the game, whatever the case of the letters; each folder is read once
    (thousands of stat() on the SD are very slow)"""
    index = _media_index.get(dirpath)
    if index is None:
        index = _media_index[dirpath] = {}
        try:
            for name in os.listdir(dirpath):
                _media_add(index, dirpath, name)
        except OSError:
            pass
    return index.get(key.lower())


def media_saved(path):
    """to call after writing a media file, so find_media sees it"""
    dirpath = os.path.dirname(path)
    _media_add(_media_index.setdefault(dirpath, {}), dirpath, os.path.basename(path))


def save_image(data, dirpath, key, mtype, max_size):
    """saves PNG or JPEG (the only formats of Frontier); with Pillow it resizes"""
    os.makedirs(dirpath, exist_ok=True)
    if Image:
        import io
        try:
            im = Image.open(io.BytesIO(data))
            im.load()
        except Exception:
            return None
        if max_size and (im.width > max_size or im.height > max_size):
            im.thumbnail((max_size, max_size), Image.LANCZOS)
        alpha = im.mode in ('RGBA', 'LA', 'P') and mtype in ('box', 'marquee')
        if alpha:
            path = os.path.join(dirpath, key + '.png')
            im.convert('RGBA').save(path, optimize=True)
        else:
            path = os.path.join(dirpath, key + '.jpg')
            im.convert('RGB').save(path, quality=85)
        return path
    if data[:4] == b'\x89PNG':
        ext = '.png'
    elif data[:2] == b'\xff\xd8':
        ext = '.jpg'
    else:
        return None  # gif, webp...: they can't be converted without Pillow
    path = os.path.join(dirpath, key + ext)
    with open(path, 'wb') as f:
        f.write(data)
    return path


#############################################################################

def share_versions(g, e, entries, have, sysname, types):
    """data and media of the game also in the entries of the other versions of the title; 1 if something changes"""
    changed = 0
    for t in types:
        if have.get(t):
            path = '../../media/%s/%s/%s' % (sysname, t, os.path.basename(have[t]))
            if e.get(GAMELIST_MEDIA[t]) != path:
                e[GAMELIST_MEDIA[t]] = path
                changed = 1
    for key, path in getattr(g, 'versions', []):
        if key == g.key:
            continue
        v = entries.get(key, {})
        for k, val in e.items():
            if k != 'path' and val and v.get(k) != val:
                v[k] = val
                changed = 1
        if v.get('path') != path:
            v['path'] = path
            changed = 1
        entries[key] = v
    return changed


NOTGAME = re.compile(r'^ZZZ\(notgame\)\s*:?\s*', re.I)


def clean_name(name, fallback):
    """ScreenScraper marks the entries that are not games with "ZZZ(notgame):" (and sometimes a
    placeholder like "pas un jeu"): prefix removed, placeholder replaced by the title of the file"""
    if not name or not NOTGAME.match(name):
        return name
    rest = NOTGAME.sub('', name).strip()
    if not rest or re.search(r'pas un jeu|not a game|no es un juego', rest, re.I):
        return fallback
    return rest


NOTFOUND_DAYS = 30


class NotFound:
    """games tried without finding all that was asked (no source has it), in
    .scrape_cache/notfound_<system>.tsv: not tried again, nor counted, for NOTFOUND_DAYS days,
    unless more types or sources are asked; --force, --refresh-data and --retry-missing try them"""

    def __init__(self, cache, sysname, want, sources):
        self.path = os.path.join(cache, 'notfound_%s.tsv' % sysname)
        self.want, self.sources = set(want), set(sources)
        self.items = {}  # key -> (date, types, sources)
        self.changed = False
        try:
            with open(self.path, encoding='utf-8') as f:
                for line in f:
                    p = line.rstrip('\n').split('\t')
                    if len(p) == 4:
                        self.items[p[0]] = (p[1], set(p[2].split(',')) - {''}, set(p[3].split(',')) - {''})
        except OSError:
            pass

    def skip(self, key):
        it = self.items.get(key)
        if not it:
            return False
        try:
            age = (datetime.date.today() - datetime.date.fromisoformat(it[0])).days
        except ValueError:
            return False
        return 0 <= age < NOTFOUND_DAYS and self.want <= it[1] and self.sources <= it[2]

    def add(self, key):
        self.items[key] = (datetime.date.today().isoformat(), self.want, self.sources)
        self.changed = True

    def remove(self, key):
        if self.items.pop(key, None):
            self.changed = True

    def save(self):
        if not self.changed:
            return
        if self.items or os.path.exists(self.path):
            write_file(self.path, ''.join('%s\t%s\t%s\t%s\n' % (k, v[0], ','.join(sorted(v[1])), ','.join(sorted(v[2])))
                                          for k, v in sorted(self.items.items())))
        self.changed = False


def chosen(games, names):
    """the games called so (file name without extension, any case; for a game by title
    also the name of one of its versions)"""
    want = {n.lower() for n in names}
    return [g for g in games if g.key.lower() in want or any(v[0].lower() in want for v in getattr(g, 'versions', ()))]


def scrape(args, http, games, sysname, cred):
    fe = args.frontier
    gl_path = os.path.join(fe, 'gamelists', sysname, 'gamelist.xml')
    t0 = time.time()
    entries = read_gamelist(gl_path)
    cache = os.path.join(fe, '.scrape_cache')
    types = args.types
    need = [t for t in ('snap', 'box', 'video') if t in types]  # without them a game is scraped again
    redo = args.force or args.refresh_data
    retry = redo or args.retry_missing

    if args.limit:
        games = games[:args.limit]
    if args.game:
        # only these games, and the alternatives that take from them
        mine = {g.key for g in chosen(games, args.game)}
        games = [g for g in games if g.key in mine or g.main in mine]
        if not mine:
            log('%s: %s not found among the games' % (sysname, ', '.join(args.game)))
    log('%s: %d games' % (sysname, len(games)))
    by_key = {g.key: g for g in games}
    dirty = not os.path.exists(gl_path)  # the gamelist is written only if something changes

    for g in games:  # names already saved with the "ZZZ(notgame):" marker
        e = entries.get(g.key)
        if e and e.get('name') and NOTGAME.match(e['name']):
            e['name'] = clean_name(e['name'], g.title)
            dirty = True

    mdir = {t: os.path.join(fe, 'media', sysname, t) for t in types}

    def media_of(key):
        return {t: find_media(mdir[t], key) for t in types}

    def is_complete(g, e, have):
        name = None if e.get('name') == g.title and not e.get('desc') else e.get('name')  # fallback name: not a real one
        return bool((args.no_text or (name and e.get('desc'))) and all(have.get(t) for t in need))

    def has_data(key):
        """the game has something to give to its alternatives"""
        e, g = entries.get(key) or {}, by_key.get(key)
        return bool(e.get('desc') or (e.get('name') and g and e['name'] != g.title) or any(media_of(key).values()))

    # one look at every game: complete, alternative (from its main game), not found
    # before (skipped) or to scrape; the counter only counts the last ones
    STATUS.set(True, system=sysname, step='check', n=0, total=0)
    nf = NotFound(cache, sysname, list(types) + ([] if args.no_text else ['text']), args.sources)
    work, alts, skipped, done = [], [], 0, 0
    for g in games:
        e = entries.get(g.key, {})
        if g.main and g.main in by_key:
            alts.append(g)
            continue
        have = media_of(g.key)
        if not redo and is_complete(g, e, have):
            nf.remove(g.key)
            if share_versions(g, e, entries, have, sysname, types):
                done += 1
            continue
        if not retry and nf.skip(g.key):
            skipped += 1
            if share_versions(g, e, entries, have, sysname, types):
                done += 1
            continue
        work.append(g)
    work_keys = {g.key for g in work}
    # alternatives scraped on their own: their main game has nothing and is not scraped now
    alone = [g for g in alts if g.main not in work_keys and not has_data(g.main)
             and not (not redo and is_complete(g, entries.get(g.key, {}), media_of(g.key)))
             and (retry or not nf.skip(g.key))]
    todo = len(work) + len(alone)
    dirty = dirty or done > 0
    log('%s: %d to scrape%s, %d alternatives from their main game; check %.1f s' % (
        sysname, todo, (', %d not found in the last %d days skipped (--retry-missing)' % (skipped, NOTFOUND_DAYS)) if skipped else '',
        len(alts) - len(alone), time.time() - t0))

    # games not found before and tried again: the "not found" answers in the caches are asked again
    # a game asked by name (--game): any saved answer is asked again
    fresh = {g.key for g in work + alone if g.key in nf.items or args.game}
    fresh_sets = {g.setname for g in work + alone if g.key in fresh and g.setname}
    adb, adb_failed = {}, set()
    if 'adb' in args.sources and (sysname == 'arcade' or any(g.setname for g in games)):
        STATUS.set(True, step='adb')
        t1 = time.time()
        adb = adb_fetch(http, os.path.join(cache, adb_cache(args.lang)), work + alone, args.lang, adb_failed, fresh_sets,
                        fresh_sets if args.game else ())
        if work or alone:
            log('%s: ArcadeDB %.1f s' % (sysname, time.time() - t1))
    STATUS.set(True, system=sysname, step='scrape', n=0, total=todo)

    # libretro pictures that do not exist (404), remembered between runs (--force and --refresh-data ignore them)
    os.makedirs(cache, exist_ok=True)
    miss_path = os.path.join(cache, 'libretro_miss_%s.txt' % sysname)
    misses = set()
    if not redo and os.path.exists(miss_path):
        with open(miss_path, encoding='utf-8') as f:
            misses = set(l.rstrip('\n') for l in f)
    miss_file = open(miss_path, 'a', encoding='utf-8')

    def fetch(g):
        """the data and the media of a game from the sources"""
        e = entries.get(g.key, {})
        have = media_of(g.key)
        if e.get('name') == g.title and not e.get('desc'):
            del e['name']  # fallback name written by a previous run: the real one is looked for
        http.trouble = g.setname in adb_failed
        before = {k: e.get(k) for k in FIELDS}
        info, urls = {}, {}
        for src in args.sources:
            if src == 'adb' and g.setname in adb:
                i, m = adb_info(adb[g.setname], Image is None)
            elif src == 'ss':
                try:
                    i, m = ss_fetch(http, os.path.join(cache, 'ss'), g, cred, args.lang,
                                    ('all' if args.game else True) if g.key in fresh else False)
                except (FileNotFoundError, NotADirectoryError) as ex:
                    # file moved or deleted while the scraper runs
                    log('   file not readable, skipped:', ex)
                    i, m = None, {}
                    http.trouble = True
            elif src == 'libretro':
                i, m = None, libretro_media(g)
            else:
                continue
            for k, v in (i or {}).items():
                if v and not info.get(k):
                    info[k] = v
            for k, v in m.items():
                urls.setdefault(k, [])
                urls[k] += v if isinstance(v, list) else [v]

        e['path'] = g.path
        if info.get('name'):
            info['name'] = clean_name(info['name'], g.title)
        for k, v in info.items():
            if args.no_text and k != 'name':
                continue
            if v and (redo or not e.get(k)):
                e[k] = str(v)
        if not e.get('name'):
            e['name'] = g.title

        got = []
        for t in types:
            if have[t] and not args.force:
                continue
            for url in urls.get(t, []):
                if url in misses and g.key not in fresh:
                    continue
                data = http.get(url)
                if not data and http.status == 404 and 'libretro.com' in url and url not in misses:
                    misses.add(url)  # not there: not asked again in the next runs
                    miss_file.write(url + '\n')
                    miss_file.flush()
                if not data or len(data) < 100:
                    continue
                if t == 'video':
                    os.makedirs(mdir[t], exist_ok=True)
                    path = os.path.join(mdir[t], g.key + '.mp4')
                    with open(path, 'wb') as f:
                        f.write(data)
                    mjv = path[:-4] + '.mjv'
                    if args.mjv and shutil.which('ffmpeg') and make_mjv(path, mjv, args.video_fps, args.video_width, args.video_seconds):
                        if not args.keep_mp4:
                            os.remove(path)
                        path = mjv
                else:
                    path = save_image(data, mdir[t], g.key, t, args.max_size)
                if path:
                    media_saved(path)
                    have[t] = path
                    got.append(t)
                    break

        for t in types:
            if have[t]:
                e[GAMELIST_MEDIA[t]] = '../../media/%s/%s/%s' % (sysname, t, os.path.basename(have[t]))
        entries[g.key] = e
        share_versions(g, e, entries, have, sysname, types)
        # still missing something with all the sources answering: not tried again for a while
        missing = not is_complete(g, e, have)
        if not missing:
            nf.remove(g.key)
        elif not http.trouble:
            nf.add(g.key)
        # something really new: pictures, or data (not just the name of the file)
        new = bool(got) or any(e.get(k) and e.get(k) != before[k] and (k != 'name' or e[k] != g.title) for k in FIELDS)
        return e, got, new, missing and not http.trouble

    def from_main(g):
        """an alternative: what it misses from its main game (its own name stays), media
        pointing to the files of the main game; 1 if something changes"""
        e, m = entries.get(g.key, {}), entries.get(g.main) or {}
        have, mhave = media_of(g.key), media_of(g.main)
        old = dict(e)
        for k, v in m.items():
            if v and k not in ('path', 'name') and k not in GAMELIST_MEDIA.values() and (args.refresh_data or args.force or not e.get(k)):
                e[k] = v
        e['path'] = g.path
        if not e.get('name'):
            e['name'] = g.title
        for t, tag in GAMELIST_MEDIA.items():
            if t in types and (have.get(t) or mhave.get(t)):
                e[tag] = '../../media/%s/%s/%s' % (sysname, t, os.path.basename(have.get(t) or mhave[t]))
            elif not e.get(tag) and m.get(tag):
                e[tag] = m[tag]
        if e == old:
            return 0
        entries[g.key] = e
        nf.remove(g.key)
        return 1

    last_write = time.time()
    updated, notfound = 0, skipped  # games with something new, games no source has
    n = 0  # games that needed work
    total = todo
    t1 = time.time()
    try:
        # the main games first, then the alternatives take from them
        for g in work + alts:
            own = g.key in work_keys
            if own or not has_data(g.main):
                if not own:
                    # an alternative whose main game has nothing: on its own
                    if not redo and is_complete(g, entries.get(g.key, {}), media_of(g.key)):
                        continue
                    if not retry and nf.skip(g.key):
                        notfound += 1
                        continue
                    if 'adb' in args.sources and g.setname and g.setname not in adb and g.setname not in adb_failed:
                        adb.update(adb_fetch(http, os.path.join(cache, adb_cache(args.lang)), [g], args.lang, adb_failed))
                n += 1
                if n > total:
                    total = n
                e, got, new, missing = fetch(g)
                updated += new
                notfound += missing
                done += 1
                dirty = True
                log('[%d/%d] %s: %s%s' % (n, total, g.key, e.get('name', ''), (' + ' + ' '.join(got)) if got else ''))
                STATUS.set(n=n, total=total, game=e.get('name', g.key))
            elif from_main(g):
                done += 1
                dirty = True

            # writing the gamelist (thousands of entries) takes long on the MiSTer:
            # every few minutes, not every 25 games
            if dirty and time.time() - last_write > 300:
                write_gamelist(gl_path, entries)
                nf.save()
                last_write = time.time()
    finally:
        miss_file.close()
        if dirty:
            t2 = time.time()
            write_gamelist(gl_path, entries)  # also on Ctrl+C
            log('%s: gamelist written, %.1f s' % (sysname, time.time() - t2))
        nf.save()
        # the totals of the run, for Frontier ("Scraper finished: 3 games with new data or pictures")
        STATUS.set(True, updated=int(STATUS.data.get('updated', 0)) + updated,
                   notfound=int(STATUS.data.get('notfound', 0)) + notfound)
    GAMELISTS[gl_path] = entries
    log('%s: %d games with new data or pictures, %d not found; %d entries changed, %s (%.0f s)' % (
        sysname, updated, notfound, done, gl_path, time.time() - t0))


def dedupe_media(args, dry):
    """--dedupe-media: no network. The arcade versions (the .mra of _alternatives and the versions
    of a core, see group_versions) which have their own media identical (same bytes) to those of
    their main game are made to use the files of the main game: the gamelist points there and
    the copies are deleted (--dry-run: only says). Different files stay, as do the files that
    another game's entry uses"""
    cache = os.path.join(args.frontier, '.scrape_cache')
    games = list_arcade(args.root, cache)
    by_key = {g.key: g for g in games}
    gl_path = os.path.join(args.frontier, 'gamelists', 'arcade', 'gamelist.xml')
    entries = read_gamelist(gl_path)
    mdir = {t: os.path.join(args.frontier, 'media', 'arcade', t) for t in MEDIA_TYPES}
    gl_dir = os.path.dirname(gl_path)

    def norm_path(p):
        return os.path.normpath(p).lower()

    refs = {}  # media file -> keys of the entries which use it
    for k, e in entries.items():
        for tag in GAMELIST_MEDIA.values():
            if e.get(tag):
                refs.setdefault(norm_path(os.path.join(gl_dir, e[tag])), set()).add(k)
    digests = {}

    def digest(path):
        if path not in digests:
            h = hashlib.md5()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(1 << 20), b''):
                    h.update(chunk)
            digests[path] = h.hexdigest()
        return digests[path]

    plan = []  # (game, type, own file, main file, size)
    t0 = time.time()
    for g in games:
        if not g.main or g.main not in by_key or g.key not in entries:
            continue
        for t in MEDIA_TYPES:
            own, main = find_media(mdir[t], g.key), find_media(mdir[t], g.main)
            if not own or not main or norm_path(own) == norm_path(main):
                continue
            try:
                size = os.path.getsize(own)
                if size != os.path.getsize(main) or digest(own) != digest(main):
                    continue
            except OSError:
                continue
            if refs.get(norm_path(own), set()) - {g.key}:
                continue  # another game uses this file
            plan.append((g, t, own, main, size))
    total = sum(p[4] for p in plan)
    per = {}
    for p in plan:
        per.setdefault(p[1], [0, 0])
        per[p[1]][0] += 1
        per[p[1]][1] += p[4]
    for t, (n, b) in sorted(per.items()):
        log('%s: %d copies, %.1f MB' % (t, n, b / 1e6))
    for g, t, own, main, size in plan[:10]:
        log('   %s: %s = %s' % (t, os.path.basename(own), os.path.basename(main)))
    log('media identical to those of the main game: %d files, %.1f MB (%.1f s)%s' % (
        len(plan), total / 1e6, time.time() - t0, ' (dry run: nothing changed)' if dry else ''))
    if dry or not plan:
        return
    # the gamelist first (the main game's files exist), then the copies
    for g, t, own, main, size in plan:
        entries[g.key][GAMELIST_MEDIA[t]] = '../../media/arcade/%s/%s' % (t, os.path.basename(main))
    write_gamelist(gl_path, entries)
    deleted = 0
    for g, t, own, main, size in plan:
        try:
            os.remove(own)
            deleted += 1
        except OSError as ex:
            log('   not deleted:', own, ex)
    log('deleted %d files, %.1f MB; gamelist updated' % (deleted, total / 1e6))


#############################################################################
# groups: different titles of the same game (Thunder Force IV / Lightening Force)
# from the MAME software lists (cloneof), matching the files by name or by CRC.
# Result: gamelists/<folder>/groups.txt, lines "<group>\t<title>",
# only for the games with more titles (Frontier already joins equal titles).

TAG_EXCLUDED = ('hack', 't+', 't-', 'translat', 'patch', 'trainer', 'cracked', 'pirate')


def date_len(name):
    """'1991-08-23 F-Zero (USA)': release date in front (collections sorted by date)"""
    m = re.match(r'^\d{4}-\d{2}-\d{2}[ _-]+', name)
    return m.end() if m and len(name) > m.end() else 0


def drop_numbered(found):
    """numbered copies of the collections ("006 Lightening Force (USA).md", "057 - Wonder Boy (Japan).sg"),
    keys = lowercase file names without date: removed if the name without the number is another
    file or its title is the title of another file (as fe_group.cpp)"""
    titles = {t for t in (title_region(os.path.splitext(k)[0]) for k in found) if t}
    for k in list(found):
        m = re.match(r'^\d+[ ._-]+(.+)$', k)
        if m and (m.group(1) in found or title_region(os.path.splitext(m.group(1))[0]) in titles):
            del found[k]


def title_region(stem):
    """'Title (USA, Europe) (Rev 1)' -> 'Title'; None if it isn't a No-Intro name with a
    region (hacks, translations, text after the tags...), as fe_group.cpp"""
    name = stem[date_len(stem):]
    if not name or name[0] == '[':
        return None
    p = name.find(' (')
    if p < 0 or '[' in name[:p]:
        return None
    title, rest = name[:p].strip(), name[p:]
    if not title or re.sub(r'\s*(\([^)]*\)|\[[^\]]*\])', '', rest).strip():
        return None
    first = True
    for m in re.finditer(r'\(([^)]*)\)|\[([^\]]*)\]', rest):
        if m.group(2) is not None:
            if m.group(2) != '!':
                return None
            continue
        tag = m.group(1).lower()
        if first:
            first = False
            regions = [x.strip() for x in tag.split(',') if x.strip()]
            if not regions or any(r not in REGIONS for r in regions):
                return None
        elif any(w in tag for w in TAG_EXCLUDED):
            return None
    return None if first else title


def norm(s):
    return ' '.join(s.lower().split())


def softlist(http, args, name):
    """(name -> group, crc -> name, normalized description -> name) of hash/<name>.xml"""
    cache = os.path.join(args.frontier, '.scrape_cache')
    path = os.path.join(cache, 'mame_%s.xml' % name)
    if args.force or not os.path.exists(path):
        log('   MAME %s: downloading' % name)
        data = http.get(MAME_HASH % name)
        if not data:
            log('   MAME %s: not found' % name)
            return {}, {}, {}
        os.makedirs(cache, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
    group, crcs, descs = {}, {}, {}
    for _, el in ET.iterparse(path):
        if el.tag != 'software':
            continue
        sw = el.get('name')
        group[sw] = '%s:%s' % (name, el.get('cloneof') or sw)
        d = el.findtext('description')
        if d:
            descs.setdefault(norm(d), sw)
        for info in el.findall('info'):
            if info.get('name') == 'alt_title' and info.get('value'):
                descs.setdefault(norm(re.sub(r' \((Box|Title|Manual)[^)]*\)$', '', info.get('value'))), sw)
        for rom in el.iter('rom'):
            if rom.get('crc'):
                crcs.setdefault(rom.get('crc').lower(), sw)
        el.clear()
    return group, crcs, descs


def rom_crcs(data, ext):
    """CRC of the file and of the content without header (NES, SNES, Lynx, 7800)"""
    out = [zlib.crc32(data)]
    if data[:4] == b'NES\x1a' and len(data) > 16:
        prg = data[4] * 16384
        out += [zlib.crc32(data[16:]), zlib.crc32(data[16:16 + prg])]
    elif ext in ('sfc', 'smc') and len(data) % 1024 == 512:
        out.append(zlib.crc32(data[512:]))
    elif data[:4] == b'LYNX' and len(data) > 64:
        out.append(zlib.crc32(data[64:]))
    elif data[1:10] == b'ATARI7800' and len(data) > 128:
        out.append(zlib.crc32(data[128:]))
    return ['%08x' % (c & 0xFFFFFFFF) for c in out]


def make_groups(args, http, folder, patterns):
    lists = SOFTLISTS.get(folder.lower())
    if not lists:
        log('%s: no known MAME list, groups skipped' % folder)
        return
    log('%s: groups from MAME %s' % (folder, ', '.join(lists)))
    group, crcs, descs = {}, {}, {}
    for name in lists:
        g, c, d = softlist(http, args, name)
        group.update(g)
        for k, v in c.items():
            crcs.setdefault(k, v)
        for k, v in d.items():
            descs.setdefault(k, v)
    if not group:
        return

    # CRCs already computed: path -> [size, mtime, crc...]
    cache_path = os.path.join(args.frontier, '.scrape_cache', 'crc_%s.json' % folder.lower())
    try:
        with open(cache_path, encoding='utf-8') as f:
            crc_cache = json.load(f)
    except Exception:
        crc_cache = {}

    # files with a region, one per name (as fe_group.cpp)
    found = {}
    base = os.path.join(args.root, 'games', folder)
    t0 = time.time()
    for d, dirs, files in os.walk(base):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.') and x.lower() not in EXCLUDE_DIRS)
        for f in sorted(files):
            ext = os.path.splitext(f)[1][1:].lower()
            if not ext_ok(ext, patterns) or not title_region(os.path.splitext(f)[0]):
                continue
            # same file in more folders: first the one without a date in front
            dl = date_len(f)
            key = f[dl:].lower()
            if key not in found or (found[key][1] and not dl):
                found[key] = (os.path.join(d, f), dl)
    found = {k: v[0] for k, v in found.items()}
    if not found:
        # no files with a region (e.g. Megadrive with only the 240p Test Suite next to MegaDrive):
        # groups.txt is by lowercase name, it must not be overwritten with the one of another folder
        log('%s: no files with a region, groups skipped' % folder)
        return
    drop_numbered(found)

    titles = {}  # group -> {title key: title}
    by_name, by_crc, unmatched = 0, 0, 0
    for p in found.values():
        f = os.path.basename(p)
        stem, ext = os.path.splitext(f)
        ext = ext[1:].lower()
        title = title_region(stem)
        sw = descs.get(norm(stem))
        if sw:
            by_name += 1
        else:
            try:
                st = os.stat(p)
            except OSError:
                continue  # broken link (the file was moved)
            c = crc_cache.get(p)
            if not c or c[0] != st.st_size or c[1] != int(st.st_mtime):
                if st.st_size > 64 * 1024 * 1024:
                    continue
                with open(p, 'rb') as fh:
                    c = [st.st_size, int(st.st_mtime)] + rom_crcs(fh.read(), ext)
                crc_cache[p] = c
            sw = next((crcs[x] for x in c[2:] if x in crcs), None)
            if sw:
                by_crc += 1
            else:
                unmatched += 1
                continue
        titles.setdefault(group[sw], {})[norm(title)] = title

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(crc_cache, f)

    lines = []
    for g in sorted(titles):
        if len(titles[g]) > 1:
            lines += ['%s\t%s' % (g, t) for t in sorted(titles[g].values())]
    out = os.path.join(args.frontier, 'gamelists', folder.lower(), 'groups.txt')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# fe_scrape.py --groups %s (MAME %s): games with more titles\n' % (time.strftime('%Y-%m-%d'), ', '.join(lists)))
        f.write('\n'.join(lines) + ('\n' if lines else ''))
    ngroups = sum(1 for g in titles if len(titles[g]) > 1)
    log('%s: %d files with a region (%d by name, %d by CRC, %d not found), %d games with more titles, %.0f s -> %s'
        % (folder, len(found), by_name, by_crc, unmatched, ngroups, time.time() - t0, out))


#############################################################################
# index of the games for Frontier's "Lists" (lists of games by publisher, genre, year...):
# frontier/.cache/meta.tsv, a line for each game of the gamelists and each .mra of _Arcade:
#   <system>\t<file>\t<core>\t<publisher>\t<developer>\t<genre>\t<subgenre>\t<year>\t<series>\t<players>
# system = folder of gamelists/ (arcade for the .mra files), file = key of the gamelist (file
# name without extension; .mra: file name in _Arcade), values separated by '|'. The genres
# are made the same with genres.ini, the companies with publishers.ini and the arcade cores
# with arcade_cores.ini (next to this script). Made from the gamelists, from the answers of
# ScreenScraper and ArcadeDB in .scrape_cache (genres by id, series) and from the .mra files:
# no network.

INDEX_VERSION = 'FEM1'
INDEX_SUMMARY = 1  # format of .scrape_cache/index_*.json


def read_table(name, section):
    """genres.ini, publishers.ini, arcade_cores.ini: lowercase key -> value"""
    cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=('=',), comment_prefixes=(';', '#'))
    try:
        cp.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), encoding='utf-8')
    except Exception as e:
        log('%s: %s' % (name, e))
        return {}
    return {k.strip().lower(): v.strip() for k, v in cp[section].items()} if cp.has_section(section) else {}


def clean_value(s):
    return ' '.join((s or '').replace('|', '/').split())


def companies(text, aliases):
    """'Mitchell (Capcom license)' -> ['Mitchell', 'Capcom'], 'Capcom / Arika' -> ['Capcom', 'Arika']"""
    out = []
    text = html.unescape(text or '')
    for m in re.finditer(r'\(([^()]*?)\s+licen[cs]e[^()]*\)', text, re.I):
        text += ' / ' + m.group(1)
    text = re.sub(r'\([^()]*\)', ' ', text)
    for part in re.split(r'\s*/\s*|\s+\+\s+', text):
        p = clean_value(part).strip(' ,.-')
        while True:
            q = re.sub(r'(?i)[ ,]+(co\.?,? ?ltd\.?|co\.|ltd\.?|inc\.?|corp\.?|corporation|limited|llc|gmbh|s\.?a\.?|s\.?r\.?l\.?|k\.?k\.?'
                       r'|u\.?s\.?a\.?|of america|america|europe|of europe|japan|u\.?k\.?)$', '', p).strip(' ,.-')
            if q == p:
                break
            p = q
        if not p or p.lower() in ('unknown', 'unlicensed', '<unknown>', 'various'):
            continue
        if p.lower().startswith('bootleg'):
            p = 'Bootleg'
        p = aliases.get(p.lower(), p)
        if p not in out:
            out.append(p)
    return out


def genre_lookup(name, table, english):
    """(genre, subgenre) of a source genre; english: the rest after the first part can be the subgenre"""
    name = clean_value(re.sub(r'^TTL \* ', '', name or ''))
    if not name:
        return None
    v = table.get(name.lower())
    if v is None and ' / ' in name:
        first, rest = name.split(' / ', 1)
        v = table.get(first.lower())
        if v is not None and english and ' / ' not in v:
            v += ' / ' + rest
    if v is None:
        return None
    g, _, sub = v.partition(' / ')
    return g.strip(), sub.strip()


def summary_cache(cache, kind, extract):
    """values of the API answers in .scrape_cache/<kind> (1.9 GB for 14000 games: read once,
    then only the new files): file name -> extract(json)"""
    path = os.path.join(cache, 'index_%s.json' % kind)
    src = os.path.join(cache, kind)
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if data.get('version') != INDEX_SUMMARY:
            data = {}
    except Exception:
        data = {}
    items = data.get('items', {})
    names = [n for n in os.listdir(src) if n.endswith('.json')] if os.path.isdir(src) else []
    todo = [n for n in names if n not in items]
    if todo:
        log('index: reading %d answers of %s in .scrape_cache (only the first time)' % (len(todo), kind))
    t0 = time.time()
    for i, n in enumerate(todo, 1):
        try:
            with open(os.path.join(src, n), encoding='utf-8') as f:
                items[n] = extract(json.load(f))
        except Exception:
            items[n] = None
        if i % 1000 == 0:
            log('   %d/%d (%.0f s)' % (i, len(todo), time.time() - t0))
    if todo:
        write_file(path, json.dumps({'version': INDEX_SUMMARY, 'items': items}))
    return items


def ss_extract(d):
    jeu = ((d or {}).get('response') or {}).get('jeu')
    if not jeu:
        return None
    genres = []
    for g in jeu.get('genres') or []:
        en = [n.get('text', '') for n in g.get('noms') or [] if n.get('langue') == 'en']
        genres.append([str(g.get('id', '')), str(g.get('parentid', '')), en[0] if en else ''])
    fam = ''
    for f in jeu.get('familles') or []:
        names = [n.get('text', '') for n in f.get('noms') or [] if n.get('text')]
        if names:
            fam = names[0]
            break
    return {'genres': genres, 'series': fam}


def adb_extract(d):
    if not isinstance(d, dict):
        return None
    return {'genre': d.get('genre') or '', 'series': d.get('serie') or ''}


def ss_genres(info, table, unknown):
    """[(genre, subgenre)] of a game of ScreenScraper, from its genres (English names, by id)"""
    names = {g[0]: g[2] for g in info.get('genres', [])}
    out = []
    for gid, parent, name in info.get('genres', []):
        if parent not in ('', '0') and parent in names and not name.startswith(names[parent]):
            r = genre_lookup(name, table, True) or genre_lookup(names[parent], table, True)
        else:
            r = genre_lookup(name, table, True)
        if r is None:
            if name:
                unknown[name] = unknown.get(name, 0) + 1
            continue
        out.append(r)
    # "Shoot'em Up" and "Shoot'em Up / Vertical": only the second one
    return [r for r in out if r[1] or not any(o[0] == r[0] and o[1] for o in out)]


def players_value(text):
    nums = [int(x) for x in re.findall(r'\d+', text or '')]
    if not nums or max(nums) < 1:
        return ''
    n = max(nums)
    return str(n) if n <= 4 else '5+'


def year_value(text):
    m = re.match(r'(\d{4})', (text or '').strip())
    return m.group(1) if m and 1970 <= int(m.group(1)) <= 2100 else ''


def core_name(rbf, cores):
    r = (rbf or '').strip().lower()
    r = re.sub(r'_\d{8}.*$', '', r)
    if r in cores:
        return cores[r]
    r = re.sub(r'_(mister|bazset)$', '', r)
    if r in cores:
        return cores[r]
    return re.sub(r'^arcade-', '', r)


INDEX_COLS = ('core', 'publisher', 'developer', 'genre', 'subgenre', 'year', 'series', 'players')


def index_rows(out, touched, root_mras, mc, root):
    """rows of the meta.tsv there that can stay: of the systems not scraped in this run
    (touched), with the gamelist older than meta.tsv and the same tables and scraper;
    arcade also with the same .mra files in _Arcade. System -> [rows as lists of strings:
    system, file, the columns of INDEX_COLS] (not parsed further: thousands of rows)"""
    keep = {}
    try:
        t = os.path.getmtime(out)
        here = os.path.dirname(os.path.abspath(__file__))
        if any(os.path.getmtime(os.path.join(here, f)) >= t for f in ('genres.ini', 'publishers.ini', 'arcade_cores.ini', os.path.basename(__file__))
               if os.path.exists(os.path.join(here, f))):
            return {}
        with open(out, encoding='utf-8') as f:
            if not f.readline().startswith(INDEX_VERSION + '\t'):
                return {}
            for line in f:
                p = line.rstrip('\n').split('\t')
                if len(p) == 2 + len(INDEX_COLS):
                    keep.setdefault(p[0], []).append(p)
    except (OSError, ValueError):
        return {}
    gl_dir = os.path.join(os.path.dirname(os.path.dirname(out)), 'gamelists')
    for sysname in list(keep):
        gl = os.path.join(gl_dir, sysname, 'gamelist.xml')
        try:
            ok = sysname not in touched and (not os.path.exists(gl) and sysname == 'arcade' or os.path.getmtime(gl) < t)
        except OSError:
            ok = False
        if ok and sysname == 'arcade':
            # the same .mra files, none changed
            before = mc.read
            for f in root_mras:
                mc.get(root, os.path.join('_Arcade', f))
            ok = mc.read == before and sorted(r[1] for r in keep[sysname]) == sorted(root_mras)
        if not ok:
            del keep[sysname]
    return keep


def build_index(args, touched=None):
    """touched: systems scraped in this run, the others can be copied from the meta.tsv
    there (index_rows()); None: all of them made again (--index)"""
    t0 = time.time()
    STATUS.set(True, step='index', system='', n=0, total=0)
    fe = args.frontier
    cache = os.path.join(fe, '.scrape_cache')
    genres_t = read_table('genres.ini', 'genres')
    aliases = {k: v for k, v in read_table('publishers.ini', 'publishers').items()}
    cores = read_table('arcade_cores.ini', 'cores')
    ss = summary_cache(cache, 'ss', ss_extract)
    adb = summary_cache(cache, adb_cache(args.lang), adb_extract)
    unknown = {}

    def cache_name(sysname, key):
        return re.sub(r'[^\w.()+-]', '_', '%s_%s' % (sysname, key))[:150] + '.json'

    names = {}  # companies() of the same text: once

    def company(text):
        if text not in names:
            names[text] = companies(text, aliases)
        return list(names[text])

    rows = []  # [system, file, {column: [values]}, ...] or a row of index_rows()
    gl_dir = os.path.join(fe, 'gamelists')
    systems = sorted(d for d in os.listdir(gl_dir) if os.path.isfile(os.path.join(gl_dir, d, 'gamelist.xml'))) if os.path.isdir(gl_dir) else []
    if 'arcade' not in systems and os.path.isdir(os.path.join(args.root, '_Arcade')):
        systems.append('arcade')
    # the .mra files of the list Arcade of Frontier: _Arcade only, not its subfolders
    base = os.path.join(args.root, '_Arcade')
    root_mras = sorted(f for f in os.listdir(base) if f.lower().endswith('.mra') and os.path.isfile(os.path.join(base, f))) if os.path.isdir(base) else []
    mc = mra_cache(args.root, cache)
    out = os.path.join(fe, '.cache', 'meta.tsv')
    keep = index_rows(out, touched, root_mras, mc, args.root) if touched is not None else {}
    for sysname in systems:
        if sysname in keep:
            rows += keep[sysname]
            continue
        gl = os.path.join(gl_dir, sysname, 'gamelist.xml')
        entries = GAMELISTS.get(gl) or read_gamelist(gl)
        items = []  # (file, gamelist entry, .mra info)
        if sysname == 'arcade':
            for f in root_mras:
                items.append((f, entries.get(f[:-4], {}), mc.get(args.root, os.path.join('_Arcade', f))))
        else:
            items = [(k, e, {}) for k, e in entries.items()]

        sys_rows = []
        for f, e, mra in items:
            key = f[:-4] if sysname == 'arcade' else f
            cols = {}
            cols['core'] = [core_name(mra['rbf'], cores)] if mra.get('rbf') else []
            cols['publisher'] = company(e.get('publisher') or mra.get('manufacturer', ''))
            cols['developer'] = company(e.get('developer') or mra.get('manufacturer', ''))
            gen = []
            si = ss.get(cache_name(sysname, key))
            ai = adb.get((mra.get('setname') or '') + '.json') if mra.get('setname') else None
            raw = e.get('genre', '')
            # the genre of the gamelist comes from the first source: ArcadeDB, then ScreenScraper
            if ai and ai.get('genre') and clean_value(ai['genre']) == clean_value(raw):
                r = genre_lookup(raw, genres_t, False)
                if r:
                    gen = [r]
                else:
                    unknown[raw] = unknown.get(raw, 0) + 1
            if not gen and si:
                gen = ss_genres(si, genres_t, unknown)
            if not gen and raw:
                r = genre_lookup(raw, genres_t, False) or genre_lookup(raw.split(' / ')[0], genres_t, False)
                if r:
                    gen = [r]
            if not gen and mra.get('category'):
                r = genre_lookup(mra['category'], genres_t, True)
                if r:
                    gen = [r]
            cols['genre'] = list(dict.fromkeys(g for g, _ in gen))
            cols['subgenre'] = list(dict.fromkeys('%s / %s' % (g, s) for g, s in gen if s))
            y = year_value(e.get('releasedate')) or year_value(mra.get('year'))
            cols['year'] = [y] if y else []
            series = (si or {}).get('series') or (ai or {}).get('series') or ''
            cols['series'] = [clean_value(series)] if clean_value(series) else []
            p = players_value(e.get('players') or mra.get('players'))
            cols['players'] = [p] if p else []
            sys_rows.append([sysname, f, cols, clean_value(e.get('name', '')).lower(), raw])

        # versions without their own answers in the cache (data copied from the version
        # scraped, share_versions()): the genre and the series of a version with the same name
        best = {}
        for r in sys_rows:
            if r[2]['genre'] and r[3] and (r[3], r[4]) not in best:
                best[(r[3], r[4])] = r[2]
        for r in sys_rows:
            b = best.get((r[3], r[4]))
            if b is None:
                continue
            for c in ('genre', 'subgenre', 'series'):
                if not r[2][c]:
                    r[2][c] = b[c]
        rows += sys_rows

    # one spelling for the same name ("SEGA", "Sega"): the most used one
    def values(r, c):
        return r[2][c] if isinstance(r[2], dict) else [v for v in r[2 + INDEX_COLS.index(c)].split('|') if v]

    for c in ('publisher', 'developer', 'series'):
        count = {}
        for r in rows:
            for v in values(r, c):
                count[v] = count.get(v, 0) + 1
        spelling = {}
        for v, n in sorted(count.items(), key=lambda x: (-x[1], x[0])):
            spelling.setdefault(v.lower(), v)
        for r in rows:
            vals = values(r, c)
            new = list(dict.fromkeys(spelling[v.lower()] for v in vals))
            if isinstance(r[2], dict):
                r[2][c] = new
            elif new != vals:
                r[2 + INDEX_COLS.index(c)] = '|'.join(clean_value(v) for v in new)

    mc.save()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cols = INDEX_COLS
    lines = ['%s\t%s\n' % (INDEX_VERSION, time.strftime('%Y-%m-%d %H:%M'))]
    for r in rows:
        if isinstance(r[2], dict):
            lines.append('\t'.join([r[0], r[1].replace('\t', ' ')] + ['|'.join(clean_value(v) for v in r[2][c]) for c in cols]) + '\n')
        else:
            lines.append('\t'.join(r) + '\n')
    write_file(out, ''.join(lines))
    with_genre = sum(1 for r in rows if values(r, 'genre'))
    log('index: %d games of %d systems (%d with a genre%s), %.0f s -> %s' % (
        len(rows), len(systems), with_genre, ', %d systems as they were' % len(keep) if keep else '', time.time() - t0, out))
    if unknown:
        log('index: genres not in genres.ini (games): ' + ', '.join('%s (%d)' % kv for kv in sorted(unknown.items(), key=lambda x: -x[1])))


def glob_dirs(path):
    return [os.path.join(path, d) for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))] if os.path.isdir(path) else []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default='/media/fat', help='root of the SD card (default /media/fat)')
    ap.add_argument('--frontier', '--frontend', dest='frontier', help='Frontier\'s folder (default <root>/frontier)')
    ap.add_argument('--arcade', action='store_true', help='.mra games of _Arcade')
    ap.add_argument('--system', action='append', default=[], help='folder of games/ (repeatable)')
    ap.add_argument('--all-systems', action='store_true', help='all the folders of games/ known to systems.ini')
    ap.add_argument('--category', action='append', default=[], help='folders of games/ of the systems of a category of systems.ini: Console, Handheld, Computer, Other; repeatable')
    ap.add_argument('--all-files', action='store_true', help='all the files of the systems, also hacks, translations and copies (default: as the list of Frontier, one game per title)')
    ap.add_argument('--sources', default='ss,adb,libretro', help='sources in order (default ss,adb,libretro)')
    ap.add_argument('--lang', default='en', help='language of descriptions and genres, e.g. en, it, fr, de, es (default en)')
    ap.add_argument('--max-size', type=int, default=640, help='longest side of the pictures with Pillow (default 640, 0 = original)')
    ap.add_argument('--fanart', action='store_true', help='also download the fanart (large backgrounds, they take space)')
    ap.add_argument('--video', action='store_true', help='also download the videos (mp4, played by Frontier)')
    ap.add_argument('--media', help='only these pictures and videos, e.g. box,snap,video (box, snap, title, marquee, fanart, video; "none" = no media); instead of the default + --fanart/--video')
    ap.add_argument('--no-text', action='store_true', help='do not write the data (descriptions, genres...): only the pictures and videos chosen')
    ap.add_argument('--status', help='file with the progress (key=value lines), for Frontier')
    ap.add_argument('--mjv', action='store_true', help='convert the downloaded videos to .mjv, lighter to play (needs ffmpeg: on a PC)')
    ap.add_argument('--convert-videos', action='store_true', help='convert to .mjv the mp4 files already in media/*/video (needs ffmpeg)')
    ap.add_argument('--video-fps', type=float, default=15, help='frames per second of the .mjv files (default 15)')
    ap.add_argument('--video-width', type=int, default=320, help='width of the .mjv files (default 320)')
    ap.add_argument('--video-seconds', type=int, default=30, help='maximum length of the .mjv files in seconds (default 30)')
    ap.add_argument('--keep-mp4', action='store_true', help='keep the mp4 files after the conversion')
    ap.add_argument('--groups', action='store_true', help='only the groups of titles (Thunder Force IV = Lightening Force) from the MAME lists, for --system/--all-systems')
    ap.add_argument('--box-regions', help='preferred regions for the box art (ScreenScraper), e.g. jp or jp,us; also in scraper.ini: [scraper] box_regions = jp')
    ap.add_argument('--systems-info', action='store_true', help='only the data of the systems (Wikipedia: description, maker, year, hardware) for --system/--category/--all-systems; also done with the games, unless --no-text')
    ap.add_argument('--dedupe-media', action='store_true', help='only (no network): the arcade versions whose media are identical to those of their main game use its files and their copies are deleted; with --dry-run it only says what')
    ap.add_argument('--dry-run', action='store_true', help='with --dedupe-media: nothing is changed or deleted')
    ap.add_argument('--index', action='store_true', help='only the data of Frontier\'s "Lists" (.cache/meta.tsv) from the gamelists and the cache, no network; also done at the end of every run')
    ap.add_argument('--game', action='append', default=[], help='only this game of the system (file name without extension, '
                    'repeatable): asked again to the sources, its data and pictures downloaded again')
    ap.add_argument('--force', action='store_true', help='download again also what is already there')
    ap.add_argument('--retry-missing', action='store_true', help='try again now the games not found in the last %d days (otherwise skipped)' % NOTFOUND_DAYS)
    ap.add_argument('--refresh-data', action='store_true', help='write again the data (names, descriptions, genres...) in the language of --lang, without downloading again the pictures already there')
    ap.add_argument('--limit', type=int, default=0, help='at most N games per system (tests)')
    ap.add_argument('--no-crc', action='store_true', help='do not compute the CRC of the files (faster, ScreenScraper less precise)')
    ap.add_argument('--delay', type=float, default=0.3, help='seconds between requests (default 0.3)')
    ap.add_argument('--ss-user'), ap.add_argument('--ss-password')
    ap.add_argument('--ss-devid'), ap.add_argument('--ss-devpassword')
    args = ap.parse_args()

    args.frontier = args.frontier or os.path.join(args.root, 'frontier')
    if args.media is not None:
        args.types = [t for t in (x.strip().lower() for x in args.media.split(',')) if t in MEDIA_TYPES]
        args.video = 'video' in args.types
    else:
        args.types = [t for t in MEDIA_TYPES if t not in OPTIONAL_TYPES or getattr(args, t)]
    STATUS.path = args.status
    if args.game:
        args.force = True  # a game asked by name: all again
    args.sources = [s.strip() for s in args.sources.split(',') if s.strip()]

    # credentials: command line or <frontier>/scraper.ini, section [screenscraper]
    cp = configparser.ConfigParser(interpolation=None)
    cp.read([os.path.join(args.frontier, 'scraper.ini'),
             os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scraper.ini')], encoding='utf-8')
    ss = cp['screenscraper'] if cp.has_section('screenscraper') else {}
    # developer credentials of Frontier (they name the program, not the user): the
    # ones of the command line or of scraper.ini win
    dev = ss_dev()
    cred = {
        'user': args.ss_user or ss.get('user'), 'password': args.ss_password or ss.get('password'),
        'devid': args.ss_devid or ss.get('devid') or dev[0],
        'devpassword': args.ss_devpassword or ss.get('devpassword') or dev[1],
    }
    if not all(cred.values()):
        if 'ss' in args.sources:
            log('ScreenScraper: credentials missing, source skipped')
        cred = None
        args.sources = [s for s in args.sources if s != 'ss']

    if args.video and args.mjv and not shutil.which('ffmpeg'):
        log('ffmpeg not found: the videos stay in mp4 (Frontier plays them too)')
    if not Image:
        log('Pillow not found: pictures saved as downloaded (PNG/JPEG only)')

    if args.dedupe_media:
        dedupe_media(args, args.dry_run)
        return

    http = Http(args.delay)

    cats = {}
    exts = read_systems_ini(os.path.join(args.frontier, 'systems.ini'), cats)
    folders = list(args.system)
    gdir = os.path.join(args.root, 'games')
    if args.all_systems:
        folders += sorted(d for d in os.listdir(gdir) if d.lower() in exts and os.path.isdir(os.path.join(gdir, d)))
    for c in args.category:
        want = CATEGORY_NAMES.get(c.lower())
        if not want:
            log('unknown category: %s (Console, Handheld, Computer, Other)' % c)
            continue
        folders += sorted(d for d in os.listdir(gdir) if want in cats.get(d.lower(), ())
                          and os.path.isdir(os.path.join(gdir, d)))

    # order of the regions for the version to start: regions= of frontier.ini
    regions = ['usa', 'world', 'europe', 'japan']
    try:
        with open(os.path.join(args.frontier, 'frontier.ini'), encoding='utf-8') as f:
            for line in f:
                m = re.match(r'\s*regions\s*=\s*(.+)', line)
                if m:
                    regions = [x.strip().lower() for x in m.group(1).split(',') if x.strip()] or regions
                m = re.match(r'\s*exclude_dirs\s*=(.*)', line)
                if m:
                    EXCLUDE_DIRS.clear()
                    EXCLUDE_DIRS.update(x.strip().lower() for x in m.group(1).split(',') if x.strip())
    except OSError:
        pass
    SS_PREF[:] = [SS_REGION[r] for r in regions if r in SS_REGION]
    box = args.box_regions or (cp['scraper'].get('box_regions', '') if cp.has_section('scraper') else '')
    for r in (x.strip().lower() for x in box.split(',') if x.strip()):
        r = SS_REGION.get(r, r)  # japan -> jp, or already the ScreenScraper code
        if r not in SS_BOX:
            SS_BOX.append(r)
    if SS_BOX:
        log('box art: first %s' % ', '.join(SS_BOX))
    todo = list(dict.fromkeys(folders))
    # the data of the systems (Wikipedia), before their games
    if args.systems_info or (todo and not args.no_text and not args.groups and not args.game):
        scrape_systems(args, http, todo)
        if args.systems_info:
            folders, todo, args.arcade = [], [], False
    arcade = 1 if args.arcade else 0
    STATUS.set(True, systems=len(todo) + arcade, done=0, updated=0, notfound=0)
    cache = os.path.join(args.frontier, '.scrape_cache')
    if args.arcade:
        STATUS.set(True, system='arcade', step='list', n=0, total=0)
        t0 = time.time()
        games = list_arcade(args.root, cache)
        log('arcade: list %.1f s (%d .mra read, the others from the cache)' % (time.time() - t0, mra_cache(args.root, cache).read))
        scrape(args, http, games, 'arcade', cred)
    for sn, folder in enumerate(todo, 1):
        STATUS.set(True, system=folder.lower(), step='list', n=0, total=0, done=sn - 1 + arcade)
        patterns = exts.get(folder.lower())
        if not patterns:
            log('%s: folder not in systems.ini, skipped' % folder)
            continue
        if args.groups:
            make_groups(args, http, folder, patterns)
            continue
        if folder.lower() in ROMSET_DIRS:
            games = list_romsets(args.root, folder, regions)
        elif args.all_files:
            games = list_system(args.root, folder, patterns, not args.no_crc)
        else:
            games = list_titles(args.root, folder, patterns, not args.no_crc, regions)
            if args.game and not chosen(games, args.game):
                # a file of the folders that is not in the list by title (a hack, a copy)
                games = list_system(args.root, folder, patterns, not args.no_crc)
        if games:
            scrape(args, http, games, folder.lower(), cred)

    if args.convert_videos:
        if not shutil.which('ffmpeg'):
            log('ffmpeg not found: the videos can not be converted')
        for sysdir in sorted(glob_dirs(os.path.join(args.frontier, 'media'))):
            convert_videos(args, os.path.join(sysdir, 'video'))

    # the data of Frontier's "Lists" from the gamelists just written
    if args.index or ((args.arcade or folders) and not args.groups):
        touched = None if args.index else {f.lower() for f in todo} | ({'arcade'} if args.arcade else set())
        build_index(args, touched)

    if not args.arcade and not folders and not args.convert_videos and not args.index and not args.systems_info:
        ap.print_help()


def stop(signum, frame):
    raise KeyboardInterrupt


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, stop)  # Frontier stops it so
    try:
        main()
        STATUS.set(True, state='done', step='', done=STATUS.data.get('systems', 0))
    except KeyboardInterrupt:
        log('stopped: what was downloaded is saved, the next run resumes from there')
        STATUS.set(True, state='stopped')
        sys.exit(130)
    except Exception as ex:
        STATUS.set(True, state='error', error='%s: %s' % (type(ex).__name__, ex))
        raise
