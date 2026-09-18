# Changelog

## Unreleased

- Initial repository and MIT licensing.
- Privacy-aware mailbox policy model with Safe Auto warm-up.
- SQLite state store and protocol-observation tracking.
- Fixed local broker protocol skeleton with systemd socket activation.
- Safe Maildir spam/ham queue engine with move/delete-on-success semantics.
- Explicit non-shell `rspamc` client.
- Regression tests for the historical empty-`cur`/non-empty-`new` failure.
- ISPConfig admin-module skeleton.
- systemd service/socket/timer definitions.
- Non-mutating installer preflight.
- GitHub Actions workflow.
- Reused MIT-licensed ISPConfig admin module assignment/unassignment helpers with attribution.
- Added Rspamd controller endpoint/password-file/classifier/delivery-context support based on BSD-2-Clause train-spam-scanner interoperability patterns.
- Added current Dovecot 2.4 IMAPSieve spam/ham feedback templates and transient feedback command.
- Added Sieve compilation to preflight and CI validation.
- Implemented broker status/discovery/classifier-stats/dry-run/run APIs and persistent aggregate run history.
- Added Dovecot-backed serialized run orchestration with move/expunge only after successful learning and GUID/UID duplicate suppression for aged-Inbox ham.
- Added privacy-safe ISPConfig mailbox inventory/reconciliation and dedicated spam-source state.
- Added narrow root-only ISPConfig mailbox snapshot exporter plus hardened 15-minute discovery timer design, keeping ISPConfig database credentials out of the trainer.
- Added separate low-privilege IMAP/POP3 observation socket and fail-open Dovecot post-login wrappers that record only mailbox identity, protocol and timestamp.
- Enriched mailbox inventory status with observed protocol usage, effective policy, aged-Inbox eligibility and dedicated-spam-source state.
- Replaced the status-only ISPConfig page with an admin-only management dashboard for health, inventory refresh, dry-run, asynchronous run-now, per-mailbox policy and explicit trusted-spam-source confirmation.
- Added ISPConfig-native CSRF protection for all UI mutations and static regression checks forbidding shell/database access from the PHP module.
- Added a fixed asynchronous trainer launcher and multi-worker broker so status/policy requests remain responsive while a scheduled run is active.
- Added safe, repeatable `install.sh --stage` packaging with fixed runtime wrappers, no pip/venv production dependency, development-artifact filtering, and a project-owned SHA-256/mode install manifest.
- Added staged-install CI/idempotence tests while keeping live production activation disabled pending Debian 13 integration.
- Added manifest-driven staged uninstall/upgrade planning with modified-file, permission-drift, collision, missing-file and malicious-path protection; live-root mutation remains disabled.
- Added a dedicated Dovecot doveadm Unix-socket design and `doveadm -O ... -S` client support so the trainer does not need `vmail` filesystem membership or read access to protected Dovecot configuration.
