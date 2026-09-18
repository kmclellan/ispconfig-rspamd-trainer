import argparse
import json
import os
import socket

from .observer import DEFAULT_SOCKET


def observe(protocol, user, socket_path=DEFAULT_SOCKET, timeout=1.0):
    request = {"protocol": protocol, "user": user}
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect(socket_path)
    with sock:
        sock.sendall(json.dumps(request).encode("utf-8"))
        data = sock.recv(4096)
    response = json.loads(data.decode("utf-8"))
    if not response.get("ok"):
        raise RuntimeError(response.get("error", "observer failed"))
    return response["result"]


def build_parser():
    parser = argparse.ArgumentParser(prog="ispconfig-rspamd-observe")
    parser.add_argument("protocol", choices=["imap", "pop3"])
    parser.add_argument("user")
    parser.add_argument(
        "--socket",
        default=os.environ.get("ISPCRT_OBSERVER_SOCKET", DEFAULT_SOCKET),
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        observe(args.protocol, args.user, socket_path=args.socket)
    except Exception:
        # Post-login integration is deliberately fail-open: observation must
        # never prevent a user from accessing mail.
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
