import unittest

from ispconfig_rspamd_trainer.inventory import MailboxRecord, access_mode_summary


class InventoryTests(unittest.TestCase):
    def test_access_modes(self):
        rows = [
            MailboxRecord(1, "a@example.test", 1, True, False),
            MailboxRecord(2, "b@example.test", 1, False, True),
            MailboxRecord(3, "c@example.test", 1, True, True),
            MailboxRecord(4, "d@example.test", 1, False, False),
            MailboxRecord(5, "e@example.test", 1, True, False, active=False),
        ]
        self.assertEqual(
            {
                "imap_only": 1,
                "pop3_only": 1,
                "mixed_capable": 1,
                "no_remote_access": 1,
                "inactive": 1,
            },
            access_mode_summary(rows),
        )

    def test_invalid_address_is_rejected(self):
        with self.assertRaises(ValueError):
            MailboxRecord(1, "-bad", 1, True, False).validate()


if __name__ == "__main__":
    unittest.main()
