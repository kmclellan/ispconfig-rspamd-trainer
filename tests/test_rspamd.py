import tempfile
import unittest
from pathlib import Path

from ispconfig_rspamd_trainer.rspamd import (
    RspamdClient,
    RspamdConnection,
    RspamdLearningError,
)


class Result:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class Recorder:
    def __init__(self, result=None):
        self.result = result or Result(stdout=b"success")
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return self.result


class RspamdClientTests(unittest.TestCase):
    def fake_binary(self, directory, exit_code=0):
        path = Path(directory) / "fake-rspamc"
        path.write_text(
            "#!/bin/sh\n"
            "printf 'arg=%s bytes=' \"$1\"\n"
            "wc -c\n"
            "exit {}\n".format(exit_code)
        )
        path.chmod(0o755)
        return str(path)

    def test_message_is_passed_on_stdin_with_fixed_command(self):
        with tempfile.TemporaryDirectory() as td:
            client = RspamdClient(binary=self.fake_binary(td))
            result = client.learn_spam(b"Subject: x\n\nbody")
            self.assertEqual("spam", result.kind)
            self.assertIn("arg=learn_spam", result.response)
            self.assertIn("bytes=16", result.response)

    def test_nonzero_exit_is_failure_without_message_content(self):
        with tempfile.TemporaryDirectory() as td:
            client = RspamdClient(binary=self.fake_binary(td, exit_code=7))
            secret = b"private-message-body"
            with self.assertRaises(RspamdLearningError) as caught:
                client.learn_ham(secret)
            self.assertNotIn("private-message-body", str(caught.exception))

    def test_controller_model_builds_fixed_rspamc_arguments(self):
        recorder = Recorder()
        connection = RspamdConnection(
            endpoint="/run/rspamd/worker-controller.socket",
            password_file="/etc/ispconfig-rspamd-trainer/controller.password",
            classifier="bayes_user",
        )
        client = RspamdClient(
            binary="/usr/bin/rspamc",
            connection=connection,
            runner=recorder,
        )
        client.learn_spam(b"spam", deliver_to="user@example.test")
        argv, kwargs = recorder.calls[0]
        self.assertEqual(
            [
                "/usr/bin/rspamc",
                "-h",
                "/run/rspamd/worker-controller.socket",
                "-P",
                "/etc/ispconfig-rspamd-trainer/controller.password",
                "-c",
                "bayes_user",
                "-d",
                "user@example.test",
                "learn_spam",
            ],
            argv,
        )
        self.assertEqual(b"spam", kwargs["input"])

    def test_relative_password_file_is_rejected(self):
        with self.assertRaises(ValueError):
            RspamdConnection(password_file="secret.txt").validate()

    def test_option_shaped_endpoint_is_rejected(self):
        with self.assertRaises(ValueError):
            RspamdConnection(endpoint="--exec=id").validate()

    def test_newline_in_delivery_identity_is_rejected(self):
        client = RspamdClient(runner=Recorder())
        with self.assertRaises(ValueError):
            client.learn_ham(b"ham", deliver_to="user@example.test\nPassword: bad")


if __name__ == "__main__":
    unittest.main()
