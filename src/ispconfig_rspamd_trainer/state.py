import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .policy import MailboxPolicy, ProtocolObservation

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS mailbox_policy (
  mailbox_id INTEGER PRIMARY KEY,
  mode TEXT NOT NULL,
  age_days INTEGER NOT NULL,
  batch_size INTEGER NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS protocol_observation (
  mailbox_id INTEGER PRIMARY KEY,
  observed_since TEXT NOT NULL,
  last_imap TEXT,
  last_pop3 TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS run_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  attempted INTEGER NOT NULL DEFAULT 0,
  learned_spam INTEGER NOT NULL DEFAULT 0,
  learned_ham INTEGER NOT NULL DEFAULT 0,
  skipped INTEGER NOT NULL DEFAULT 0,
  failed INTEGER NOT NULL DEFAULT 0
);
"""


def _iso(value):
    return None if value is None else value.astimezone(timezone.utc).isoformat()


def _dt(value):
    return None if value is None else datetime.fromisoformat(value)


class StateStore:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        con = sqlite3.connect(str(self.path))
        con.row_factory = sqlite3.Row
        return con

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)

    def set_policy(self, policy):
        policy.validate()
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO mailbox_policy(mailbox_id, mode, age_days, batch_size)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(mailbox_id) DO UPDATE SET
                  mode=excluded.mode,
                  age_days=excluded.age_days,
                  batch_size=excluded.batch_size,
                  updated_at=CURRENT_TIMESTAMP
                """,
                (policy.mailbox_id, policy.mode, policy.age_days, policy.batch_size),
            )

    def get_policy(self, mailbox_id):
        with self.connect() as con:
            row = con.execute(
                "SELECT mailbox_id, mode, age_days, batch_size FROM mailbox_policy WHERE mailbox_id=?",
                (mailbox_id,),
            ).fetchone()
        return None if row is None else MailboxPolicy(**dict(row))

    def list_policies(self):
        with self.connect() as con:
            rows = con.execute(
                "SELECT mailbox_id, mode, age_days, batch_size FROM mailbox_policy ORDER BY mailbox_id"
            ).fetchall()
        return [MailboxPolicy(**dict(row)) for row in rows]

    def record_protocol(self, mailbox_id, protocol, when):
        if mailbox_id <= 0:
            raise ValueError("mailbox_id must be positive")
        if protocol not in {"imap", "pop3"}:
            raise ValueError("unsupported protocol")
        if when.tzinfo is None:
            raise ValueError("when must be timezone-aware")
        column = "last_imap" if protocol == "imap" else "last_pop3"
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO protocol_observation(mailbox_id, observed_since, {column})
                VALUES (?, ?, ?)
                ON CONFLICT(mailbox_id) DO UPDATE SET
                  {column}=CASE
                    WHEN {column} IS NULL OR {column} < excluded.{column}
                    THEN excluded.{column} ELSE {column} END,
                  updated_at=CURRENT_TIMESTAMP
                """.format(column=column),
                (mailbox_id, _iso(when), _iso(when)),
            )

    def get_observation(self, mailbox_id):
        with self.connect() as con:
            row = con.execute(
                "SELECT observed_since, last_imap, last_pop3 FROM protocol_observation WHERE mailbox_id=?",
                (mailbox_id,),
            ).fetchone()
        if row is None:
            return ProtocolObservation()
        return ProtocolObservation(
            observed_since=_dt(row["observed_since"]),
            last_imap=_dt(row["last_imap"]),
            last_pop3=_dt(row["last_pop3"]),
        )
