#!/usr/bin/env python3
"""Run offline against an actual Downloader ZIP or source directory.

Usage: python3 tools/fe/protect_updates_downloader_test.py <Downloader ZIP or src>
Only HTTP responses are replaced with fixtures; all update and deletion code runs.
The SD holds a test distribution_mister and Frontier's database as a drop-in
(built by make_db.py from a package ZIP, as a release); frontier/guard.sh and
protect_updates.py are the real ones.
"""
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

if len(sys.argv) < 2:
    raise SystemExit(__doc__)
ARCHIVE = str(Path(sys.argv[1]).resolve())
HERE = Path(__file__).resolve().parent
PROTECT = HERE / 'sd/frontier/protect_updates.py'
GUARD = HERE / 'sd/frontier/guard.sh'
sys.path.insert(0, str(HERE))
import make_db  # noqa: E402

OFFICIAL = b'\x7fELF-official-MiSTer'
FRONTIER_1, FRONTIER_2 = b'\x7fELF-frontier-1', b'\x7fELF-frontier-2'


def run_downloader(root):
    sys.path.insert(0, ARCHIVE)
    from downloader.http_gateway import HttpGateway
    from downloader.main import main, read_env

    class Response(io.BytesIO):
        status = 200

    @contextlib.contextmanager
    def offline_open(self, url, *args, **kwargs):
        assert url.startswith('https://fixture.invalid/'), url
        data = (root / 'server' / url.split('https://fixture.invalid/')[1]).read_bytes()
        yield url, Response(data)

    HttpGateway.open = offline_open
    env = read_env('offline-probe')
    env.update(DOWNLOADER_INI_PATH=str(root / 'downloader.ini'),
               DEFAULT_BASE_PATH=str(root), FORCED_BASE_PATH=str(root),
               SKIP_FREE_SPACE_CHECKS='true', ALLOW_REBOOT='0', UPDATE_LINUX='false',
               DEBUG='true', HTTP_PROXY='', HTTPS_PROXY='')
    return main(env, time.monotonic(), ['downloader'])


def fixture(root, registered):
    """SD after an older Frontier install: filter with !menu, Frontier's menu in the root."""
    server = root / 'server'
    server.mkdir()
    files = {}
    for name, tags, data in [('MiSTer', ['essential', 'misterfirmware'], OFFICIAL),
                             ('menu.rbf', ['essential', 'cores', 'menu'], b'official-menu'),
                             ('_Console/Test_20261022.rbf', ['console'], b'new-core')]:
        (server / Path(name).name).write_bytes(data)
        files[name] = dict(hash=make_db.hashlib.md5(data).hexdigest(), size=len(data), tags=tags,
                           path='system' if '/' not in name else 'standard',
                           url='https://fixture.invalid/' + Path(name).name)
    db = dict(v=1, db_id='distribution_mister', timestamp=int(time.time()),
              files=files, folders={'_Console': {'tags': ['console']}})
    (server / 'db.json').write_text(json.dumps(db))

    # Frontier's published tree and database (version 2)
    tree = server / 'frontier_tree'
    (tree / 'frontier/bin').mkdir(parents=True)
    (tree / 'frontier/bin/MiSTer').write_bytes(FRONTIER_2)
    (tree / 'frontier/bin/menu.rbf').write_bytes(b'frontier-menu-2')
    (tree / 'frontier/frontier.ini').write_text('theme=default\n')
    shutil.copy2(GUARD, tree / 'frontier/guard.sh')
    shutil.copy2(PROTECT, tree / 'frontier/protect_updates.py')
    (tree / 'frontier/downloader_frontiermr.ini').write_text(
        '[frontiermr]\ndb_url = https://fixture.invalid/frontier.json\n')
    (tree / 'Scripts').mkdir()
    (tree / 'Scripts/frontier_on_off.sh').write_text('#!/bin/sh\n')
    # as a package ZIP: the database takes every file from it (one archive)
    with make_db.zipfile.ZipFile(server / 'Frontier.zip', 'w', make_db.zipfile.ZIP_DEFLATED) as z:
        for path in sorted(tree.rglob('*')):
            if path.is_file():
                rel = path.relative_to(tree).as_posix()
                z.write(path, ('SD/frontier_setup/' if rel.startswith('frontier/') else 'SD/') + rel)
        z.writestr('INSTALL.txt', 'not on the SD card\n')
    make_db.write(make_db.build(server / 'Frontier.zip', 'https://fixture.invalid/Frontier.zip'), server / 'frontier.json')

    # the SD: Frontier 1 installed by an older package
    (root / '_Console').mkdir()
    old = '_Console/Test_20261021.rbf'
    (root / old).write_bytes(b'old')
    (root / 'linux').mkdir()
    (root / 'linux/user-startup.sh').write_text('#!/bin/sh\n')
    (root / 'frontier/bin').mkdir(parents=True)
    for path in ('guard.sh', 'protect_updates.py', 'downloader_frontiermr.ini'):
        shutil.copy2(tree / 'frontier' / path, root / 'frontier' / path)
    (root / 'frontier/frontier.ini').write_text('theme=user\n')
    (root / 'frontier/bin/MiSTer').write_bytes(FRONTIER_1)
    (root / 'frontier/bin/menu.rbf').write_bytes(b'frontier-menu-1')
    (root / 'MiSTer').write_bytes(FRONTIER_1)
    (root / 'menu.rbf').write_bytes(b'frontier-menu-1')
    cache = root / 'Scripts/.config/downloader'
    cache.mkdir(parents=True)
    owned = {old: dict(hash='0' * 32, size=3)}
    if registered:
        owned.update({'MiSTer': files['MiSTer'], 'menu.rbf': files['menu.rbf']})
    store = {'migration_version': 13, 'internal': True, 'db_fingerprints': {},
             'dbs': {'distribution_mister': dict(files=owned, folders={'_Console': {}}, zips={}, base_path=str(root))}}
    (cache / 'downloader.json').write_text(json.dumps(store))
    write_ini(root, '!misterfirmware !menu')


