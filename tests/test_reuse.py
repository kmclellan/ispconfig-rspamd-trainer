import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReuseTests(unittest.TestCase):
    def test_third_party_notices_cover_direct_reuse(self):
        notice = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
        self.assertIn("ispconfig-theme-customizer", notice)
        self.assertIn("Copyright (c) 2026 Wade John Beckett", notice)
        self.assertIn("train-spam-scanner", notice)
        self.assertIn("BSD 2-Clause License", notice)

    def test_assignment_helper_is_admin_only(self):
        text = (ROOT / "bin/assign_module.php").read_text()
        self.assertIn("WHERE typ = 'admin'", text)
        self.assertIn("'rspamd_trainer'", text)
        self.assertIn("Copyright (c) 2026 Wade Beckett", text)

    def test_unassignment_cleans_stale_startmodule(self):
        text = (ROOT / "bin/unassign_module.php").read_text()
        self.assertIn("startmodule", text)
        self.assertIn("'dashboard'", text)
        self.assertIn("return $x !== 'rspamd_trainer'", text)

    def test_sieve_ham_feedback_ignores_deletion_folders(self):
        text = (
            ROOT / "dovecot/sieve/ispconfig-rspamd-report-ham.sieve"
        ).read_text()
        for mailbox in ("Trash", "Deleted Items", "Deleted Messages"):
            self.assertIn(mailbox, text)
        self.assertIn("ispconfig-rspamd-learn-ham", text)

    def test_sieve_wrappers_delegate_to_single_feedback_command(self):
        spam = (
            ROOT / "dovecot/sieve-pipe/ispconfig-rspamd-learn-spam"
        ).read_text()
        ham = (
            ROOT / "dovecot/sieve-pipe/ispconfig-rspamd-learn-ham"
        ).read_text()
        self.assertIn('ispconfig-rspamd-feedback spam "$1"', spam)
        self.assertIn('ispconfig-rspamd-feedback ham "$1"', ham)
        self.assertNotIn("rspamc", spam)
        self.assertNotIn("rspamc", ham)


if __name__ == "__main__":
    unittest.main()
