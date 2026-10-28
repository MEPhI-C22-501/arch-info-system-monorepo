"""Observed SCD2 history, consistent daily snapshots and source serialization."""
import copy
import json
import os
import threading
import unittest
from unittest.mock import patch

from test_pipeline import Tracker
from adapters import Rejected
from db import Database
from demo import fixture
from etl import load, tracker_extract


def catalog(rows, stamp='2026-10-01T12:00:00+00:00'):
    return {'employees': copy.deepcopy(rows)}, stamp, stamp, None


class History(unittest.TestCase):
    def setUp(self):
        self.db = Database('sqlite::memory:'); self.db.initialize()

    def tearDown(self):
        self.db.close()

    def test_reference_change_and_explicit_deletion_preserve_history(self):
        first = [{'id': 42, 'org_unit_id': 1, 'is_deleted': False, 'revision': 1}]
        load(self.db, 'reference', lambda: catalog(first))
        load(self.db, 'reference', lambda: catalog(first, '2026-10-02T12:00:00+00:00'))
        changed = [dict(first[0], org_unit_id=2, revision=2)]
        load(self.db, 'reference', lambda: catalog(changed, '2026-10-03T12:00:00+00:00'))
        deleted = [dict(changed[0], is_deleted=True, revision=3)]
        load(self.db, 'reference', lambda: catalog(deleted, '2026-10-04T12:00:00+00:00'))
        versions = self.db.execute('SELECT payload,valid_from,valid_to FROM dwh.dimension_version ORDER BY valid_from').fetchall()
        self.assertEqual(len(versions), 3)
        self.assertEqual(json.loads(versions[0][0])['org_unit_id'], 1)
        self.assertEqual(versions[0][2], versions[1][1])
        self.assertEqual(versions[1][2], versions[2][1])
        self.assertIsNone(versions[2][2])
        self.assertTrue(json.loads(versions[2][0])['is_deleted'])
        # Absence in a later full scan must not become an invented deletion.
        load(self.db, 'reference', lambda: catalog([], '2026-10-05T12:00:00+00:00'))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM dwh.dimension_version').fetchone()[0], 3)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM app.subject_binding').fetchone()[0], 0)

    def test_snapshot_is_one_complete_successful_batch_per_day(self):
        with patch('etl.now', return_value='2026-10-01T12:00:00+00:00'):
            load(self.db, 'reference', lambda: catalog([{'id': 1, 'revision': 1}]))
        with patch('etl.now', return_value='2026-10-01T18:00:00+00:00'):
            load(self.db, 'reference', lambda: catalog([{'id': 1, 'revision': 2}, {'id': 2}], '2026-10-01T18:00:00+00:00'))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM dwh.source_snapshot').fetchone()[0], 1)
        payload = self.db.execute('SELECT payload FROM dwh.source_snapshot').fetchone()[0]
        self.assertEqual(json.loads(payload)['revision'], 1)
        with patch('etl.now', return_value='2026-10-02T12:00:00+00:00'):
            load(self.db, 'reference', lambda: catalog([{'id': 1, 'revision': 2}, {'id': 2}], '2026-10-02T12:00:00+00:00'))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM dwh.source_snapshot').fetchone()[0], 3)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM etl.snapshot_batch').fetchone()[0], 2)

    def test_stale_or_timezone_free_batch_cannot_replace_current_history(self):
        load(self.db, 'reference', lambda: catalog([{'id': 42, 'revision': 2}], '2026-10-02T12:00:00Z'))
        for stamp in ['2026-10-01T12:00:00Z', '2026-10-03T12:00:00']:
            with self.assertRaises(Rejected):
                load(self.db, 'reference', lambda: catalog([{'id': 42, 'revision': 1}], stamp))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM dwh.dimension_version').fetchone()[0], 1)
        self.assertEqual(json.loads(self.db.execute('SELECT payload FROM dwh.source_record').fetchone()[0])['revision'], 2)

    def test_failure_rolls_back_closed_versions_and_new_daily_snapshot(self):
        with patch('etl.now', return_value='2026-10-01T12:00:00+00:00'):
            load(self.db, 'reference', lambda: catalog([{'id': 42, 'revision': 1}]))
        def broken():
            entities, cursor, stamp, _ = catalog([{'id': 42, 'revision': 2}], '2026-10-02T12:00:00Z')
            return entities, cursor, stamp, [('bad', 'user', 'project', None, '2026-10-02', -1)]
        with patch('etl.now', return_value='2026-10-02T12:00:00+00:00'), self.assertRaises(Rejected):
            load(self.db, 'reference', broken)
        row = self.db.execute('SELECT payload,valid_to FROM dwh.dimension_version').fetchone()
        self.assertEqual(json.loads(row[0])['revision'], 1); self.assertIsNone(row[1])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM etl.snapshot_batch').fetchone()[0], 1)

    def test_all_five_tracker_resources_and_nonpaged_status_contract(self):
        result = load(self.db, 'tracker', lambda: tracker_extract(Tracker()))
        self.assertEqual(result['rows'], 10)
        resources = {row[0] for row in self.db.execute('SELECT DISTINCT entity FROM dwh.source_record')}
        self.assertEqual(resources, {'work-items', 'time-logs', 'iterations', 'history', 'statuses'})
        for resource, field in [('history', 'occurredAt'), ('iterations', 'state'), ('statuses', 'category')]:
            data = fixture(); del data[resource][0][field]
            with self.assertRaisesRegex(Rejected, 'CONTRACT'):
                tracker_extract(Tracker(data))


@unittest.skipUnless(os.getenv('REPORTS_TEST_DATABASE_URL'), 'PostgreSQL test DSN not supplied')
class ConcurrentSource(unittest.TestCase):
    def test_parallel_source_job_is_rejected_before_extraction(self):
        dsn = os.environ['REPORTS_TEST_DATABASE_URL']
        left, right = Database(dsn), Database(dsn)
        left.initialize(); right.initialize()
        entered, release = threading.Event(), threading.Event()
        errors = []
        def extract():
            entered.set()
            if not release.wait(10): raise RuntimeError('Test extraction timed out')
            return catalog([])
        def run():
            try: load(left, 'concurrency-test', extract)
            except Exception as error: errors.append(type(error).__name__)
        thread = threading.Thread(target=run); thread.start()
        try:
            self.assertTrue(entered.wait(5))
            with self.assertRaisesRegex(Rejected, 'SOURCE_LOAD_IN_PROGRESS'):
                load(right, 'concurrency-test', lambda: self.fail('Concurrent extraction started'))
        finally:
            release.set(); thread.join(10); left.close(); right.close()
        self.assertFalse(thread.is_alive()); self.assertEqual(errors, [])


if __name__ == '__main__': unittest.main()
