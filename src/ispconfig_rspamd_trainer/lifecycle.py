import argparse
import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


class LifecycleError(RuntimeError):
    pass


MANIFEST_PATH = Path(
    "usr/share/doc/ispconfig-rspamd-trainer/install-manifest.json"
)
PROJECT_DIRS = (
    Path("usr/local/lib/ispconfig-rspamd-trainer"),
    Path("usr/local/ispconfig/interface/web/rspamd_trainer"),
    Path("usr/local/libexec/ispconfig-rspamd-trainer"),
    Path("usr/share/doc/ispconfig-rspamd-trainer"),
)
ALLOWED_GLOBAL_NAMES = {
    "ispconfig-rspamd-trainer",
    "ispconfig-rspamd-trainer-broker",
    "ispconfig-rspamd-feedback",
    "ispconfig-rspamd-trainer-observer",
    "ispconfig-rspamd-observe",
    "ispconfig-rspamd-lifecycle",
}


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(path_value):
    if not isinstance(path_value, str) or not path_value.startswith("/"):
        raise LifecycleError("manifest path must be absolute")
    candidate = Path(path_value)
    if ".." in candidate.parts:
        raise LifecycleError("manifest path traversal is forbidden")
    relative = Path(*candidate.parts[1:])
    if not relative.parts:
        raise LifecycleError("manifest may not own filesystem root")

    allowed = False
    for prefix in PROJECT_DIRS:
        if relative == prefix or prefix in relative.parents:
            allowed = True
            break
    if not allowed and relative.parent == Path("usr/local/bin"):
        allowed = relative.name in ALLOWED_GLOBAL_NAMES
    if not allowed and relative.parent == Path("etc/systemd/system"):
        allowed = relative.name.startswith("ispconfig-rspamd-trainer")
    if not allowed and relative.parent == Path("etc/dovecot/sieve"):
        allowed = relative.name.startswith("ispconfig-rspamd-")
    if not allowed and relative.parent == Path("usr/lib/dovecot/sieve-pipe"):
        allowed = relative.name.startswith("ispconfig-rspamd-")
    if not allowed and relative == Path(
        "etc/ispconfig-rspamd-trainer/rspamd.ini.example"
    ):
        allowed = True
    if not allowed:
        raise LifecycleError("manifest path is outside project-owned locations")
    return relative


def load_manifest(root):
    root = Path(root).resolve()
    manifest_path = root / MANIFEST_PATH
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise LifecycleError("install manifest is unavailable or invalid") from exc
    if payload.get("schema") != 1:
        raise LifecycleError("unsupported install manifest schema")
    if payload.get("project") != "ispconfig-rspamd-trainer":
        raise LifecycleError("manifest belongs to a different project")
    files = payload.get("files")
    if not isinstance(files, list):
        raise LifecycleError("manifest file list is invalid")
    normalized = []
    seen = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise LifecycleError("invalid manifest entry")
        if set(entry) != {"path", "mode", "sha256"}:
            raise LifecycleError("unexpected manifest entry fields")
        relative = _safe_relative(entry["path"])
        if relative in seen:
            raise LifecycleError("duplicate manifest path")
        seen.add(relative)
        mode = entry["mode"]
        digest = entry["sha256"]
        if (
            not isinstance(mode, str)
            or len(mode) != 4
            or any(ch not in "01234567" for ch in mode)
        ):
            raise LifecycleError("invalid manifest mode")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise LifecycleError("invalid manifest digest")
        normalized.append(
            {
                "relative": relative,
                "path": entry["path"],
                "mode": mode,
                "sha256": digest,
            }
        )
    return normalized


@dataclass(frozen=True)
class FileState:
    path: str
    state: str
    expected_mode: str
    actual_mode: Optional[str] = None


@dataclass
class RemovalPlan:
    unchanged: list
    modified: list
    missing: list
    unsafe: list

    @property
    def removable_count(self):
        return len(self.unchanged)

    @property
    def blocked_count(self):
        return len(self.modified) + len(self.unsafe)

    def as_dict(self):
        return {
            "unchanged": [asdict(item) for item in self.unchanged],
            "modified": [asdict(item) for item in self.modified],
            "missing": [asdict(item) for item in self.missing],
            "unsafe": [asdict(item) for item in self.unsafe],
            "removable_count": self.removable_count,
            "blocked_count": self.blocked_count,
        }


def plan_removal(root):
    root = Path(root).resolve()
    entries = load_manifest(root)
    plan = RemovalPlan([], [], [], [])
    for entry in entries:
        target = (root / entry["relative"]).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            plan.unsafe.append(
                FileState(entry["path"], "escapes_root", entry["mode"])
            )
            continue
        if not target.exists():
            plan.missing.append(
                FileState(entry["path"], "missing", entry["mode"])
            )
            continue
        if not target.is_file():
            plan.unsafe.append(
                FileState(entry["path"], "not_regular_file", entry["mode"])
            )
            continue
        actual_mode = "{:04o}".format(stat.S_IMODE(target.stat().st_mode))
        digest = _sha256(target)
        if digest == entry["sha256"] and actual_mode == entry["mode"]:
            plan.unchanged.append(
                FileState(
                    entry["path"],
                    "unchanged",
                    entry["mode"],
                    actual_mode,
                )
            )
        else:
            plan.modified.append(
                FileState(
                    entry["path"],
                    "modified",
                    entry["mode"],
                    actual_mode,
                )
            )
    return plan


