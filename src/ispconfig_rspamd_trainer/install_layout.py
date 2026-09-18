import argparse
import hashlib
import json
import shutil
import stat
import sys
from pathlib import Path


class LayoutError(RuntimeError):
    pass


IGNORED_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
IGNORED_SUFFIXES = (
    ".pyc",
    ".pyo",
)
MANIFEST_RELATIVE = Path(
    "usr/share/doc/ispconfig-rspamd-trainer/install-manifest.json"
)


def _ignored(path):
    name = path.name
    if name in IGNORED_NAMES:
        return True
    if ".bak." in name:
        return True
    return name.endswith(IGNORED_SUFFIXES)


def _copy_file(source, destination, mode=None):
    if _ignored(source):
        raise LayoutError("refusing to stage development artefact: {}".format(source.name))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(source), str(destination))
    if mode is None:
        mode = stat.S_IMODE(source.stat().st_mode)
    destination.chmod(mode)


def _copy_tree(source, destination):
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        str(source),
        str(destination),
        ignore=shutil.ignore_patterns(
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "*.pyc",
            "*.pyo",
            "*.bak.*",
        ),
    )


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(root, managed_paths):
    manifest_path = root / MANIFEST_RELATIVE
    files = []
    unique_paths = sorted({Path(path).resolve() for path in managed_paths})
    for path in unique_paths:
        if not path.is_file() or path == manifest_path:
            continue
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise LayoutError("manifest path escapes staging root") from exc
        files.append(
            {
                "path": "/" + relative.as_posix(),
                "mode": "{:04o}".format(stat.S_IMODE(path.stat().st_mode)),
                "sha256": _sha256(path),
            }
        )
    payload = {
        "schema": 1,
        "project": "ispconfig-rspamd-trainer",
        "files": files,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_path.chmod(0o644)


def _validated_stage_root(root, source_root):
    root = Path(root).resolve()
    source_root = Path(source_root).resolve()
    if root == Path("/"):
        raise LayoutError("refusing to stage directly into /")
    if root == source_root or source_root in root.parents:
        raise LayoutError("staging root must not be inside the source repository")
    return root, source_root


def stage_repository(root, source_root):
    root, source_root = _validated_stage_root(root, source_root)

    required = (
        source_root / "src/ispconfig_rspamd_trainer",
        source_root / "ispconfig/interface/web/rspamd_trainer",
        source_root / "systemd",
        source_root / "packaging/wrappers",
    )
    if not all(path.exists() for path in required):
        raise LayoutError("repository source tree is incomplete")

    # Runtime Python package: dependency-free, intentionally not installed via
    # pip into Debian's system Python.
    _copy_tree(
        source_root / "src/ispconfig_rspamd_trainer",
        root / "usr/local/lib/ispconfig-rspamd-trainer/ispconfig_rspamd_trainer",
    )

    wrapper_names = (
        "ispconfig-rspamd-trainer",
        "ispconfig-rspamd-trainer-broker",
        "ispconfig-rspamd-feedback",
        "ispconfig-rspamd-trainer-observer",
        "ispconfig-rspamd-observe",
    )
    for name in wrapper_names:
        source = source_root / "packaging/wrappers" / name
        if not source.is_file():
            raise LayoutError("required wrapper missing: {}".format(name))
        _copy_file(source, root / "usr/local/bin" / name, 0o755)

    # Additive ISPConfig module; no ISPConfig core files are modified.
    _copy_tree(
        source_root / "ispconfig/interface/web/rspamd_trainer",
        root / "usr/local/ispconfig/interface/web/rspamd_trainer",
    )

    # Fixed privileged helpers. They remain outside the web tree.
    libexec = root / "usr/local/libexec/ispconfig-rspamd-trainer"
    _copy_file(
        source_root / "bin/export_mailboxes.php",
        libexec / "export_mailboxes.php",
        0o750,
    )
    _copy_file(
        source_root / "bin/assign_module.php",
        libexec / "assign_module.php",
        0o750,
    )
    _copy_file(
        source_root / "bin/unassign_module.php",
        libexec / "unassign_module.php",
        0o750,
    )
    for name in ("ispconfig-rspamd-observe-imap", "ispconfig-rspamd-observe-pop3"):
        _copy_file(
            source_root / "dovecot/postlogin" / name,
            libexec / name,
            0o755,
        )

    # IMAPSieve scripts are inert until the administrator/installer activates
    # the validated Dovecot config.
    for path in sorted((source_root / "dovecot/sieve").glob("*.sieve")):
        _copy_file(path, root / "etc/dovecot/sieve" / path.name, 0o644)
    for path in sorted((source_root / "dovecot/sieve-pipe").iterdir()):
        if path.is_file() and not _ignored(path):
            _copy_file(path, root / "usr/lib/dovecot/sieve-pipe" / path.name, 0o755)

    # Dovecot 2.4 service snippets are examples until target-specific merge
    # validation is complete. Staging must never activate them automatically.
    examples = root / "usr/share/doc/ispconfig-rspamd-trainer/examples/dovecot-2.4"
    for path in sorted((source_root / "dovecot/2.4").glob("*.example")):
        _copy_file(path, examples / path.name, 0o644)

    for unit in sorted((source_root / "systemd").iterdir()):
        if unit.is_file() and not _ignored(unit):
            _copy_file(unit, root / "etc/systemd/system" / unit.name, 0o644)

    config_dir = root / "etc/ispconfig-rspamd-trainer"
    config_dir.mkdir(parents=True, exist_ok=True)
    _copy_file(
        source_root / "config/rspamd.ini.example",
        config_dir / "rspamd.ini.example",
        0o640,
    )

    doc_dir = root / "usr/share/doc/ispconfig-rspamd-trainer"
    for name in (
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "README.md",
        "SECURITY.md",
        "PROVENANCE.md",
        "CHANGELOG.md",
    ):
        _copy_file(source_root / name, doc_dir / name, 0o644)
    _copy_tree(source_root / "docs", doc_dir / "docs")

    # The manifest includes only files owned by this project. Never scan the
    # whole staging root: it may intentionally contain unrelated files.
    managed_paths = []
    for owned_dir in (
        root / "usr/local/lib/ispconfig-rspamd-trainer",
        root / "usr/local/ispconfig/interface/web/rspamd_trainer",
        root / "usr/local/libexec/ispconfig-rspamd-trainer",
        root / "usr/share/doc/ispconfig-rspamd-trainer",
    ):
        if owned_dir.exists():
            managed_paths.extend(
                path for path in owned_dir.rglob("*") if path.is_file()
            )
    managed_paths.extend(
        root / "usr/local/bin" / name for name in wrapper_names
    )
    managed_paths.extend(
        root / "etc/dovecot/sieve" / path.name
        for path in (source_root / "dovecot/sieve").glob("*.sieve")
    )
    managed_paths.extend(
        root / "usr/lib/dovecot/sieve-pipe" / path.name
        for path in (source_root / "dovecot/sieve-pipe").iterdir()
        if path.is_file() and not _ignored(path)
    )
    managed_paths.extend(
        root / "etc/systemd/system" / path.name
        for path in (source_root / "systemd").iterdir()
        if path.is_file() and not _ignored(path)
    )
    managed_paths.append(config_dir / "rspamd.ini.example")
    _write_manifest(root, managed_paths)

    return root


def build_parser():
    parser = argparse.ArgumentParser(prog="ispconfig-rspamd-install-layout")
    parser.add_argument("--root", required=True)
    parser.add_argument("--source", default=".")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        stage_repository(args.root, args.source)
    except LayoutError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
