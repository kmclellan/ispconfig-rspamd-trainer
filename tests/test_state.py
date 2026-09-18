import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ispconfig_rspamd_trainer.inventory import MailboxRecord, SpamSource
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

    def test_inventory_reconciliation_tracks_missing_without_deleting_policy(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(Path(td) / "state.db")
            store.initialize()
            record = MailboxRecord(7, "old@example.test", 1, True, False)
            store.reconcile_inventory([record])
            store.set_policy(MailboxPolicy(7, "imap", 30, 100))
            renamed = MailboxRecord(7, "new@example.test", 1, True, False)
            store.reconcile_inventory([renamed])
            self.assertEqual("new@example.test", store.get_inventory(7).email)
            store.reconcile_inventory([])
            self.assertEqual([], store.list_inventory(present=True))
            self.assertEqual(1, len(store.list_inventory(present=False)))
            self.assertEqual("imap", store.get_policy(7).mode)

    def test_spam_source_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(Path(td) / "state.db")
            store.initialize()
            source = SpamSource(9, True, "Trained", "Ham")
            store.set_spam_source(source)
            self.assertEqual([source], store.list_spam_sources(enabled_only=True))

    def test_learned_message_marker(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(Path(td) / "state.db")
            store.initialize()
            self.assertFalse(store.was_learned(2, "guid", 8, "ham"))
            store.mark_learned(2, "guid", 8, "ham")
            self.assertTrue(store.was_learned(2, "guid", 8, "ham"))

    def test_run_log_records_aggregate_only(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(Path(td) / "state.db")
            store.initialize()
            run_id = store.start_run(dry_run=True)
            store.finish_run(
                run_id,
                {
                    "attempted": 0,
                    "candidate_ham": 4,
                    "candidate_spam": 2,
                    "failed": 0,
                },
                "success",
            )
            latest = store.latest_run()
            self.assertEqual(run_id, latest["id"])
            self.assertEqual(1, latest["dry_run"])
            self.assertEqual(4, latest["candidate_ham"])
            self.assertEqual(2, latest["candidate_spam"])
            self.assertNotIn("email", latest)


if __name__ == "__main__":
    unittest.main()
