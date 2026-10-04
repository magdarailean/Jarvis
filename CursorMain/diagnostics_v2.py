"""Console-only diagnostics. Never log audio, screenshots, headers or prompts."""
import json
import logging
from pathlib import Path
import re
import sys
import threading
import time
import traceback


LOGGER = logging.getLogger("jarvis.companion")
LOGGER.addHandler(logging.NullHandler())
LOGGER.propagate = False
_sensitive = []
_lock = threading.Lock()
_debug = False


def protect(value):
    """Redact credentials/transcripts even if a remote error repeats them."""
    if not value:
        return
    with _lock:
        if value not in _sensitive:
            _sensitive.append(value)
            del _sensitive[:-32]


def scrub(value):
    if isinstance(value, dict):
        return {str(k): scrub(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    if not isinstance(value, str):
        return value
    with _lock:
        secrets = list(_sensitive)
    for secret in sorted(secrets, key=len, reverse=True):
        value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"AIza[\w-]{20,}|sk-(?:proj-)?[\w-]{20,}", "[REDACTED]", value)
    value = re.sub(r"(?i)(x-goog-api-key|authorization|api_key)\s*[:=]\s*[^\s,;]+",
                   r"\1=[REDACTED]", value)
    return value[:1200]


def configure(debug=False, stream=None):
    global _debug
    _debug = debug
    for handler in list(LOGGER.handlers):
        LOGGER.removeHandler(handler)
        handler.close()
    output = stream if stream is not None else sys.stdout
    if output is None:
        LOGGER.addHandler(logging.NullHandler())  # pythonw: no console or log file.
    else:
        handler = logging.StreamHandler(output)
        formatter = logging.Formatter("%(asctime)s UTC %(levelname)s %(message)s", "%H:%M:%S")
        formatter.converter = time.gmtime
        handler.setFormatter(formatter)
        LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.DEBUG if debug else logging.INFO)


def event(name, *, level=logging.INFO, **fields):
    LOGGER.log(level, json.dumps(scrub(dict(event=name, **fields)), ensure_ascii=True, default=str))


def exception(name, error, **fields):
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    if not isinstance(status, (str, int)):
        status = None
    message = str(error)
    # Never dump a reflected request body or encoded screenshot from an SDK error.
    if any(marker in message.lower() for marker in (
        "original_goal", "verified_steps", "pending_attempt", "base64", "ivbor", "data:image"
    )):
        message = "Error contains request data; omitted. See exception type/status/stage."
    detail = dict(error_type=type(error).__name__, http_status=status, message=message)
    causes = []
    cause = error.__cause__ or error.__context__
    while cause is not None and len(causes) < 3:
        causes.append(type(cause).__name__)
        cause = cause.__cause__ or cause.__context__
    if causes:
        detail["causes"] = causes
    if _debug:
        detail["stack"] = [f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
                           for frame in traceback.extract_tb(error.__traceback__)[-8:]]
    event(name, level=logging.ERROR, **fields, **detail)
