"""The CI/local initializer must never replace or print existing credentials."""
import contextlib
import io
import os
import secrets
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'ci'))
from init_pilot_secrets import initialize, REQUIRED


class Credentials(unittest.TestCase):
    def test_initialization_preserves_other_keys_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pathlib.Path.home', return_value=Path(tmp)):
            path = Path(tmp)/'secrets.env'
            existing = secrets.token_urlsafe(32)
            prefix = '# Existing settings\nUNRELATED='+existing+'\nREPORTS_DB_PASSWORD='+existing
            path.write_text(prefix)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(initialize(), len(REQUIRED)-1)
                original = path.read_bytes()
                self.assertEqual(initialize(), 0)
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(path.read_text().startswith(prefix+'\n'))
            values = dotenv_values(path)
            self.assertTrue(all(values.get(name) for name in REQUIRED))
            self.assertTrue(all(value not in output.getvalue() for value in values.values()))
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_symlink_cannot_redirect_writes_to_another_file(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pathlib.Path.home', return_value=Path(tmp)):
            target = Path(tmp)/'original.txt'; target.write_text('unchanged')
            (Path(tmp)/'secrets.env').symlink_to(target)
            with self.assertRaises(OSError): initialize()
            self.assertEqual(target.read_text(), 'unchanged')
