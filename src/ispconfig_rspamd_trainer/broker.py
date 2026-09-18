import json
import os
import socket

from .service import TrainerService
from .state import StateStore

DEFAULT_SOCKET = "/run/ispconfig-rspamd-trainer/broker.sock"
DEFAULT_STATE = "/var/lib/ispconfig-rspamd-trainer/state.db"
MAX_REQUEST = 65536


def listener(socket_path):
    # systemd socket activation passes the first listening descriptor as fd 3.
    listen_pid = int(os.environ.get("LISTEN_PID", "0") or "0")
    listen_fds = int(os.environ.get("LISTEN_FDS", "0") or "0")
    if listen_pid == os.getpid() and listen_fds >= 1:
        return socket.fromfd(3, socket.AF_UNIX, socket.SOCK_STREAM)

    # Development/manual mode. Production should normally use the systemd
    # socket unit so ownership/mode are established outside this process.
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(socket_path)
    os.chmod(socket_path, 0o660)
    sock.listen(8)
    return sock


def serve(socket_path=DEFAULT_SOCKET, state_path=DEFAULT_STATE):
    store = StateStore(state_path)
    store.initialize()
    service = TrainerService(store)
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
                    response = {"ok": True, "result": service.handle(request)}
                except Exception as exc:
                    response = {"ok": False, "error": str(exc)}
            conn.sendall((json.dumps(response, sort_keys=True) + "\n").encode("utf-8"))


def main():
    serve(
        os.environ.get("ISPCRT_SOCKET", DEFAULT_SOCKET),
        os.environ.get("ISPCRT_STATE", DEFAULT_STATE),
    )


if __name__ == "__main__":
    main()
