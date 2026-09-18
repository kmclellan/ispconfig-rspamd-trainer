import fcntl
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from .policy import MailboxPolicy, aged_inbox_allowed


class RunInProgress(RuntimeError):
    pass


@dataclass
class RunSummary:
    dry_run: bool
    attempted: int = 0
    learned_spam: int = 0
    learned_ham: int = 0
    skipped: int = 0
    failed: int = 0
    candidate_spam: int = 0
    candidate_ham: int = 0
    mailboxes_considered: int = 0
    mailboxes_eligible: int = 0
    warnings: list = field(default_factory=list)

    def as_dict(self):
        return {
            "dry_run": self.dry_run,
            "attempted": self.attempted,
            "learned_spam": self.learned_spam,
            "learned_ham": self.learned_ham,
            "skipped": self.skipped,
            "failed": self.failed,
            "candidate_spam": self.candidate_spam,
            "candidate_ham": self.candidate_ham,
            "mailboxes_considered": self.mailboxes_considered,
            "mailboxes_eligible": self.mailboxes_eligible,
            "warnings": list(self.warnings),
        }


@contextmanager
def exclusive_run_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RunInProgress("another trainer run is already active") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class RunCoordinator:
    def __init__(self, state, dovecot, rspamd, lock_path=None):
        self.state = state
        self.dovecot = dovecot
        self.rspamd = rspamd
        self.lock_path = Path(lock_path or (state.path.parent / "run.lock"))

    def _policy_for(self, mailbox_id):
        return self.state.get_policy(mailbox_id) or MailboxPolicy(mailbox_id)

    def _message_failure(self, summary, label):
        summary.failed += 1
        if label not in summary.warnings:
            summary.warnings.append(label)

    def _process_spam_source(self, record, source, summary):
        policy = self._policy_for(record.mailbox_id)
        limit = policy.batch_size
        try:
            spam_refs = self.dovecot.search_mailbox(record.email, "INBOX")[:limit]
            ham_refs = self.dovecot.search_mailbox(record.email, source.ham_mailbox)[:limit]
        except Exception as exc:
            self._message_failure(summary, "spam_source_search:{}".format(type(exc).__name__))
            return

        summary.candidate_spam += len(spam_refs)
        summary.candidate_ham += len(ham_refs)
        if summary.dry_run:
            return

        for guid, uid in spam_refs:
            summary.attempted += 1
            try:
                message = self.dovecot.fetch_text(record.email, guid, uid)
                self.rspamd.learn_spam(message, deliver_to=record.email)
                self.dovecot.move_uid(record.email, source.archive_mailbox, guid, uid)
                summary.learned_spam += 1
            except Exception as exc:
                self._message_failure(
                    summary, "spam_message:{}".format(type(exc).__name__)
                )

        for guid, uid in ham_refs:
            summary.attempted += 1
            try:
                message = self.dovecot.fetch_text(record.email, guid, uid)
                self.rspamd.learn_ham(message, deliver_to=record.email)
                self.dovecot.expunge_uid(record.email, guid, uid)
                summary.learned_ham += 1
            except Exception as exc:
                self._message_failure(
                    summary, "ham_queue_message:{}".format(type(exc).__name__)
                )

    def _process_aged_ham(self, record, summary):
        policy = self._policy_for(record.mailbox_id)
        observation = self.state.get_observation(record.mailbox_id)
        allowed = aged_inbox_allowed(
            policy,
            observation,
            imap_enabled=record.imap_enabled,
            pop3_enabled=record.pop3_enabled,
        )
        if not allowed:
            return
        summary.mailboxes_eligible += 1
        try:
            refs = self.dovecot.search_aged_inbox(record.email, policy.age_days)
        except Exception as exc:
            self._message_failure(summary, "aged_ham_search:{}".format(type(exc).__name__))
            return

        candidates = []
        for guid, uid in refs:
            if self.state.was_learned(record.mailbox_id, guid, uid, "ham"):
                summary.skipped += 1
                continue
            candidates.append((guid, uid))
            if len(candidates) >= policy.batch_size:
                break

        summary.candidate_ham += len(candidates)
        if summary.dry_run:
            return

        for guid, uid in candidates:
            summary.attempted += 1
            try:
                message = self.dovecot.fetch_text(record.email, guid, uid)
                self.rspamd.learn_ham(message, deliver_to=record.email)
                self.state.mark_learned(record.mailbox_id, guid, uid, "ham")
                summary.learned_ham += 1
            except Exception as exc:
                self._message_failure(
                    summary, "aged_ham_message:{}".format(type(exc).__name__)
                )

    def execute(self, dry_run=False):
        summary = RunSummary(dry_run=bool(dry_run))
        with exclusive_run_lock(self.lock_path):
            inventory = self.state.list_inventory(present=True)
            spam_sources = {
                source.mailbox_id: source
                for source in self.state.list_spam_sources(enabled_only=True)
            }
            for record in inventory:
                summary.mailboxes_considered += 1
                if not record.active or not record.doveadm_enabled:
                    continue
                source = spam_sources.get(record.mailbox_id)
                if source is not None:
                    self._process_spam_source(record, source, summary)
                    # Dedicated corpus mailbox contents have explicit semantics;
                    # never also treat its ordinary Inbox as aged ham.
                    continue
                self._process_aged_ham(record, summary)
        return summary
