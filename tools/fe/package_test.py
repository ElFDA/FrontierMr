#!/usr/bin/env python3
"""Exercise the distributed install, upgrade, guard and uninstall scripts offline."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).parent / 'sd'
FRONTIER = b'\x7fELF-frontier-main'
OFFICIAL = b'\x7fELF-official-main'


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'sd'
        self.root.mkdir()
        self.setup = self.root / 'frontier_setup'
        (self.setup / 'frontier/bin').mkdir(parents=True)
        for name in ('protect_updates.py', 'guard.sh'):
            shutil.copy2(SOURCE / 'frontier' / name, self.setup / 'frontier' / name)
        (self.setup / 'frontier/frontier.ini').write_text('theme=package\n')
        (self.setup / 'frontier/bin/MiSTer').write_bytes(FRONTIER)
        (self.setup / 'frontier/bin/menu.rbf').write_bytes(b'frontier-menu')
        (self.root / 'MiSTer').write_bytes(OFFICIAL)
        (self.root / 'menu.rbf').write_bytes(b'official-menu')
        (self.root / 'linux').mkdir()
        self.startup = self.root / 'linux/user-startup.sh'
        self.startup.write_text('#!/bin/sh\necho user\n')
        self.ini = self.root / 'downloader.ini'
        self.ini.write_text('[MiSTer]\nfilter=!cheats\nallow_delete=1\n'
                            '[distribution_mister]\ndb_url=https://fixture.invalid/db.json\n')
        self.index = self.root / 'Scripts/.config/downloader/downloader.json'
        self.index.parent.mkdir(parents=True)
        self.index.write_text(json.dumps({'dbs': {'distribution_mister': {'files': {
            'MiSTer': {}, 'menu.rbf': {}, '_Console/Other.rbf': {}}}}, 'db_fingerprints': {}}))
        for path in (SOURCE / 'Scripts').glob('*.sh'):
            shutil.copy2(path, self.root / 'Scripts' / path.name)
        (self.root / 'frontier').mkdir()
        (self.root / 'frontier/frontier.ini').write_text('theme=user\n')
        (self.root / 'frontier/favorites.txt').write_text('keep-favorites\n')
        commands = Path(self.temp.name) / 'commands'
        commands.mkdir()
        for command in ('sleep', 'sync', 'killall', 'setsid'):
            path = commands / command
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o755)
        (commands / 'pidof').write_text('#!/bin/sh\nexit 1\n')
        (commands / 'pidof').chmod(0o755)
        reboot = commands / 'reboot'
        reboot.write_text('#!/bin/sh\nprintf "reboot\\n" >> "$FRONTIER_SD_ROOT/reboots.txt"\n')
        reboot.chmod(0o755)
        self.env = dict(os.environ, FRONTIER_SD_ROOT=str(self.root),
                        PATH=str(commands) + os.pathsep + os.environ['PATH'])

    def run_script(self, name):
        return subprocess.run(['bash', str(self.root / 'Scripts' / name)], env=self.env,
                              capture_output=True, text=True)

    def guard(self, action):
        return subprocess.run(['sh', str(self.root / 'frontier/guard.sh'), action], env=self.env,
                              capture_output=True, text=True).returncode

    def reboots(self):
        path = self.root / 'reboots.txt'
        return path.read_text().count('reboot') if path.exists() else 0

    def files(self):
        return json.loads(self.index.read_text())['dbs']['distribution_mister']['files']

    def test_install_update_guard_uninstall_reinstall(self):
        result = self.run_script('frontier_install.sh')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(FRONTIER, (self.root / 'MiSTer').read_bytes())
        self.assertEqual(FRONTIER, (self.root / 'frontier/bin/MiSTer').read_bytes())
        self.assertEqual(b'frontier-menu', (self.root / 'frontier/bin/menu.rbf').read_bytes())
        self.assertEqual(b'official-menu', (self.root / 'menu.rbf').read_bytes())
        self.assertEqual(OFFICIAL, (self.root / 'MiSTer.orig').read_bytes())
        self.assertEqual('theme=user\n', (self.root / 'frontier/frontier.ini').read_text())
        self.assertIn('filter = [MiSTer] !misterfirmware\n', self.ini.read_text())
        self.assertEqual({'menu.rbf': {}, '_Console/Other.rbf': {}}, self.files())
        self.assertIn('frontier/guard.sh', self.startup.read_text())
        self.assertIn('echo user', self.startup.read_text())

        # an updater puts the official MiSTer back: the guard undoes it at shutdown
        (self.root / 'MiSTer').write_bytes(OFFICIAL)
        self.assertEqual(0, self.guard('stop'))
        self.assertEqual(FRONTIER, (self.root / 'MiSTer').read_bytes())

        # Frontier's own update arrives in frontier/bin (update_all) and is installed the same way
        (self.root / 'frontier/bin/MiSTer').write_bytes(FRONTIER + b'-2')
        self.assertEqual(0, self.guard('stop'))
        self.assertEqual(FRONTIER + b'-2', (self.root / 'MiSTer').read_bytes())

        (self.setup / 'frontier/bin/MiSTer').write_bytes(FRONTIER + b'-3')
        self.assertEqual(0, self.run_script('frontier_install.sh').returncode)
        self.assertEqual(FRONTIER + b'-3', (self.root / 'MiSTer').read_bytes())
        self.assertEqual(OFFICIAL, (self.root / 'MiSTer.orig').read_bytes())
        self.assertEqual(0, self.run_script('frontier_on_off.sh').returncode)
        self.assertTrue((self.root / 'frontier.off').exists())
        self.assertIn('!misterfirmware', self.ini.read_text())

        result = self.run_script('frontier_uninstall.sh')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(OFFICIAL, (self.root / 'MiSTer').read_bytes())
        self.assertEqual(b'official-menu', (self.root / 'menu.rbf').read_bytes())
        self.assertNotIn('!misterfirmware', self.ini.read_text())
        self.assertIn('filter=!cheats', self.ini.read_text())
        self.assertIn('allow_delete=1', self.ini.read_text())
        self.assertNotIn('guard.sh', self.startup.read_text())
        self.assertIn('echo user', self.startup.read_text())
        self.assertEqual('theme=user\n', (self.root / 'frontier/frontier.ini').read_text())
        self.assertEqual('keep-favorites\n', (self.root / 'frontier/favorites.txt').read_text())
        self.assertFalse((self.root / 'MiSTer.orig').exists())
        self.assertFalse((self.root / 'frontier.off').exists())
        # the guard stays out of the way even if called
        self.assertEqual(0, self.guard('stop'))
        self.assertEqual(OFFICIAL, (self.root / 'MiSTer').read_bytes())

        self.assertEqual(0, self.run_script('frontier_install.sh').returncode)
        self.assertEqual(FRONTIER + b'-3', (self.root / 'MiSTer').read_bytes())
        self.assertIn('frontier/guard.sh', self.startup.read_text())
        self.assertFalse((self.root / 'frontier/uninstalled').exists())
        self.assertEqual(5, self.reboots())

    def test_upgrade_from_the_version_that_replaced_menu_rbf(self):
        (self.root / 'menu.rbf').write_bytes(b'frontier-menu-old')
        (self.root / 'menu.rbf.orig').write_bytes(b'official-menu')
        (self.root / 'Scripts/frontier_crt_menu.sh').write_text('#!/bin/sh\n')
        (self.root / 'Scripts/frontier_scrape.sh').write_text('#!/bin/sh\n')
        self.ini.write_text(self.ini.read_text() + 'filter = !misterfirmware !menu\n')
        self.index.write_text(json.dumps({'dbs': {'distribution_mister': {'files': {
            '_Console/Other.rbf': {}}}}, 'db_fingerprints': {}}))
        result = self.run_script('frontier_install.sh')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(b'official-menu', (self.root / 'menu.rbf').read_bytes())
        self.assertFalse((self.root / 'menu.rbf.orig').exists())
        self.assertFalse((self.root / 'Scripts/frontier_crt_menu.sh').exists())
        self.assertFalse((self.root / 'Scripts/frontier_scrape.sh').exists())
        self.assertIn('filter = !misterfirmware\n', self.ini.read_text())

    def test_install_from_files_downloaded_by_update_all(self):
        shutil.copytree(self.setup / 'frontier', self.root / 'frontier', dirs_exist_ok=True)
        (self.root / 'frontier/frontier.ini').write_text('theme=user\n')
        shutil.rmtree(self.setup)
        result = self.run_script('frontier_install.sh')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(FRONTIER, (self.root / 'MiSTer').read_bytes())
        self.assertEqual(OFFICIAL, (self.root / 'MiSTer.orig').read_bytes())
        self.assertEqual('theme=user\n', (self.root / 'frontier/frontier.ini').read_text())

    def test_failed_protection_keeps_firmware_and_does_not_reboot(self):
        self.index.write_text('{broken')
        before = self.ini.read_bytes(), self.startup.read_bytes()
        result = self.run_script('frontier_install.sh')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Installation stopped', result.stdout)
        self.assertEqual(OFFICIAL, (self.root / 'MiSTer').read_bytes())
        self.assertEqual(before, (self.ini.read_bytes(), self.startup.read_bytes()))
        self.assertEqual(0, self.reboots())
        self.assertTrue((self.root / 'frontier/update_protection.log').exists())

    def test_incomplete_package_does_not_change_firmware(self):
        (self.setup / 'frontier/guard.sh').unlink()
        result = self.run_script('frontier_install.sh')
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.root / 'MiSTer.orig').exists())
        self.assertEqual(OFFICIAL, (self.root / 'MiSTer').read_bytes())
        self.assertEqual(0, self.reboots())

    def test_uninstall_without_backup_leaves_it_to_update_all(self):
        self.assertEqual(0, self.run_script('frontier_install.sh').returncode)
        (self.root / 'MiSTer.orig').unlink()
        result = self.run_script('frontier_uninstall.sh')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('Run update_all', result.stdout)
        self.assertTrue((self.root / 'frontier.off').exists())
        self.assertNotIn('!misterfirmware', self.ini.read_text())
        self.assertNotIn('guard.sh', self.startup.read_text())
        self.assertEqual(2, self.reboots())

    def test_old_default_theme_is_moved_out_of_the_theme_list(self):
        (self.root / 'frontier/themes/default').mkdir(parents=True)
        (self.root / 'frontier/themes/default/theme.ini').write_text('old\n')
        (self.setup / 'frontier/themes/simple').mkdir(parents=True)
        self.assertEqual(0, self.run_script('frontier_install.sh').returncode)
        self.assertFalse((self.root / 'frontier/themes/default').exists())
        self.assertEqual('old\n', (self.root / 'frontier/old/default/theme.ini').read_text())

    def test_crt_script_toggles_only_crt(self):
        ini = self.root / 'frontier/frontier.ini'
        ini.write_text('; crt=1 comment\ntheme=user\ncrt_width=90')
        self.assertEqual(0, self.run_script('frontier_crt.sh').returncode)
        self.assertEqual('; crt=1 comment\ntheme=user\ncrt_width=90\ncrt=1\n', ini.read_text())
        self.assertEqual(0, self.run_script('frontier_crt.sh').returncode)
        self.assertEqual('; crt=1 comment\ntheme=user\ncrt_width=90\ncrt=0\n', ini.read_text())
        self.assertEqual(0, self.run_script('frontier_crt.sh').returncode)
        self.assertIn('\ncrt=1\n', ini.read_text())
        self.assertEqual(3, self.reboots())
        ini.unlink()
        self.assertNotEqual(0, self.run_script('frontier_crt.sh').returncode)

    def test_empty_existing_settings_are_preserved(self):
        (self.root / 'frontier/frontier.ini').write_bytes(b'')
        self.assertEqual(0, self.run_script('frontier_install.sh').returncode)
        self.assertEqual(b'', (self.root / 'frontier/frontier.ini').read_bytes())


if __name__ == '__main__':
    unittest.main()
