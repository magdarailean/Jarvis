# ION REVIEW

Reviewed merge `6ca704b` on 2026-10-04. The repository has no `Ion` directory: the merged implementation is `CursorMain`. That entire directory was treated as read-only. No owner files were edited, renamed, moved, reformatted or fixed; the adapter disables bytecode writes while importing it.

## Reusable public behavior

`workingVersion1.py` has import-safe definitions guarded by `if __name__ == "__main__"`:

- `record_voice()` calls `sd.rec(frames=10 * 16000, samplerate=16000, channels=1, dtype="float32")`, blocks in `sd.wait()`, and returns mono NumPy audio.
- `transcribe_voice(model, audio)` calls the supplied model with Romanian language, transcription task, beam size 5 and temperature 0, consumes its segment generator, and returns joined text.
- `main()` creates the Gemini client and a `large-v3` CPU/int8 Whisper model, captures the primary monitor, records, transcribes and calls Gemini. Jarvis never calls this function, `load_api_key()`, or Ion's capture function.
- `speack-to-text.py` is a separate five-second console loop; its only callable entry point is `main()`. It is not used by the adapter.
- `test.py` exposes a PyQt6 `Companion` with cursor following and `point_at(x, y)` animation. It is not imported into the PySide6 application.
- `main.py` and `takeScreenShot.py` execute interactive/network or screenshot-file behavior at import time. Neither is imported.
- Owner requirements: `google-genai`, `faster-whisper`, `sounddevice`, `mss`, `PyQt6`, all unpinned. The voice integration installs the first four as optional dependencies because `workingVersion1.py` imports them. PyQt6 is not required or installed by Jarvis.

## 1. Fixed-duration recorder has no start/stop handle

- Issue: `record_voice()` owns a fixed ten-second recording and only returns after `sd.wait()`.
- Why it may be a problem: push-to-talk needs release-driven stop and exact recorded sample length. Early `sounddevice.stop()` leaves the allocated buffer longer than the utterance.
- Severity: High for integration.
- Suggested change for the owner: expose start/stop/cancel operations with a returned recording handle and actual sample count. Keep transcription separately callable.
- Current outside-folder adaptation: a subprocess-local sounddevice proxy forwards Ion's `rec`/`wait`, stops on release, and trims the unused tail using elapsed time. This is approximate, not sample-accurate. Ion's ten-second maximum is preserved; reaching it automatically stops/transcribes even if the shortcut remains held.

## 2. Large model initialization and recognition are blocking

- Issue: the selected `large-v3` CPU/int8 model is constructed synchronously, with no owner-exposed readiness, timeout or cancellation API.
- Why it may be a problem: cold download/loading and inference may take substantial time and memory; placing it on the UI thread would freeze the assistant. Romanian accuracy and latency are not yet measured here.
- Severity: High for responsiveness/deployment.
- Suggested change for the owner: expose model configuration/readiness and documented cancellation/timeout behavior, and measure the chosen model on the target machine.
- Current outside-folder adaptation: isolated process, local-files-only model loading, 120-second initialization/transcription limits and process termination on active cancellation/End Session/exit. No automatic model download. `JARVIS_ION_MODEL` accepts a local CTranslate2 model directory or cached model name.

## 3. Voice helpers share imports with AI and capture

- Issue: importing the reusable functions also imports `google.genai` and `mss`.
- Why it may be a problem: voice-only integration must install unrelated packages; dependency failures can prevent speech setup even though AI/capture functions are unused.
- Severity: Medium.
- Suggested change for the owner: publish a side-effect-free STT module with only the audio/transcription dependencies and a documented API. Keep the demo orchestration separate.

## 4. Cursor Qt binding differs from Jarvis

- Issue: `test.py` uses PyQt6; Jarvis uses PySide6.
- Why it may be a problem: mixing bindings and application/event-loop ownership in one process is not a supported integration boundary for this project.
- Severity: Medium; blocks direct cursor embedding, not the voice pipeline.
- Suggested change for the owner: agree on a PySide6 public cursor widget/service or a separate-process interface. No cursor code was ported or replaced here.

## 5. Some scripts perform actions during import

- Issue: `main.py` loads credentials and enters a Gemini console loop at module scope; `takeScreenShot.py` prompts and saves a screenshot at module scope.
- Why it may be a problem: accidental imports can block startup, contact AI or persist screenshots outside Jarvis's explicit activation flow.
- Severity: Medium.
- Suggested change for the owner: guard executable/demo behavior with a main entry point and keep reusable definitions import-safe.

## 6. Owner code is not packaged with the Jarvis wheel

- Issue: `CursorMain` is outside the configured `src/jarvis` package and has no published package API.
- Why it may be a problem: a standalone wheel install does not include the owner module. Editable repository checkout works; deployment needs a source path or owner package.
- Severity: Medium for distribution.
- Suggested change for the owner: define a stable distributable package/module and dependency versions. Until then set `JARVIS_ION_SOURCE` to the absolute `workingVersion1.py` path when outside this checkout.
