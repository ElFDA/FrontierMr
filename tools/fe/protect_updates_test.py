#!/usr/bin/env python3
"""Regression checks for protect_updates.py (guard line, filter, index, drop-in)."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

SCRIPT = Path(__file__).parent / 'sd/frontier/protect_updates.py'
spec = importlib.util.spec_from_file_location('protect_updates', SCRIPT)
protect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protect)


class ProtectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('MiSTer', 'menu.rbf'):
            (self.root / name).write_bytes(b'official-' + name.encode())
        (self.root / 'frontier/bin').mkdir(parents=True)
        (self.root / 'frontier/bin/MiSTer').write_bytes(b'\x7fELF-frontier')
        (self.root / 'linux').mkdir()
        self.startup = self.root / 'linux/user-startup.sh'
        self.startup.write_text('#!/bin/sh\n\n# user line\n[ -x /x ] && /x start\n')
        self.ini = self.root / 'downloader.ini'
        self.ini.write_text('[MiSTer]\nfilter = !cheats\nallow_delete=1\n\n'
                            '[distribution_mister]\ndb_url=https://example.invalid/db.json\n')
        self.store = self.root / protect.CACHE / 'downloader.json'
        self.store.parent.mkdir(parents=True)
        self.data = {'migration_version': 5, 'db_fingerprints': {'distribution_mister': {'filter': ''}},
                     'dbs': {'distribution_mister': {'files': {'MiSTer': {}, 'menu.rbf': {},
                             '_Console/Other.rbf': {}}, 'zips': {}, 'folders': {}},
                             'jtcores': {'files': {'_Arcade/Other.rbf': {}}}}}
        self.store.write_text(json.dumps(self.data))

    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args],
                              capture_output=True, text=True)

    def snapshot(self):
        return {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_setup_forgets_only_mister_and_adds_guard_line(self):
        result = self.run_script()
        self.assertEqual(0, result.returncode, result.stderr)
        expected = copy.deepcopy(self.data)
        del expected['dbs']['distribution_mister']['files']['MiSTer']
        self.assertEqual(expected, json.loads(self.store.read_text()))
        for name in ('MiSTer', 'menu.rbf'):
            self.assertEqual(b'official-' + name.encode(), (self.root / name).read_bytes())
        self.assertIn('filter = [MiSTer] !misterfirmware\n', self.ini.read_text())
        self.assertIn('allow_delete=1', self.ini.read_text())
        lines = self.startup.read_text().splitlines()
        self.assertEqual(['#!/bin/sh', protect.GUARD_LINE, '', '# user line', '[ -x /x ] && /x start'], lines)
        backup = next(self.store.parent.glob('downloader.json.bak-frontier-*'))
        self.assertEqual(self.data, json.loads(backup.read_text()))
        self.assertTrue(list(self.startup.parent.glob('user-startup.sh.bak-frontier-*')))
        self.assertEqual(0, self.run_script('--check').returncode)
        before = self.snapshot()
        self.assertEqual(0, self.run_script().returncode)
        self.assertEqual(before, self.snapshot())

    def test_check_never_changes_files(self):
        before = self.snapshot()
        result = self.run_script('--check')
        self.assertEqual(1, result.returncode)
        self.assertIn('guard line', result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_filters_comments_case_and_line_endings_are_preserved(self):
        ini = b'[MiSTer]\r\nfilter=!cheats\r\n[Distribution_MiSTer]\r\nFilter = "console !menu" ; chosen cores\r\n[jtcores]\r\nfilter=all\r\n'
        updated = protect.protect_ini(ini)
        self.assertIn(b'Filter = console !misterfirmware ; chosen cores\r\n', updated)
        self.assertIn(b'[jtcores]\r\nfilter=all\r\n', updated)
        self.assertEqual(updated, protect.protect_ini(updated))

    def test_empty_filter_line_and_reinstall_after_uninstall(self):
        # an empty "filter =" (older --disable) must not lose its end of line
        for ini, expected in ((b'[distribution_mister]\ndb_url = x\nfilter = \n\n[jtcores]\n',
                               b'[distribution_mister]\ndb_url = x\nfilter = !misterfirmware\n\n[jtcores]\n'),
                              (b'[distribution_mister]\r\nfilter =\r\n[a]\r\n',
                               b'[distribution_mister]\r\nfilter =!misterfirmware\r\n[a]\r\n')):
            self.assertEqual(expected, protect.protect_ini(ini))
        self.ini.write_text('[distribution_mister]\ndb_url = x\nfilter = !misterfirmware !menu\n\n[jtcores]\nfilter = [MiSTer]\n')
        self.assertEqual(0, self.run_script('--disable').returncode)
        self.assertEqual('[distribution_mister]\ndb_url = x\n\n[jtcores]\nfilter = [MiSTer]\n', self.ini.read_text())
        self.assertEqual(0, self.run_script().returncode)
        self.assertEqual('[distribution_mister]\ndb_url = x\nfilter = [MiSTer] !misterfirmware\n\n[jtcores]\nfilter = [MiSTer]\n',
                         self.ini.read_text())

    def test_existing_safe_configuration_is_unchanged_and_legacy_menu_removed(self):
        ini = b'[distribution_mister]\nfilter = !misterfirmware\n'
        self.assertEqual(ini, protect.protect_ini(ini))
        self.assertEqual(b'[distribution_mister]\nfilter = !misterfirmware\n',
                         protect.protect_ini(b'[distribution_mister]\nfilter = !misterfirmware !menu\n'))

    def test_old_zip_store_is_also_detached(self):
        archive = self.store.with_name('downloader.json.zip')
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('downloader.json', self.store.read_bytes())
        self.assertEqual(0, self.run_script().returncode)
        with zipfile.ZipFile(archive) as z:
            files = json.loads(z.read('downloader.json'))['dbs']['distribution_mister']['files']
        self.assertNotIn('MiSTer', files)
        self.assertIn('menu.rbf', files)

    def test_nested_archive_and_external_ownership_of_mister_are_forgotten(self):
        data = copy.deepcopy(self.data)
        db = data['dbs']['distribution_mister']
        db['external'] = {'/media/usb0': {'files': {'MISTER': {}, 'games/MiSTer': {}}}}
        db['zips'] = {'example': {'files': {'MENU.RBF': {}, 'mister': {}}}}
        protect.forget_files(data)
        self.assertEqual({'games/MiSTer': {}}, db['external']['/media/usb0']['files'])
        self.assertEqual({'MENU.RBF': {}}, db['zips']['example']['files'])

    def test_other_database_claims_abort_before_any_write(self):
        self.data['dbs']['jtcores']['files']['MiSTer'] = {}
        self.store.write_text(json.dumps(self.data))
        before = self.snapshot()
        result = self.run_script()
        self.assertEqual(1, result.returncode)
        self.assertIn('Another database owns', result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_missing_frontier_firmware_or_corrupt_store_aborts(self):
        (self.root / 'frontier/bin/MiSTer').write_bytes(b'')
        before = self.snapshot()
        self.assertEqual(1, self.run_script().returncode)
        self.assertEqual(before, self.snapshot())
        (self.root / 'frontier/bin/MiSTer').write_bytes(b'\x7fELF')
        self.store.write_text('{corrupt')
        before = self.snapshot()
        self.assertEqual(1, self.run_script().returncode)
        self.assertEqual(before, self.snapshot())

    def test_unknown_distributions_and_store_formats_are_rejected(self):
        with self.assertRaises(ValueError):
            protect.protect_ini(b'[different_distribution]\ndb_url=https://example.invalid\n')
        with self.assertRaises(ValueError):
            protect.protect_ini(b'[MiSTer]\nbase_system_path=/media/other\n')
        with self.assertRaises(ValueError):
            protect.protect_ini(b'[MiSTer]\nbase_system_path=/media/other/\n')

    def test_default_paths_written_by_update_all_are_accepted(self):
        ini = (b"[MiSTer]\nbase_path = '/media/fat/'\nbase_system_path = '/media/fat/'\n\n"
               b"[distribution_mister]\ndb_url = https://example.invalid/db.json.zip\n")
        self.assertIn(b'filter = [MiSTer] !misterfirmware', protect.protect_ini(ini))
        disabled = protect.protect_ini(protect.protect_ini(ini), disable=True)
        self.assertNotIn(b'misterfirmware', disabled)
        with self.assertRaises(ValueError):
            protect.protect_store(b'{"dbs":{"distribution_mister":{"files":[]}}}', False)

    def test_updater_process_detection_ignores_archive_arguments_to_other_scripts(self):
        entry = Mock()
        entry.parent.name = '999999'
        with patch.object(protect.Path, 'glob', return_value=[entry]):
            entry.read_bytes.return_value = b'python3\0/test_runner.py\0/downloader_latest.zip\0'
            self.assertFalse(protect.updater_running())
            entry.read_bytes.return_value = b'python3\0/downloader_latest.zip\0'
            self.assertTrue(protect.updater_running())
            entry.read_bytes.return_value = b'/media/fat/Scripts/.config/downloader/downloader_bin\0'
            self.assertTrue(protect.updater_running())

    def test_drop_in_follows_the_template_unless_downloader_ini_has_the_database(self):
        template = self.root / protect.DROP_IN_TEMPLATE
        template.write_text('[frontiermr]\ndb_url = https://example.invalid/a.json.zip\n')
        self.assertEqual(0, self.run_script().returncode)
        drop_in = self.root / protect.DROP_IN
        self.assertEqual(template.read_bytes(), drop_in.read_bytes())
        template.write_text('[frontiermr]\ndb_url = https://example.invalid/b.json.zip\n')
        self.assertEqual(0, self.run_script().returncode)
        self.assertEqual(template.read_bytes(), drop_in.read_bytes())
        drop_in.unlink()
        self.ini.write_text(self.ini.read_text() + '\n[FrontierMr]\ndb_url = https://example.invalid/c.json.zip\n')
        self.assertEqual(0, self.run_script().returncode)
        self.assertFalse(drop_in.exists())

    def test_startup_script_variants(self):
        self.assertEqual(('#!/bin/sh\n' + protect.GUARD_LINE + '\n').encode(), protect.startup_script(b''))
        self.assertEqual(('#!/bin/sh\r\n' + protect.GUARD_LINE + '\r\necho x\r\n').encode(),
                         protect.startup_script(b'#!/bin/sh\r\necho x\r\n'))
        self.assertEqual(('#!/bin/bash\n' + protect.GUARD_LINE + '\n').encode(), protect.startup_script(b'#!/bin/bash'))
        old = b'#!/bin/sh\necho x\nsh /media/fat/frontier/guard.sh "$1"\n'
        self.assertEqual(('#!/bin/sh\n' + protect.GUARD_LINE + '\necho x\n').encode(), protect.startup_script(old))
        self.assertEqual(b'#!/bin/sh\necho x\n', protect.startup_script(old, disable=True))
        self.assertEqual(b'echo x\n', protect.startup_script(b'echo x\n', disable=True))
        (self.startup).unlink()
        self.assertEqual(0, self.run_script().returncode)
        self.assertEqual('#!/bin/sh\n' + protect.GUARD_LINE + '\n', self.startup.read_text())

    def test_disable_undoes_everything_and_keeps_other_settings(self):
        (self.root / protect.DROP_IN_TEMPLATE).write_text('[frontiermr]\ndb_url = https://example.invalid/a\n')
        self.assertEqual(0, self.run_script().returncode)
        self.ini.write_text(self.ini.read_text().replace('!misterfirmware', '!misterfirmware !menu !manuals'))
        index = self.store.read_bytes()
        result = self.run_script('--disable')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn('!misterfirmware', self.ini.read_text())
        self.assertNotIn('!menu', self.ini.read_text())
        self.assertIn('[MiSTer] !manuals', self.ini.read_text())
        self.assertIn('filter = !cheats', self.ini.read_text())
        self.assertEqual(index, self.store.read_bytes())
        self.assertNotIn('guard.sh', self.startup.read_text())
        self.assertIn('# user line', self.startup.read_text())
        self.assertFalse((self.root / protect.DROP_IN).exists())
        self.assertTrue((self.root / protect.UNINSTALLED).exists())
        self.assertEqual(0, self.run_script('--disable', '--check').returncode)
        before = self.snapshot()
        self.assertEqual(0, self.run_script('--disable').returncode)
        self.assertEqual(before, self.snapshot())
        # repair does nothing after an uninstall, a new setup removes the marker
        self.assertEqual(0, self.run_script('--repair').returncode)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(0, self.run_script().returncode)
        self.assertFalse((self.root / protect.UNINSTALLED).exists())
        self.assertIn('guard.sh', self.startup.read_text())

    def test_disable_handles_empty_filters_missing_files_and_repeated_calls(self):
        self.ini.write_text('[distribution_mister]\nfilter = !menu !misterfirmware\n')
        (self.root / 'MiSTer').unlink()
        (self.root / 'frontier/bin/MiSTer').unlink()
        self.startup.unlink()
        self.assertEqual(0, self.run_script('--disable').returncode)
        self.assertNotIn('filter', self.ini.read_text())
        self.assertFalse(self.startup.exists())
        before = self.snapshot()
        self.assertEqual(0, self.run_script('--disable').returncode)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(b'', protect.protect_ini(b'', disable=True))

    def test_repair_is_silent_when_in_place_and_restores_what_was_undone(self):
        self.assertEqual(0, self.run_script().returncode)
        result = self.run_script('--repair')
        self.assertEqual((0, ''), (result.returncode, result.stdout))
        self.assertFalse((self.root / 'frontier/update_protection.log').exists())
        # update_all recreated the section, another tool rewrote user-startup.sh
        self.ini.write_text('[distribution_mister]\ndb_url=https://example.invalid/db.json\n')
        self.startup.write_text('#!/bin/sh\necho other\n')
        self.assertEqual(0, self.run_script('--repair').returncode)
        self.assertIn('!misterfirmware', self.ini.read_text())
        self.assertIn(protect.GUARD_LINE, self.startup.read_text())
        self.assertIn('echo other', self.startup.read_text())
        self.assertIn('repaired at boot', (self.root / 'frontier/update_protection.log').read_text())


if __name__ == '__main__':
    unittest.main()
