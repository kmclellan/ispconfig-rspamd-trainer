# Existing options reviewed

## Rspamd WebUI / controller

Official/current engine UI and API. Keep it for statistics, history, rule
administration, and manual learning.

## jnorell/train-spam-scanner

BSD-2-Clause and the closest precedent for ISPConfig/Dovecot mailbox training.
Useful as prior art, but its shell/config/cron design is not adopted as this
project's core architecture.

## darix/dovecot-sieve-antispam-rspamd

Useful IMAPSieve concept reference. Do not copy source unless licensing is
clarified.

## NethServer ns8-mail

Modern Rspamd integration/bulk learning example, but tied to NethServer's
container architecture.

## ispconfig-theme-customizer

MIT. Useful current example of an additive ISPConfig extension with
install/uninstall workflow and no ISPConfig core modifications.
