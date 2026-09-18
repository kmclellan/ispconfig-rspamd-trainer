# Provenance and prior art

This repository is a new implementation.

Design research considered:

- Rspamd documentation and controller/WebUI behavior.
- `jnorell/train-spam-scanner`, BSD-2-Clause. It is a useful design precedent
  for Dovecot/ISPConfig mail training. Any future copied code must retain its
  copyright/licence notice. No source from it is currently incorporated.
- `darix/dovecot-sieve-antispam-rspamd`. Its repository metadata did not
  declare a licence during initial research, so source must not be copied
  unless licensing is clarified.
- `ispconfig-theme-customizer`, MIT, as an example of an additive ISPConfig
  module and installer pattern.

Documentation and protocol behavior may be used as interoperability reference.
Keep third-party source provenance explicit.
