import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ispconfig_rspamd_trainer.inventory import MailboxRecord, SpamSource
from ispconfig_rspamd_trainer.orchestrator import RunCoordinator, RunInProgress, exclusive_run_lock
from ispconfig_rspamd_trainer.policy import MailboxPolicy
from ispconfig_rspamd_trainer.state import StateStore


class FakeDovecot:
    def __init__(self):
        self.mailboxes = {}
        self.fetches = []
        self.moves = []
        self.expunges = []

    def set_mailbox(self, user, mailbox, refs):
        self.mailboxes[(user, mailbox)] = list(refs)

    def search_mailbox(self, user, mailbox, savedbefore_days=None):
        return list(self.mailboxes.get((user, mailbox), []))

    def search_aged_inbox(self, user, age_days):
        return list(self.mailboxes.get((user, "AGED"), []))

    def fetch_text(self, user, guid, uid):
        self.fetches.append((user, guid, uid))
        return ("message-{}-{}".format(guid, uid)).encode()

    def move_uid(self, user, destination, guid, uid):
        self.moves.append((user, destination, guid, uid))

    def expunge_uid(self, user, guid, uid):
        self.expunges.append((user, guid, uid))


class FakeRspamd:
    def __init__(self, fail_ham_uid=None):
        self.spam = []
        self.ham = []
        self.fail_ham_uid = fail_ham_uid

    def learn_spam(self, message, deliver_to=None):
        self.spam.append((message, deliver_to))

    def learn_ham(self, message, deliver_to=None):
        if self.fail_ham_uid is not None and message.endswith(
            "-{}".format(self.fail_ham_uid).encode()
        ):
            raise RuntimeError("simulated")
        self.ham.append((message, deliver_to))


class OrchestratorTests(unittest.TestCase):
    def make_state(self):
        td = tempfile.TemporaryDirectory()
        store = StateStore(Path(td.name) / "state.db")
        store.initialize()
        return td, store

    def test_imap_only_auto_mailbox_can_train_without_observation_warmup(self):
        td, store = self.make_state()
        try:
            record = MailboxRecord(1, "imap@example.test", 1, True, False)
            store.reconcile_inventory([record])
            dovecot = FakeDovecot()
            dovecot.set_mailbox(record.email, "AGED", [("g1", 1)])
            rspamd = FakeRspamd()
            summary = RunCoordinator(store, dovecot, rspamd).execute()
            self.assertEqual(1, summary.learned_ham)
            self.assertEqual(1, summary.mailboxes_eligible)
            self.assertTrue(store.was_learned(1, "g1", 1, "ham"))
        finally:
            td.cleanup()

    def test_mixed_capable_auto_requires_observation_evidence(self):
        td, store = self.make_state()
        try:
            record = MailboxRecord(1, "mixed@example.test", 1, True, True)
            store.reconcile_inventory([record])
            dovecot = FakeDovecot()
            dovecot.set_mailbox(record.email, "AGED", [("g1", 1)])
            summary = RunCoordinator(store, dovecot, FakeRspamd()).execute()
            self.assertEqual(0, summary.candidate_ham)
            self.assertEqual([], dovecot.fetches)
        finally:
            td.cleanup()

    def test_aged_ham_is_not_relearned_after_success(self):
        td, store = self.make_state()
        try:
            record = MailboxRecord(1, "imap@example.test", 1, True, False)
            store.reconcile_inventory([record])
            dovecot = FakeDovecot()
            dovecot.set_mailbox(record.email, "AGED", [("g1", 1)])
            rspamd = FakeRspamd()
            coordinator = RunCoordinator(store, dovecot, rspamd)
            first = coordinator.execute()
            second = coordinator.execute()
            self.assertEqual(1, first.learned_ham)
            self.assertEqual(0, second.learned_ham)
            self.assertEqual(1, second.skipped)
            self.assertEqual(1, len(rspamd.ham))
        finally:
            td.cleanup()

    def test_dry_run_never_fetches_or_learns(self):
        td, store = self.make_state()
        try:
            record = MailboxRecord(1, "imap@example.test", 1, True, False)
            store.reconcile_inventory([record])
            dovecot = FakeDovecot()
            dovecot.set_mailbox(record.email, "AGED", [("g1", 1), ("g1", 2)])
            rspamd = FakeRspamd()
            summary = RunCoordinator(store, dovecot, rspamd).execute(dry_run=True)
            self.assertEqual(2, summary.candidate_ham)
            self.assertEqual(0, summary.attempted)
            self.assertEqual([], dovecot.fetches)
            self.assertEqual([], rspamd.ham)
        finally:
            td.cleanup()

    def test_dedicated_spam_source_moves_spam_and_deletes_explicit_ham(self):
        td, store = self.make_state()
        try:
            record = MailboxRecord(9, "spam@example.test", 1, True, False)
            store.reconcile_inventory([record])
            store.set_spam_source(SpamSource(9, True, "Trained", "Ham"))
            dovecot = FakeDovecot()
            dovecot.set_mailbox(record.email, "INBOX", [("gs", 1)])
            dovecot.set_mailbox(record.email, "Ham", [("gh", 2)])
            rspamd = FakeRspamd()
            summary = RunCoordinator(store, dovecot, rspamd).execute()
            self.assertEqual(1, summary.learned_spam)
            self.assertEqual(1, summary.learned_ham)
            self.assertEqual(
                [(record.email, "Trained", "gs", 1)],
                dovecot.moves,
            )
            self.assertEqual([(record.email, "gh", 2)], dovecot.expunges)
        finally:
            td.cleanup()

    def test_ham_failure_preserves_message_by_not_expunging(self):
        td, store = self.make_state()
        try:
            record = MailboxRecord(9, "spam@example.test", 1, True, False)
            store.reconcile_inventory([record])
            store.set_spam_source(SpamSource(9, True, "Trained", "Ham"))
            dovecot = FakeDovecot()
            dovecot.set_mailbox(record.email, "Ham", [("gh", 2)])
            summary = RunCoordinator(
                store, dovecot, FakeRspamd(fail_ham_uid=2)
            ).execute()
            self.assertEqual(1, summary.failed)
            self.assertEqual([], dovecot.expunges)
        finally:
            td.cleanup()

    def test_batch_size_limits_aged_ham(self):
        td, store = self.make_state()
        try:
            record = MailboxRecord(1, "imap@example.test", 1, True, False)
            store.reconcile_inventory([record])
            store.set_policy(MailboxPolicy(1, mode="auto", age_days=30, batch_size=2))
            dovecot = FakeDovecot()
            dovecot.set_mailbox(
                record.email, "AGED", [("g1", 1), ("g1", 2), ("g1", 3)]
            )
            summary = RunCoordinator(store, dovecot, FakeRspamd()).execute()
            self.assertEqual(2, summary.attempted)
            self.assertEqual(2, summary.learned_ham)
        finally:
            td.cleanup()

    def test_lock_rejects_concurrent_run(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.lock"
            with exclusive_run_lock(path):
                with self.assertRaises(RunInProgress):
                    with exclusive_run_lock(path):
                        pass


if __name__ == "__main__":
    unittest.main()
