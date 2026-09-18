import hashlib
import json
import stat
import tempfile
import unittest
from pathlib import Path

from ispconfig_rspamd_trainer.install_layout import stage_repository
from ispconfig_rspamd_trainer.lifecycle import (
    LifecycleError,
    apply_removal,
    load_manifest,
    plan_removal,
    plan_upgrade,
    verify,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(
    "usr/share/doc/ispconfig-rspamd-trainer/install-manifest.json"
)


def rewrite_manifest_entry(root, path_value, content=None, mode=None):
    root = Path(root)
    manifest_path = root / MANIFEST
    payload = json.loads(manifest_path.read_text())
    by_path = {entry["path"]: entry for entry in payload["files"]}
    entry = by_path[path_value]
    target = root / path_value.lstrip("/")
    if content is not None:
        target.write_text(content)
        entry["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    if mode is not None:
        target.chmod(mode)
        entry["mode"] = "{:04o}".format(mode)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


class LifecycleTests(unittest.TestCase):
    def test_fresh_stage_verifies_clean(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            stage_repository(target, ROOT)
            result = verify(target)
            self.assertTrue(result["ok"])
            self.assertEqual(0, result["plan"]["blocked_count"])
            self.assertGreater(result["plan"]["removable_count"], 50)

    def test_content_change_blocks_default_uninstall(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            stage_repository(target, ROOT)
            wrapper = target / "usr/local/bin/ispconfig-rspamd-trainer"
            wrapper.write_text(wrapper.read_text() + "\n# local change\n")
            plan = plan_removal(target)
            modified = {item.path for item in plan.modified}
            self.assertIn("/usr/local/bin/ispconfig-rspamd-trainer", modified)
            with self.assertRaises(LifecycleError):
                apply_removal(target)
            self.assertTrue(wrapper.exists())
            self.assertTrue((target / MANIFEST).exists())

    def test_mode_change_is_local_modification(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            stage_repository(target, ROOT)
            wrapper = target / "usr/local/bin/ispconfig-rspamd-trainer"
            wrapper.chmod(0o700)
            plan = plan_removal(target)
            modified = {item.path for item in plan.modified}
            self.assertIn("/usr/local/bin/ispconfig-rspamd-trainer", modified)

    def test_uninstall_removes_owned_files_and_preserves_unrelated(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            unrelated = target / "opt/unrelated.txt"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("keep me")
            stage_repository(target, ROOT)
            result = apply_removal(target)
            self.assertGreater(len(result["removed"]), 50)
            self.assertEqual("keep me", unrelated.read_text())
            self.assertFalse((target / MANIFEST).exists())
            self.assertFalse(
                (target / "usr/local/bin/ispconfig-rspamd-trainer").exists()
            )

    def test_allow_modified_is_explicit_destructive_override(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            stage_repository(target, ROOT)
            wrapper = target / "usr/local/bin/ispconfig-rspamd-trainer"
            wrapper.write_text("local replacement")
            result = apply_removal(target, allow_modified=True)
            self.assertFalse(wrapper.exists())
            self.assertIn(
                "/usr/local/bin/ispconfig-rspamd-trainer",
                result["removed"],
            )

    def test_missing_file_is_safe_and_reported(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            stage_repository(target, ROOT)
            wrapper = target / "usr/local/bin/ispconfig-rspamd-trainer"
            wrapper.unlink()
            plan = plan_removal(target)
            missing = {item.path for item in plan.missing}
            self.assertIn("/usr/local/bin/ispconfig-rspamd-trainer", missing)

    def test_manifest_cannot_claim_arbitrary_path(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "root"
            stage_repository(target, ROOT)
            manifest_path = target / MANIFEST
            payload = json.loads(manifest_path.read_text())
            payload["files"].append(
                {
                    "path": "/etc/passwd",
                    "mode": "0644",
                    "sha256": "0" * 64,
                }
            )
            manifest_path.write_text(json.dumps(payload))
            with self.assertRaises(LifecycleError):
                load_manifest(target)

    def test_identical_candidate_upgrade_is_safe(self):
        with tempfile.TemporaryDirectory() as td:
            current = Path(td) / "current"
            candidate = Path(td) / "candidate"
            stage_repository(current, ROOT)
            stage_repository(candidate, ROOT)
            plan = plan_upgrade(current, candidate)
            self.assertTrue(plan["safe"])
            self.assertEqual([], plan["changed"])
            self.assertEqual([], plan["added"])
            self.assertEqual([], plan["retired"])
            self.assertGreater(len(plan["unchanged"]), 50)

    def test_upgrade_detects_modified_file_that_candidate_changes(self):
        with tempfile.TemporaryDirectory() as td:
            current = Path(td) / "current"
            candidate = Path(td) / "candidate"
            stage_repository(current, ROOT)
            stage_repository(candidate, ROOT)
            path_value = "/usr/local/bin/ispconfig-rspamd-trainer"

            current_target = current / path_value.lstrip("/")
            current_target.write_text(current_target.read_text() + "\n# admin change\n")

            rewrite_manifest_entry(
                candidate,
                path_value,
                content=(candidate / path_value.lstrip("/")).read_text()
                + "\n# new release\n",
            )

            plan = plan_upgrade(current, candidate)
            self.assertFalse(plan["safe"])
            self.assertIn(path_value, plan["changed"])
            self.assertIn(path_value, plan["locally_modified"])
            self.assertIn(path_value, plan["conflicts"])

    def test_upgrade_detects_new_file_collision(self):
        with tempfile.TemporaryDirectory() as td:
            current = Path(td) / "current"
            candidate = Path(td) / "candidate"
            stage_repository(current, ROOT)
            stage_repository(candidate, ROOT)

            path_value = (
                "/usr/local/lib/ispconfig-rspamd-trainer/"
                "ispconfig_rspamd_trainer/future.py"
            )
            current_target = current / path_value.lstrip("/")
            current_target.parent.mkdir(parents=True, exist_ok=True)
            current_target.write_text("unrelated local file")

            candidate_target = candidate / path_value.lstrip("/")
            candidate_target.parent.mkdir(parents=True, exist_ok=True)
            candidate_target.write_text("future release file")

            manifest_path = candidate / MANIFEST
            payload = json.loads(manifest_path.read_text())
            payload["files"].append(
                {
                    "path": path_value,
                    "mode": "0644",
                    "sha256": hashlib.sha256(
                        candidate_target.read_bytes()
                    ).hexdigest(),
                }
            )
            manifest_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n"
            )

            plan = plan_upgrade(current, candidate)
            self.assertFalse(plan["safe"])
            self.assertIn(path_value, plan["collisions"])
            self.assertIn(path_value, plan["conflicts"])


if __name__ == "__main__":
    unittest.main()
