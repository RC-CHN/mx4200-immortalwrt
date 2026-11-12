from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from local_overlay import sync


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        self.output = self.root / 'output'
        self.state = self.root / 'state.json'

    def run_sync(self):
        sync([self.inputs], self.output, self.state)

    def test_deleted_file_removed_and_unrelated_file_preserved(self):
        old = self.inputs / 'argon.css'
        old.write_text('old')
        self.run_sync()
        (self.output / 'user.txt').write_text('keep')
        old.unlink()
        (self.inputs / 'vantage.css').write_text('new')
        self.run_sync()
        self.assertFalse((self.output / 'argon.css').exists())
        self.assertEqual((self.output / 'user.txt').read_text(), 'keep')
        self.assertEqual((self.output / 'vantage.css').read_text(), 'new')

    def test_local_change_aborts_before_any_deletion(self):
        for name in ('a', 'b'):
            (self.inputs / name).write_text('old')
        self.run_sync()
        (self.output / 'b').write_text('user edit')
        for item in self.inputs.iterdir():
            item.unlink()
        with self.assertRaises(ValueError):
            self.run_sync()
        self.assertTrue((self.output / 'a').exists())
        self.assertEqual((self.output / 'b').read_text(), 'user edit')

    def test_adopt_old_record_and_preserve_executable_mode(self):
        previous = self.root / 'previous'
        previous.mkdir()
        (previous / 'old').write_text('old')
        self.output.mkdir()
        (self.output / 'old').write_text('old')
        (self.inputs / 'new').write_text('#!/bin/sh\n')
        (self.inputs / 'new').chmod(0o755)
        sync([self.inputs], self.output, self.state, [previous])
        self.assertFalse((self.output / 'old').exists())
        self.assertEqual((self.output / 'new').stat().st_mode & 0o777, 0o755)

    def test_symlink_cannot_escape_destination(self):
        (self.inputs / 'folder').mkdir()
        (self.inputs / 'folder/file').write_text('new')
        self.output.mkdir()
        outside = self.root / 'outside'
        outside.mkdir()
        (self.output / 'folder').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.run_sync()
        self.assertFalse((outside / 'file').exists())
