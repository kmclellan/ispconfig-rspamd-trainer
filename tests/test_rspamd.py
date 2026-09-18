import os
import tempfile
import unittest
from pathlib import Path

from ispconfig_rspamd_trainer.rspamd import RspamdClient, RspamdLearningError


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


if __name__ == "__main__":
    unittest.main()