def _prune_project_dirs(root):
    root = Path(root).resolve()
    for relative in PROJECT_DIRS:
        current = root / relative
        if not current.exists():
            continue
        for directory, _, _ in os.walk(current, topdown=False):
            path = Path(directory)
            try:
                path.rmdir()
            except OSError:
                pass


def apply_removal(root, allow_modified=False):
    root = Path(root).resolve()
    if root == Path("/"):
        raise LifecycleError("live-root lifecycle mutation is not enabled")
    plan = plan_removal(root)
    if plan.unsafe:
        raise LifecycleError("unsafe manifest entries block removal")
    if plan.modified and not allow_modified:
        raise LifecycleError(
            "modified project files block removal; inspect or explicitly allow them"
        )

    entries = {item.path: item for item in plan.unchanged}
    if allow_modified:
        entries.update({item.path: item for item in plan.modified})

    removed = []
    for path_value in sorted(entries, reverse=True):
        relative = _safe_relative(path_value)
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise LifecycleError("removal target escapes root") from exc
        if target.is_file():
            target.unlink()
            removed.append(path_value)

    manifest_file = root / MANIFEST_PATH
    if manifest_file.is_file():
        manifest_file.unlink()
        removed.append("/" + MANIFEST_PATH.as_posix())

    _prune_project_dirs(root)
    return {
        "removed": removed,
        "preserved_modified": []
        if allow_modified
        else [item.path for item in plan.modified],
        "already_missing": [item.path for item in plan.missing],
    }


def verify(root):
    plan = plan_removal(root)
    return {
        "ok": not plan.modified and not plan.unsafe,
        "plan": plan.as_dict(),
    }


def _manifest_by_path(root):
    return {entry["path"]: entry for entry in load_manifest(root)}


def plan_upgrade(current_root, candidate_root):
    current_root = Path(current_root).resolve()
    candidate_root = Path(candidate_root).resolve()
    current = _manifest_by_path(current_root)
    candidate = _manifest_by_path(candidate_root)

    result = {
        "unchanged": [],
        "changed": [],
        "added": [],
        "retired": [],
        "locally_modified": [],
        "collisions": [],
        "missing": [],
    }

    for path_value, old_entry in sorted(current.items()):
        target = current_root / _safe_relative(path_value)
        if not target.exists():
            result["missing"].append(path_value)
            local_digest = None
        elif target.is_symlink() or not target.is_file():
            result["collisions"].append(path_value)
            continue
        else:
            local_digest = _sha256(target)
            local_mode = "{:04o}".format(stat.S_IMODE(target.stat().st_mode))
            if (
                local_digest != old_entry["sha256"]
                or local_mode != old_entry["mode"]
            ):
                result["locally_modified"].append(path_value)

        new_entry = candidate.get(path_value)
        if new_entry is None:
            result["retired"].append(path_value)
        elif new_entry["sha256"] == old_entry["sha256"] and new_entry["mode"] == old_entry["mode"]:
            result["unchanged"].append(path_value)
        else:
            result["changed"].append(path_value)

    for path_value in sorted(set(candidate) - set(current)):
        target = current_root / _safe_relative(path_value)
        if target.exists() or target.is_symlink():
            result["collisions"].append(path_value)
        else:
            result["added"].append(path_value)

    conflict_paths = sorted(
        set(result["collisions"])
        | (
            set(result["locally_modified"])
            & (set(result["changed"]) | set(result["retired"]))
        )
    )
    result["conflicts"] = conflict_paths
    result["safe"] = not conflict_paths
    return result


def build_parser():
    parser = argparse.ArgumentParser(prog="ispconfig-rspamd-lifecycle")
    parser.add_argument("--root", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    sub.add_parser("plan-uninstall")
    upgrade_parser = sub.add_parser("plan-upgrade")
    upgrade_parser.add_argument("--candidate-root", required=True)
    apply_parser = sub.add_parser("apply-uninstall")
    apply_parser.add_argument("--allow-modified", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    if root == Path("/"):
        print(
            "error: live-root lifecycle mutation is not enabled in this pre-alpha",
            file=sys.stderr,
        )
        return 1
    try:
        if args.command == "verify":
            result = verify(root)
        elif args.command == "plan-uninstall":
            result = plan_removal(root).as_dict()
        elif args.command == "plan-upgrade":
            result = plan_upgrade(root, args.candidate_root)
        else:
            result = apply_removal(root, allow_modified=args.allow_modified)
    except LifecycleError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
