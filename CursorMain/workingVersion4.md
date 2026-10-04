# OpenRouter desktop guide

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe .\CursorMain\workingVersion4.py
```

Dependencies: `python -m pip install -r CursorMain/requirements-workingVersion4.txt`.

The default model is `google/gemini-2.5-flash-lite`. Credentials come from
`OPENROUTER_API_KEY`, otherwise `CursorMain/apikeyOpenRouter.txt` with `KEY="..."`.
The local key file is ignored by Git and removed from the index. If a key was
previously committed, removing the file does not erase it from Git history:
revoke that key in OpenRouter and configure its replacement locally.

- **Ctrl+Space:** start a spoken command; press again to finish recording.
- **Ctrl+Alt+Space:** capture again and refresh the current task.
- **Escape:** cancel the task, hide its caption and stop speech.
- **Ctrl+Alt+Q:** quit.

Voice-input errors ask you to retry with Ctrl+Space. Ctrl+Alt+Space also restarts
voice input when an error occurred before any command was transcribed; once a
command exists, it refreshes the screenshot for that task.

The app captures a new image after transcription, then requests one step. Images
sent to OpenRouter are JPEGs with a maximum dimension of 1280 pixels; smaller
images are not enlarged. Coordinates remain normalized and are mapped back to
the monitor for pointing and click verification.

The blue companion pointer moves to the target, with a short click-through
caption nearby. The user controls the real mouse. A click on the target triggers
a new screenshot to verify the result before moving to the next step.
The screenshot is taken after a 2.5-second pause following the click (plus the
brief overlay-hide delay). Further clicks during this pause restart it so the
next page has time to load. Once the original goal is visibly complete, the
session ends and no further clicks or refreshes continue that task.

A click during capture or AI analysis invalidates the old capture and its
responses. The task and pending click verification are preserved, and a new
capture follows the same 2.5-second quiet interval. Clicking outside the target,
including on another monitor, also requests a fresh capture. Queued clicks from
before the current capture started do not invalidate it.

The guide pauses instead of repeatedly recommending the same action on the same
page after two attempts, or alternating between two actions in a cycle. It
compares the instruction, expected effect, overlapping target and a hash of a
small screenshot; distinct steps such as Save Workspace, Create and Open may
reuse the same position. Page animation or reworded instructions can prevent a
match; the overall request limit remains in effect. This is a blocked state,
not a success claim: Escape dismisses it and Ctrl+Space starts a new command.

Invalid model JSON or target coordinates trigger at most one correction request,
using the same screenshot. This extra request consumes OpenRouter tokens only
when validation fails. The controller receives only the validated final answer;
two invalid answers pause the session with an explanation. Cancellation prevents
an in-flight answer from triggering a correction request. Network and
authentication errors are not automatically retried.

Romanian spoken explanations use Microsoft Edge's online TTS service, through
`edge-tts`, with `ro-RO-AlinaNeural`. Only explanation text is sent to that
service; generated audio stays in memory. Use `--mute` to disable speech or
`--tts-voice ro-RO-EmilNeural` for the alternative Romanian voice. Speech failures
leave the pointer and caption available. New steps and cancellation interrupt
old speech; refreshing the same unchanged step does not repeat it.

Optional active-window capture:

```powershell
.\.venv\Scripts\python.exe .\CursorMain\workingVersion4.py --capture-mode window
```

This crops the selected monitor's screenshot to the visible foreground window
frame. It falls back to the full monitor when no suitable frame is available.
The default `--capture-mode screen` keeps menus and the surrounding desktop in
view. Cropped coordinates are converted back to monitor coordinates.

`--demo` simulates voice input and two steps without a microphone, OpenRouter or
TTS calls. Tests use mocked HTTP and simulated images:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s CursorMain -p test_workingVersion4.py -v
```
