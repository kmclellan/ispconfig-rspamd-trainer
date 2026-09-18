import json
import tempfile
import unittest
from pathlib import Path

from ispconfig_rspamd_trainer.snapshot import SnapshotError, SnapshotMailboxSource


class SnapshotTests(unittest.TestCase):
    def test_snapshot_maps_minimal_mailbox_fields(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mailboxes.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "generated_at": "2026-09-18T12:00:00Z",
                        "mailboxes": [
                            {
                                "mailuser_id": 7,
                                "server_id": 1,
                                "email": "user@example.test",
                                "disableimap": "n",
                                "disablepop3": "y",
                                "access": "y",
                                "disabledoveadm": "n",
                            }
                        ],
                    }
                )
            )
            rows = SnapshotMailboxSource(path).list_mailboxes()
            self.assertEqual(1, len(rows))
            self.assertEqual("imap_only", rows[0].access_mode)

    def test_snapshot_rejects_unknown_schema(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mailboxes.json"
            path.write_text('{"schema": 999, "mailboxes": []}')
            with self.assertRaises(SnapshotError):
                SnapshotMailboxSource(path).list_mailboxes()


if __name__ == "__main__":
    unittest.main()
