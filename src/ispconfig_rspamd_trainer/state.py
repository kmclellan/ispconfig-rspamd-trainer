import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .inventory import MailboxRecord, SpamSource
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
CREATE TABLE IF NOT EXISTS mailbox_inventory (
  mailbox_id INTEGER PRIMARY KEY,
  email TEXT NOT NULL,
  server_id INTEGER NOT NULL,
  imap_enabled INTEGER NOT NULL,
  pop3_enabled INTEGER NOT NULL,
  active INTEGER NOT NULL,
  doveadm_enabled INTEGER NOT NULL,
  present INTEGER NOT NULL DEFAULT 1,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS spam_source (
  mailbox_id INTEGER PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 0,
  archive_mailbox TEXT NOT NULL DEFAULT 'Trained',
  ham_mailbox TEXT NOT NULL DEFAULT 'Ham',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS learned_message (
  mailbox_id INTEGER NOT NULL,
  mailbox_guid TEXT NOT NULL,
  uid INTEGER NOT NULL,
  kind TEXT NOT NULL,
  learned_at TEXT NOT NULL,
  PRIMARY KEY(mailbox_id, mailbox_guid, uid, kind)
);
CREATE TABLE IF NOT EXISTS run_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  dry_run INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  attempted INTEGER NOT NULL DEFAULT 0,
  learned_spam INTEGER NOT NULL DEFAULT 0,
  learned_ham INTEGER NOT NULL DEFAULT 0,
  skipped INTEGER NOT NULL DEFAULT 0,
  failed INTEGER NOT NULL DEFAULT 0,
  candidate_spam INTEGER NOT NULL DEFAULT 0,
  candidate_ham INTEGER NOT NULL DEFAULT 0,
  error_class TEXT
);
"""


def _iso(value):
    return None if value is None else value.astimezone(timezone.utc).isoformat()


def _dt(value):
    return None if value is None else datetime.fromisoformat(value)


def _utcnow():
    return datetime.now(timezone.utc)


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
            self._upgrade_run_log(con)

    def _upgrade_run_log(self, con):
        columns = {row["name"] for row in con.execute("PRAGMA table_info(run_log)")}
        wanted = {
            "dry_run": "INTEGER NOT NULL DEFAULT 0",
            "candidate_spam": "INTEGER NOT NULL DEFAULT 0",
            "candidate_ham": "INTEGER NOT NULL DEFAULT 0",
            "error_class": "TEXT",
        }
        for name, definition in wanted.items():
            if name not in columns:
                con.execute("ALTER TABLE run_log ADD COLUMN {} {}".format(name, definition))

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

    def reconcile_inventory(self, records, when=None):
        when = when or _utcnow()
        when_iso = _iso(when)
        records = [record.validate() for record in records]
        seen_ids = {record.mailbox_id for record in records}
        with self.connect() as con:
            if seen_ids:
                placeholders = ",".join("?" for _ in seen_ids)
                con.execute(
                    "UPDATE mailbox_inventory SET present=0 WHERE mailbox_id NOT IN ({})".format(
                        placeholders
                    ),
                    tuple(sorted(seen_ids)),
                )
            else:
                con.execute("UPDATE mailbox_inventory SET present=0")
            for record in records:
                con.execute(
                    """
                    INSERT INTO mailbox_inventory(
                      mailbox_id,email,server_id,imap_enabled,pop3_enabled,
                      active,doveadm_enabled,present,first_seen_at,last_seen_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(mailbox_id) DO UPDATE SET
                      email=excluded.email,
                      server_id=excluded.server_id,
                      imap_enabled=excluded.imap_enabled,
                      pop3_enabled=excluded.pop3_enabled,
                      active=excluded.active,
                      doveadm_enabled=excluded.doveadm_enabled,
                      present=1,
                      last_seen_at=excluded.last_seen_at
                    """,
                    (
                        record.mailbox_id,
                        record.email,
                        record.server_id,
                        int(record.imap_enabled),
                        int(record.pop3_enabled),
                        int(record.active),
                        int(record.doveadm_enabled),
                        1,
                        when_iso,
                        when_iso,
                    ),
                )
        return {
            "present": len(records),
            "missing": len(self.list_inventory(present=False)),
        }

    def list_inventory(self, present=True):
        query = """
            SELECT mailbox_id,email,server_id,imap_enabled,pop3_enabled,
                   active,doveadm_enabled
            FROM mailbox_inventory
        """
        params = ()
        if present is not None:
            query += " WHERE present=?"
            params = (int(present),)
        query += " ORDER BY mailbox_id"
        with self.connect() as con:
            rows = con.execute(query, params).fetchall()
        return [
            MailboxRecord(
                mailbox_id=row["mailbox_id"],
                email=row["email"],
                server_id=row["server_id"],
                imap_enabled=bool(row["imap_enabled"]),
                pop3_enabled=bool(row["pop3_enabled"]),
                active=bool(row["active"]),
                doveadm_enabled=bool(row["doveadm_enabled"]),
            )
            for row in rows
        ]

    def _inventory_row_to_record(self, row):
        if row is None:
            return None
        return MailboxRecord(
            mailbox_id=row["mailbox_id"],
            email=row["email"],
            server_id=row["server_id"],
            imap_enabled=bool(row["imap_enabled"]),
            pop3_enabled=bool(row["pop3_enabled"]),
            active=bool(row["active"]),
            doveadm_enabled=bool(row["doveadm_enabled"]),
        )

    def get_inventory(self, mailbox_id):
        with self.connect() as con:
            row = con.execute(
                """
                SELECT mailbox_id,email,server_id,imap_enabled,pop3_enabled,
                       active,doveadm_enabled
                FROM mailbox_inventory
                WHERE mailbox_id=? AND present=1
                """,
                (mailbox_id,),
            ).fetchone()
        return self._inventory_row_to_record(row)

    def get_inventory_by_email(self, email):
        if not isinstance(email, str) or not email or len(email) > 320:
            raise ValueError("invalid mailbox email")
        with self.connect() as con:
            row = con.execute(
                """
                SELECT mailbox_id,email,server_id,imap_enabled,pop3_enabled,
                       active,doveadm_enabled
                FROM mailbox_inventory
                WHERE email = ? COLLATE NOCASE AND present=1
                """,
                (email,),
            ).fetchone()
        return self._inventory_row_to_record(row)

    def set_spam_source(self, source):
        source.validate()
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO spam_source(mailbox_id,enabled,archive_mailbox,ham_mailbox)
                VALUES (?,?,?,?)
                ON CONFLICT(mailbox_id) DO UPDATE SET
                  enabled=excluded.enabled,
                  archive_mailbox=excluded.archive_mailbox,
                  ham_mailbox=excluded.ham_mailbox,
                  updated_at=CURRENT_TIMESTAMP
                """,
                (
                    source.mailbox_id,
                    int(source.enabled),
                    source.archive_mailbox,
                    source.ham_mailbox,
                ),
            )

    def list_spam_sources(self, enabled_only=False):
        query = "SELECT mailbox_id,enabled,archive_mailbox,ham_mailbox FROM spam_source"
        if enabled_only:
            query += " WHERE enabled=1"
        query += " ORDER BY mailbox_id"
        with self.connect() as con:
            rows = con.execute(query).fetchall()
        return [
            SpamSource(
                mailbox_id=row["mailbox_id"],
                enabled=bool(row["enabled"]),
                archive_mailbox=row["archive_mailbox"],
                ham_mailbox=row["ham_mailbox"],
            )
            for row in rows
        ]

    def mark_learned(self, mailbox_id, mailbox_guid, uid, kind, when=None):
        if mailbox_id <= 0 or int(uid) <= 0:
            raise ValueError("invalid learned message identity")
        if kind not in {"ham", "spam"}:
            raise ValueError("invalid learned message kind")
        if not isinstance(mailbox_guid, str) or not mailbox_guid or len(mailbox_guid) > 255:
            raise ValueError("invalid mailbox guid")
        when = when or _utcnow()
        with self.connect() as con:
            con.execute(
                """
                INSERT OR IGNORE INTO learned_message(
                  mailbox_id,mailbox_guid,uid,kind,learned_at
                ) VALUES (?,?,?,?,?)
                """,
                (mailbox_id, mailbox_guid, int(uid), kind, _iso(when)),
            )

    def was_learned(self, mailbox_id, mailbox_guid, uid, kind):
        with self.connect() as con:
            row = con.execute(
                """
                SELECT 1 FROM learned_message
                WHERE mailbox_id=? AND mailbox_guid=? AND uid=? AND kind=?
                """,
                (mailbox_id, mailbox_guid, int(uid), kind),
            ).fetchone()
        return row is not None

    def start_run(self, dry_run=False, when=None):
        when = when or _utcnow()
        with self.connect() as con:
            cur = con.execute(
                "INSERT INTO run_log(started_at,dry_run,status) VALUES (?,?,?)",
                (_iso(when), int(dry_run), "running"),
            )
            return cur.lastrowid

    def finish_run(self, run_id, result, status, error_class=None, when=None):
        when = when or _utcnow()
        fields = {
            "attempted": int(result.get("attempted", 0)),
            "learned_spam": int(result.get("learned_spam", 0)),
            "learned_ham": int(result.get("learned_ham", 0)),
            "skipped": int(result.get("skipped", 0)),
            "failed": int(result.get("failed", 0)),
            "candidate_spam": int(result.get("candidate_spam", 0)),
            "candidate_ham": int(result.get("candidate_ham", 0)),
        }
        with self.connect() as con:
            con.execute(
                """
                UPDATE run_log SET
                  finished_at=?, status=?, attempted=?, learned_spam=?,
                  learned_ham=?, skipped=?, failed=?, candidate_spam=?,
                  candidate_ham=?, error_class=?
                WHERE id=?
                """,
                (
                    _iso(when),
                    status,
                    fields["attempted"],
                    fields["learned_spam"],
                    fields["learned_ham"],
                    fields["skipped"],
                    fields["failed"],
                    fields["candidate_spam"],
                    fields["candidate_ham"],
                    error_class,
                    run_id,
                ),
            )

    def latest_run(self):
        with self.connect() as con:
            row = con.execute(
                """
                SELECT id,started_at,finished_at,dry_run,status,attempted,
                       learned_spam,learned_ham,skipped,failed,
                       candidate_spam,candidate_ham,error_class
                FROM run_log ORDER BY id DESC LIMIT 1
                """
            ).fetchone()
        return None if row is None else dict(row)
