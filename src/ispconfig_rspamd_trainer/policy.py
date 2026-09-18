from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

MODES = {"auto", "imap", "mixed", "off"}
MIN_AGE_DAYS = 30
DEFAULT_AGE_DAYS = 30
DEFAULT_POP3_LOOKBACK_DAYS = 90
DEFAULT_AUTO_WARMUP_DAYS = 30
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
    observed_since: Optional[datetime] = None
    last_imap: Optional[datetime] = None
    last_pop3: Optional[datetime] = None


def _aware(value, name):
    if value is not None and value.tzinfo is None:
        raise ValueError("{} must be timezone-aware".format(name))


def aged_inbox_allowed(
    policy,
    observation,
    now=None,
    pop3_lookback_days=DEFAULT_POP3_LOOKBACK_DAYS,
    auto_warmup_days=DEFAULT_AUTO_WARMUP_DAYS,
    imap_enabled=True,
    pop3_enabled=True,
):
    policy.validate()
    if policy.mode in {"off", "mixed"}:
        return False
    if not imap_enabled:
        return False
    if policy.mode == "imap":
        return True

    # ISPConfig can explicitly disable POP3 for a mailbox. That is stronger
    # evidence than waiting to observe the absence of POP3 activity.
    if not pop3_enabled:
        return True

    now = now or datetime.now(timezone.utc)
    _aware(observation.observed_since, "observed_since")
    _aware(observation.last_imap, "last_imap")
    _aware(observation.last_pop3, "last_pop3")

    # Auto mode with POP3 allowed needs positive observation evidence, not
    # merely an absence of observed POP3 on a fresh installation.
    if observation.observed_since is None or observation.last_imap is None:
        return False
    if observation.observed_since > now - timedelta(days=auto_warmup_days):
        return False
    if observation.last_pop3 is not None:
        if observation.last_pop3 >= now - timedelta(days=pop3_lookback_days):
            return False
    return True
