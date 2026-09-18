import unittest
from datetime import datetime, timedelta, timezone

from ispconfig_rspamd_trainer.policy import MailboxPolicy, ProtocolObservation, aged_inbox_allowed


class PolicyTests(unittest.TestCase):
    def test_default_auto_unknown_is_not_allowed(self):
        self.assertFalse(aged_inbox_allowed(MailboxPolicy(1), ProtocolObservation()))

    def test_auto_requires_warmup(self):
        now = datetime(2026, 9, 18, tzinfo=timezone.utc)
        obs = ProtocolObservation(
            observed_since=now - timedelta(days=10),
            last_imap=now - timedelta(days=1),
        )
        self.assertFalse(aged_inbox_allowed(MailboxPolicy(1), obs, now=now))

    def test_auto_imap_after_warmup_without_recent_pop3_is_allowed(self):
        now = datetime(2026, 9, 18, tzinfo=timezone.utc)
        obs = ProtocolObservation(
            observed_since=now - timedelta(days=31),
            last_imap=now - timedelta(days=1),
        )
        self.assertTrue(aged_inbox_allowed(MailboxPolicy(1), obs, now=now))

    def test_recent_pop3_suspends_auto(self):
        now = datetime(2026, 9, 18, tzinfo=timezone.utc)
        obs = ProtocolObservation(
            observed_since=now - timedelta(days=100),
            last_imap=now - timedelta(days=1),
            last_pop3=now - timedelta(days=30),
        )
        self.assertFalse(aged_inbox_allowed(MailboxPolicy(1), obs, now=now))

    def test_old_pop3_no_longer_blocks_auto(self):
        now = datetime(2026, 9, 18, tzinfo=timezone.utc)
        obs = ProtocolObservation(
            observed_since=now - timedelta(days=100),
            last_imap=now - timedelta(days=1),
            last_pop3=now - timedelta(days=91),
        )
        self.assertTrue(aged_inbox_allowed(MailboxPolicy(1), obs, now=now))

    def test_explicit_imap_does_not_need_warmup(self):
        self.assertTrue(
            aged_inbox_allowed(MailboxPolicy(1, mode="imap"), ProtocolObservation())
        )

    def test_mixed_never_allows_aged_inbox(self):
        now = datetime(2026, 9, 18, tzinfo=timezone.utc)
        self.assertFalse(
            aged_inbox_allowed(
                MailboxPolicy(1, mode="mixed"),
                ProtocolObservation(observed_since=now, last_imap=now),
                now=now,
            )
        )

    def test_minimum_age_is_enforced(self):
        with self.assertRaises(ValueError):
            MailboxPolicy(1, age_days=29).validate()


if __name__ == "__main__":
    unittest.main()
