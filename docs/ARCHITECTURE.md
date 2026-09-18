# Architecture

Three trust zones:

1. ISPConfig UI: authenticated admin interface, unprivileged for mail
   operations.
2. Local broker/state: validates fixed operations and stores policy/aggregate
   state.
3. Trainer/runtime: performs approved Rspamd learning and mailbox operations
   with minimum local privileges.

The broker is Unix-socket only. The UI must never provide an arbitrary
filesystem path. Mailbox locations are resolved from trusted server metadata.

State is separate from the ISPConfig database so install/uninstall does not
alter ISPConfig schema.
