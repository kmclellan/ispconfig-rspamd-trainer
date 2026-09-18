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
