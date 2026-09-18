import sqlite3
from pathlib import Path

from .policy import MailboxPolicy

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
