import json
from pathlib import Path

from .ispconfig import mailbox_from_row


class SnapshotError(RuntimeError):
    pass


class SnapshotMailboxSource:
    def __init__(self, path):
        self.path = Path(path)

    def available(self):
        return self.path.is_file()

    def list_mailboxes(self):
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            raise SnapshotError("mailbox snapshot is unavailable or invalid") from exc
        if not isinstance(payload, dict) or payload.get("schema") != 1:
            raise SnapshotError("unsupported mailbox snapshot schema")
        rows = payload.get("mailboxes")
        if not isinstance(rows, list):
            raise SnapshotError("mailbox snapshot lacks mailbox list")
        return [mailbox_from_row(row) for row in rows]
