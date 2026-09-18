# Privacy model

Ham is privacy-sensitive training input, not an archive.

- Aged-Inbox ham is learned in place.
- Explicit Ham queue copies are deleted only after successful learning.
- POP3/mixed mailboxes are not automatic aged-Inbox sources without sufficient
  policy/evidence.
- Dedicated spam corpora are retained only after administrator confirmation.

## Protocol observation

Safe Auto needs to distinguish sustained IMAP-style use from POP3/mixed use
when ISPConfig permits both protocols.

The optional Dovecot post-login observer stores only:

- stable ISPConfig mailbox ID;
- first observation timestamp;
- most recent IMAP observation timestamp;
- most recent POP3 observation timestamp.

The post-login request itself contains only authenticated mailbox identity and
the fixed protocol label `imap` or `pop3`. The observer resolves that
identity to the already-discovered ISPConfig mailbox ID and ignores unknown
mailboxes.

It does **not** store:

- client IP address;
- local server IP;
- session identifier;
- device/client name;
- authentication secret;
- message identifiers or content.

The observation socket is separate from the management broker and exposes no
policy, run, status or filesystem operations. The Dovecot wrappers are
fail-open: a broken observer must not stop a user logging into mail.

## Persistent state

Persistent project state may contain:

- ISPConfig mailbox ID and current mailbox address for administration;
- protocol capability flags;
- mailbox training policy;
- dedicated-spam-source settings;
- aggregate run counters/status;
- protocol observation timestamps;
- Dovecot mailbox GUID/UID/kind markers for successfully learned aged-Inbox
  ham, solely to avoid repeated training.

It must not contain message bodies, subjects, message sender/recipient
metadata, mailbox passwords, client IPs, session identifiers, or copied ham.
