# Jarvis

**Optional cursor accuracy adapter:** run `.\.venv\Scripts\python.exe -B -m jarvis.cursor_guide`
for the OpenRouter cursor prototype with separate target localization. See
[CURSOR_TARGETING.md](CURSOR_TARGETING.md) for calibration, costs and manual checks.
This is separate from the main shell described below.

A Windows desktop assistant and tutor for Romanian-speaking users, primarily in Moldova.

**Current state: Part 5, background push-to-talk through the AI boundary.** Hold **Ctrl+Shift+Space** in another application: Jarvis starts Ion's recorder and automatically captures that application's monitor once. Release to stop recording and transcribe Romanian speech. A prepared interaction contains the question, screenshot, session history, mode and annotations. **No AI provider is called or implemented.** Idle operation never records the microphone or screen.

## Prerequisites

- Windows 10/11 x64; tested on Windows 11 build 26200.
- Python **3.12 or newer, 64-bit** with pip/venv. Python 3.12 is the verified baseline. Use the Python launcher (`py`) or substitute your installed Python executable in the setup command.
- Internet access for dependency/model installation only. Voice requires a local faster-whisper model; no account, API key or AI backend is required for this pipeline.

No .NET SDK/runtime, Visual Studio, separate Qt installation, database or administrator privileges are required. The old C# solution has been removed.

## Install

In PowerShell at the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

This installs Jarvis in editable mode and the pinned `PySide6-Essentials==6.11.2` package (with matching `shiboken6`). No activation script or PowerShell execution-policy change is needed. Open this folder in your Python IDE and select `.venv\Scripts\python.exe` as its interpreter.

**On the current development machine, `.venv` has been recreated and installed.** You can run the commands below immediately. This environment uses the available Python 3.12.14 runtime; teammates should create their own environment with their installed Python. Do not commit or copy `.venv` between computers.
 
## Run

Normal launch stays in the tray, without opening the diagnostic window. **Deschide Jarvis** or a duplicate launch opens that window. Use `python -m jarvis --window` to open diagnostics immediately.

With a console for development:

```powershell
.\.venv\Scripts\python.exe -m jarvis
```

Without a console:

```powershell
.\.venv\Scripts\jarvis.exe
```

You may also double-click `.venv\Scripts\jarvis.exe` in File Explorer. It is a Python GUI launcher, not a standalone installer. Choose **Ieșire** before changing or reinstalling the app.

## Manual behavior check

1. Launch Jarvis, then choose **Deschide Jarvis** from the tray (or launch with `--window`). Check the title **Jarvis — Asistent și tutore** and the Romanian notices. Missing voice dependencies/model produce a visible error instead of recording.
2. Find the blue **J** beside the clock (possibly under the hidden-icons arrow). Its tooltip is **Jarvis — Gata · Microfon oprit**.
3. Click **Ascunde** or the window **X**. The window disappears but the application stays running.
4. Double-click J, or right-click it and choose **Deschide Jarvis**. The same window returns.
5. Hide the window and run Jarvis again from another PowerShell window or File Explorer. The original window returns; the second process exits. Repeat with the window minimized.
6. Resize down to the minimum size. Text wraps and scrolls; **Ascunde** and **Ieșire** remain visible. Use Tab to focus the buttons and Enter or Space to activate them.
7. Choose **Ieșire** from the window or tray. The window/icon and Python process exit. Relaunch and exit again to verify restart.

If the tray is unavailable or initialization fails, hiding is disabled, a Romanian explanation appears, and X exits. The app does not register itself to start with Windows. Single-instance scope is the current Windows user and login session, including compatibility with an already-running previous C# build.

## Voice setup and normal interaction (Part 5)

