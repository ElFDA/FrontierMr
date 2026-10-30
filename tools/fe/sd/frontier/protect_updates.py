#!/usr/bin/env python3
"""Keep Frontier's MiSTer through updates and get Frontier's own updates.

Frontier keeps its firmware in frontier/bin: menu.rbf is loaded from there and
frontier/guard.sh (called by linux/user-startup.sh at boot and shutdown) copies
frontier/bin/MiSTer to the root. This script sets up everything around it:
- the guard line in linux/user-startup.sh;
- '!misterfirmware' in the filter of [distribution_mister], and the official
  MiSTer forgotten in Downloader's index (with the filter alone Downloader would
  delete it); '!menu' of older Frontier versions is removed, so the official
  menu.rbf in the root updates again; the default filter of the database
  (MiSTer-DB9: '!unstable !jtbeta !dualsdram') is kept in it;
- the Downloader drop-in of Frontier's database (frontier/downloader_frontiermr.ini
  copied to the root), so update_all also updates Frontier.
--disable undoes all of it for frontier_uninstall.
"""
import argparse
import configparser
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
import zipfile

PROTECTED = {'mister'}
TAGS = ('!misterfirmware',)
LEGACY_TAGS = ('!menu',)  # Frontier's menu.rbf now lives in frontier/bin
CACHE = Path('Scripts/.config/downloader')
DEFAULT_DB = 'https://raw.githubusercontent.com/MiSTer-devel/Distribution_MiSTer/main/db.json.zip'
# the filter a distribution database sets for itself (db.json "default_options"). Downloader uses it
# only while its section of downloader.ini has no filter (and [MiSTer] has none): the filter written
# here must keep it, or the cores it leaves out are downloaded ("[MiSTer]" is only the filter of [MiSTer])
DB_DEFAULT_FILTERS = (('/mister-db9/', '!unstable !jtbeta !dualsdram'),)  # MiSTer-DB9's dbencc.json.zip
FIRMWARE = Path('frontier/bin/MiSTer')
UNINSTALLED = Path('frontier/uninstalled')
STARTUP = Path('linux/user-startup.sh')
GUARD_MARK = 'frontier/guard.sh'
GUARD_LINE = '[ -f /media/fat/frontier/guard.sh ] && sh /media/fat/frontier/guard.sh "$1" # Frontier guard'
DB_ID = 'frontiermr'
DROP_IN_TEMPLATE = Path('frontier/downloader_frontiermr.ini')
DROP_IN = Path('downloader_frontiermr.ini')


def _norm(tag):
    return tag.lower().replace('_', '').replace('-', '')


def db_default_filter(db_url):
    url = db_url.strip().strip('\"\'').lower()
    return next((terms.split() for key, terms in DB_DEFAULT_FILTERS if key in url), [])


def protect_ini(data, root=Path('/media/fat'), disable=False):
    text = data.decode('utf-8-sig')
    parser = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(';', '#'))
    parser.read_string(text)
    global_filter = False
    for section in parser.sections():
        if section.lower() == 'mister':
            global_filter = parser.has_option(section, 'filter')
            system_path = parser.get(section, 'base_system_path', fallback='/media/fat').strip().strip('\"\'')
            # update_all writes '/media/fat/' (trailing slash)
            if os.path.normpath(system_path) not in ('/media/fat', str(root)):
                raise ValueError('Custom base_system_path: review its Downloader store separately.')
    sections = [s for s in parser.sections() if s.lower() == 'distribution_mister']
    if len(sections) > 1:
        raise ValueError('Duplicate distribution_mister sections; fix downloader.ini first.')
    if not sections:
        if disable:
            return data
        if any(s.lower() not in ('mister', DB_ID) for s in parser.sections()):
            raise ValueError('No distribution_mister section. This setup needs a separate review.')
        return (text.rstrip() + '\n\n[distribution_mister]\ndb_url = ' + DEFAULT_DB +
                '\nfilter = [MiSTer] ' + ' '.join(TAGS) + '\n').encode('utf-8')
    section = sections[0]
    # the default filter of the database counts only while [MiSTer] has no filter
    default = [] if global_filter else db_default_filter(parser.get(section, 'db_url', fallback=''))
    value = parser.get(section, 'filter', fallback='' if disable else ' '.join(['[MiSTer]'] + default))
    value = value.strip().strip('\"\'')
    if '\n' in value:
        raise ValueError('Multiline filters are not supported; put this filter on one line.')
    tokens = value.split()
    remove = {_norm(t) for t in LEGACY_TAGS + (TAGS if disable else ())}
    remaining = [t for t in tokens if _norm(t) not in remove]
    ours = {'[mister]'} | {_norm(t) for t in TAGS + LEGACY_TAGS}
    if disable:
        # only what Frontier wrote is left: no filter line, the database's default filter is back
        if default and {_norm(t) for t in remaining} <= {'[mister]'} | {_norm(t) for t in default}:
            remaining = []
    else:
        if default and tokens and {_norm(t) for t in tokens} <= ours:
            # written by Frontier before it kept the default filter: put it back
            remaining = [t for t in remaining if _norm(t) == '[mister]'] or ['[MiSTer]']
            remaining += default
        remaining += [t for t in TAGS if _norm(t) not in {_norm(x) for x in remaining}]
    if remaining == tokens:
        return data
    value = ' '.join(remaining)
    lines = text.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines)
                 if re.match(r'^\s*\[' + re.escape(section) + r'\]\s*(?:[;#].*)?$', line.strip()))
    end = next((i for i in range(start + 1, len(lines)) if re.match(r'^\s*\[', lines[i])), len(lines))
    newline = '\r\n' if '\r\n' in text else '\n'
    for i in range(start + 1, end):
        # [ \t] only: \s would also take the end of the line of an empty filter
        match = re.match(r'^([ \t]*filter[ \t]*=[ \t]*)(.*?)(\r?\n)?$', lines[i], re.I)
        if match:
            comment = re.search(r'[ \t]+[;#].*$', match[2])
            if not value and not comment:
                del lines[i]  # nothing left (--disable): no empty filter line
            else:
                lines[i] = match[1] + value + (comment[0] if comment else '') + newline
            break
    else:
        # after the last line of the section, before the blank lines that end it
        at = end
        while at > start + 1 and not lines[at - 1].strip():
            at -= 1
        if not lines[at - 1].endswith('\n'):
            lines[at - 1] += newline
        lines.insert(at, 'filter = ' + value + newline)
    return ''.join(lines).encode('utf-8')


