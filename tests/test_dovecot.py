import json
import subprocess
import unittest

from ispconfig_rspamd_trainer.dovecot import DoveadmClient, DovecotError


class Result:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class Recorder:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return self.results.pop(0)


class DovecotTests(unittest.TestCase):
    def test_search_aged_inbox_uses_fixed_argument_vector(self):
        output = json.dumps([{"mailbox-guid": "abc123", "uid": "42"}]).encode()
        runner = Recorder([Result(stdout=output)])
        client = DoveadmClient(runner=runner)
        refs = client.search_aged_inbox("user@example.test", 30)
        self.assertEqual([("abc123", 42)], refs)
        self.assertEqual(
            [
                "doveadm", "-f", "json", "search", "-u", "user@example.test",
                "mailbox", "INBOX", "savedbefore", "30d",
            ],
            runner.calls[0][0],
        )

    def test_fetch_returns_message_bytes(self):
        runner = Recorder([Result(stdout=json.dumps([{"text": "Subject: x\n\nbody"}]).encode())])
        client = DoveadmClient(runner=runner)
        self.assertEqual(b"Subject: x\n\nbody", client.fetch_text("user@example.test", "abc", 9))

    def test_move_has_no_shell(self):
        runner = Recorder([Result()])
        client = DoveadmClient(runner=runner)
        client.move_uid("user@example.test", "Trained", "abc", 9)
        self.assertEqual(
            ["doveadm", "move", "-u", "user@example.test", "Trained", "mailbox-guid", "abc", "uid", "9"],
            runner.calls[0][0],
        )

    def test_invalid_user_is_rejected_before_subprocess(self):
        runner = Recorder([])
        client = DoveadmClient(runner=runner)
        with self.assertRaises(ValueError):
            client.search_aged_inbox("-A", 30)
        self.assertEqual([], runner.calls)

    def test_command_failure_does_not_include_message_data(self):
        runner = Recorder([Result(returncode=75, stderr=b"private")])
        client = DoveadmClient(runner=runner)
        with self.assertRaises(DovecotError) as caught:
            client.move_uid("user@example.test", "Trained", "abc", 9)
        self.assertNotIn("private", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