Ion's merged code lives in **CursorMain**, which is read-only. Read [ION_REVIEW.md](ION_REVIEW.md) for its API, dependencies and owner issues.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[voice]'
```

These optional dependencies are installed in this checkout's `.venv`. **The large-v3 model is not installed by that command.** Supply an existing local CTranslate2/faster-whisper model directory:

```powershell
$env:JARVIS_ION_MODEL = 'C:\path\to\faster-whisper-large-v3'
.\.venv\Scripts\python.exe -m jarvis
```

Without that setting, the adapter looks for an already cached `large-v3`, preserving Ion's model choice. Loading is local-files-only: Jarvis does not silently download a multi-gigabyte model. The model must include its tokenizer/configuration files. Startup warms the model without opening the microphone; wait for **Gata**. A missing model produces a Romanian error. Cold loading/CPU transcription has not been measured on this machine.

1. Work in Chrome, a PDF, Word or another desktop application.
2. Hold **Ctrl+Shift+Space** and wait for **Ascult...**. Jarvis records through Ion and captures the foreground application's monitor automatically. Jarvis's own window, status indicator and overlay are hidden briefly for that capture.
3. Speak Romanian, then release any key of the shortcut. The microphone stops; **Procesez...** appears while Ion transcribes.
4. **Context pregătit · AI neconectat** means the future-AI request is ready. No AI request is sent. The main window stays closed; optional diagnostics show the recognized text and preview.
5. Start another hold for a new turn. While transcription is running, additional presses are ignored; press again once processing finishes. Ion currently caps recording at ten seconds, after which it stops automatically.
6. Use the tray's **Încheie sesiunea** to discard conversation, image, annotations and worker audio buffers. Reopening the diagnostic window during recording/transcription cancels that active interaction. After cancellation/end, the next press restarts voice initialization; wait for **Gata**, then press again to speak.

Optional configuration, set before launch:

- `JARVIS_HOTKEY`: default `Ctrl+Shift+Space`; supports Ctrl/Alt/Shift plus Space, A–Z or F1–F24. Registration conflicts are reported. No idle keyboard polling; release checks run only while held.
- `JARVIS_ION_MODEL`: local model directory or already cached faster-whisper model name.
- `JARVIS_ION_SOURCE`: absolute path to Ion's `workingVersion1.py`; defaults to this checkout's `CursorMain/workingVersion1.py`. A standalone Jarvis wheel does not bundle the owner folder.

Model readiness, native microphone permissions/device selection, physical shortcut behavior in other applications, mixed-monitor capture and Romanian recognition quality require manual verification. Automated tests use fake audio/models/images; they also call Ion's real functions with those substitutes and exercise native hotkey registration/message dispatch.

## Diagnostic overlay review (Part 2)

1. Launch Jarvis and click **Arată demonstrația** (scroll down if needed). Static shapes, an arrow and Romanian labels appear on the monitor containing Jarvis. They do not describe the content underneath.
2. Click **Ascunde**, switch to another application, and click/type/scroll beneath both the shapes and labels. The overlay should stay visible without taking focus or blocking input.
3. Reopen Jarvis from its tray icon and click **Șterge adnotările**. All marks disappear. Repeating the demo replaces its previous overlay.
4. Move Jarvis to another monitor and show the demo again. Check alignment and readable labels at your usual Windows scaling. Changing display geometry/DPI or disconnecting the target monitor clears stale marks.
5. Choose **Ieșire** while marks are visible. Both Jarvis and the overlay should disappear.

The demo captures no screen/audio and sends no requests. Marks stay fixed when underlying content scrolls or changes; clear them yourself. This foundation targets ordinary desktop windows, not the Windows secure desktop or exclusive fullscreen applications. Physical click-through and mixed-monitor DPI behavior remain manual release checks.

## Diagnostic screen capture review (Part 3)

1. Place Jarvis on the monitor you want captured. Scroll to **Capturează peste 3 secunde** and click it. That monitor is selected at activation, even if the pointer moves elsewhere.
2. Jarvis and its overlay hide for three seconds. Switch to the desired application if needed. The tray tooltip reports the pending capture. Reopening Jarvis before the delay ends cancels it.
3. Jarvis returns with a reduced preview and the full image's pixel dimensions. The original PNG and monitor geometry remain only in memory. Nothing is sent to AI or saved to disk.
4. Change the underlying content: the preview must stay unchanged. Capture again to replace it, or click **Eliberează captura** to discard it and the preview.
5. Repeat while demo annotations are visible: they should be absent from the captured image and reappear afterward. Exit during the delay: no late capture or reopened window should occur.
6. If available, repeat on a second monitor and at fractional Windows scaling. A target-monitor geometry/DPI change or removal discards its stored image and cancels a pending capture.

The image includes everything visible on the selected monitor, including other applications and the taskbar. Capture does not follow scrolling, detect protected/black content, or guarantee secure-desktop/exclusive-fullscreen support. Captures are capped at 40 million pixels. Releasing an image drops application references; it is not a secure-memory erasure guarantee. This explicit button is a development activation path until push-to-talk is integrated.

## Diagnostic typed session review (Part 4)

1. Scroll to **Conversație · Introducere prin text**, select a mode, type a Romanian question, and press Enter or **Trimite întrebarea**. Blank questions show validation feedback without adding a turn.
2. The question appears with its mode and whether a capture was available. **Stare serviciu** explicitly says AI is not connected. No request is sent, no answer is fabricated, and the mode currently records intent only.
3. Hide/reopen Jarvis. The current conversation remains. Submit another question; at most 12 complete exchanges are retained (also bounded by total text size).
4. Optionally take a capture and show demo annotations. **Încheie sesiunea** clears the conversation, unsent draft, capture/preview, annotations and pending capture; it resets the assistance mode. You can start again without restarting Jarvis.
5. Exit/relaunch. No conversation or images should return. Session history is memory-only and question text is excluded from diagnostic logs.

This prepares follow-up context and reply identity checks for the future provider. Actual understanding of follow-up questions requires that provider; the current application cannot answer questions yet.

## Build and test

Python source needs no application compilation. Validate syntax, dependencies and lifecycle:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src/jarvis tests
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run tests on an unlocked Windows desktop. They briefly open real Qt windows/tray icons and test widget mouse/keyboard events, native tray action callbacks, duplicate child processes, shutdown/restart, simulated tray failure, abrupt child termination, logging failure and log size limits. Close an existing Jarvis first to include the installed-launcher test; other tests use unique instance names. Only test-created child processes are terminated. The suite uses standard-library `unittest` and QtTest, with no separate test framework.

Tests write app-only window renders to ignored `.artifacts/`. Capture tests use synthetic pixmaps and an injected capture adapter; they do not capture the desktop. Real screen acquisition, compositor timing, mixed-monitor alignment, physical taskbar tray clicks, Windows logoff and Explorer restart still require manual checks.

Build a distributable Python wheel (not a standalone Windows installer):

```powershell
.\.venv\Scripts\python.exe -m pip wheel . --no-deps --wheel-dir dist
```

The wheel is `dist\jarvis_desktop-0.1.0-py3-none-any.whl`. It contains Python source and declares Qt dependencies; Windows is still required because single-instance integration uses Windows APIs. The build backend downloads setuptools into an isolated build environment when needed.

## Configuration and diagnostics

The shell needs no configuration; optional voice settings are listed above. Windows' standard `LOCALAPPDATA` determines the diagnostic path:

```powershell
Get-Content "$env:LOCALAPPDATA\Jarvis\logs\application.log" -Tail 20
```

The same log location as before records startup, tray creation, hide/reopen, duplicate notification and shutdown. It resets near 1 MiB and contains no screenshots, audio, prompts, responses or credentials. Logging failures do not block operation. In Python, processes are named `python.exe`/`pythonw.exe` or the launcher; do not terminate unrelated Python processes when checking shutdown.

## Project structure

```text
src/jarvis/
  app.py                         # Composition and desktop lifetime
  presentation/main_window.py    # Romanian Qt widgets and UI signals
  features/overlay/              # Validated annotations, Qt renderer, static demo
  features/screen_capture/       # One-shot capture, memory ownership, coordinate mapping
  features/session/              # Bounded conversation state and typed fallback panel
  features/hotkey/               # Native global hold/release events
  features/voice_input/          # Outside-Ion subprocess and start/stop adapter
  features/interaction/          # Background orchestration, status, future-AI boundary
  infrastructure/
    single_instance.py          # Windows mutex/event boundary
    tray.py                     # Tray menu/icon adapter
    app_log.py                  # Bounded, best-effort logging
tests/                          # Real Windows/Qt integration + logging tests
pyproject.toml                  # Package, pinned dependency and GUI entry point
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for boundaries and [STATUS.md](STATUS.md) for verification and the roadmap. `.venv`, generated outputs and test renders are ignored. Deletions of C# source/build files in this migration are intentional; Python is now the only implementation.

Development stops after each milestone for manual review/commit. No automatic Git commits.
