import tempfile
import unittest
from pathlib import Path

from ispconfig_rspamd_trainer.service import TrainerService
from ispconfig_rspamd_trainer.state import StateStore


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.store = StateStore(Path(self.td.name) / "state.db")
        self.store.initialize()
        self.service = TrainerService(self.store)

    def tearDown(self):
        self.td.cleanup()

    def test_unknown_operation_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.handle({"op": "shell", "args": {}})

    def test_arbitrary_argument_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.handle({"op": "health", "args": {"command": "id"}})

    def test_policy_set_and_get(self):
        response = self.service.handle({
            "op": "policy_set",
            "args": {"mailbox_id": 5, "mode": "auto", "age_days": 30, "batch_size": 100},
        })
        self.assertEqual(5, response["policy"]["mailbox_id"])
        got = self.service.handle({"op": "policy_get", "args": {"mailbox_id": 5}})
        self.assertEqual("auto", got["policy"]["mode"])


if __name__ == "__main__":
    unittest.main()
