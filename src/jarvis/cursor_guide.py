"""Optional isolated launcher: python -m jarvis.cursor_guide.

Ion's PyQt6 prototype runs in this process; never import it into the PySide6 shell.
Only the AI transport boundary and image-size setting are adapted in memory.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

from jarvis.features.targeting.grounding import ground_response, locate
from jarvis.features.targeting.progress import evaluate, install_progress


def load_owner():
    source = Path(__file__).resolve().parents[2] / "CursorMain" / "workingVersion4.py"
    if not source.is_file():
        raise SystemExit("Run this adapter from an editable Jarvis checkout containing CursorMain.")
    sys.dont_write_bytecode = True  # Owner folder remains read-only, including caches.
    sys.path.insert(0, str(source.parent))
    spec = importlib.util.spec_from_file_location("jarvis_ion_cursor_v4", source)
    owner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = owner
    spec.loader.exec_module(owner)
    return owner


def install_grounding(owner, *, inspect_targets=False):
    original = owner.request_openrouter
    owner.MAX_IMAGE_EDGE = 1920

    def request(api_key, image, context, model, image_mime="image/png"):
        response = original(api_key, image, context, model, image_mime)
        try:
            owner.Decision.parse(response)
        except ValueError:
            return response  # Let the owner's worker perform its existing repair.
        worker = owner.QThread.currentThread()
        response, worker.awaiting_page, worker.action_identity = evaluate(response, context)
        result = ground_response(
            response, image, context, api_key,
            os.environ.get("JARVIS_TARGET_MODEL", model), image_mime,
            cancelled=worker.isInterruptionRequested,
            locator=locate,
            report=lambda **fields: owner.diagnostics.event("target.location", **fields))
        owner.diagnostics.event("target.grounding", status=owner.Decision.parse(result).status)
        if inspect_targets and not worker.isInterruptionRequested():
            # Worker-local, bounded to the current request. Never written to disk.
            worker.target_review = (image, response, result)
        return result

    owner.request_openrouter = request


def main():
    from jarvis.features.targeting.credentials import prompt_key, check_key
    if "--prompt-key" in sys.argv:
        sys.argv.remove("--prompt-key")
        try:
            prompt_key()
        except (ValueError, EOFError, KeyboardInterrupt, Warning):
            raise SystemExit("Key input failed. Use a regular PowerShell window and paste only the key.") from None
    owner = load_owner()
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Adapter option: --calibrate (offline nine-point alignment test).")
        print("Adapter option: --inspect-target (in-memory screenshot with AI rectangles).")
        print("Adapter option: --prompt-key (hidden prompt; key stays in this process).")
        print("Adapter option: --check-key (read-only OpenRouter authentication check, then exit).")
        print("Normal mode: planning and full-image location; two requests per valid action.")
    if "--calibrate" in sys.argv:
        from jarvis.features.targeting.calibration import run
        run(owner)
        return
    if "--check-key" in sys.argv or not any(flag in sys.argv for flag in ("--help", "-h", "--demo")):
        try:
            key = owner.load_api_key()
        except (ValueError, OSError):
            raise SystemExit("OpenRouter key could not be loaded. Start with --prompt-key to enter it securely.") from None
        if "--check-key" in sys.argv:
            ok, message = check_key(key)
            print(message)
            raise SystemExit(0 if ok else 1)
        print(f"OpenRouter key loaded locally. Cursor adapter PID: {os.getpid()}", flush=True)
    inspect_targets = "--inspect-target" in sys.argv
    install_progress(owner)
    if inspect_targets:
        sys.argv.remove("--inspect-target")
        from jarvis.features.targeting.inspector import install_inspector
        install_inspector(owner)
    install_grounding(owner, inspect_targets=inspect_targets)
    owner.main()


if __name__ == "__main__":
    main()
