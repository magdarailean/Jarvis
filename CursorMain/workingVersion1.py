import base64
import time
from pathlib import Path

import mss
import mss.tools
import sounddevice as sd
from faster_whisper import WhisperModel
from google import genai

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_RATE = 16000
RECORD_SECONDS = 10


def load_api_key():
    key_file = BASE_DIR / "api key.txt"
    content = key_file.read_text(encoding="utf-8-sig").strip()

    name, separator, value = content.partition("=")
    key = value.strip()

    if len(key) >= 2 and key[0] == key[-1] and key[0] in ('"', "'"):
        key = key[1:-1].strip()

    if name.strip() != "KEY" or not separator or not key:
        raise ValueError('Use KEY="your-api-key" in api key.txt')

    return key


def capture_screen():
    with mss.mss() as screen:
        image = screen.grab(screen.monitors[1])
        return mss.tools.to_png(image.rgb, image.size)


def record_voice():
    print(f"Speak now! Recording for {RECORD_SECONDS} seconds.")

    audio = sd.rec(
        frames=RECORD_SECONDS * SAMPLE_RATE,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()

    return audio[:, 0]


def transcribe_voice(model, audio):
    segments, _ = model.transcribe(
        audio,
        language="ro",
        task="transcribe",
        beam_size=5,
        temperature=0.0,
    )

    return " ".join(segment.text.strip() for segment in segments)


def main():
    client = genai.Client(api_key=load_api_key())

    print("Loading speech recognition model...")
    speech_model = WhisperModel(
        "large-v3",
        device="cpu",
        compute_type="int8",
    )

    previous_interaction_id = None

    while True:
        command = input("\nEnter to start, or type exit: ").strip()

        if command.lower() == "exit":
            break

        try:
            print("Select your target window. Starting in 3 seconds...")
            time.sleep(3)

            # Capture before recording and before slow transcription.
            screenshot_bytes = capture_screen()
            audio = record_voice()

            print("Transcribing...")
            text = transcribe_voice(speech_model, audio)
            print("You said:", text)

            if not text:
                print("No speech recognized. Please try again.")
                continue

            print("Sending your text and screenshot to Gemini...")

            interaction = client.interactions.create(
                model="gemini-3.8-flash",
                input=[
                    {
                        "type": "text",
                        "text": (
                            "Answer the user's request using the attached "
                            "screenshot as context. Reply in Romanian.\n\n"
                            f"User request: {text}"
                        ),
                    },
                    {
                        "type": "image",
                        "mime_type": "image/png",
                        "data": base64.b64encode(
                            screenshot_bytes
                        ).decode("utf-8"),
                    },
                ],
                previous_interaction_id=previous_interaction_id,
            )

            print("\nGemini:", interaction.output_text)
            previous_interaction_id = interaction.id

        except Exception as error:
            print("Error:", error)


if __name__ == "__main__":
    main()
