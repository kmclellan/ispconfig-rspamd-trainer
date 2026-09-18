import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ispconfig_rspamd_trainer.launcher import AsyncRunLauncher, LaunchError


class FakeProcess:
    pid = 4321


class LauncherTests(unittest.TestCase):
    def test_launcher_uses_fixed_cli_and_socket_arguments(self):
        with tempfile.TemporaryDirectory() as td:
            binary = Path(td) / "trainer"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o755)
            launcher = AsyncRunLauncher(str(binary), "/run/example/broker.sock")
            with patch(
                "ispconfig_rspamd_trainer.launcher.subprocess.Popen",
                return_value=FakeProcess(),
            ) as popen:
                result = launcher.start()
            self.assertEqual({"started": True, "pid": 4321}, result)
            self.assertEqual(
                [
                    str(binary),
                    "--socket",
                    "/run/example/broker.sock",
                    "run",
                ],
                popen.call_args.args[0],
            )
            self.assertNotIn("shell", popen.call_args.kwargs)

    def test_launcher_requires_absolute_executable_file(self):
        launcher = AsyncRunLauncher("trainer", "/run/example/broker.sock")
        self.assertFalse(launcher.available())
        with self.assertRaises(LaunchError):
            launcher.start()


if __name__ == "__main__":
    unittest.main()
