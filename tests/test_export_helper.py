import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportHelperTests(unittest.TestCase):
    def test_export_query_does_not_select_sensitive_mail_user_fields(self):
        text = (ROOT / "bin/export_mailboxes.php").read_text()
        query_region = text[text.index('$sql ='):text.index('$result =')]
        for forbidden in (
            "password",
            "maildir",
            "name",
            "forward",
            "autoresponder",
            "custom_mailfilter",
        ):
            self.assertNotIn(forbidden, query_region)
        for required in (
            "mailuser_id",
            "server_id",
            "email",
            "disableimap",
            "disablepop3",
            "access",
            "disabledoveadm",
        ):
            self.assertIn(required, query_region)


if __name__ == "__main__":
    unittest.main()
