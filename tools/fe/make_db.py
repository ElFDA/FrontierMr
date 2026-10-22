#!/usr/bin/env python3
"""Build Frontier's Downloader database (db.json.zip) from a package ZIP.

The database has one archive: the package ZIP itself (package.py), downloaded
once from ZIP_URL. Downloader extracts from it the files of SD/frontier_setup/
frontier/ into frontier/ and SD/Scripts/frontier_*.sh into Scripts/, each
checked by its MD5 (the "archives" of Downloader 2.4,
docs/custom-databases-archives.md in Downloader_MiSTer). Nothing is downloaded
from the repository: a release needs only the ZIP (and the drop-in to start).

  make_db.py --zip dist/Frontier_vX.zip \\
             --url https://github.com/OWNER/FrontierMr/releases/download/vX/Frontier_vX.zip -o db.json.zip

Downloader rejects MiSTer and menu.rbf in the root from any database but the
official one: Frontier's are in frontier/bin and frontier/guard.sh installs MiSTer.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile

DB_ID = 'frontiermr'
ARC_ID = 'frontier'
# where the files are in the package ZIP -> where they go on the SD card
PREFIXES = (('SD/frontier_setup/frontier/', 'frontier/'), ('SD/Scripts/', 'Scripts/'))
SKIP_PARTS = {'__pycache__', '.git'}
SKIP_SUFFIXES = ('.pyc', '~')
# files the user changes: installed once, never replaced by an update
KEEP_USER_COPY = {'frontier/frontier.ini'}
# a new MiSTer is installed by the guard at shutdown: ask update_all to reboot
REBOOT = {'frontier/bin/MiSTer'}


def wanted(rel):
    parts = rel.split('/')
    if SKIP_PARTS & set(parts) or rel.endswith(SKIP_SUFFIXES) or '.bak' in parts[-1] or parts[-1].startswith('.'):
        return False
    if parts[-1] in ('update_protection.log', 'guard.log', 'uninstalled'):
        return False
    return parts[0] == 'frontier' or (parts[0] == 'Scripts' and len(parts) == 2 and parts[1].startswith('frontier_'))


def build(archive, url, timestamp=None):
    archive = Path(archive)
    files, folders = {}, {}
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            rel = next((dst + info.filename[len(src):] for src, dst in PREFIXES if info.filename.startswith(src)), None)
            if rel is None or not wanted(rel):
                continue
            data = z.read(info)
            entry = {'hash': hashlib.md5(data).hexdigest(), 'size': len(data), 'arc_id': ARC_ID, 'arc_at': info.filename}
            if rel in KEEP_USER_COPY:
                entry['overwrite'] = False
            if rel in REBOOT:
                entry['reboot'] = True
            files[rel] = entry
            parent = Path(rel).parent
            while parent != Path('.'):
                folders[parent.as_posix()] = {'arc_id': ARC_ID}
                parent = parent.parent
    for required in ('frontier/bin/MiSTer', 'frontier/guard.sh', 'frontier/protect_updates.py'):
        if required not in files:
            raise SystemExit('%s: %s is missing' % (archive, required))
    data = archive.read_bytes()
    return {'v': 1, 'db_id': DB_ID, 'timestamp': int(timestamp or time.time()), 'files': {}, 'folders': {},
            'archives': {ARC_ID: {
                'format': 'zip', 'extract': 'selective', 'description': 'Extracting Frontier',
                'archive_file': {'hash': hashlib.md5(data).hexdigest(), 'size': len(data), 'url': url},
                'summary_inline': {'files': dict(sorted(files.items())), 'folders': dict(sorted(folders.items()))}}}}


def write(db, output):
    output = Path(output)
    data = json.dumps(db, separators=(',', ':'), sort_keys=True).encode()
    if output.name.endswith('.zip'):
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr(output.name[:-4], data)
    else:
        output.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--zip', required=True, type=Path, help='the package ZIP (package.py)')
    parser.add_argument('--url', required=True, help='where the ZIP is published')
    parser.add_argument('-o', '--output', required=True, type=Path, help='db.json.zip (or .json)')
    parser.add_argument('--timestamp', type=int, help='default: now')
    args = parser.parse_args()
    db = build(args.zip, args.url, args.timestamp)
    write(db, args.output)
    files = db['archives'][ARC_ID]['summary_inline']['files']
    print('%s: %d files from %s (%.1f MiB)' % (args.output, len(files), args.zip.name,
                                                db['archives'][ARC_ID]['archive_file']['size'] / 1024**2))


if __name__ == '__main__':
    main()
