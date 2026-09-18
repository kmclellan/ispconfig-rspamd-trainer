import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ispconfig_rspamd_trainer.inventory import MailboxRecord
from ispconfig_rspamd_trainer.observer import ObservationError, ObservationService
from ispconfig_rspamd_trainer.state import StateStore


class ObserverTests(unittest.TestCase):
    def make_store(self):
        td = tempfile.TemporaryDirectory()
        store = StateStore(Path(td.name) / "state.db")
        store.initialize()
        store.reconcile_inventory(
            [MailboxRecord(7, "user@example.test", 1, True, True)]
        )
        return td, store

    def test_imap_observation_records_only_timestamp_for_known_mailbox(self):
        td, store = self.make_store()
        try:
            when = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
            result = ObservationService(store).observe(
                "imap", "USER@example.test", when=when
            )
            self.assertTrue(result["recorded"])
            obs = store.get_observation(7)
            self.assertEqual(when, obs.last_imap)
            self.assertIsNone(obs.last_pop3)
        finally:
            td.cleanup()

    def test_pop3_observation_records_pop3(self):
        td, store = self.make_store()
        try:
            when = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
            ObservationService(store).observe(
                "pop3", "user@example.test", when=when
            )
            self.assertEqual(when, store.get_observation(7).last_pop3)
        finally:
            td.cleanup()

    def test_unknown_user_is_ignored_not_created(self):
        td, store = self.make_store()
        try:
            result = ObservationService(store).observe(
                "imap", "unknown@example.test"
            )
            self.assertFalse(result["recorded"])
        finally:
            td.cleanup()

    def test_protocol_is_fixed(self):
        td, store = self.make_store()
        try:
            with self.assertRaises(ObservationError):
                ObservationService(store).observe(
                    "smtp", "user@example.test"
                )
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
