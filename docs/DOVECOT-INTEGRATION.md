# Dovecot integration

Production mailbox operations should prefer Dovecot's supported `doveadm`
mail commands instead of moving Maildir files directly.

Current Dovecot 2.4 supports:

- `doveadm search` to obtain mailbox GUIDs and UIDs;
- `doveadm fetch` to retrieve message text;
- `doveadm move` to move selected messages to a training archive;
- `doveadm expunge` to remove selected messages.

This keeps Dovecot indexes/mailbox semantics authoritative.

## Immediate IMAPSieve feedback

The repository now contains a current Dovecot 2.4 implementation of a workflow
also proven by `jnorell/train-spam-scanner`:

- `dovecot/2.4/99-ispconfig-rspamd-trainer.conf.example`;
- `dovecot/sieve/ispconfig-rspamd-report-spam.sieve`;
- `dovecot/sieve/ispconfig-rspamd-report-ham.sieve`;
- `dovecot/sieve-pipe/ispconfig-rspamd-learn-spam`;
- `dovecot/sieve-pipe/ispconfig-rspamd-learn-ham`.

Moving a message into Junk sends it transiently to
`ispconfig-rspamd-feedback spam <user>`. Moving a message out of Junk sends
ham feedback, except when the destination is a Trash/Deleted/Junk/Spam folder.
That prevents ordinary deletion of spam from becoming a false ham signal.

The wrappers do not contain Rspamd passwords. The Python feedback command
loads the controller endpoint/password-file/classifier from the protected
`rspamd.ini` configuration and supplies the message to `rspamc` on stdin.

The Dovecot configuration is deliberately an example until the Debian 13
target is available for integration validation. The installer must verify the
actual special-use Junk mailbox name and Dovecot version before activation.

## Intended periodic/bulk flows

### Aged Inbox ham

1. Fixed search: user + `mailbox INBOX savedbefore <Nd>`.
2. Fetch one selected GUID/UID.
3. Send bytes to `rspamc learn_ham`.
4. On success, leave the Inbox message exactly where it is.
5. On failure, make no mailbox change.

### Dedicated spam mailbox

1. Search the logical Inbox of the administrator-designated spam account.
2. Fetch a bounded GUID/UID batch.
3. Learn each message as spam.
4. On success, move that UID to a configured logical archive mailbox such as
   `Trained` using `doveadm move`.
5. On failure, leave it in place.

### Explicit Ham mailbox

1. Search the logical Ham mailbox.
2. Fetch one UID.
3. Learn as ham.
4. On success, expunge that exact GUID/UID through Dovecot.
5. On failure, retain it for retry.

No web/API field may accept an arbitrary search query. The trainer constructs
the query from validated mailbox identity, fixed mailbox roles, and bounded
numeric settings.

The direct-Maildir queue code remains useful for isolated unit testing and as a
possible explicitly tested fallback, but Dovecot-backed operations are the
preferred production architecture.

Exact Dovecot 2.4 formatter/output behavior and IMAPSieve activation must still
be integration-tested on the Debian 13 target before enabling message
mutation.
