"""Period/pagination must preserve totals and the mandatory employee scope."""
import unittest
import json
import os
from test_pipeline import Tracker
from api import report
from db import Database
from demo import MEMBER_1, MEMBER_2
from etl import load, tracker_extract


class Reports(unittest.TestCase):
    def setUp(self):
        self.db = Database('sqlite::memory:'); self.db.initialize()
        with self.db.transaction():
            for subject in (MEMBER_1, MEMBER_2):
                self.db.execute('INSERT INTO app.subject_binding VALUES (?,?)', (subject, subject))
        load(self.db, 'tracker', lambda: tracker_extract(Tracker()))
        self.member = {'sub': MEMBER_1, 'resource_access': {'reports': {'roles': ['reports-member']}}}
        self.admin = {'sub': 'admin', 'resource_access': {'reports': {'roles': ['reports-admin']}}}

    def tearDown(self): self.db.close()

    def test_period_limits_and_pagination_never_remove_member_scope(self):
        first = report(self.db, self.member, 'record', 1, 0, '2026-10-01', '2026-10-04')
        second = report(self.db, self.member, 'record', 1, 1, '2026-10-01', '2026-10-04')
        self.assertTrue(first['pagination']['hasMore'])
        self.assertFalse(second['pagination']['hasMore'])
        self.assertEqual(first['pagination']['totalGroups'], 2)
        self.assertNotEqual(first['data'][0]['dimension'], second['data'][0]['dimension'])
        self.assertEqual(sum(row['hours'] for data in [first, second] for row in data['data']), 2.5)
        self.assertEqual(report(self.db, self.member, start_date='2020-01-01', end_date='2020-01-02')['data'], [])

    def test_more_than_1000_groups_are_not_silently_lost(self):
        with self.db.transaction():
            for i in range(1001):
                self.db.execute('INSERT INTO dwh.fact_time_log(id,user_id,project_id,work_item_id,logged_date,hours_cents) VALUES (?,?,?,?,?,?)',
                                ('extra-'+str(i), MEMBER_1, 'project-'+str(i), None, '2026-10-01', 100))
        page = report(self.db, self.member, 'project')
        self.assertEqual(page['pagination']['totalGroups'], 1002)
        self.assertTrue(page['pagination']['hasMore'])
        tail = report(self.db, self.member, 'project', offset=1000)
        self.assertEqual(len(tail['data']), 2)
        self.assertFalse(tail['pagination']['hasMore'])

    def test_invalid_period_or_pagination_is_rejected(self):
        for args in [{'limit': True}, {'limit': 0}, {'limit': 1001}, {'offset': -1},
                     {'start_date': '2026-10-01'}, {'start_date': '2026-10-04', 'end_date': '2026-10-01'},
                     {'start_date': 'invalid', 'end_date': '2026-10-01'}]:
            with self.subTest(args=args), self.assertRaises(ValueError): report(self.db, self.member, **args)


@unittest.skipUnless(os.getenv('REPORTS_TEST_DATABASE_URL'), 'PostgreSQL test DSN not supplied')
class PostgreSQLSerialization(unittest.TestCase):
    def test_bigint_sum_is_json_serializable_in_actual_postgres(self):
        db = Database(os.environ['REPORTS_TEST_DATABASE_URL']); db.initialize()
        try:
            with db.transaction():
                for subject in (MEMBER_1, MEMBER_2):
                    db.execute('''INSERT INTO app.subject_binding VALUES (?,?)
                        ON CONFLICT(subject) DO UPDATE SET tracker_user_id=excluded.tracker_user_id''', (subject, subject))
            load(db, 'tracker', lambda: tracker_extract(Tracker()))
            member = {'sub': MEMBER_1, 'resource_access': {'reports': {'roles': ['reports-member']}}}
            payload = json.loads(json.dumps(report(db, member, 'employee')))
            self.assertEqual(payload['data'][0]['hours'], 3.75)
            self.assertEqual(payload['pagination']['totalGroups'], 1)
        finally: db.close()
