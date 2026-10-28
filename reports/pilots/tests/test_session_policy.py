"""Expiration is absolute, and missing/malformed session expiry fails closed."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'superset'))
from session_policy import expired


class SessionExpiry(unittest.TestCase):
    def test_verified_expiry_is_absolute_and_not_extended_by_activity(self):
        self.assertFalse(expired(300, now=299))
        self.assertTrue(expired(300, now=300))
        self.assertTrue(expired(300, now=301))

    def test_missing_or_malformed_expiry_fails_closed(self):
        for value in [None, True, '300', 300.0, {}, []]:
            self.assertTrue(expired(value, now=1))
