import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ispconfig_rspamd_trainer.policy import MailboxPolicy
from ispconfig_rspamd_trainer.state import StateStore


class StateTests(unittest.TestCase):
    def test_policy_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(Path(td) / "state.db")
            store.initialize()
            policy = MailboxPolicy(7, "imap", 45, 50)
            store.set_policy(policy)
            self.assertEqual(policy, store.get_policy(7))
            self.assertEqual([policy], list(store.list_policies()))

    def test_protocol_observations_keep_first_seen_and_latest_protocol(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(Path(td) / "state.db")
            store.initialize()
            first = datetime(2026, 1, 1, tzinfo=timezone.utc)
            later = first + timedelta(days=10)
            store.record_protocol(7, "imap", first)
            store.record_protocol(7, "pop3", later)
            obs = store.get_observation(7)
            self.assertEqual(first, obs.observed_since)
            self.assertEqual(first, obs.last_imap)
            self.assertEqual(later, obs.last_pop3)


if __name__ == "__main__":
    unittest.main()
