# Installation and staging

The project is still pre-alpha. Production activation is deliberately disabled
until the Debian 13 / ISPConfig 3.3.x / Dovecot 2.4 target has been validated.

## Preflight

Run the target checks as root:

```sh
sudo ./install.sh --check
```

Preflight checks the required commands, Python version, ISPConfig 3.3.x,
PHP/mysqli, PHP helper syntax, Sieve compilation, effective Dovecot IMAP/POP3
executable chains, and Rspamd configuration syntax.

A non-default existing Dovecot IMAP or POP3 executable chain is not overwritten.
Preflight reports it so the final activation step can merge the observer into
the existing post-login chain.

## Staging

The complete filesystem payload can be built without root:

```sh
./install.sh --stage /tmp/ispconfig-rspamd-trainer-root
```

Staging is safe for inspection and packaging:

- it refuses to stage directly into `/`;
- it refuses a target inside the source repository;
- it copies only named runtime wrappers;
- development artefacts such as `.bak.*`, `__pycache__`, and `.pyc`
  are excluded;
- Dovecot service snippets are placed under project documentation as examples,
  not under `/etc/dovecot/conf.d`;
- the operation is deterministic/idempotent for the files it owns.

The staged runtime intentionally uses Debian's `/usr/bin/python3` directly.
The runtime code has no third-party Python package dependency, so production
installation does not need pip, a virtualenv, or modifications to Debian's
system Python site-packages.

## Install manifest

Every staged payload contains:

```text
/usr/share/doc/ispconfig-rspamd-trainer/install-manifest.json
```

The manifest contains only project-owned files, with path, mode, and SHA-256.
It deliberately does not scan or claim unrelated files that happen to be
present in the staging root.

This manifest is the basis for safe upgrade verification and
manifest-driven uninstall. The manifest itself is not listed inside itself.

## Upgrade and uninstall lifecycle

A staged payload now includes `ispconfig-rspamd-lifecycle`. The lifecycle
engine verifies manifest ownership before any removal or replacement.

It distinguishes:

- unchanged owned files;
- locally modified owned files, including permission-mode drift;
- already-missing files;
- files added/changed/retired by a candidate release;
- collisions where a candidate project path is already occupied locally.

Manifest paths are constrained to the project's known installation locations;
a forged manifest cannot claim arbitrary paths such as `/etc/passwd`.

For development/testing, `uninstall.sh` supports only disposable staged
roots:

```sh
./uninstall.sh --stage-root /tmp/ispconfig-rspamd-trainer-root --plan
./uninstall.sh --stage-root /tmp/ispconfig-rspamd-trainer-root --apply
```

Default staged uninstall refuses to proceed if any owned file has been locally
modified, preserving both that file and the manifest for inspection. An
explicit `--allow-modified` override exists only for deliberate destructive
testing.

Live-root uninstall remains disabled.

State and administrator-created configuration are outside the install
manifest, so the future production uninstall can preserve them independently
from package-owned files.

## Important activation boundary

Staging is not activation.

The current no-argument `sudo ./install.sh` path deliberately refuses to
modify the live system. Before that gate is opened, target integration must
validate:

- actual ISPConfig 3.3.x PHP/web ownership and module permissions;
- Rspamd controller access and Bayes statistics;
- Dovecot 2.4 IMAPSieve/extprogram configuration;
- existing IMAP/POP3 post-login chains;
- systemd user/group/socket ownership;
- module assignment/unassignment;
- state/config preservation across upgrade/uninstall;
- reboot and service recovery.

In particular, no staged Dovecot configuration example is automatically
activated.
