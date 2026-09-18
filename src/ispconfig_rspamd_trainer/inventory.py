from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MailboxRecord:
    mailbox_id: int
    email: str
    server_id: int
    imap_enabled: bool
    pop3_enabled: bool
    active: bool = True
    doveadm_enabled: bool = True

    def validate(self):
        if self.mailbox_id <= 0:
            raise ValueError("mailbox_id must be positive")
        if self.server_id <= 0:
            raise ValueError("server_id must be positive")
        if not isinstance(self.email, str) or not self.email or len(self.email) > 320:
            raise ValueError("invalid mailbox email")
        if self.email.startswith("-") or any(ch.isspace() or ch in "\r\n\x00" for ch in self.email):
            raise ValueError("invalid mailbox email")
        return self

    @property
    def access_mode(self):
        if not self.active:
            return "inactive"
        if self.imap_enabled and not self.pop3_enabled:
            return "imap_only"
        if self.pop3_enabled and not self.imap_enabled:
            return "pop3_only"
        if self.imap_enabled and self.pop3_enabled:
            return "mixed_capable"
        return "no_remote_access"


@dataclass(frozen=True)
class SpamSource:
    mailbox_id: int
    enabled: bool = False
    archive_mailbox: str = "Trained"
    ham_mailbox: str = "Ham"

    def validate(self):
        if self.mailbox_id <= 0:
            raise ValueError("mailbox_id must be positive")
        for value, name in (
            (self.archive_mailbox, "archive mailbox"),
            (self.ham_mailbox, "ham mailbox"),
        ):
            if not isinstance(value, str) or not value or len(value) > 255:
                raise ValueError("invalid {}".format(name))
            if value.startswith("-") or "\x00" in value or any(ch in "\r\n" for ch in value):
                raise ValueError("invalid {}".format(name))
        return self


def access_mode_summary(records):
    counts = {
        "imap_only": 0,
        "pop3_only": 0,
        "mixed_capable": 0,
        "no_remote_access": 0,
        "inactive": 0,
    }
    for record in records:
        counts[record.access_mode] += 1
    return counts
