"""The neighbour contract check fails on a change in what Reports reads, names the owner, and ignores the rest."""
import contextlib
import io
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'reports/ci'))
import check_contracts  # noqa: E402


class NeighbourContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='reports-contracts-'))
        for _, (file, _) in check_contracts.NEIGHBOURS.items():
            (self.tmp/file).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/file, self.tmp/file)
        (self.tmp/'reports/ci').mkdir(parents=True)
        shutil.copyfile(check_contracts.LOCK, self.tmp/'reports/ci/contracts.lock.json')
        self.patch = (check_contracts.ROOT, check_contracts.LOCK)
        check_contracts.ROOT, check_contracts.LOCK = self.tmp, self.tmp/'reports/ci/contracts.lock.json'

    def tearDown(self):
        check_contracts.ROOT, check_contracts.LOCK = self.patch
        shutil.rmtree(self.tmp)

    def run_check(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), unittest.mock.patch.object(sys, 'argv', ['check_contracts.py']):
            code = check_contracts.main()
        return code, output.getvalue()

    def edit_tracker(self, change):
        path = self.tmp/'api/openapi/task-tracker/v1/openapi.yaml'
        spec = yaml.safe_load(path.read_text(encoding='utf-8'))
        change(spec)
        path.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding='utf-8')

    def test_the_shared_catalog_matches_the_lock(self):
        self.assertEqual(self.run_check()[0], 0)

    def test_a_changed_field_that_reports_reads_fails_and_names_the_owner(self):
        self.edit_tracker(lambda spec: spec['components']['schemas']['TimeLog']['properties'].pop('loggedDate'))
        code, output = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('task-tracker изменил контракт', output)
        self.assertIn('GET /reports/time-logs', output)
        self.assertNotIn('qa изменил', output)

    def test_a_change_outside_what_reports_reads_passes(self):
        self.edit_tracker(lambda spec: spec['info'].update(description='Changed text'))
        self.assertEqual(self.run_check()[0], 0)


if __name__ == '__main__':
    unittest.main()