def write_ini(root, filter_value):
    (root / 'downloader.ini').write_text(
        '[MiSTer]\nupdate_linux=false\nallow_reboot=0\nstorage_priority=off\nfile_checking=verify_integrity\n\n'
        '[distribution_mister]\ndb_url=https://fixture.invalid/db.json\n' +
        ('filter=%s\n' % filter_value if filter_value is not None else ''))


def update(root, label):
    result = subprocess.run([sys.executable, __file__, ARCHIVE, str(root)], text=True, capture_output=True, timeout=60)
    (root / (label + '.log')).write_text(result.stdout + result.stderr)
    if result.returncode:
        print((result.stdout + result.stderr)[-2500:])
    assert result.returncode == 0, label
    assert (root / '_Console/Test_20261022.rbf').exists(), label
    assert not (root / '_Console/Test_20261021.rbf').exists(), label


def script(*args, root):
    result = subprocess.run(list(args), text=True, capture_output=True,
                            env=dict(PATH='/usr/bin:/bin', FRONTIER_SD_ROOT=str(root)))
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def protect(root, *args):
    return script(sys.executable, str(root / 'frontier/protect_updates.py'), '--root', str(root), *args, root=root)


def guard(root):
    script('sh', str(root / 'frontier/guard.sh'), 'stop', root=root)


def read(root, name):
    path = root / name
    return path.read_bytes() if path.exists() else None


def check(root, label, expected):
    got = {name: read(root, name) for name in expected}
    short = {name: value if value is None or len(value) < 48 else value[:40] + b'...' for name, value in got.items()}
    print(label, 'OK' if got == expected else 'FAILED', short, flush=True)
    assert got == expected, (label, got, expected)


def scenario(name, registered=False):
    root = Path(tempfile.mkdtemp(prefix='frontier-updater-' + name + '-'))
    fixture(root, registered)
    print('==', name, root, flush=True)
    return root


