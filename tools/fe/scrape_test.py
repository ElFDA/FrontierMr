#!/usr/bin/env python3
"""frontier/scraper/fe_scrape.py --arcade on a simulated SD card, without network (the
answers of ScreenScraper, ArcadeDB and libretro come from a stub)."""
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import urllib.parse
import zlib

SCRAPER = Path(__file__).parent / 'sd/frontier/scraper/fe_scrape.py'


def png(seed):
    """a real 16x16 PNG (more than 100 bytes, Pillow can open it)"""
    raw = b''.join(b'\0' + bytes((seed * 7 + x * 13 + y * 29) & 255 for x in range(48)) for y in range(16))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 16, 16, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def mra(name, setname, zips):
    return ('<misterromdescription>\n  <name>%s</name>\n  <setname>%s</setname>\n  <rbf>jtcps1</rbf>\n'
            '  <year>1991</year>\n  <manufacturer>Capcom</manufacturer>\n  <rom index="0" zip="%s" md5="none"/>\n'
            '</misterromdescription>\n' % (name, setname, '|'.join(z + '.zip' for z in zips)))


class Net:
    """answers by URL: ss = {setname: game name} (others: 404), media and ArcadeDB empty"""

    def __init__(self, ss):
        self.ss = ss
        self.urls = []
        self.down = False  # network errors

    def get(self, http, url, tries=3, ua=None):
        self.urls.append(url)
        http.status = None
        if self.down:
            http.trouble = True
            return None
        if 'jeuInfos.php' in url:
            rom = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)['romnom'][0][:-4]
            if rom not in self.ss:
                http.status = 404
                return None
            http.status = 200
            jeu = {'noms': [{'region': 'wor', 'text': self.ss[rom]}],
                   'synopsis': [{'langue': 'en', 'text': 'About ' + self.ss[rom]}],
                   'medias': [{'type': 'ss', 'region': 'wor', 'url': 'https://media.test/ss/%s.png' % rom},
                              {'type': 'box-2D', 'region': 'wor', 'url': 'https://media.test/box/%s.png' % rom}]}
            return json.dumps({'response': {'jeu': jeu}}).encode()
        if 'media.test' in url:
            http.status = 200
            return png(len(url))
        if 'arcadeitalia' in url:
            http.status = 200
            return json.dumps({'result': []}).encode()
        http.status = 404
        return None

    def asked(self, text):
        return [u for u in self.urls if text in urllib.parse.unquote_plus(u)]


class ScrapeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.arcade = self.root / '_Arcade'
        (self.root / 'frontier').mkdir()
        self.add('Main Game', 'game', ['game'])
        self.add('Other', 'other', ['other'])
        self.add('_alternatives/_Main Game/Main Game (Japan)', 'gamej', ['gamej', 'game'])
        self.add('_alternatives/_Lonely/Lonely (Bootleg)', 'lonely', ['lonely'])
        # neogeo.zip in more than 3 .mra: a BIOS, not a reason to join two games
        for i in range(4):
            self.add('Neo %d' % i, 'neo%d' % i, ['neo%d' % i, 'neogeo'])
        self.add('_alternatives/_Neo X/Neo X (Hack)', 'neox', ['neox', 'neogeo'])
        self.net = Net({'game': 'The Main Game', 'lonely': 'Lonely', 'neo0': 'Neo Zero'})

    def add(self, rel, setname, zips):
        path = self.arcade / (rel + '.mra')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(mra(path.stem, setname, zips))

    def run_scraper(self, *extra):
        """a fresh copy of the module for each run (its caches in memory start empty)"""
        spec = importlib.util.spec_from_file_location('fe_scrape_%d' % len(self.net.urls), SCRAPER)
        F = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(F)
        net = self.net
        F.Http.get = lambda http, url, tries=3, ua=None: net.get(http, url, tries, ua)
        self.F = F
        argv = sys.argv
        sys.argv = ['fe_scrape.py', '--root', str(self.root), '--arcade', '--media', 'box,snap', '--delay', '0',
                    '--ss-user', 'u', '--ss-password', 'p', '--ss-devid', 'd', '--ss-devpassword', 'p'] + list(extra)
        out = []
        F.log = lambda *a: out.append(' '.join(str(x) for x in a))
        try:
            F.main()
        finally:
            sys.argv = argv
        self.out = '\n'.join(out)
        return F

    def gamelist(self):
        return self.F.read_gamelist(str(self.root / 'frontier/gamelists/arcade/gamelist.xml'))

    def notfound(self):
        path = self.root / 'frontier/.scrape_cache/notfound_arcade.tsv'
        return [l.split('\t')[0] for l in path.read_text().splitlines()] if path.exists() else []

    def test_alternative_takes_the_main_game(self):
        self.run_scraper()
        e = self.gamelist()
        alt = e['Main Game (Japan)']
        self.assertEqual('Main Game (Japan)', alt['name'])  # its own name
        self.assertEqual('About The Main Game', alt['desc'])
        # media: the files of the main game (.jpg with Pillow)
        self.assertRegex(alt['image'], r'^\.\./\.\./media/arcade/snap/Main Game\.(png|jpg)$')
        self.assertRegex(alt['thumbnail'], r'^\.\./\.\./media/arcade/box/Main Game\.(png|jpg)$')
        self.assertEqual('./Main Game (Japan).mra', alt['path'])
        self.assertEqual([], self.net.asked('gamej.zip'))  # never asked
        self.assertEqual([], list((self.root / 'frontier/media/arcade/snap').glob('Main Game (Japan).*')))
        # an alternative without a main game: on its own
        self.assertEqual('Lonely', e['Lonely (Bootleg)']['name'])
        self.assertTrue(self.net.asked('romnom=lonely.zip'))

    def test_versions_of_a_core_are_one_game(self):
        # Heavy Unit style: the versions of a core are not in _alternatives
        self.add('_Core/_Group/Group Game (World)', 'grp', ['grp'])
        self.add('_Core/_Group/Group Game (Japan)', 'grpj', ['grpj', 'grp'])
        self.add('_Core/_Group/Group Game (US)', 'grpu', ['grpu', 'grp'])
        self.add('_alternatives/_Group Game/Group Game (Bootleg)', 'grpb', ['grpb', 'grpj'])
        self.net.ss['grp'] = 'The Group Game'
        F = self.run_scraper()
        games = {g.key: g for g in F.list_arcade(str(self.root), str(self.root / 'frontier/.scrape_cache'))}
        self.assertIsNone(games['Group Game (World)'].main)
        self.assertEqual('Group Game (World)', games['Group Game (Japan)'].main)
        self.assertEqual('Group Game (World)', games['Group Game (US)'].main)
        self.assertEqual('Group Game (World)', games['Group Game (Bootleg)'].main)  # through Japan
        self.assertIsNone(games['Main Game'].main)
        self.assertIsNone(games['Neo 0'].main)
        e = self.gamelist()
        self.assertEqual('Group Game (US)', e['Group Game (US)']['name'])
        self.assertEqual('About The Group Game', e['Group Game (US)']['desc'])
        self.assertEqual([], self.net.asked('grpu.zip'))
        self.assertEqual([], self.net.asked('grpj.zip'))

    def test_dedupe_media_of_the_versions(self):
        self.run_scraper()
        snap, box = self.root / 'frontier/media/arcade/snap', self.root / 'frontier/media/arcade/box'
        main_snap = next(snap.glob('Main Game.*'))
        ext = main_snap.suffix
        # the Japanese version has its own copies: the snap identical, the box different
        (snap / ('Main Game (Japan)' + ext)).write_bytes(main_snap.read_bytes())
        (box / ('Main Game (Japan)' + ext)).write_bytes(b'something else')
        gl = self.root / 'frontier/gamelists/arcade/gamelist.xml'
        # as after scraping the version on its own: its entry uses its own files
        entries = self.gamelist()
        entries['Main Game (Japan)']['image'] = '../../media/arcade/snap/Main Game (Japan)' + ext
        entries['Main Game (Japan)']['thumbnail'] = '../../media/arcade/box/Main Game (Japan)' + ext
        self.F.write_gamelist(str(gl), entries)
        before = gl.read_text()
        self.run_scraper('--dedupe-media', '--dry-run')
        self.assertIn('1 files', self.out)
        self.assertTrue((snap / ('Main Game (Japan)' + ext)).exists())
        self.assertEqual(before, gl.read_text())
        self.run_scraper('--dedupe-media')
        self.assertFalse((snap / ('Main Game (Japan)' + ext)).exists())
        self.assertTrue((box / ('Main Game (Japan)' + ext)).exists())  # different: stays
        self.assertTrue(main_snap.exists())
        e = self.gamelist()['Main Game (Japan)']
        self.assertEqual('../../media/arcade/snap/' + main_snap.name, e['image'])
        self.assertTrue(e['thumbnail'].endswith('Main Game (Japan)' + ext))
        self.run_scraper('--dedupe-media')
        self.assertIn('0 files', self.out)

    def test_bios_zip_does_not_join(self):
        F = self.run_scraper()
        games = {g.key: g for g in F.list_arcade(str(self.root), str(self.root / 'frontier/.scrape_cache'))}
        self.assertEqual('Main Game', games['Main Game (Japan)'].main)
        self.assertIsNone(games['Neo X (Hack)'].main)
        self.assertIsNone(games['Lonely (Bootleg)'].main)
        self.assertIsNone(games['Main Game'].main)

    def test_not_found_remembered(self):
        self.run_scraper()
        self.assertIn('Other', self.notfound())
        self.assertNotIn('Main Game', self.notfound())
        self.net.urls.clear()
        self.run_scraper()
        self.assertEqual([], self.net.asked('romnom=other.zip'))
        self.assertIn('0 to scrape', self.out)
        # more types asked: tried again
        self.run_scraper('--media', 'box,snap,title')
        self.assertTrue(self.net.asked('romnom=other.zip'))
        self.net.urls.clear()
        self.run_scraper('--retry-missing', '--media', 'box,snap,title')
        self.assertTrue(self.net.asked('romnom=other.zip'))

    def test_not_found_old_tried_again(self):
        self.run_scraper()
        path = self.root / 'frontier/.scrape_cache/notfound_arcade.tsv'
        path.write_text(path.read_text().replace(self.F.datetime.date.today().isoformat(), '2020-01-01'))
        self.net.urls.clear()
        self.run_scraper()
        self.assertTrue(self.net.asked('romnom=other.zip'))

    def test_network_errors_not_remembered(self):
        self.net.down = True
        self.run_scraper()
        self.assertEqual([], self.notfound())
        self.net.down = False
        self.net.urls.clear()
        self.run_scraper()
        self.assertTrue(self.net.asked('romnom=game.zip'))
        self.assertEqual('The Main Game', self.gamelist()['Main Game']['name'])

    def test_mra_files_read_once(self):
        F = self.run_scraper()
        self.assertEqual(9, F.mra_cache(str(self.root), '').read)
        F = self.run_scraper()
        self.assertEqual(0, F.mra_cache(str(self.root), '').read)
        self.add('Other', 'other2', ['other2'])
        os.utime(self.arcade / 'Other.mra', (1, 1))
        F = self.run_scraper()
        self.assertEqual(1, F.mra_cache(str(self.root), '').read)

    def test_arcadedb_only_new_names_in_batches(self):
        for i in range(30):
            self.add('New %02d' % i, 'z%02d' % i if i % 2 else 'a%02d' % i, ['n%02d' % i])
        self.run_scraper()
        first = len(self.net.asked('arcadeitalia'))
        self.assertEqual(2, first)  # 39 names not in the cache: 2 batches of 25
        self.net.urls.clear()
        self.add('Newer', 'm00', ['m00'])
        self.run_scraper()
        asked = self.net.asked('arcadeitalia')
        self.assertEqual(1, len(asked))
        self.assertIn('game_name=m00', asked[0])  # only the new game, not the ones skipped

    def status(self):
        return dict(l.split('=', 1) for l in (self.root / 'status.txt').read_text().splitlines())

    def test_totals_for_frontier(self):
        self.run_scraper('--status', str(self.root / 'status.txt'))
        st = self.status()
        self.assertEqual(('3', '5'), (st['updated'], st['notfound']))  # Main Game, Lonely, Neo 0; Other, Neo 1-3, Neo X
        self.run_scraper('--status', str(self.root / 'status.txt'))
        st = self.status()
        self.assertEqual(('0', '5'), (st['updated'], st['notfound']))  # nothing new, 5 skipped

    def test_media_found_whatever_the_case(self):
        # on the SD card (exFAT) "Main Game" and "main game" are the same file
        self.run_scraper()
        self.add('_MeatCores/main game', 'game', ['game'])
        self.net.urls.clear()
        self.run_scraper()
        self.assertEqual([], self.net.asked('media.test'))

    def test_one_game(self):
        self.run_scraper()
        self.net.ss['game'] = 'The Main Game Deluxe'
        self.net.urls.clear()
        self.run_scraper('--game', 'main game')  # any case
        # only that game, asked again although it was in the cache, pictures downloaded again
        self.assertEqual(1, len(self.net.asked('jeuInfos.php')))
        self.assertTrue(self.net.asked('romnom=game.zip'))
        self.assertEqual(2, len(self.net.asked('media.test')))
        e = self.gamelist()
        self.assertEqual('The Main Game Deluxe', e['Main Game']['name'])
        self.assertEqual('Main Game (Japan)', e['Main Game (Japan)']['name'])  # its alternative: own name
        self.assertEqual('About The Main Game Deluxe', e['Main Game (Japan)']['desc'])  # data again from it
        self.assertIn('arcade: 2 games', self.out)
        # a game not found before: tried again; a name that is not there: nothing asked
        self.net.urls.clear()
        self.run_scraper('--game', 'Other')
        self.assertTrue(self.net.asked('romnom=other.zip'))
        self.net.urls.clear()
        self.run_scraper('--game', 'Nothing')
        self.assertEqual([], self.net.asked('jeuInfos.php'))
        self.assertIn('Nothing not found among the games', self.out)

    def test_one_game_by_title(self):
        # NES by title: Frontier passes the names of the versions it knows
        (self.root / 'frontier/systems.ini').write_text('[NES]\nfolders=NES\nslot0=Cart,0,1,nes\n')
        nes = self.root / 'games/NES'
        nes.mkdir(parents=True)
        for n in ('Zelda (USA).nes', 'Zelda (Japan).nes', 'Mario (USA).nes', 'My Hack.nes'):
            (nes / n).write_bytes(b'NES\x1a' + n.encode() * 10)
        self.run_scraper('--system', 'NES', '--game', 'Zelda (Japan)')
        self.assertIn('nes: 1 games', self.out)
        self.assertTrue(self.net.asked('Zelda (USA).nes'))  # the version it launches
        self.assertEqual([], self.net.asked('Mario'))
        # a file that is not in the list by title (Folders): all the files
        self.net.urls.clear()
        self.run_scraper('--system', 'NES', '--game', 'My Hack')
        self.assertTrue(self.net.asked('My Hack.nes'))
        self.assertEqual([], self.net.asked('Zelda'))

    def test_unchanged_gamelist_not_written(self):
        self.run_scraper()
        path = self.root / 'frontier/gamelists/arcade/gamelist.xml'
        os.utime(path, (1, 1))
        self.run_scraper()
        self.assertEqual(1, path.stat().st_mtime)

    def test_index_keeps_systems_not_scraped(self):
        gl = self.root / 'frontier/gamelists/nes/gamelist.xml'
        gl.parent.mkdir(parents=True)
        gl.write_text('<gameList><game><path>./Zelda.nes</path><name>Zelda</name><genre>Adventure</genre>'
                      '<publisher>Nintendo</publisher></game></gameList>')
        os.utime(gl, (1, 1))
        self.run_scraper()
        self.run_scraper('--index')  # all made again
        self.assertNotIn('as they were', self.out)
        meta = (self.root / 'frontier/.cache/meta.tsv').read_text()
        self.assertIn('nes\tZelda\t', meta)
        self.run_scraper()  # arcade only: nes copied
        self.assertIn('1 systems as they were', self.out)
        self.assertEqual(meta.split('\n', 1)[1], (self.root / 'frontier/.cache/meta.tsv').read_text().split('\n', 1)[1])
        os.utime(gl)  # gamelist changed: made again
        self.run_scraper()
        self.assertNotIn('as they were', self.out)


if __name__ == '__main__':
    unittest.main()
