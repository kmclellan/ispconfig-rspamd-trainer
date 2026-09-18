import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PostLoginTests(unittest.TestCase):
    def test_postlogin_scripts_fail_open_and_exec_session(self):
        for name, protocol in (
            ("ispconfig-rspamd-observe-imap", "imap"),
            ("ispconfig-rspamd-observe-pop3", "pop3"),
        ):
            text = (ROOT / "dovecot/postlogin" / name).read_text()
            self.assertIn("ispconfig-rspamd-observe {}".format(protocol), text)
            self.assertIn("|| true", text)
            self.assertIn('exec "$@"', text)
            self.assertNotIn("IP", text)

    def test_observer_socket_is_not_management_broker_socket(self):
        observer = (
            ROOT / "systemd/ispconfig-rspamd-trainer-observer.socket"
        ).read_text()
        broker = (
            ROOT / "systemd/ispconfig-rspamd-trainer-broker.socket"
        ).read_text()
        self.assertIn("observe.sock", observer)
        self.assertIn("broker.sock", broker)
        self.assertNotEqual(observer, broker)


if __name__ == "__main__":
    unittest.main()
