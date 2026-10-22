#!/usr/bin/env python3
"""frontier/guard.sh on a simulated SD card (killall, pidof and setsid replaced)."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

GUARD = Path(__file__).parent / 'sd/frontier/guard.sh'
FRONTIER = b'\x7fELF-frontier'


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'sd'
        (self.root / 'frontier/bin').mkdir(parents=True)
        (self.root / 'frontier/bin/MiSTer').write_bytes(FRONTIER)
        (self.root / 'MiSTer').write_bytes(b'\x7fELF-official')
        commands = Path(self.temp.name) / 'commands'
        commands.mkdir()
        for name, body in (('killall', 'echo "killall $*" >>"$FRONTIER_SD_ROOT/calls"'),
                           ('pidof', 'exit 1'),
                           ('setsid', 'echo "setsid $*" >>"$FRONTIER_SD_ROOT/calls"')):
            (commands / name).write_text('#!/bin/sh\n' + body + '\n')
            (commands / name).chmod(0o755)
        self.env = dict(os.environ, FRONTIER_SD_ROOT=str(self.root),
                        PATH=str(commands) + os.pathsep + os.environ['PATH'])

    def guard(self, action):
        result = subprocess.run(['sh', str(GUARD), action], env=self.env, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        return result

    def calls(self):
        path = self.root / 'calls'
        return path.read_text() if path.exists() else ''

    def test_stop_restores_frontier_and_logs(self):
        self.guard('stop')
        self.assertEqual(FRONTIER, (self.root / 'MiSTer').read_bytes())
        self.assertTrue(os.access(self.root / 'MiSTer', os.X_OK))
        self.assertIn('stop: MiSTer restored', (self.root / 'frontier/guard.log').read_text())
        self.assertEqual('', self.calls())
        self.assertFalse((self.root / 'MiSTer.frontier-new').exists())

    def wait_started(self):
        # MiSTer is started in the background: wait for it, or it writes into
        # the folder of the test while it is removed
        for _ in range(100):
            if 'setsid' in self.calls():
                return
            time.sleep(0.05)

    def test_start_restores_and_restarts_main(self):
        self.guard('start')
        self.assertEqual(FRONTIER, (self.root / 'MiSTer').read_bytes())
        self.wait_started()
        self.assertEqual('killall MiSTer\nsetsid %s/MiSTer\n' % self.root, self.calls())

    def test_missing_mister_is_restored(self):
        (self.root / 'MiSTer').unlink()
        self.guard('start')
        self.assertEqual(FRONTIER, (self.root / 'MiSTer').read_bytes())
        self.wait_started()

    def test_same_file_changes_nothing(self):
        (self.root / 'MiSTer').write_bytes(FRONTIER)
        self.guard('start')
        self.assertFalse((self.root / 'frontier/guard.log').exists())
        self.assertEqual('', self.calls())

    def test_wrong_or_missing_source_and_uninstall_change_nothing(self):
        for setup in (lambda: (self.root / 'frontier/bin/MiSTer').write_bytes(b'<html>404</html>'),
                      lambda: (self.root / 'frontier/bin/MiSTer').write_bytes(b''),
                      lambda: (self.root / 'frontier/bin/MiSTer').unlink(),
                      lambda: ((self.root / 'frontier/bin/MiSTer').write_bytes(FRONTIER),
                               (self.root / 'frontier/uninstalled').write_text('x'))):
            setup()
            self.guard('start')
            self.assertEqual(b'\x7fELF-official', (self.root / 'MiSTer').read_bytes())
            self.assertEqual('', self.calls())

    def test_long_log_is_trimmed(self):
        (self.root / 'frontier/guard.log').write_text(''.join('line %d\n' % i for i in range(60)))
        self.guard('stop')
        lines = (self.root / 'frontier/guard.log').read_text().splitlines()
        self.assertEqual(21, len(lines))
        self.assertIn('MiSTer restored', lines[-1])


if __name__ == '__main__':
    unittest.main()
