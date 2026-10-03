# Architecture

## Selected stack

Python 3.12+ (64-bit), PySide6 / Qt Widgets, Windows 10/11. Qt supplies the desktop window, native tray, accessibility, DPI scaling and future transparent overlays. Only `PySide6-Essentials` 6.11.2 and matching `shiboken6` are required, isolated in `.venv`. No Qt Addons, browser runtime, server, database or .NET dependency. [Qt setup](https://doc.qt.io/qtforpython-6/gettingstarted.html).

The shell was migrated to Python in milestone 1. Part 2 adds the overlay without restructuring that shell. Close-to-tray behavior, explicit exit, duplicate activation, privacy and diagnostic path are preserved. Qt manages DPI and session-ending integration; no custom executable manifest is required for this Python launch path.

## Boundaries

- `src/jarvis/app.py`: composition root and desktop lifecycle. Owns the Qt application/event loop; connects presentation signals to actions.
- `presentation/main_window.py`: Romanian widgets, wrapping/scrolling layout, hide/exit signals. No Windows or AI calls.
- `infrastructure/tray.py`: native Qt tray adapter and generated J icon.
- `infrastructure/single_instance.py`: Windows mutex/events via standard-library ctypes, with explicit handle ownership and a blocking notification worker.
- `infrastructure/app_log.py`: best-effort bounded lifecycle diagnostics.
- `tests/`: standard-library unittest, real Qt widgets/event loop and child processes. QtTest drives application widgets directly, without a desktop-control helper.

New independent functionality lives in `features/<feature>/`. Keep domain models and service contracts independent of Qt, Windows and concrete providers; introduce layers only where needed. Sessions will remain in memory; add settings persistence only when needed. No database. Speech-to-Text is owned by a teammate and must be integrated through their public interface later, not implemented or redesigned here.

## Screen overlay (Part 2)

- `features/overlay/model.py`: immutable validated `Annotation`, `Shape` enum and bounded `AnnotationScene`. IDs are stable; upsert replaces by ID and preserves insertion order. The scene supports visibility, highlight, idempotent removal and clear. Missing IDs for highlight/visibility raise `KeyError`. Up to 64 annotations and 200 characters per label; invalid input is rejected before mutation.
- Coordinates are normalized [0, 1] relative to one monitor. Rectangles/ellipses/labels use left/top/right/bottom; arrows/lines use start/end, including reversed endpoints. A numbered step is plain label text. The model has no Qt dependency or persistence.
- `features/overlay/window.py`: GUI-thread-only adapter exposing `upsert`, `set_visible`, `highlight`, `remove`, `clear` and immutable `annotations` snapshots. It owns its scene and repaints on changes. A frameless topmost tool window uses translucent painting, native input transparency and no-focus flags. No timers, hooks or screen capture.
- One window targets one `QScreen`. Map normalized positions into its local logical width/height, placing the window at the screen's geometry (including negative origins). Qt handles DPI; do not multiply painter coordinates by DPR. See [Qt high-DPI coordinates](https://doc.qt.io/qtforpython-6/overviews/qtdoc-highdpi.html). Screenshot pixel/monitor mapping is supplied by `screen_capture.ScreenGeometry`.
- Geometry/DPI changes clear marks. Monitor removal invalidates the overlay; create a new one before adding marks. Underlying window/content changes are not detected yet. Labels wrap inside their bounds and may clip if the caller supplies insufficient space; general text layout is future work.
- `features/overlay/demo.py` contains only static sample annotations. The composition root owns demo/clear/shutdown and logs events without text/geometry. Display failures produce Romanian feedback and leave the shell usable. The main window emits intent signals and has no renderer logic.

Shared production files changed in Part 2: `app.py` and `presentation/main_window.py`. Other changes are the isolated feature, focused tests, and project documentation. No dependencies added; no STT code touched.

## One-shot screen capture (Part 3)

- `features/screen_capture/model.py`: immutable `ScreenFrame` (unique ID, UTC timestamp, PNG bytes omitted from repr) and `ScreenGeometry` (monitor name, logical desktop bounds, actual image dimensions and DPR). No Qt imports. `pixel_to_normalized` maps actual image-edge coordinates to the overlay's [0, 1] space; `normalized_to_desktop` adds the monitor's logical origin. Actual image dimensions avoid fractional-DPI rounding drift. These helpers apply to the original image; a later AI adapter must account for resizing/cropping if introduced.
- `qt_capture.py`: GUI-thread `capture_screen(QScreen)` performs a single `grabWindow(0)` and encodes the returned pixmap into a memory-only PNG with `QBuffer`. Checks null images and a 40-million-pixel limit. Capturing one target screen avoids assuming that logical monitor positions form a contiguous desktop. See [QScreen capture and high-DPI semantics](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QScreen.html).
- `session.py`: `CaptureSession` owns one frame and a single-shot activation timer. `begin(screen, delay_ms=3000)` freezes the target, clears previous context, rejects duplicate pending requests, and schedules one call. The injectable capture callable allows synthetic tests without desktop access. Signals report frame replacement/release, completion/cancellation and sanitized failure type. `clear()` stops pending work, disconnects monitor signals and drops the frame. All operations run on the GUI thread; there is no idle polling or continuous monitoring.
- Target geometry/DPI changes or removal cancel pending work and release stored context. A geometry/DPR signature is checked immediately before and after acquisition. Content changes and scrolling are not detected. The stored image is explicitly a snapshot, not a live view.
- Composition hides the shell and overlay during the delay, restoring them on completion/failure/cancellation. Reopen cancels a pending capture; shutdown cancels without restoring windows. Overlay annotations remain intact during ordinary capture. Display invalidation still clears them using their existing behavior. No general session/end-session feature is added yet.
- The shell displays a reduced preview and release button. UI status and tray tooltip describe pending capture/error/ready. Clearing/replacing/shutdown releases both original context and preview. No files, external services, screenshots in logs, STT or new dependencies.

Shared production files changed in Part 3: `app.py`, `presentation/main_window.py`, and `infrastructure/tray.py` (status setter only). The overlay package is unchanged. Automated tests use synthetic image data; actual capture and compositor exclusion timing remain manual Windows review checks.

## Current lifecycle

Launch -> per-user/per-login-session mutex -> native tray + Romanian window -> Ascunde/X hides -> tray double-click / Deschide Jarvis / duplicate launch reopens -> Ieșire disposes resources and quits.

The same `Local\Jarvis.<Windows SID>.Instance` mutex and `.Activate` auto-reset event as the old C# app are retained. Secondary processes signal and exit before creating UI. A worker blocks on activation/stop handles without polling and emits a queued Qt signal; the main thread performs all UI changes. Shutdown wakes/joins the worker before closing handles. Mutex acquire/release stays on the main thread. Late activation cannot reopen a closed controller, and Windows releases ownership on process death. Session-ending requests trigger clean exit.

Without a successfully initialized tray, hiding stays disabled, a Romanian message is shown, and X requests exit. Qt handles normal tray integration; Explorer restart and actual Windows session-ending still need release verification.

Lifecycle events and error types go to `%LOCALAPPDATA%\Jarvis\logs\application.log`, reset near 1 MiB. File errors cannot block the UI. No prompts, screenshots, audio, credentials or conversation content are logged. Idle means no recording, captures or network activity. No automatic startup registration.

## Future pipeline (not implemented)

Hold Ctrl+Shift+Space -> interrupt speech -> listening indicator -> one relevant screen capture + bounded recording -> release -> Romanian STT -> session + screenshot + annotation snapshot -> local AI -> validated structured result -> persistent overlay actions + Romanian text/TTS.

First planned provider remains local Ollama + Gemma 3 4B via HTTP/JSON. The inspected machine has about 32 GB RAM and AMD 880M integrated graphics. CPU latency and Romanian/math quality require evaluation in milestone 5. Local inference avoids API charges and cloud screenshot uploads; do not add a second provider before the first works. [Model reference](https://ollama.com/library/gemma3).

Speech-to-Text implementation and library selection belong to the teammate. Use their interface or typed input during development. TTS remains a separate future feature; the earlier local Piper idea still needs license and Romanian voice-quality evaluation. No voice packages are installed here.

Annotation commands use stable IDs and normalized geometry. Validate operations, finite coordinates, IDs and limits independently of explanation text. Preserve annotations after speech, maintain multi-turn history, serialize/cancel turns and reject stale responses. Record monitor/DPI context and hide stale overlays under an explicit screen-change rule. AI gets no shell or clicking tools. No permanent screen/audio archive, accounts, telemetry or cloud database.
