# Architecture

The project has four deliberately separated trust zones.

1. **ISPConfig UI** - authenticated administrator interface, unprivileged for
   mail operations.
2. **Local broker/state** - validates fixed operations and stores policy,
   privacy-safe inventory and aggregate state.
3. **Trainer/runtime** - performs approved Rspamd learning and Dovecot mailbox
   operations with the minimum required local privileges.
4. **Inventory exporter** - a narrow root-run one-shot helper that may read
   ISPConfig's protected database configuration but exports only seven approved
   mailbox fields to an atomic local JSON snapshot.

## Broker boundary

The management broker is Unix-socket only. Its protocol has fixed operations
and exact argument sets. The UI must never supply an arbitrary filesystem
path, executable, service name, Dovecot search expression or rspamc argument.

Implemented operations include health/status, policy list/get/set, inventory,
dedicated spam-source configuration, discovery, classifier statistics,
dry-run and run.

## Mailbox discovery without database credential sharing

The long-running Python processes do not read ISPConfig's database password.

A hardened one-shot service executes `bin/export_mailboxes.php` periodically.
That helper uses ISPConfig's own protected configuration to select only:

- `mailuser_id`;
- `server_id`;
- `email`;
- `disableimap`;
- `disablepop3`;
- `access`;
- `disabledoveadm`.

It atomically writes a group-readable JSON snapshot under the trainer state
directory. Passwords, names, maildir paths, forwarding data, autoresponders and
mail filters are not queried.

The broker reconciles stable ISPConfig mailbox IDs against that snapshot.
Renames update the existing inventory record; missing IDs become inactive
rather than having their policy silently transferred to another mailbox.

## Training execution

Runs are serialized with a non-blocking local file lock.

Before every run or dry-run the broker refreshes the inventory and fails
closed if the configured inventory source is unavailable. This prevents a
stale renamed/deleted account from being trained.

### Ordinary mailboxes

Aged-Inbox ham is eligible only when policy and access evidence permit it.
ISPConfig `disablepop3=y` is strong evidence that a mailbox cannot be using
POP3 and may make Safe Auto eligible without an observation warm-up. When POP3
is allowed, Safe Auto requires positive IMAP observation history and no recent
POP3 observation.

Eligible Inbox messages are identified through Dovecot mailbox GUID/UID. The
message is fetched only for a real run, learned as ham, left in place, and a
non-content GUID/UID marker is stored so it is not repeatedly relearned.

### Dedicated spam sources

Administrator-designated corpus mailboxes have explicit semantics:

- normal Inbox -> trusted spam queue;
- configured archive mailbox -> successfully learned spam;
- configured Ham mailbox -> transient explicit ham queue.

Spam moves only after successful learning. Explicit ham is expunged only after
successful learning. Failures remain in place.

A dedicated spam-source mailbox is never simultaneously treated as an ordinary
aged-Inbox ham source.

## Dry-run

Dry-run performs only inventory reconciliation and Dovecot metadata searches.
It records candidate counts but does not fetch message bodies, call Rspamd,
move mail, expunge mail or create learned-message markers.

## State

The SQLite database is separate from ISPConfig and may contain:

- stable ISPConfig mailbox ID and mailbox address;
- protocol capability flags;
- policy mode/threshold/batch size;
- last IMAP/POP3 observation timestamps;
- dedicated spam-source settings;
- mailbox GUID/UID/kind markers for successful aged-Inbox learning;
- aggregate run counters and error classes.

It must not contain message bodies, subjects, sender/recipient message
metadata, passwords, client IP addresses or copied ham.
