import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ISPConfigLayoutTests(unittest.TestCase):
    def test_module_config_is_in_supported_lib_location(self):
        self.assertTrue(
            (ROOT / "ispconfig/interface/web/rspamd_trainer/lib/module.conf.php").is_file()
        )
        self.assertFalse(
            (ROOT / "ispconfig/interface/web/rspamd_trainer/module.conf.php").exists()
        )

    def test_page_checks_module_permission_and_admin(self):
        text = (ROOT / "ispconfig/interface/web/rspamd_trainer/index.php").read_text()
        self.assertIn("check_module_permissions('rspamd_trainer')", text)
        self.assertIn("is_admin()", text)
        self.assertIn("form.tpl.htm", text)

    def test_module_does_not_reference_shell_execution(self):
        base = ROOT / "ispconfig/interface/web/rspamd_trainer"
        combined = "\n".join(
            p.read_text(errors="replace")
            for p in base.rglob("*.php")
        )
        for forbidden in ("shell_exec(", "exec(", "system(", "passthru(", "popen("):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
