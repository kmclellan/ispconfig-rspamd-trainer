import argparse
import json
import os
import socket

from .broker import DEFAULT_SOCKET
from .policy import MailboxPolicy


def call_broker(request, socket_path=DEFAULT_SOCKET):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(socket_path)
    with sock:
        sock.sendall(json.dumps(request).encode("utf-8"))
        data = sock.recv(65536)
    return json.loads(data.decode("utf-8"))


def build_parser():
    parser = argparse.ArgumentParser(prog="ispconfig-rspamd-trainer")
    parser.add_argument("--socket", default=os.environ.get("ISPCRT_SOCKET", DEFAULT_SOCKET))
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("health", "status", "policies", "discovery", "classifier-stats", "dry-run", "run"):
        sub.add_parser(command)
    getp = sub.add_parser("policy-get")
    getp.add_argument("mailbox_id", type=int)
    setp = sub.add_parser("policy-set")
    setp.add_argument("mailbox_id", type=int)
    setp.add_argument("--mode", choices=["auto", "imap", "mixed", "off"], default="auto")
    setp.add_argument("--age-days", type=int, default=30)
    setp.add_argument("--batch-size", type=int, default=100)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    simple = {
        "health": "health",
        "status": "status",
        "policies": "policy_list",
        "discovery": "discovery",
        "classifier-stats": "classifier_stats",
        "dry-run": "dry_run",
        "run": "run",
    }
    if args.command in simple:
        request = {"op": simple[args.command], "args": {}}
    elif args.command == "policy-get":
        request = {"op": "policy_get", "args": {"mailbox_id": args.mailbox_id}}
    else:
        policy = MailboxPolicy(args.mailbox_id, args.mode, args.age_days, args.batch_size).validate()
        request = {"op": "policy_set", "args": policy.__dict__}
    response = call_broker(request, args.socket)
    print(json.dumps(response, indent=2, sort_keys=True))
    if not response.get("ok"):
        return 1
    result = response.get("result")
    if isinstance(result, dict) and result.get("implemented") is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
