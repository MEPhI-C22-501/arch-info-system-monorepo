"""The security gate reports file names and never prints matching values."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

spec = importlib.util.spec_from_file_location('reports_secret_scan', Path(__file__).resolve().parents[2]/'ci/check_secrets.py')
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


class SecretScan(unittest.TestCase):
    def test_raw_urlencoded_and_json_encoded_values_are_detected_without_disclosure(self):
        # Synthetic marker, not a credential or a new project secret file.
        marker = 'synthetic-marker/"+\\'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in [('raw', marker), ('url', quote(marker, safe='')),
                                ('json', json.dumps(marker)[1:-1])]:
                (root/(name+'.log')).write_text(value)
            result = scanner.scan(root, [marker])
            self.assertFalse(result['passed'])
            self.assertEqual(len(result['findings']), 3)
            self.assertNotIn(marker, json.dumps(result))

    def test_private_key_and_jwt_in_logs_fail_the_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'key.txt').write_text('-----BEGIN '+'PRIVATE KEY-----')
            (root/'access.log').write_text('eyJ'+'a'*20+'.'+'b'*20+'.'+'c'*24)
            result = scanner.scan(root, [])
            self.assertEqual({r['reasons'][0] for r in result['findings']}, {'private-key', 'unredacted-jwt'})

    def test_clean_files_and_excluded_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'README.md').write_text('Read credentials from ~/secrets.env')
            (root/'node_modules').mkdir()
            (root/'node_modules/dependency.txt').write_text('test-marker')
            result = scanner.scan(root, ['test-marker'])
            self.assertTrue(result['passed'])
            self.assertEqual(result['files_scanned'], 1)
