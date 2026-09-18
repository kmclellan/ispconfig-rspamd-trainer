import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ispconfig_rspamd_trainer.inventory import MailboxRecord
from ispconfig_rspamd_trainer.service import DependencyUnavailable, TrainerService
from ispconfig_rspamd_trainer.state import StateStore


class FakeInventorySource:
    def list_mailboxes(self):
        return [
            MailboxRecord(1, "imap@example.test", 1, True, False),
            MailboxRecord(2, "pop@example.test", 1, False, True),
        ]


class FakeRspamd:
    def stat(self):
        return {"scanned": 123}


class FakeSummary:
    failed = 0

    def __init__(self, dry_run):
        self.dry_run = dry_run

    def as_dict(self):
        return {
            "dry_run": self.dry_run,
            "attempted": 0 if self.dry_run else 2,
            "learned_spam": 0 if self.dry_run else 1,
            "learned_ham": 0 if self.dry_run else 1,
            "skipped": 0,
            "failed": 0,
            "candidate_spam": 1,
            "candidate_ham": 1,
            "mailboxes_considered": 2,
            "mailboxes_eligible": 1,
            "warnings": [],
        }


class FakeCoordinator:
    def execute(self, dry_run=False):
        return FakeSummary(dry_run)


class FakeLauncher:
    def __init__(self, available=True):
        self._available = available
        self.started = 0

    def available(self):
        return self._available

    def start(self):
        self.started += 1
        return {"started": True, "pid": 1234}


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.store = StateStore(Path(self.td.name) / "state.db")
        self.store.initialize()
        self.service = TrainerService(self.store)

    def tearDown(self):
        self.td.cleanup()

    def test_unknown_operation_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.handle({"op": "shell", "args": {}})

    def test_arbitrary_argument_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.handle({"op": "health", "args": {"command": "id"}})

    def test_policy_set_and_get(self):
        self.store.reconcile_inventory(
            [MailboxRecord(5, "policy@example.test", 1, True, False)]
        )
        response = self.service.handle({
            "op": "policy_set",
            "args": {"mailbox_id": 5, "mode": "auto", "age_days": 30, "batch_size": 100},
        })
        self.assertEqual(5, response["policy"]["mailbox_id"])
        got = self.service.handle({"op": "policy_get", "args": {"mailbox_id": 5}})
        self.assertEqual("auto", got["policy"]["mode"])

    def test_policy_rejects_unknown_mailbox(self):
        with self.assertRaises(ValueError):
            self.service.handle({
                "op": "policy_set",
                "args": {
                    "mailbox_id": 500,
                    "mode": "auto",
                    "age_days": 30,
                    "batch_size": 100,
                },
            })

    def test_discovery_reconciles_synthetic_inventory(self):
        service = TrainerService(self.store, inventory_source=FakeInventorySource())
        result = service.handle({"op": "discovery", "args": {}})
        self.assertEqual(2, result["present"])
        self.assertEqual(1, result["access_modes"]["imap_only"])
        self.assertEqual(1, result["access_modes"]["pop3_only"])

    def test_classifier_stats_uses_injected_controller(self):
        service = TrainerService(self.store, rspamd=FakeRspamd())
        result = service.handle({"op": "classifier_stats", "args": {}})
        self.assertEqual({"scanned": 123}, result["stats"])

    def test_unconfigured_dependency_fails_closed(self):
        with self.assertRaises(DependencyUnavailable):
            self.service.handle({"op": "classifier_stats", "args": {}})

    def test_dry_run_and_run_are_persisted(self):
        service = TrainerService(
            self.store,
            inventory_source=FakeInventorySource(),
            coordinator=FakeCoordinator(),
        )
        dry = service.handle({"op": "dry_run", "args": {}})
        self.assertEqual(0, dry["attempted"])
        self.assertEqual("success", self.store.latest_run()["status"])
        real = service.handle({"op": "run", "args": {}})
        self.assertEqual(2, real["attempted"])
        self.assertEqual(1, real["learned_spam"])

    def test_inventory_payload_exposes_observation_and_eligibility(self):
        service = TrainerService(
            self.store,
            inventory_source=FakeInventorySource(),
        )
        service.handle({"op": "discovery", "args": {}})
        self.store.record_protocol(
            1,
            "imap",
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        payload = service.handle({"op": "inventory_list", "args": {}})
        by_id = {row["mailbox_id"]: row for row in payload["mailboxes"]}
        self.assertEqual("imap", by_id[1]["observed_access"])
        self.assertTrue(by_id[1]["aged_inbox_eligible"])
        self.assertEqual("unknown", by_id[2]["observed_access"])
        self.assertFalse(by_id[2]["aged_inbox_eligible"])

    def test_async_run_uses_fixed_launcher(self):
        launcher = FakeLauncher()
        service = TrainerService(self.store, async_launcher=launcher)
        result = service.handle({"op": "run_async", "args": {}})
        self.assertTrue(result["started"])
        self.assertEqual(1, launcher.started)

    def test_health_reports_async_launcher_availability(self):
        launcher = FakeLauncher(available=False)
        service = TrainerService(self.store, async_launcher=launcher)
        result = service.handle({"op": "health", "args": {}})
        self.assertFalse(result["async_run"])

    def test_spam_source_must_reference_known_mailbox(self):
        with self.assertRaises(ValueError):
            self.service.handle({
                "op": "spam_source_set",
                "args": {
                    "mailbox_id": 99,
                    "enabled": True,
                    "archive_mailbox": "Trained",
                    "ham_mailbox": "Ham",
                },
            })


if __name__ == "__main__":
    unittest.main()
