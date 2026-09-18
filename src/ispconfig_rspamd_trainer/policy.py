from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

MODES = {"auto", "imap", "mixed", "off"}
MIN_AGE_DAYS = 30
DEFAULT_AGE_DAYS = 30
DEFAULT_POP3_LOOKBACK_DAYS = 90
DEFAULT_BATCH_SIZE = 100


@dataclass(frozen=True)
class MailboxPolicy:
    mailbox_id: int
    mode: str = "auto"
    age_days: int = DEFAULT_AGE_DAYS
    batch_size: int = DEFAULT_BATCH_SIZE

    def validate(self):
        if self.mailbox_id <= 0:
            raise ValueError("mailbox_id must be positive")
        if self.mode not in MODES:
            raise ValueError("unsupported mailbox mode")
        if self.age_days < MIN_AGE_DAYS:
            raise ValueError("age_days must be at least 30")
        if not 1 <= self.batch_size <= 1000:
            raise ValueError("batch_size must be between 1 and 1000")
        return self


@dataclass(frozen=True)
class ProtocolObservation:
    last_imap: Optional[datetime] = None
    last_pop3: Optional[datetime] = None


def aged_inbox_allowed(policy, observation, now=None, pop3_lookback_days=DEFAULT_POP3_LOOKBACK_DAYS):
    policy.validate()
    if policy.mode in {"off", "mixed"}:
        return False
    if policy.mode == "imap":
        return True
    if observation.last_imap is None:
        return False
    now = now or datetime.now(timezone.utc)
    if observation.last_imap.tzinfo is None:
        raise ValueError("last_imap must be timezone-aware")
    if observation.last_pop3 is not None:
        if observation.last_pop3.tzinfo is None:
            raise ValueError("last_pop3 must be timezone-aware")
        if observation.last_pop3 >= now - timedelta(days=pop3_lookback_days):
            return False
    return True
