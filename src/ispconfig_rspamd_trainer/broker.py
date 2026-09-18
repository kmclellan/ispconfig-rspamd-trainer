import json
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .dovecot import DoveadmClient
from .feedback import load_client
from .launcher import AsyncRunLauncher
from .orchestrator import RunCoordinator
from .service import TrainerService
from .snapshot import SnapshotMailboxSource
from .state import StateStore

DEFAULT_SOCKET = "/run/ispconfig-rspamd-trainer/broker.sock"
DEFAULT_STATE = "/var/lib/ispconfig-rspamd-trainer/state.db"
DEFAULT_SNAPSHOT = "/var/lib/ispconfig-rspamd-trainer/mailboxes.json"
DEFAULT_RSPAMD_CONFIG = "/etc/ispconfig-rspamd-trainer/rspamd.ini"
DEFAULT_DOVEADM = "/usr/bin/doveadm"
DEFAULT_DOVEADM_SOCKET = "/run/dovecot/ispconfig-rspamd-trainer-doveadm"
DEFAULT_OBSERVER_SOCKET = "/run/ispconfig-rspamd-trainer/observe.sock"
DEFAULT_CLI = "/usr/local/bin/ispconfig-rspamd-trainer"
MAX_REQUEST = 65536
MAX_WORKERS = 8


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
    doveadm_socket=DEFAULT_DOVEADM_SOCKET,
    observer_socket_path=DEFAULT_OBSERVER_SOCKET,
    management_socket_path=DEFAULT_SOCKET,
    cli_binary=DEFAULT_CLI,
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
    socket_path = Path(doveadm_socket)
    if not path.is_file() or not os.access(str(path), os.X_OK):
        dependency_errors["doveadm"] = "binary unavailable"
    elif not socket_path.is_socket():
        dependency_errors["doveadm"] = "dedicated socket unavailable"
    else:
        dovecot = DoveadmClient(
            binary=str(path),
            server_socket=str(socket_path),
        )

    coordinator = None
    if rspamd is not None and dovecot is not None:
        coordinator = RunCoordinator(store, dovecot, rspamd)

    async_launcher = AsyncRunLauncher(
        cli_binary=cli_binary,
        socket_path=management_socket_path,
    )

    return TrainerService(
        store,
        inventory_source=inventory_source,
        rspamd=rspamd,
        coordinator=coordinator,
        dependency_errors=dependency_errors,
        observer_socket_path=observer_socket_path,
        async_launcher=async_launcher,
    )


def handle_connection(conn, service):
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


def serve(
    socket_path=DEFAULT_SOCKET,
    state_path=DEFAULT_STATE,
    snapshot_path=DEFAULT_SNAPSHOT,
    rspamd_config=DEFAULT_RSPAMD_CONFIG,
    doveadm_binary=DEFAULT_DOVEADM,
    doveadm_socket=DEFAULT_DOVEADM_SOCKET,
    observer_socket_path=DEFAULT_OBSERVER_SOCKET,
    cli_binary=DEFAULT_CLI,
):
    service = build_service(
        state_path=state_path,
        snapshot_path=snapshot_path,
        rspamd_config=rspamd_config,
        doveadm_binary=doveadm_binary,
        doveadm_socket=doveadm_socket,
        observer_socket_path=observer_socket_path,
        management_socket_path=socket_path,
        cli_binary=cli_binary,
    )
    sock = listener(socket_path)
    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS,
        thread_name_prefix="ispconfig-rspamd-broker",
    ) as executor:
        while True:
            conn, _ = sock.accept()
            executor.submit(handle_connection, conn, service)


def main():
    serve(
        socket_path=os.environ.get("ISPCRT_SOCKET", DEFAULT_SOCKET),
        state_path=os.environ.get("ISPCRT_STATE", DEFAULT_STATE),
        snapshot_path=os.environ.get("ISPCRT_SNAPSHOT", DEFAULT_SNAPSHOT),
        rspamd_config=os.environ.get("ISPCRT_RSPAMD_CONFIG", DEFAULT_RSPAMD_CONFIG),
        doveadm_binary=os.environ.get("ISPCRT_DOVEADM", DEFAULT_DOVEADM),
        doveadm_socket=os.environ.get(
            "ISPCRT_DOVEADM_SOCKET", DEFAULT_DOVEADM_SOCKET
        ),
        observer_socket_path=os.environ.get(
            "ISPCRT_OBSERVER_SOCKET", DEFAULT_OBSERVER_SOCKET
        ),
        cli_binary=os.environ.get("ISPCRT_CLI", DEFAULT_CLI),
    )


if __name__ == "__main__":
    main()
