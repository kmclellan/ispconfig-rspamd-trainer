import io
import tempfile
import unittest
from pathlib import Path

from ispconfig_rspamd_trainer.feedback import (
    learn_feedback,
    load_client,
    read_bounded_message,
)


class FakeClient:
    def __init__(self):
        self.calls = []

    def learn_spam(self, message, deliver_to=None):
        self.calls.append(("spam", message, deliver_to))

    def learn_ham(self, message, deliver_to=None):
        self.calls.append(("ham", message, deliver_to))


class FeedbackTests(unittest.TestCase):
    def test_spam_feedback_is_transient_and_passes_delivery_identity(self):
        client = FakeClient()
        learn_feedback(
            "spam",
            "user@example.test",
            io.BytesIO(b"Subject: test\r\n\r\nbody"),
            client,
        )
        self.assertEqual(
            [("spam", b"Subject: test\r\n\r\nbody", "user@example.test")],
            client.calls,
        )

    def test_ham_feedback_calls_ham_learning(self):
        client = FakeClient()
        learn_feedback("ham", "user@example.test", io.BytesIO(b"ham"), client)
        self.assertEqual([("ham", b"ham", "user@example.test")], client.calls)

    def test_message_size_is_bounded(self):
        with self.assertRaises(ValueError):
            read_bounded_message(io.BytesIO(b"12345"), max_bytes=4)

    def test_empty_message_is_rejected(self):
        with self.assertRaises(ValueError):
            read_bounded_message(io.BytesIO(b""), max_bytes=10)

    def test_relative_binary_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "rspamd.ini"
            config.write_text("[rspamd]\nbinary = rspamc\n")
            with self.assertRaises(ValueError):
                load_client(config)

    def test_config_reuses_controller_password_file_model(self):
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "rspamd.ini"
            config.write_text(
                "[rspamd]\n"
                "binary = /usr/bin/rspamc\n"
                "endpoint = /run/rspamd/worker-controller.socket\n"
                "password_file = /etc/ispconfig-rspamd-trainer/controller.password\n"
                "classifier = bayes_user\n"
                "timeout = 45\n"
            )
            client = load_client(config)
            self.assertEqual("/usr/bin/rspamc", client.binary)
            self.assertEqual(45, client.timeout)
            self.assertEqual(
                "/run/rspamd/worker-controller.socket",
                client.connection.endpoint,
            )
            self.assertEqual(
                "/etc/ispconfig-rspamd-trainer/controller.password",
                client.connection.password_file,
            )
            self.assertEqual("bayes_user", client.connection.classifier)


if __name__ == "__main__":
    unittest.main()
