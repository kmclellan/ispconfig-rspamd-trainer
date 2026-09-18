import os
import subprocess
from pathlib import Path


class LaunchError(RuntimeError):
    pass


class AsyncRunLauncher:
    def __init__(self, cli_binary, socket_path):
        self.cli_binary = Path(cli_binary)
        self.socket_path = str(socket_path)

    def available(self):
        return (
            self.cli_binary.is_absolute()
            and self.cli_binary.is_file()
            and os.access(str(self.cli_binary), os.X_OK)
        )

    def start(self):
        if not self.available():
            raise LaunchError("trainer CLI is unavailable")
        proc = subprocess.Popen(
            [
                str(self.cli_binary),
                "--socket",
                self.socket_path,
                "run",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        return {"started": True, "pid": proc.pid}
