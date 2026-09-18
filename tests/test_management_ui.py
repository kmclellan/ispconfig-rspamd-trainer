import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ManagementUITests(unittest.TestCase):
    def setUp(self):
        self.index = (
            ROOT / "ispconfig/interface/web/rspamd_trainer/index.php"
        ).read_text()
        self.template = (
            ROOT / "ispconfig/interface/web/rspamd_trainer/templates/index.htm"
        ).read_text()
        self.broker = (
            ROOT / "ispconfig/interface/web/rspamd_trainer/lib/broker.inc.php"
        ).read_text()

    def test_mutations_use_ispconfig_csrf(self):
        self.assertIn("csrf_token_check()", self.index)
        self.assertIn("csrf_token_get('rspamd_trainer')", self.index)

    def test_ui_is_admin_only(self):
        self.assertIn("check_module_permissions('rspamd_trainer')", self.index)
        self.assertIn("is_admin()", self.index)

    def test_ui_uses_broker_not_shell_or_database(self):
        combined = self.index + "\n" + self.broker
        for forbidden in (
            "shell_exec(",
            "exec(",
            "passthru(",
            "popen(",
            "$app->db",
            "mysqli",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertIn("'/run/ispconfig-rspamd-trainer/broker.sock'", self.broker)
        self.assertIn("'unix://' . $socket_path", self.broker)

    def test_actions_are_fixed_broker_operations(self):
        for operation in (
            "'discovery'",
            "'dry_run'",
            "'run_async'",
            "'policy_set'",
            "'spam_source_set'",
        ):
            self.assertIn(operation, self.index)
        self.assertNotIn("'run', 'args'", self.index)

    def test_spam_source_requires_explicit_confirmation(self):
        self.assertIn("confirm_spam_", self.index)
        self.assertIn("spam_confirmation_required_txt", self.index)
        self.assertIn("I confirm every non-Ham message", (
            ROOT / "ispconfig/interface/web/rspamd_trainer/lib/lang/en.lng"
        ).read_text())

    def test_buttons_submit_page_form_to_fixed_module_actions(self):
        self.assertIn('data-submit-form="pageForm"', self.template)
        self.assertIn("action=policy_save&id=", self.template)
        self.assertIn("action=spam_enable&id=", self.template)
        self.assertIn("action=dry_run", self.template)


if __name__ == "__main__":
    unittest.main()
