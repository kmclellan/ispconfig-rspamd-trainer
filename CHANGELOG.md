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
