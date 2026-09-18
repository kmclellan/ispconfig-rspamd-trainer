from .inventory import MailboxRecord


MAIL_USER_QUERY = """
SELECT
  mailuser_id,
  server_id,
  email,
  disableimap,
  disablepop3,
  access,
  disabledoveadm
FROM mail_user
ORDER BY mailuser_id
"""


def _enabled(disable_value):
    if disable_value not in ("y", "n"):
        raise ValueError("unexpected ISPConfig enable/disable value")
    return disable_value == "n"


def mailbox_from_row(row):
    record = MailboxRecord(
        mailbox_id=int(row["mailuser_id"]),
        server_id=int(row["server_id"]),
        email=str(row["email"]),
        imap_enabled=_enabled(row["disableimap"]),
        pop3_enabled=_enabled(row["disablepop3"]),
        active=str(row["access"]) == "y",
        doveadm_enabled=_enabled(row["disabledoveadm"]),
    )
    return record.validate()


class ISPConfigMailboxSource:
    """Read-only adapter over an already-authorized DB-API connection.

    Credential acquisition is intentionally outside this class. Production
    installation will provide a narrowly privileged discovery path after the
    Debian 13 target is available; tests use an in-memory synthetic database.
    """

    def __init__(self, connection):
        self.connection = connection

    def list_mailboxes(self):
        cursor = self.connection.cursor()
        try:
            cursor.execute(MAIL_USER_QUERY)
            columns = [item[0] for item in cursor.description]
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [mailbox_from_row(dict(zip(columns, row))) for row in rows]
