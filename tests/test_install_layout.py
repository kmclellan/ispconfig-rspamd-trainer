import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path

from ispconfig_rspamd_trainer.install_layout import LayoutError, stage_repository


ROOT = Path(__file__).resolve().parents[1]


def tree_manifest(root):
    root = Path(root)
    result = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = stat.S_IMODE(path.stat().st_mode)
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result.append(("file", relative, mode, digest))
        elif path.is_dir():
            result.append(("dir", relative, mode, None))
    return result


class InstallLayoutTests(unittest.TestCase):
    def test_stage_contains_expected_runtime_layout(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            stage_repository(target, ROOT)

            expected = (
                "usr/local/bin/ispconfig-rspamd-trainer",
                "usr/local/bin/ispconfig-rspamd-trainer-broker",
                "usr/local/bin/ispconfig-rspamd-feedback",
                "usr/local/bin/ispconfig-rspamd-trainer-observer",
                "usr/local/bin/ispconfig-rspamd-observe",
                "usr/local/lib/ispconfig-rspamd-trainer/ispconfig_rspamd_trainer/broker.py",
                "usr/local/ispconfig/interface/web/rspamd_trainer/index.php",
                "usr/local/libexec/ispconfig-rspamd-trainer/export_mailboxes.php",
                "etc/systemd/system/ispconfig-rspamd-trainer-broker.service",
                "etc/systemd/system/ispconfig-rspamd-trainer-inventory.timer",
                "etc/ispconfig-rspamd-trainer/rspamd.ini.example",
                "usr/share/doc/ispconfig-rspamd-trainer/LICENSE",
            )
            for relative in expected:
                self.assertTrue((target / relative).is_file(), relative)

    def test_stage_does_not_activate_dovecot_service_snippets(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            stage_repository(target, ROOT)

            self.assertFalse((target / "etc/dovecot/conf.d").exists())
            examples = (
                target
                / "usr/share/doc/ispconfig-rspamd-trainer/examples/dovecot-2.4"
            )
            self.assertTrue(
                (examples / "98-ispconfig-rspamd-observer.conf.example").is_file()
            )
            self.assertTrue(
                (examples / "99-ispconfig-rspamd-trainer.conf.example").is_file()
            )

    def test_stage_filters_development_artifacts(self):
        source_backup = (
            ROOT / "packaging/wrappers/ispconfig-rspamd-trainer.bak.test-only"
        )
        pycache = ROOT / "src/ispconfig_rspamd_trainer/__pycache__/stage-test.pyc"
        try:
            source_backup.write_text("must not stage")
            pycache.parent.mkdir(parents=True, exist_ok=True)
            pycache.write_bytes(b"must not stage")
            with tempfile.TemporaryDirectory() as td:
                target = Path(td) / "root"
                stage_repository(target, ROOT)
                staged_names = [
                    path.name for path in target.rglob("*") if path.is_file()
                ]
                self.assertFalse(
                    any(".bak." in name for name in staged_names),
                    staged_names,
                )
                self.assertFalse(any(name.endswith(".pyc") for name in staged_names))
                self.assertFalse(
                    any(path.name == "__pycache__" for path in target.rglob("*"))
                )
        finally:
            source_backup.unlink(missing_ok=True)
            pycache.unlink(missing_ok=True)

    def test_stage_is_repeatable(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            stage_repository(target, ROOT)
            first = tree_manifest(target)
            stage_repository(target, ROOT)
            second = tree_manifest(target)
            self.assertEqual(first, second)

    def test_install_manifest_matches_staged_files(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            unrelated = target / "opt/unrelated.txt"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("not owned by this project")
            stage_repository(target, ROOT)
            manifest_path = (
                target
                / "usr/share/doc/ispconfig-rspamd-trainer/install-manifest.json"
            )
            payload = json.loads(manifest_path.read_text())
            self.assertEqual(1, payload["schema"])
            self.assertEqual("ispconfig-rspamd-trainer", payload["project"])
            by_path = {entry["path"]: entry for entry in payload["files"]}
            wrapper = "/usr/local/bin/ispconfig-rspamd-trainer"
            self.assertIn(wrapper, by_path)
            wrapper_path = target / wrapper.lstrip("/")
            self.assertEqual(
                hashlib.sha256(wrapper_path.read_bytes()).hexdigest(),
                by_path[wrapper]["sha256"],
            )
            self.assertEqual("0755", by_path[wrapper]["mode"])
            self.assertNotIn(
                "/usr/share/doc/ispconfig-rspamd-trainer/install-manifest.json",
                by_path,
            )
            self.assertNotIn("/opt/unrelated.txt", by_path)
            self.assertEqual("not owned by this project", unrelated.read_text())

    def test_staged_modes_are_restrictive(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            stage_repository(target, ROOT)

            wrapper = target / "usr/local/bin/ispconfig-rspamd-trainer"
            helper = (
                target
                / "usr/local/libexec/ispconfig-rspamd-trainer/export_mailboxes.php"
            )
            config = target / "etc/ispconfig-rspamd-trainer/rspamd.ini.example"
            unit = (
                target
                / "etc/systemd/system/ispconfig-rspamd-trainer-broker.service"
            )
            self.assertEqual(0o755, stat.S_IMODE(wrapper.stat().st_mode))
            self.assertEqual(0o750, stat.S_IMODE(helper.stat().st_mode))
            self.assertEqual(0o640, stat.S_IMODE(config.stat().st_mode))
            self.assertEqual(0o644, stat.S_IMODE(unit.stat().st_mode))

    def test_refuses_real_root(self):
        with self.assertRaises(LayoutError):
            stage_repository("/", ROOT)

    def test_refuses_stage_inside_source_repository(self):
        target = ROOT / "local/stage-test"
        try:
            with self.assertRaises(LayoutError):
                stage_repository(target, ROOT)
        finally:
            if target.exists():
                import shutil
                shutil.rmtree(target)


if __name__ == "__main__":
    unittest.main()
