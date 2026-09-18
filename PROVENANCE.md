# Provenance and prior art

This repository is primarily an original implementation, with the explicitly
documented reuse below.

## Directly adapted source

### ispconfig-theme-customizer

Repository: https://github.com/wadejbeckett/ispconfig-theme-customizer

Licence: MIT.

`bin/assign_module.php` and `bin/unassign_module.php` are adapted from Wade
Beckett's module assignment/unassignment helpers. They retain the upstream
copyright notice and are modified for the `rspamd_trainer` module.

The useful behavior retained is:

- idempotent assignment to ISPConfig admin users;
- preserving every existing module in `sys_user.modules`;
- charset-safe raw mysqli access using ISPConfig's configured charset;
- uninstall cleanup across all users, because an administrator may have
  manually assigned the module after installation;
- resetting `startmodule` to `dashboard` if it points at the removed module.

See `THIRD_PARTY_NOTICES.md` for the complete upstream MIT notice.

## Design/API reuse without copied source

### jnorell/train-spam-scanner

Repository: https://github.com/jnorell/train-spam-scanner

Licence: BSD-2-Clause.

No upstream source file is copied into this repository. The project is credited
as prior art for:

- ISPConfig + Dovecot + Rspamd training integration;
- using Rspamd controller password files rather than putting secrets directly
  in process arguments;
- optional controller endpoint and classifier selection;
- passing per-user delivery context to Rspamd learning;
- immediate IMAPSieve feedback alongside periodic/bulk training;
- avoiding ham learning when a user is merely deleting spam to Trash.

Those concepts are independently implemented in Python and Dovecot 2.4
configuration using the current Rspamd and Dovecot interfaces.

The upstream BSD-2-Clause notice is reproduced in
`THIRD_PARTY_NOTICES.md` for transparency even though no source is copied.

### darix/dovecot-sieve-antispam-rspamd

Useful IMAPSieve conceptual reference. The repository metadata did not declare
a licence during initial research, so no source is copied from it.

### Rspamd and Dovecot documentation

Current public APIs/configuration are interoperability references. In
particular, the project uses supported `rspamc` options and Dovecot 2.4
IMAPSieve/extprogram configuration rather than importing daemon source code.

Keep third-party source provenance explicit in future changes.
