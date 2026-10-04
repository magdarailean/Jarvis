"""Interactive, memory-only credential setup and a read-only API check."""
import getpass
import json
import os
import ssl
import warnings
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def prompt_key():
    # Refuse getpass's echoed-input fallback in consoles that cannot hide input.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        value = getpass.getpass("Paste OpenRouter API key (hidden), then Enter: ").strip()
    if not value or any(char.isspace() for char in value) or not value.isascii():
        raise ValueError("Paste only the key, without spaces or a PowerShell command.")
    if value.startswith(("KEY=", "OPENROUTER_API_KEY=", "'", '"')):
        raise ValueError("Paste only the key, without KEY= or quotation marks.")
    os.environ["OPENROUTER_API_KEY"] = value


def check_key(key):
    """Return sanitized status only; never print server bodies or key metadata."""
    request = Request("https://openrouter.ai/api/v1/key",
                      headers={"Authorization": "Bearer " + key})
    try:
        with urlopen(request, timeout=15) as response:
            body = json.load(response)
        if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
            return False, "Unexpected response from OpenRouter."
        return True, "OpenRouter accepted the key. Model access and available credits are not verified."
    except HTTPError as error:
        if error.code == 401:
            return False, "OpenRouter rejected the key (HTTP 401). Check or replace it in your OpenRouter account."
        return False, f"OpenRouter returned HTTP {error.code}; this is not a local key-loading error."
    except (URLError, TimeoutError, ssl.SSLError):
        return False, "Cannot reach OpenRouter: check connection, proxy or TLS settings."
    except (ValueError, TypeError):
        return False, "Could not read OpenRouter's response."
