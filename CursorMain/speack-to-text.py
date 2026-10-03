import sounddevice as sd
from faster_whisper import WhisperModel

import time

SAMPLE_RATE = 16000
RECORD_SECONDS = 5


def main():
    print("Se încarcă modelul...")

    model = WhisperModel(
        "large-v3",
        device="cpu",
        compute_type="int8",
    )

    while True:
        command = input("\nEnter pentru înregistrare sau exit: ").strip()

        if command.lower() == "exit":
            break

        print(f"Vorbește acum! Înregistrez {RECORD_SECONDS} secunde.")

        audio = sd.rec(
            frames=RECORD_SECONDS * SAMPLE_RATE,
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )
        sd.wait()

        print("Transcriu...")

        segments, info = model.transcribe(
            audio[:, 0],
            language="ro",
            task="transcribe",
            beam_size=5,
            temperature=0.0,
        )

        text = " ".join(segment.text.strip() for segment in segments)
        print("Ai spus:", text)


if __name__ == "__main__":
    main()