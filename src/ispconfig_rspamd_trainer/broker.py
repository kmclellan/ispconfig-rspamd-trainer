import json
import os
import socket
from pathlib import Path

from .dovecot import DoveadmClient
from .feedback import load_client
from .orchestrator import RunCoordinator
from .service import TrainerService
from .snapshot import SnapshotMailboxSource
from .state import StateStore

DEFAULT_SOCKET = "/run/ispconfig-rspamd-trainer/broker.sock"
DEFAULT_STATE = "/var/lib/ispconfig-rspamd-trainer/state.db"
DEFAULT_SNAPSHOT = "/var/lib/ispconfig-rspamd-trainer/mailboxes.json"
DEFAULT_RSPAMD_CONFIG = "/etc/ispconfig-rspamd-trainer/rspamd.ini"
DEFAULT_DOVEADM = "/usr/bin/doveadm"
DEFAULT_OBSERVER_SOCKET = "/run/ispconfig-rspamd-trainer/observe.sock"
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


def build_service(
    state_path=DEFAULT_STATE,
    snapshot_path=DEFAULT_SNAPSHOT,
    rspamd_config=DEFAULT_RSPAMD_CONFIG,
    doveadm_binary=DEFAULT_DOVEADM,
    observer_socket_path=DEFAULT_OBSERVER_SOCKET,
):
    store = StateStore(state_path)
    store.initialize()

    inventory_source = SnapshotMailboxSource(snapshot_path)
    dependency_errors = {}

    rspamd = None
    try:
        if Path(rspamd_config).is_file():
            rspamd = load_client(rspamd_config)
        else:
            dependency_errors["rspamd"] = "configuration missing"
    except Exception as exc:
        dependency_errors["rspamd"] = "configuration error: {}".format(
            type(exc).__name__
        )

    dovecot = None
    path = Path(doveadm_binary)
    if path.is_file() and os.access(str(path), os.X_OK):
        dovecot = DoveadmClient(binary=str(path))
    else:
        dependency_errors["doveadm"] = "binary unavailable"

    coordinator = None
    if rspamd is not None and dovecot is not None:
        coordinator = RunCoordinator(store, dovecot, rspamd)

    return TrainerService(
        store,
        inventory_source=inventory_source,
        rspamd=rspamd,
        coordinator=coordinator,
        dependency_errors=dependency_errors,
        observer_socket_path=observer_socket_path,
    )


def serve(
    socket_path=DEFAULT_SOCKET,
    state_path=DEFAULT_STATE,
    snapshot_path=DEFAULT_SNAPSHOT,
    rspamd_config=DEFAULT_RSPAMD_CONFIG,
    doveadm_binary=DEFAULT_DOVEADM,
    observer_socket_path=DEFAULT_OBSERVER_SOCKET,
):
    service = build_service(
        state_path=state_path,
        snapshot_path=snapshot_path,
        rspamd_config=rspamd_config,
        doveadm_binary=doveadm_binary,
        observer_socket_path=observer_socket_path,
    )
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
                    # Keep the broker response privacy-safe: exception class +
                    # bounded message only, never tracebacks or request payloads.
                    response = {
                        "ok": False,
                        "error": type(exc).__name__,
                        "message": str(exc)[:512],
                    }
            conn.sendall((json.dumps(response, sort_keys=True) + "\n").encode("utf-8"))


def main():
    serve(
        socket_path=os.environ.get("ISPCRT_SOCKET", DEFAULT_SOCKET),
        state_path=os.environ.get("ISPCRT_STATE", DEFAULT_STATE),
        snapshot_path=os.environ.get("ISPCRT_SNAPSHOT", DEFAULT_SNAPSHOT),
        rspamd_config=os.environ.get("ISPCRT_RSPAMD_CONFIG", DEFAULT_RSPAMD_CONFIG),
        doveadm_binary=os.environ.get("ISPCRT_DOVEADM", DEFAULT_DOVEADM),
        observer_socket_path=os.environ.get(
            "ISPCRT_OBSERVER_SOCKET", DEFAULT_OBSERVER_SOCKET
        ),
    )


if __name__ == "__main__":
    main()