def ini_has_db(data, db_id):
    parser = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(';', '#'))
    parser.read_string(data.decode('utf-8-sig'))
    return any(s.lower() == db_id for s in parser.sections())


def startup_script(data, disable=False):
    """linux/user-startup.sh with (or without) the guard line, right after #!."""
    text = data.decode('utf-8', 'surrogateescape')
    lines = text.splitlines(keepends=True)
    kept = [line for line in lines if GUARD_MARK not in line]
    if disable:
        return ''.join(kept).encode('utf-8', 'surrogateescape') if len(kept) != len(lines) else data
    if len(lines) - len(kept) == 1 and GUARD_LINE in text:
        return data
    newline = '\r\n' if '\r\n' in text else '\n'
    if not kept:
        kept = ['#!/bin/sh' + newline]
    if not kept[0].endswith('\n'):
        kept[0] += newline
    kept.insert(1 if kept[0].startswith('#!') else 0, GUARD_LINE + newline)
    return ''.join(kept).encode('utf-8', 'surrogateescape')


def forget_files(store):
    if not isinstance(store, dict) or not isinstance(store.get('dbs'), dict):
        raise ValueError('Unrecognized Downloader store format; no files were changed.')
    removed = []

    def visit(node, db_id):
        if not isinstance(node, dict):
            return
        for field, child in node.items():
            if field == 'files' and isinstance(child, dict):
                for path in list(child):
                    if path.lower() in PROTECTED:
                        if db_id.lower() != 'distribution_mister':
                            raise ValueError('Another database owns %s: %s. Review its filters first.' % (path, db_id))
                        removed.append(path)
                        del child[path]
            else:
                visit(child, db_id)

    for db_id, db in store['dbs'].items():
        if not isinstance(db, dict) or not isinstance(db.get('files'), dict):
            raise ValueError('Unrecognized file index for database %s.' % db_id)
        visit(db, db_id)
    return removed


def protect_store(data, zipped):
    if not zipped:
        store = json.loads(data)
        removed = forget_files(store)
        return (json.dumps(store, separators=(',', ':')).encode('utf-8') if removed else data), removed
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        members = source.infolist()
        if len(members) != 1 or members[0].is_dir():
            raise ValueError('Unrecognized Downloader ZIP store; no files were changed.')
        updated, removed = protect_store(source.read(members[0]), False)
        if not removed:
            return data, removed
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as dest:
            dest.writestr(members[0], updated)
        return output.getvalue(), removed


def updater_running():
    names = {'update_all.sh', 'update.sh', 'downloader.sh', 'downloader_bin',
             'downloader_latest.zip', 'update_all.pyz', 'dont_download2.sh'}
    for entry in Path('/proc').glob('[0-9]*/cmdline'):
        if entry.parent.name == str(os.getpid()):
            continue
        try:
            args = entry.read_bytes().split(b'\0')
        except OSError:
            continue
        args = [os.fsdecode(arg) for arg in args if arg]
        if not args:
            continue
        program = args[0].rsplit('/', 1)[-1]
        if program in names:
            return True
        if program.startswith('python') or program in {'sh', 'bash', 'dash'}:
            script = next((arg for arg in args[1:] if not arg.startswith('-')), '')
            if script.rsplit('/', 1)[-1] in names:
                return True
    return False


