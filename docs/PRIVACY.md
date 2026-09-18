# Privacy model

Ham is privacy-sensitive training input, not an archive.

- Aged-Inbox ham is learned in place.
- Explicit Ham queue copies are deleted only after successful learning.
- POP3/mixed mailboxes are not automatic aged-Inbox sources.
- Dedicated spam corpora are retained only after administrator confirmation.

Persistent state may contain policy, aggregate counters, run status, protocol
last-seen timestamps, and non-content deduplication markers.

It must not contain bodies, subjects, sender/recipient addresses, passwords,
client IPs, or copied ham.
