# Architecture

## Selected stack

Python 3.12+ (64-bit), PySide6 / Qt Widgets, Windows 10/11. Qt supplies the desktop window, native tray, accessibility, DPI scaling and future transparent overlays. Only `PySide6-Essentials` 6.11.2 and matching `shiboken6` are required, isolated in `.venv`. No Qt Addons, browser runtime, server, database or .NET dependency. [Qt setup](https://doc.qt.io/qtforpython-6/gettingstarted.html).

This is a language migration of **milestone 1**, not a new feature milestone. Romanian copy, layout, close-to-tray behavior, explicit exit, duplicate activation, privacy and diagnostic path are preserved. C#/WPF source and build infrastructure are replaced rather than maintained as a second implementation. Qt manages DPI and session-ending integration; no custom executable manifest is required for this Python launch path.

## Boundaries

- `src/jarvis/app.py`: composition root and desktop lifecycle. Owns the Qt application/event loop; connects presentation signals to actions.
- `presentation/main_window.py`: Romanian widgets, wrapping/scrolling layout, hide/exit signals. No Windows or AI calls.
- `infrastructure/tray.py`: native Qt tray adapter and generated J icon.
- `infrastructure/single_instance.py`: Windows mutex/events via standard-library ctypes, with explicit handle ownership and a blocking notification worker.
- `infrastructure/app_log.py`: best-effort bounded lifecycle diagnostics.
- `tests/`: standard-library unittest, real Qt widgets/event loop and child processes. QtTest drives application widgets directly, without a desktop-control helper.

No empty layers. When tutoring state arrives in milestone 2, introduce framework-independent `domain` and `application` modules using Python dataclasses/enums and service protocols. Domain/Application must not import Qt, Windows or concrete providers. Future `AiProvider`, `SpeechRecognizer`, `SpeechSynthesizer` and `ScreenCapture` ports belong to Application; Infrastructure implements them. Sessions remain in memory; add settings persistence only when needed. No database.

## Current lifecycle

Launch -> per-user/per-login-session mutex -> native tray + Romanian window -> Ascunde/X hides -> tray double-click / Deschide Jarvis / duplicate launch reopens -> Ieșire disposes resources and quits.

The same `Local\Jarvis.<Windows SID>.Instance` mutex and `.Activate` auto-reset event as the old C# app are retained. Secondary processes signal and exit before creating UI. A worker blocks on activation/stop handles without polling and emits a queued Qt signal; the main thread performs all UI changes. Shutdown wakes/joins the worker before closing handles. Mutex acquire/release stays on the main thread. Late activation cannot reopen a closed controller, and Windows releases ownership on process death. Session-ending requests trigger clean exit.

Without a successfully initialized tray, hiding stays disabled, a Romanian message is shown, and X requests exit. Qt handles normal tray integration; Explorer restart and actual Windows session-ending still need release verification.

Lifecycle events and error types go to `%LOCALAPPDATA%\Jarvis\logs\application.log`, reset near 1 MiB. File errors cannot block the UI. No prompts, screenshots, audio, credentials or conversation content are logged. Idle means no recording, captures or network activity. No automatic startup registration.

## Future pipeline (not implemented)

Hold Ctrl+Shift+Space -> interrupt speech -> listening indicator -> one relevant screen capture + bounded recording -> release -> Romanian STT -> session + screenshot + annotation snapshot -> local AI -> validated structured result -> persistent overlay actions + Romanian text/TTS.

First planned provider remains local Ollama + Gemma 3 4B via HTTP/JSON. The inspected machine has about 32 GB RAM and AMD 880M integrated graphics. CPU latency and Romanian/math quality require evaluation in milestone 5. Local inference avoids API charges and cloud screenshot uploads; do not add a second provider before the first works. [Model reference](https://ollama.com/library/gemma3).

Python voice plan: local multilingual Whisper through `faster-whisper`, QtMultimedia or a focused audio adapter for capture/playback, and local Piper Romanian TTS. These replace the C#-specific Whisper.net/NAudio plan; none is installed or implemented yet. Verify engine/model licenses and Romanian quality before bundling. Typed input/text output remain fallbacks.

Annotation commands use stable IDs and normalized geometry. Validate operations, finite coordinates, IDs and limits independently of explanation text. Preserve annotations after speech, maintain multi-turn history, serialize/cancel turns and reject stale responses. Record monitor/DPI context and hide stale overlays under an explicit screen-change rule. AI gets no shell or clicking tools. No permanent screen/audio archive, accounts, telemetry or cloud database.