def apply_changes(changes):
    """changes: (path, bytes) to write or (path, None) to delete, in this order."""
    stamp = time.strftime('%Y%m%d-%H%M%S') + '-%d' % os.getpid()
    staged = []
    try:
        # Back up and stage everything before replacing any file.
        for path, data in changes:
            if path.exists() and data is not None and path.name != UNINSTALLED.name:
                backup = path.with_name(path.name + '.bak-frontier-' + stamp)
                shutil.copy2(path, backup)
                print('Backup:', backup)
            if data is None:
                staged.append((None, path))
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.frontier-', delete=False) as f:
                staged.append((Path(f.name), path))
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(f.name, path.stat().st_mode & 0o777 if path.exists() else 0o755)
        for temporary, path in staged:
            if temporary is None:
                path.unlink()
            else:
                os.replace(temporary, path)
    finally:
        for temporary, _ in staged:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    if hasattr(os, 'sync'):
        os.sync()


def read(path):
    return path.read_bytes() if path.exists() else None


def plan(root, disable):
    """List of (path, new bytes or None, description) needed for the requested state."""
    changes = []
    marker = root / UNINSTALLED
    if disable and not marker.exists():
        # first: the guard stops at once, whatever happens next
        changes.append((marker, b'Frontier was uninstalled: frontier/guard.sh does nothing.\n', 'uninstall marker'))
    if not disable and marker.exists():
        changes.append((marker, None, 'uninstall marker removed'))

    startup = root / STARTUP
    old = read(startup)
    if old is not None or not disable:
        if old is None and not startup.parent.is_dir():
            raise ValueError('%s is missing: this is not a MiSTer SD card.' % STARTUP.parent)
        new = startup_script(old or b'', disable)
        if new != old:
            changes.append((startup, new, 'guard line ' + ('removed from ' if disable else 'in ') + str(STARTUP)))

    ini = root / 'downloader.ini'
    ini_data = read(ini) or b''
    drop_in, template = root / DROP_IN, root / DROP_IN_TEMPLATE
    if disable:
        if drop_in.exists():
            changes.append((drop_in, None, 'Frontier database removed (' + str(DROP_IN) + ')'))
    elif template.is_file() and not ini_has_db(ini_data, DB_ID):
        if read(drop_in) != template.read_bytes():
            changes.append((drop_in, template.read_bytes(), 'Frontier database added (' + str(DROP_IN) + ')'))

    # Forget ownership first: an interruption must not leave a filter that deletes firmware.
    # Older Downloader loads the ZIP in preference to JSON, so handle both if present.
    for name in (() if disable else ('downloader.json.zip', 'downloader.json')):
        path = root / CACHE / name
        if path.exists():
            old = path.read_bytes()
            new, removed = protect_store(old, name.endswith('.zip'))
            if new != old:
                changes.append((path, new, 'forget ownership in %s: %s' % (name, ', '.join(removed))))
    updated = protect_ini(ini_data, root, disable)
    if updated != ini_data:
        changes.append((ini, updated, 'filter of distribution_mister'))
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path('/media/fat'), help='SD card root (default: /media/fat)')
    parser.add_argument('--check', action='store_true', help='Check without changing files')
    parser.add_argument('--disable', action='store_true', help='Undo everything (frontier_uninstall)')
    parser.add_argument('--repair', action='store_true',
                        help='Started by Frontier at boot: silent when all is in place, nothing after uninstall')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.repair and (root / UNINSTALLED).exists():
        return 0
    if not args.disable:
        firmware = root / FIRMWARE
        if not firmware.is_file() or firmware.stat().st_size == 0:
            raise ValueError('%s is missing or empty: install Frontier with frontier_install.' % FIRMWARE)
    changes = plan(root, args.disable)
    if args.check:
        for _, _, what in changes:
            print('To do:', what)
        if args.disable:
            print('Frontier update protection is still enabled.' if changes else 'Frontier update protection is already removed.')
        else:
            print('Protection needs setup.' if changes else 'MiSTer is protected and Frontier updates are set up.')
        return 1 if changes else 0
    if not changes:
        if not args.repair:
            print('Nothing to change.')
        return 0
    if updater_running():
        if args.repair:
            return 0  # next boot
        raise ValueError('An updater is running. Wait for it to finish before running this script.')
    print(time.strftime('%Y-%m-%d %H:%M:%S'), 'repair' if args.repair else 'disable' if args.disable else 'setup')
    for _, _, what in changes:
        print('-', what)
    apply_changes([(path, data) for path, data, _ in changes])
    if args.repair:
        # what an updater or another tool had undone, for whoever looks into it
        with open(root / 'frontier/update_protection.log', 'a') as log:
            log.write(time.strftime('%Y-%m-%d %H:%M:%S') + ' repaired at boot: ' +
                      '; '.join(what for _, _, what in changes) + '\n')
    print('Frontier update protection removed.' if args.disable else
          'MiSTer is protected. Other core updates and cleanup remain enabled.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, configparser.Error, zipfile.BadZipFile) as error:
        print('Error:', error, file=sys.stderr)
        sys.exit(1)
