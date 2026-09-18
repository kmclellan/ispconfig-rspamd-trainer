import unittest

from ispconfig_rspamd_trainer.ispconfig import mailbox_from_row


class ISPConfigTests(unittest.TestCase):
    def test_row_mapping_uses_protocol_disable_flags(self):
        record = mailbox_from_row(
            {
                "mailuser_id": 7,
                "server_id": 1,
                "email": "user@example.test",
                "disableimap": "n",
                "disablepop3": "y",
                "access": "y",
                "disabledoveadm": "n",
            }
        )
        self.assertTrue(record.imap_enabled)
        self.assertFalse(record.pop3_enabled)
        self.assertTrue(record.active)
        self.assertTrue(record.doveadm_enabled)

    def test_unexpected_disable_value_is_rejected(self):
        with self.assertRaises(ValueError):
            mailbox_from_row(
                {
                    "mailuser_id": 7,
                    "server_id": 1,
                    "email": "user@example.test",
                    "disableimap": "maybe",
                    "disablepop3": "n",
                    "access": "y",
                    "disabledoveadm": "n",
                }
            )


if __name__ == "__main__":
    unittest.main()
