"""Small, allowlisted local configuration loader; never logs secrets."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {"OPENROUTER_API_KEY", "OPENROUTER_MODEL", "JARVIS_ION_MODEL", "JARVIS_SPEECH_MODEL"}


def configure_console():
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def load_local_config(path=None, environ=None):
    environ = os.environ if environ is None else environ
    path = ROOT / ".env" if path is None else Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, separator, value = line.strip().partition("=")
        if separator and name in ALLOWED:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            environ.setdefault(name, value)


def speech_model(variable, default):
    configured = os.environ.get(variable, "").strip()
    local = ROOT / "models" / "stt" / default
    if not configured and variable == "JARVIS_ION_MODEL" and not (local / "model.bin").is_file():
        smaller = ROOT / "models" / "stt" / "small"
        if (smaller / "model.bin").is_file():
            return str(smaller)
    return configured or (str(local) if (local / "model.bin").is_file() else default)
