# Current Milestone

Romanian spoken responses in the normal runtime on branch TTS. Existing user changes preserved; no commit created.

# Working

- Online edge-tts Romanian Alina synthesis and in-memory audio playback through a cancellable isolated worker.
- TTS reads exactly the final rendered callout text, in painting order for multiple callouts. No separate longer spoken answer. Existing bubble text selection is preserved.
- GUIDE keeps cursor instructions and routing. EXPLAIN keeps callouts/typewriter.
- Preparing/speaking/ready states; PTT interrupts speech without waiting and preserves conversation history.
- Spoken bubbles remain during synthesis/playback and expire five seconds after speech finishes or fails; typewriter timing is unchanged. Romanian Alina speaks at +10% rate. New PTT clears temporary callouts as before.
- Speech errors/timeouts retain answer and visuals. No Ion or CursorMain changes.

# Partially Working

- Physical hold/speak/release, human assessment of Romanian pronunciation and GUIDE cursor acceptance remain manual checks.
- TTS is online and depends on the Edge speech service being available.

# Not Implemented Yet

- Offline TTS and configurable voice selection.

# Known Issues

- Multiple spoken bubbles remain together until the combined utterance finishes, then expire together five seconds later.
- Existing single-callout selection may expand a bubble to the full explanation. Speech follows the resulting visible text exactly.
- Normal startup uses the existing voice-only background interface.

# How I Tested This Milestone

- 91 tests pass, including rendered text/order, callout capacity, no-callout AUTO responses, speech failure, PTT cancellation, stale subprocess events, GUIDE routing and speech-held lifetime and five-second completion/failure grace period.
- Live runtime check passed using the actual controller, STT readiness, OpenRouter with a generated equation image, production overlay and Romanian playback: bubble retained after speech, then removed at its new deadline. The observed total reading lifetime exceeded 32 seconds, confirming the old 15-second deadline no longer removes a spoken bubble.
- No private microphone recording or desktop upload during this automated live check. Full human voice flow remains manual.

# How You Can Test It

```powershell
cd C:\Users\Magda\Documents\GitHub\Jarvis
.\.venv\Scripts\python.exe -m pip install -e ".[voice,openrouter]"
.\.venv\Scripts\python.exe -m jarvis
```

Wait for Gata. Hold Ctrl+Shift+Space and ask for a short explanation of visible content; release. Compare speech with bubble text, observe typewriter and expiry five seconds after speech finishes. Interrupt a longer answer with PTT, then ask another question. Ask where to open something and verify existing cursor guidance. Speech failure must leave text/visuals intact; automated tests simulate this failure.

# Required Configuration

Python 3.12 Windows environment with existing voice/openrouter extras, local STT model, microphone permission, OpenRouter key and internet. edge-tts and PyQt6 are already declared in the openrouter extra. No additional TTS key, environment variable or model download.

# Next Milestone

Stop for manual testing and user commit. No further development until instructed.
