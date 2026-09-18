# Existing options reviewed

## Rspamd WebUI / controller

Official/current engine UI and API. Keep it for statistics, history, rule
administration, and manual learning. This project uses the controller interface
instead of copying Rspamd UI/daemon code.

## jnorell/train-spam-scanner

BSD-2-Clause and the closest precedent for ISPConfig/Dovecot mailbox training.

Useful parts have now been adopted at the design/API level:

- controller password-file handling;
- configurable controller endpoint/classifier;
- per-user delivery context;
- IMAPSieve immediate spam/ham feedback;
- suppression of false ham learning when spam is moved to deletion folders.

These are independently implemented for current Rspamd/Dovecot rather than
copying the upstream Bash trainer. Its cron, bindfs/shared-folder aggregation,
SpamAssassin compatibility, and Debian-10-specific configuration are not used.

## darix/dovecot-sieve-antispam-rspamd

Useful IMAPSieve concept reference. No source is copied because its repository
licensing was unclear during review.

## NethServer ns8-mail

Modern Rspamd integration/bulk learning example, but tied to NethServer's
container architecture. No code is reused.

## ispconfig-theme-customizer

MIT. Its additive ISPConfig module lifecycle is directly relevant.

The module assignment/unassignment helpers are now adapted into this project
with attribution. Their idempotent admin assignment, safe preservation of
existing module CSV values, charset handling, and stale-`startmodule`
cleanup are reused.

The theme-specific installer, branding UI, templates, and theme machinery are
not reused.
