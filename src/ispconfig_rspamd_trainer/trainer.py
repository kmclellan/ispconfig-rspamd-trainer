from dataclasses import dataclass

from .maildir import archive_message, queue_files


@dataclass
class RunCounts:
    attempted: int = 0
    learned_spam: int = 0
    learned_ham: int = 0
    failed: int = 0
    archived_spam: int = 0
    deleted_ham: int = 0

    def as_dict(self):
        return {
            "attempted": self.attempted,
            "learned_spam": self.learned_spam,
            "learned_ham": self.learned_ham,
            "failed": self.failed,
            "archived_spam": self.archived_spam,
            "deleted_ham": self.deleted_ham,
        }


def process_spam_queue(maildir, rspamd, limit=100):
    counts = RunCounts()
    for message_path in queue_files(maildir, ("cur", "new"), limit=limit):
        counts.attempted += 1
        try:
            message = message_path.read_bytes()
            rspamd.learn_spam(message)
            counts.learned_spam += 1
            archive_message(maildir, message_path, ".Trained/cur")
            counts.archived_spam += 1
        except Exception:
            # The caller/journal may record an aggregate failure. Message content
            # is intentionally not returned or logged here, and the source stays
            # queued if learning/archive fails.
            counts.failed += 1
    return counts


def process_ham_queue(maildir, rspamd, limit=100):
    counts = RunCounts()
    for message_path in queue_files(maildir, (".Ham/cur", ".Ham/new"), limit=limit):
        counts.attempted += 1
        try:
            message = message_path.read_bytes()
            rspamd.learn_ham(message)
            counts.learned_ham += 1
            message_path.unlink()
            counts.deleted_ham += 1
        except Exception:
            counts.failed += 1
    return counts
