import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class RspamdLearningError(RuntimeError):
    pass


class RspamdControlError(RuntimeError):
    pass


def _validated_arg(value, name, max_len=1024):
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > max_len:
        raise ValueError("invalid {}".format(name))
    if "\x00" in value or "\r" in value or "\n" in value:
        raise ValueError("invalid {}".format(name))
    if value.startswith("-"):
        raise ValueError("invalid {}".format(name))
    return value


@dataclass(frozen=True)
class RspamdConnection:
    """Validated rspamc controller settings.

    The model intentionally mirrors the useful interoperability settings from
    jnorell/train-spam-scanner: controller endpoint, password-file
    authentication, classifier selection, and per-recipient delivery context.
    See THIRD_PARTY_NOTICES.md.
    """

    endpoint: Optional[str] = None
    password_file: Optional[str] = None
    classifier: Optional[str] = None

    def validate(self):
        _validated_arg(self.endpoint, "controller endpoint")
        _validated_arg(self.classifier, "classifier", max_len=255)
        if self.password_file is not None:
            password_file = _validated_arg(
                self.password_file, "controller password file", max_len=4096
            )
            if not Path(password_file).is_absolute():
                raise ValueError("controller password file must be an absolute path")
        return self

    def command_args(self, deliver_to=None):
        self.validate()
        args = []
        if self.endpoint:
            args.extend(["-h", self.endpoint])
        if self.password_file:
            # rspamc accepts a file path for -P; this keeps the secret itself
            # out of argv/process listings.
            args.extend(["-P", self.password_file])
        if self.classifier:
            args.extend(["-c", self.classifier])
        if deliver_to is not None:
            args.extend(["-d", _validated_arg(deliver_to, "deliver-to", max_len=320)])
        return args


@dataclass(frozen=True)
class LearnResult:
    kind: str
    returncode: int
    response: str


class RspamdClient:
    def __init__(
        self,
        binary="rspamc",
        timeout=60,
        connection=None,
        runner=None,
    ):
        self.binary = binary
        self.timeout = timeout
        self.connection = connection or RspamdConnection()
        self.runner = runner or subprocess.run

    def _run(self, argv, input_bytes=None):
        return self.runner(
            argv,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout,
            check=False,
        )

    def _learn(self, command, kind, message, deliver_to=None):
        if not isinstance(message, (bytes, bytearray)):
            raise TypeError("message must be bytes")
        argv = [self.binary]
        argv.extend(self.connection.command_args(deliver_to=deliver_to))
        argv.append(command)
        proc = self._run(argv, input_bytes=bytes(message))
        response = proc.stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            # Deliberately do not include message data, stderr, password-file
            # contents, or the controller credential in the exception.
            raise RspamdLearningError(
                "Rspamd learning failed for {} with return code {}".format(
                    kind, proc.returncode
                )
            )
        return LearnResult(kind=kind, returncode=proc.returncode, response=response[:1024])

    def learn_spam(self, message, deliver_to=None):
        return self._learn("learn_spam", "spam", message, deliver_to=deliver_to)

    def learn_ham(self, message, deliver_to=None):
        return self._learn("learn_ham", "ham", message, deliver_to=deliver_to)

    def stat(self):
        argv = [self.binary]
        argv.extend(self.connection.command_args())
        argv.extend(["-j", "stat"])
        proc = self._run(argv)
        if proc.returncode != 0:
            raise RspamdControlError(
                "Rspamd stat failed with return code {}".format(proc.returncode)
            )
        try:
            result = json.loads(proc.stdout.decode("utf-8"))
        except Exception as exc:
            raise RspamdControlError("Rspamd stat returned invalid JSON") from exc
        if not isinstance(result, (dict, list)):
            raise RspamdControlError("Rspamd stat returned unexpected JSON type")
        return result
