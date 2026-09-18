import argparse
import configparser
import sys
from pathlib import Path

from .rspamd import RspamdClient, RspamdConnection

DEFAULT_CONFIG = "/etc/ispconfig-rspamd-trainer/rspamd.ini"
DEFAULT_MAX_MESSAGE_BYTES = 64 * 1024 * 1024


def load_client(config_path=DEFAULT_CONFIG, runner=None):
    path = Path(config_path)
    parser = configparser.ConfigParser(interpolation=None)
    if not path.is_file():
        raise ValueError("Rspamd trainer configuration is not readable")
    with path.open("r", encoding="utf-8") as handle:
        parser.read_file(handle)
    if "rspamd" not in parser:
        raise ValueError("missing [rspamd] configuration section")
    section = parser["rspamd"]
    binary = section.get("binary", "/usr/bin/rspamc").strip()
    if not binary or not Path(binary).is_absolute():
        raise ValueError("rspamc binary must be an absolute path")
    timeout = section.getint("timeout", fallback=60)
    if timeout < 1 or timeout > 600:
        raise ValueError("rspamd timeout outside safe range")
    connection = RspamdConnection(
        endpoint=section.get("endpoint", fallback=None) or None,
        password_file=section.get("password_file", fallback=None) or None,
        classifier=section.get("classifier", fallback=None) or None,
    ).validate()
    return RspamdClient(
        binary=binary,
        timeout=timeout,
        connection=connection,
        runner=runner,
    )


def read_bounded_message(stream, max_bytes=DEFAULT_MAX_MESSAGE_BYTES):
    data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("message exceeds configured training size limit")
    if not data:
        raise ValueError("empty message cannot be trained")
    return data


def learn_feedback(kind, deliver_to, stream, client):
    message = read_bounded_message(stream)
    if kind == "spam":
        return client.learn_spam(message, deliver_to=deliver_to)
    if kind == "ham":
        return client.learn_ham(message, deliver_to=deliver_to)
    raise ValueError("feedback kind must be spam or ham")


def build_parser():
    parser = argparse.ArgumentParser(prog="ispconfig-rspamd-feedback")
    parser.add_argument("kind", choices=["spam", "ham"])
    parser.add_argument("deliver_to")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        client = load_client(args.config)
        learn_feedback(args.kind, args.deliver_to, sys.stdin.buffer, client)
    except Exception as exc:
        # Intentionally report only the exception class and safe diagnostic.
        # Never log message content or controller credentials here.
        print(
            "ispconfig-rspamd-feedback: {}".format(str(exc)),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
