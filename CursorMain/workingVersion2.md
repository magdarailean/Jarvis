# workingVersion2 — voice companion

Windows prototype with **only a small transparent companion**. There is no
panel, transcript, history window, target rectangle, tray menu, or spoken reply.
The original prototypes remain unchanged. All new source/cache files live in
`CursorMain`.

## Start without a console

From the repository root, using the environment with the required packages:

```powershell
.venv\Scripts\pythonw.exe CursorMain\workingVersion2.pyw
```

For console diagnostics, first close any running companion with **Ctrl + Shift + Q**,
then start this process using **python.exe**, which has a console:

```powershell
.venv\Scripts\python.exe -u CursorMain\workingVersion2.py --debug
```

This prints capture dimensions/scaling, click matches, step transitions, AI
decisions and blocked reasons, request duration, and sanitized exception details
with HTTP status when available. `--debug` adds stack filenames/functions/line
numbers without source lines or local variables. Logs flush immediately; no log
file is created. `pythonw.exe` keeps console diagnostics invisible.

After clicking File in VS Code, look for **click.accepted → capture.ready →
ai.request.start → ai.decision**. If you see `click.outside_target`, the click did
not match the AI rectangle. `ai.blocked` includes the AI's explanation; it differs
from `ai.request.error` (SDK/network/response-validation failure). A validated
next step produces `step.verification` and `target.armed`.

Audio, screenshots, raw response JSON and recognized speech are not printed.
The AI's step instruction and expected result are printed for diagnosis, with the
full original spoken request and API credentials redacted if repeated.

Dependencies are listed in `requirements-workingVersion2.txt`. They were already
available in the existing `.venv` when this version was implemented; no environment
outside CursorMain was modified for this update.

Use the existing `CursorMain/api key.txt` with `KEY="..."`, or `GEMINI_API_KEY`.
The Gemini model defaults to `gemini-3.8-flash` (`--model` or `GEMINI_MODEL` to
change it). Screenshots and the in-memory goal/history are sent only in real mode.
No audio or transcript files are written, and recognized words are not printed.

## Interaction

- **Idle:** a blue companion follows just below/right of the real mouse. It stays
  inside the screen near its edges and does not take focus or intercept clicks.
- **Ctrl + Space:** starts a new voice request. The monitor under the mouse is
  selected automatically; a screenshot is taken with the companion hidden.
- **Blue microphone:** the input stream is open. Speak your request once.
  Recording ends after approximately 1.2 seconds of quiet after speech, or when
  you press Ctrl + Space again. No speech times out after 8 seconds; recordings
  are limited to 30 seconds. These are RMS thresholds, not semantic detection.
- **Spinner:** recording is stopped and the app is transcribing/analyzing. Qt
  animation remains separate from microphone work, Whisper and network waits.
- **Blue pointer at a target:** click the indicated control yourself. The actual
  mouse is never moved. A left-button release inside the invisible target region
  triggers a fresh screenshot after 900 ms and verification before the next step.
- **Amber dot:** a gentle reminder after 12 seconds without action. No extra
  API request is made for the reminder or for clicks outside the target.
- **Green check:** task complete; the in-memory goal/history are cleared and
  the companion returns to following the mouse.
- **Red indicator:** no speech, device/API error, unsupported action or blocked
  task. No error dialog appears. Start another voice request or retry below.
- **Esc:** cancel listening/guidance, clear the in-memory session and return to
  idle. Escape is also passed through to the active application.
- **Ctrl + Shift + Space:** refresh/retry the current screen without marking
  an unattempted action as completed. Use this if a target moved or the UI changed.
- **Ctrl + Shift + Q:** exit the companion.

Ctrl + Space is ignored while processing to avoid stacking requests. From an
idle, waiting or error state it starts a new voice goal. If shortcuts are already
reserved by another application, the companion briefly signals an error and exits.
There is no automatic cross-monitor guidance; start a new request on that monitor.
Screen geometry/DPI changes cancel active guidance instead of retaining old targets.

This version guides **clickable controls only**. Typing instructions, arbitrary
keyboard shortcuts and scrolling directions cannot be communicated with a pointer
alone, so the AI must return blocked for actions that need that extra information.
The AI may still misidentify a target or incorrectly verify a change.

## Speech model

Local Romanian speech recognition uses faster-whisper on CPU, with a reusable
`small` model and limited CPU threads. The first real voice request may download
that model into `CursorMain/models`; later requests reuse it. Use
`--speech-model large-v3` (or `JARVIS_SPEECH_MODEL`) for the older prototype's model;
that model is larger and generally slower on CPU. `--voice-threshold 0.01` adjusts
the microphone RMS threshold if quiet speech is missed or background noise prevents
endpoint detection. A second Ctrl + Space manually finishes recording.

Cancel invalidates results and stops recording; ongoing model loading/inference
and already sent API calls can finish in the background. Exit hides the companion
and releases active worker threads after they finish. API calls have a 45-second
timeout, and each goal is limited to 40 decisions. Screenshot acquisition briefly
runs on the GUI thread; PNG encoding is on the AI worker.

## Offline demo and checks

```powershell
.venv\Scripts\pythonw.exe CursorMain\workingVersion2.pyw --demo
.venv\Scripts\python.exe -m unittest discover -s CursorMain -p "test_workingVersion2.py" -v
```

Demo uses the same Ctrl + Space interaction but simulates listening for 1.5
seconds and then shows two predefined targets. It does not open the microphone,
download a speech model, transcribe words or contact Gemini. Clicks pass through
to the underlying application, so test the demo over a harmless desktop/window.
The automated checks use fake audio and screenshots; they never record speech or
call an external API.
