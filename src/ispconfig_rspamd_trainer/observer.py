import json
import os
import socket
from datetime import datetime, timezone

from .state import StateStore

DEFAULT_SOCKET = "/run/ispconfig-rspamd-trainer/observe.sock"
DEFAULT_STATE = "/var/lib/ispconfig-rspamd-trainer/state.db"
MAX_REQUEST = 2048


class ObservationError(ValueError):
    pass


def _validate_user(value):
    if not isinstance(value, str) or not value or len(value) > 320:
        raise ObservationError("invalid user")
    if value.startswith("-") or any(ch.isspace() or ch in "\r\n\x00" for ch in value):
        raise ObservationError("invalid user")
    return value


class ObservationService:
    def __init__(self, state):
        self.state = state

    def observe(self, protocol, user, when=None):
        if protocol not in {"imap", "pop3"}:
            raise ObservationError("invalid protocol")
        user = _validate_user(user)
        record = self.state.get_inventory_by_email(user)
        if record is None:
            return {"recorded": False, "reason": "unknown_mailbox"}
        when = when or datetime.now(timezone.utc)
        self.state.record_protocol(record.mailbox_id, protocol, when)
        return {
            "recorded": True,
            "mailbox_id": record.mailbox_id,
            "protocol": protocol,
        }


def listener(socket_path):
    listen_pid = int(os.environ.get("LISTEN_PID", "0") or "0")
    listen_fds = int(os.environ.get("LISTEN_FDS", "0") or "0")
    if listen_pid == os.getpid() and listen_fds >= 1:
        return socket.fromfd(3, socket.AF_UNIX, socket.SOCK_STREAM)
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(socket_path)
    os.chmod(socket_path, 0o660)
    sock.listen(16)
    return sock


def serve(socket_path=DEFAULT_SOCKET, state_path=DEFAULT_STATE):
    state = StateStore(state_path)
    state.initialize()
    service = ObservationService(state)
    sock = listener(socket_path)
    while True:
        conn, _ = sock.accept()
        with conn:
            data = conn.recv(MAX_REQUEST + 1)
            if len(data) > MAX_REQUEST:
                response = {"ok": False, "error": "request_too_large"}
            else:
                try:
                    request = json.loads(data.decode("utf-8"))
                    if not isinstance(request, dict):
                        raise ObservationError("request must be an object")
                    if set(request) != {"protocol", "user"}:
                        raise ObservationError("unexpected or missing fields")
                    result = service.observe(request["protocol"], request["user"])
                    response = {"ok": True, "result": result}
                except Exception as exc:
                    response = {
                        "ok": False,
                        "error": type(exc).__name__,
                        "message": str(exc)[:256],
                    }
            conn.sendall((json.dumps(response, sort_keys=True) + "\n").encode("utf-8"))


def main():
    serve(
        socket_path=os.environ.get("ISPCRT_OBSERVER_SOCKET", DEFAULT_SOCKET),
        state_path=os.environ.get("ISPCRT_STATE", DEFAULT_STATE),
    )


if __name__ == "__main__":
    main()
