import json
import subprocess


class DovecotError(RuntimeError):
    pass


def _validate_user(user):
    if not isinstance(user, str) or not user or len(user) > 320:
        raise ValueError("invalid mailbox user")
    if user.startswith("-") or any(ch.isspace() or ch == "\x00" for ch in user):
        raise ValueError("invalid mailbox user")
    return user


def _validate_token(value, name, max_len=255):
    if not isinstance(value, str) or not value or len(value) > max_len:
        raise ValueError("invalid {}".format(name))
    if value.startswith("-") or "\x00" in value or any(ch in "\r\n" for ch in value):
        raise ValueError("invalid {}".format(name))
    return value


class DoveadmClient:
    def __init__(self, binary="doveadm", timeout=60, runner=None):
        self.binary = binary
        self.timeout = timeout
        self.runner = runner or subprocess.run

    def _run_json(self, args):
        proc = self.runner(
            [self.binary, "-f", "json"] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout,
            check=False,
        )
        if proc.returncode != 0:
            raise DovecotError("doveadm failed with return code {}".format(proc.returncode))
        try:
            result = json.loads(proc.stdout.decode("utf-8"))
        except Exception as exc:
            raise DovecotError("invalid doveadm JSON output") from exc
        if not isinstance(result, list):
            raise DovecotError("unexpected doveadm JSON result")
        return result

    def _run(self, args):
        proc = self.runner(
            [self.binary] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout,
            check=False,
        )
        if proc.returncode != 0:
            raise DovecotError("doveadm failed with return code {}".format(proc.returncode))
        return proc.stdout

    def search_mailbox(self, user, mailbox, savedbefore_days=None):
        user = _validate_user(user)
        mailbox = _validate_token(mailbox, "mailbox")
        args = ["search", "-u", user, "mailbox", mailbox]
        if savedbefore_days is not None:
            if (
                not isinstance(savedbefore_days, int)
                or savedbefore_days < 1
                or savedbefore_days > 3650
            ):
                raise ValueError("savedbefore_days outside safe range")
            args.extend(["savedbefore", "{}d".format(savedbefore_days)])
        rows = self._run_json(args)
        refs = []
        for row in rows:
            guid = row.get("mailbox-guid") or row.get("mailbox_guid")
            uid = row.get("uid")
            if guid is None or uid is None:
                raise DovecotError("search result lacks mailbox-guid/uid")
            uid = int(uid)
            if uid <= 0:
                raise DovecotError("search result has invalid uid")
            refs.append((_validate_token(str(guid), "mailbox guid"), uid))
        return refs

    def search_aged_inbox(self, user, age_days):
        if not isinstance(age_days, int) or age_days < 30 or age_days > 3650:
            raise ValueError("age_days outside safe range")
        return self.search_mailbox(user, "INBOX", savedbefore_days=age_days)

    def fetch_text(self, user, mailbox_guid, uid):
        user = _validate_user(user)
        mailbox_guid = _validate_token(mailbox_guid, "mailbox guid")
        uid = int(uid)
        if uid <= 0:
            raise ValueError("uid must be positive")
        rows = self._run_json(
            ["fetch", "-u", user, "text", "mailbox-guid", mailbox_guid, "uid", str(uid)]
        )
        if len(rows) != 1 or not isinstance(rows[0].get("text"), str):
            raise DovecotError("fetch did not return exactly one text record")
        return rows[0]["text"].encode("utf-8", errors="surrogatepass")

    def move_uid(self, user, destination, mailbox_guid, uid):
        user = _validate_user(user)
        destination = _validate_token(destination, "destination mailbox")
        mailbox_guid = _validate_token(mailbox_guid, "mailbox guid")
        uid = int(uid)
        if uid <= 0:
            raise ValueError("uid must be positive")
        self._run(
            [
                "move", "-u", user, destination,
                "mailbox-guid", mailbox_guid, "uid", str(uid),
            ]
        )

    def expunge_uid(self, user, mailbox_guid, uid):
        user = _validate_user(user)
        mailbox_guid = _validate_token(mailbox_guid, "mailbox guid")
        uid = int(uid)
        if uid <= 0:
            raise ValueError("uid must be positive")
        self._run(
            ["expunge", "-u", user, "mailbox-guid", mailbox_guid, "uid", str(uid)]
        )
