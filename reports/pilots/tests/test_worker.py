"""Failure recovery, fixed scheduling, freshness and readiness."""
import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

from test_pipeline import Tracker
from adapters import Rejected
from api import freshness, report
from db import Database
from etl import load, tracker_extract
from worker import healthy, repeat


class Clock:
    def __init__(self): self.current, self.waits, self.stopped = 0.0, [], False
    def __call__(self): return self.current
    def is_set(self): return self.stopped
    def wait(self, seconds): self.waits.append(seconds); self.current += seconds


class Worker(unittest.TestCase):
    def test_failures_are_retried_without_logging_dependency_secrets(self):
        clock, calls = Clock(), []
        def job():
            calls.append(1)
            if len(calls) == 1: raise RuntimeError('Do not log this dependency DSN')
            return {'status': 'LOADED'}
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(output):
            state = Path(tmp)/'worker.json'
            self.assertEqual(repeat(job, 60, clock, max_runs=2, clock=clock, state_file=state), 0)
            self.assertTrue(healthy(state, 180))
        self.assertEqual(clock.waits, [60])
        self.assertNotIn('DSN', output.getvalue())
        self.assertIn('DEPENDENCY_UNAVAILABLE', output.getvalue())

    def test_long_jobs_skip_ticks_and_do_not_overlap_or_burst(self):
        clock = Clock()
        def slow(): clock.current += 125; return {'status': 'LOADED'}
        with redirect_stdout(io.StringIO()):
            repeat(slow, 60, clock, max_runs=2, clock=clock)
        self.assertEqual(clock.waits, [60])

    def test_stop_prevents_another_run_and_failed_or_old_state_is_unhealthy(self):
        stop = threading.Event(); calls = []
        def job(): calls.append(1); stop.set(); return {'status': 'LOADED'}
        with redirect_stdout(io.StringIO()): self.assertEqual(repeat(job, 60, stop), 0)
        self.assertEqual(len(calls), 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'state.json'
            for status, stamp in [('REJECTED', datetime.now(timezone.utc)), ('LOADED', datetime.now(timezone.utc)-timedelta(hours=1))]:
                path.write_text(json.dumps({'status': status, 'completed_at': stamp.isoformat()}))
                self.assertFalse(healthy(path, 180))

    def test_source_failure_preserves_data_but_marks_it_stale_then_recovers(self):
        db = Database('sqlite::memory:'); db.initialize()
        try:
            load(db, 'tracker', lambda: tracker_extract(Tracker()))
            self.assertEqual(freshness(db)[1], 'FRESH')
            with self.assertRaises(Rejected):
                load(db, 'tracker', lambda: (_ for _ in ()).throw(Rejected('SOURCE_UNAVAILABLE')))
            self.assertEqual(freshness(db)[1], 'STALE')
            admin = {'sub': 'admin', 'resource_access': {'reports': {'roles': ['reports-admin']}}}
            self.assertEqual(sum(row['hours'] for row in report(db, admin)['data']), 11.25)
            load(db, 'tracker', lambda: tracker_extract(Tracker()))
            self.assertEqual(freshness(db)[1], 'FRESH')
        finally: db.close()


if __name__ == '__main__': unittest.main()
