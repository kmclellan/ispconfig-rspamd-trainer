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
    sub.add_parser("health")
    sub.add_parser("status")
    sub.add_parser("policies")
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
    if args.command == "health":
        request = {"op": "health", "args": {}}
    elif args.command == "status":
        request = {"op": "status", "args": {}}
    elif args.command == "policies":
        request = {"op": "policy_list", "args": {}}
    elif args.command == "policy-get":
        request = {"op": "policy_get", "args": {"mailbox_id": args.mailbox_id}}
    else:
        policy = MailboxPolicy(args.mailbox_id, args.mode, args.age_days, args.batch_size).validate()
        request = {"op": "policy_set", "args": policy.__dict__}
    print(json.dumps(call_broker(request, args.socket), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
