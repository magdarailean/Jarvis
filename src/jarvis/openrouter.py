"""Launch the read-only OpenRouter companion without mixing Qt bindings."""
import os
import argparse
from pathlib import Path
import runpy
import sys

from jarvis.local_config import ROOT, configure_console, load_local_config, speech_model


def main():
    configure_console()
    load_local_config()
    if "--demo" not in sys.argv and not os.environ.get("OPENROUTER_API_KEY", "").strip():
        print(f"Adaugă cheia OpenRouter după OPENROUTER_API_KEY= în {ROOT / '.env'}.")
        return 1
    model = speech_model("JARVIS_SPEECH_MODEL", "small")
    # Require a local model: the original lazy downloader writes into CursorMain.
    if "--demo" not in sys.argv:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--speech-model")
        options, _ = parser.parse_known_args()
        if options.speech_model:
            model = options.speech_model
        if not (Path(model) / "model.bin").is_file():
            print("Instalează modelul: python -m jarvis.stt_setup download --model small")
            return 1
        os.environ["JARVIS_SPEECH_MODEL"] = str(Path(model).resolve())
    sys.dont_write_bytecode = True
    source = ROOT / "CursorMain" / "workingVersion4.py"
    sys.path.insert(0, str(source.parent))
    runpy.run_path(str(source), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
