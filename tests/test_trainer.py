import tempfile
import unittest
from pathlib import Path

from ispconfig_rspamd_trainer.trainer import process_ham_queue, process_spam_queue


class FakeRspamd:
    def __init__(self, fail=False):
        self.fail = fail
        self.spam = []
        self.ham = []

    def learn_spam(self, message):
        if self.fail:
            raise RuntimeError("learning failed")
        self.spam.append(message)

    def learn_ham(self, message):
        if self.fail:
            raise RuntimeError("learning failed")
        self.ham.append(message)


class TrainerTests(unittest.TestCase):
    def maildir(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name) / "Maildir"
        for rel in ("new", "cur", ".Ham/new", ".Ham/cur", ".Trained/cur"):
            (root / rel).mkdir(parents=True)
        return td, root

    def test_empty_cur_does_not_block_new_regression(self):
        td, root = self.maildir()
        try:
            msg = root / "new" / "message-one"
            msg.write_bytes(b"Subject: spam\n\nknown spam")
            fake = FakeRspamd()
            result = process_spam_queue(root, fake)
            self.assertEqual(1, result.learned_spam)
            self.assertFalse(msg.exists())
            self.assertTrue((root / ".Trained/cur/message-one").exists())
        finally:
            td.cleanup()

    def test_spam_failure_leaves_message_queued(self):
        td, root = self.maildir()
        try:
            msg = root / "new" / "message-two"
            msg.write_bytes(b"spam")
            result = process_spam_queue(root, FakeRspamd(fail=True))
            self.assertEqual(1, result.failed)
            self.assertTrue(msg.exists())
            self.assertFalse((root / ".Trained/cur/message-two").exists())
        finally:
            td.cleanup()

    def test_ham_is_deleted_after_success_not_archived(self):
        td, root = self.maildir()
        try:
            msg = root / ".Ham/new" / "ham-one"
            msg.write_bytes(b"known ham")
            fake = FakeRspamd()
            result = process_ham_queue(root, fake)
            self.assertEqual(1, result.learned_ham)
            self.assertEqual(1, result.deleted_ham)
            self.assertFalse(msg.exists())
            self.assertEqual([b"known ham"], fake.ham)
        finally:
            td.cleanup()

    def test_ham_failure_preserves_queue_copy(self):
        td, root = self.maildir()
        try:
            msg = root / ".Ham/new" / "ham-two"
            msg.write_bytes(b"known ham")
            result = process_ham_queue(root, FakeRspamd(fail=True))
            self.assertEqual(1, result.failed)
            self.assertTrue(msg.exists())
        finally:
            td.cleanup()

    def test_unusual_maildir_filename_is_safe(self):
        td, root = self.maildir()
        try:
            name = "123.M456P789.host,S=42:2,S"
            msg = root / "new" / name
            msg.write_bytes(b"spam")
            result = process_spam_queue(root, FakeRspamd())
            self.assertEqual(1, result.archived_spam)
            self.assertTrue((root / ".Trained/cur" / name).exists())
        finally:
            td.cleanup()

    def test_batch_limit(self):
        td, root = self.maildir()
        try:
            for i in range(3):
                (root / "new" / ("m{}".format(i))).write_bytes(b"spam")
            result = process_spam_queue(root, FakeRspamd(), limit=2)
            self.assertEqual(2, result.attempted)
            self.assertEqual(1, len(list((root / "new").iterdir())))
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
