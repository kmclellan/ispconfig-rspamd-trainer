import tempfile
import unittest
from pathlib import Path

from ispconfig_rspamd_trainer.policy import MailboxPolicy
from ispconfig_rspamd_trainer.state import StateStore


class StateTests(unittest.TestCase):
    def test_policy_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(Path(td) / "state.db")
            store.initialize()
            policy = MailboxPolicy(7, "imap", 45, 50)
            store.set_policy(policy)
            self.assertEqual(policy, store.get_policy(7))
            self.assertEqual([policy], list(store.list_policies()))


if __name__ == "__main__":
    unittest.main()