if __name__ == '__main__':
    if len(sys.argv) > 2:
        raise SystemExit(run_downloader(Path(sys.argv[2])))

    # Older protection, filter only: the registered firmware is deleted (the reason for all this).
    root = scenario('filter_only', registered=True)
    update(root, 'run')
    check(root, 'filter only deletes', {'MiSTer': None})

    # The device as it is now: protect_updates.py migrates it, update_all updates
    # official menu, cores and Frontier, and keeps MiSTer.
    root = scenario('protected')
    protect(root)
    assert 'filter=!misterfirmware\n' in (root / 'downloader.ini').read_text()
    update(root, 'run1')
    check(root, 'after update', {
        'MiSTer': FRONTIER_1, 'menu.rbf': b'official-menu',
        'frontier/bin/MiSTer': FRONTIER_2, 'frontier/bin/menu.rbf': b'frontier-menu-2',
        'frontier/frontier.ini': b'theme=user\n',
        'downloader_frontiermr.ini': (root / 'frontier/downloader_frontiermr.ini').read_bytes()})
    guard(root)
    check(root, 'guard installs Frontier 2', {'MiSTer': FRONTIER_2})
    update(root, 'run2')
    check(root, 'second update', {'MiSTer': FRONTIER_2, 'menu.rbf': b'official-menu',
                                  'frontier/bin/MiSTer': FRONTIER_2})

    # update_all recreates [distribution_mister] without the filter.
    root = scenario('filter_lost')
    protect(root)
    update(root, 'run1')
    guard(root)
    write_ini(root, None)
    update(root, 'run2')
    check(root, 'official MiSTer installed', {'MiSTer': OFFICIAL, 'frontier/bin/MiSTer': FRONTIER_2})
    guard(root)
    check(root, 'guard puts Frontier back', {'MiSTer': FRONTIER_2})
    protect(root, '--repair')
    assert 'filter = [MiSTer] !misterfirmware\n' in (root / 'downloader.ini').read_text(), (root / 'downloader.ini').read_text()
    update(root, 'run3')
    check(root, 'repaired: kept, not deleted', {'MiSTer': FRONTIER_2, 'menu.rbf': b'official-menu'})

    # Frontier's database removed from the setup by hand: its files stay.
    root = scenario('drop_in_removed')
    protect(root)
    update(root, 'run1')
    (root / 'downloader_frontiermr.ini').unlink()
    (root / 'frontier/downloader_frontiermr.ini').unlink()
    update(root, 'run2')
    check(root, 'non-current database deletes nothing', {
        'frontier/bin/MiSTer': FRONTIER_2, 'frontier/guard.sh': GUARD.read_bytes(), 'MiSTer': FRONTIER_1})

    # frontier_uninstall: official firmware back with the next update.
    root = scenario('uninstalled')
    protect(root)
    update(root, 'run1')
    protect(root, '--disable')
    update(root, 'run2')
    check(root, 'official firmware after uninstall', {
        'MiSTer': OFFICIAL, 'menu.rbf': b'official-menu',
        'frontier/frontier.ini': b'theme=user\n', 'downloader_frontiermr.ini': None})
    guard(root)
    check(root, 'guard idle after uninstall', {'MiSTer': OFFICIAL})
    update(root, 'run3')
    check(root, 'official firmware stays', {'MiSTer': OFFICIAL})
    # v2026.10.22 had one URL per file: the next database is an archive; nothing
    # may be deleted on the way and the new files arrive
    root = scenario('from_files_to_archive')
    server = root / 'server'
    archive_db = (server / 'frontier.json').read_bytes()
    tree = server / 'frontier_tree'
    files = {}
    for path in sorted(tree.rglob('*')):
        if path.is_file():
            rel = path.relative_to(tree).as_posix()
            data = path.read_bytes()
            files[rel] = dict(hash=make_db.hashlib.md5(data).hexdigest(), size=len(data),
                              url='https://fixture.invalid/frontier_tree/' + rel)
    files['frontier/frontier.ini']['overwrite'] = False
    files['frontier/bin/MiSTer']['reboot'] = True
    (server / 'frontier.json').write_text(json.dumps(dict(v=1, db_id='frontiermr', timestamp=1, files=files,
        folders={str(Path(f).parent): {} for f in files if '/' in f})))
    protect(root)
    update(root, 'run1')
    check(root, 'per-file database', {'frontier/bin/MiSTer': FRONTIER_2, 'frontier/frontier.ini': b'theme=user\n'})
    (server / 'frontier.json').write_bytes(archive_db)
    update(root, 'run2')
    check(root, 'archive database: same files kept', {
        'frontier/bin/MiSTer': FRONTIER_2, 'frontier/guard.sh': GUARD.read_bytes(),
        'frontier/frontier.ini': b'theme=user\n', 'Scripts/frontier_on_off.sh': b'#!/bin/sh\n'})
    print('All scenarios passed.')
