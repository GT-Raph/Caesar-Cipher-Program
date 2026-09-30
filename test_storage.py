from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.cipher_vault.storage import export_new, read_bounded


class StorageTests(unittest.TestCase):
    def test_publish_and_reject_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'output'
            export_new(target, b'complete')
            with self.assertRaises(FileExistsError):
                export_new(target, b'replacement')
            self.assertEqual(target.read_bytes(), b'complete')
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_failure_leaves_no_partial_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'output'
            with patch('src.cipher_vault.storage.os.fsync', side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    export_new(target, b'never published')
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_read_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'input'
            target.write_bytes(b'1234')
            self.assertEqual(read_bounded(target, 4), b'1234')
            with self.assertRaises(ValueError):
                read_bounded(target, 3)
