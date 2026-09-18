import subprocess
from dataclasses import dataclass


class RspamdLearningError(RuntimeError):
    pass


@dataclass(frozen=True)
class LearnResult:
    kind: str
    returncode: int
    response: str


class RspamdClient:
    def __init__(self, binary="rspamc", timeout=60):
        self.binary = binary
        self.timeout = timeout

    def _learn(self, command, kind, message):
        if not isinstance(message, (bytes, bytearray)):
            raise TypeError("message must be bytes")
        proc = subprocess.run(
            [self.binary, command],
            input=bytes(message),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout,
            check=False,
        )
        response = proc.stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            # Deliberately do not include message data or stderr in the exception.
            raise RspamdLearningError(
                "Rspamd learning failed for {} with return code {}".format(kind, proc.returncode)
            )
        return LearnResult(kind=kind, returncode=proc.returncode, response=response[:1024])

    def learn_spam(self, message):
        return self._learn("learn_spam", "spam", message)

    def learn_ham(self, message):
        return self._learn("learn_ham", "ham", message)
