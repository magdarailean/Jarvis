"""Explicit model installation and microphone diagnostics outside Ion."""
import argparse
from pathlib import Path

from jarvis.local_config import ROOT, configure_console, load_local_config, speech_model


def main():
    configure_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("download", "check", "test"))
    parser.add_argument("--model", choices=("small", "large-v3"), default="large-v3")
    parser.add_argument("--device", type=int)
    args = parser.parse_args()
    load_local_config()
    try:
        if args.action == "download":
            from faster_whisper.utils import download_model
            target = ROOT / "models" / "stt" / args.model
            download_model(args.model, output_dir=str(target))
            print(f"Model instalat: {target}")
            return 0
        import sounddevice as sd
        import ctranslate2
        from faster_whisper import WhisperModel
        variable = "JARVIS_SPEECH_MODEL" if args.model == "small" else "JARVIS_ION_MODEL"
        model = speech_model(variable, args.model)
        print(sd.query_devices())
        sd.check_input_settings(device=args.device, samplerate=16000, channels=1, dtype="float32")
        print("Microfon compatibil cu 16 kHz, mono. Verific modelul local...")
        recognizer = WhisperModel(model, device="cpu", compute_type="int8", local_files_only=True)
        print("Model local disponibil. Nu s-a înregistrat audio.")
        if args.action == "test":
            print("Ascult 5 secunde. Spune o propoziție în română...")
            audio = sd.rec(80000, samplerate=16000, channels=1, dtype="float32", device=args.device)
            sd.wait()
            segments, _ = recognizer.transcribe(audio[:, 0], language="ro", task="transcribe")
            print("Transcriere: " + " ".join(segment.text.strip() for segment in segments))
        return 0
    except Exception as error:
        print(f"Configurarea STT a eșuat ({type(error).__name__}). Verifică dependențele, modelul local și permisiunea microfonului.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
