"""Best-effort lifecycle logging; never record screen, audio or conversation data."""

import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path


class AppLog:
    MAX_BYTES = 1_048_576

    def __init__(self, path: Path | None = None) -> None:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        self.path = path or base / "Jarvis" / "logs" / "application.log"
        self._lock = threading.Lock()

    def write(self, message: str) -> None:
        entry = f"{datetime.now(timezone.utc).isoformat()} [INFO] {message}\n"
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                mode = "w" if self.path.exists() and self.path.stat().st_size >= self.MAX_BYTES else "a"
                with self.path.open(mode, encoding="utf-8") as output:
                    output.write(entry)
        except OSError:
            try:
                if sys.stderr is not None:
                    sys.stderr.write(entry)
            except (OSError, ValueError):
                pass
