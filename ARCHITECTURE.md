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

## Tutoring session and typed fallback (Part 4)

- `features/session/model.py` is framework-independent and performs no I/O. `Session` owns a session identity, selected `AssistantMode`, bounded completed turns, latest screen reference and at most one pending `TutorRequest`. Request snapshots include the question, mode, successful history, current image and immutable annotations. Old turns retain only a frame ID, never old screenshot bytes.
- `begin` validates the question/annotation snapshot and returns a unique request ID. `complete` accepts bounded explanation text only for that pending ID. `fail` records a local service notice separately from an assistant explanation. Failed turns remain visible for review but are omitted from future AI context. Duplicate/late completions return false; replacing/releasing a frame or ending a session invalidates the pending request.
- Retain at most 12 whole turns and 96,000 total text characters, evicting oldest whole turns. Question length is capped at 2,000, explanations at 12,000 and service notices at 500 characters. This is a deterministic text budget, not a model-specific token budget; provider integration will need its own context limit.
- `features/session/panel.py` owns only typed UI, mode selection and plain-text conversation rendering. No Markdown/HTML execution, network access or microphone code. Domain state is composed in `app.py`; provider-unavailable submissions are explicitly local failures. There is no placeholder AI that produces fake explanations.
- Capture changes update the session's latest image reference. Submission snapshots overlay annotations only when their logical monitor bounds match the captured context. Mode changes affect future submissions, not previous turns. The mode selector expresses intent until a real provider is connected.
- End Session resets session identity/history/mode, clears draft/UI, cancels pending capture and releases capture/preview/overlay state. Exit does the same without reopening the shell. Hide/reopen retains the session. Clearing only the capture releases its image while retaining textual conversation history.
- These are state/model guarantees, not transport cancellation: no provider or worker exists yet. A future adapter must perform I/O off the UI thread, cancel/timeout work and discard results rejected by the request identity check; it must also release its own request snapshots.

Shared production files changed in Part 4: `app.py` and `presentation/main_window.py`. New files are confined to `features/session`, its tests and documentation. No STT, capture or overlay implementation changes and no added dependencies.

## Background push-to-talk and Ion integration (Part 5)

The normal entry point now starts in the tray (`--window` opens diagnostics). `DesktopController` keeps explicit opt-in flags for integration tests so old tests do not register global keys or initialize speech. The existing typed/capture/demo controls remain diagnostic paths, not required user actions.

- `features/hotkey/windows.py` registers `Ctrl+Shift+Space` with Win32 `RegisterHotKey` and `MOD_NOREPEAT`. Qt's native event filter receives `WM_HOTKEY`; a 15 ms key-state timer exists only during a hold and emits release when any chord key is up. Shortcut parsing/registration is independent of STT. Conflicts fail visibly; shutdown unregisters.
- `features/voice_input/ion_worker.py` is an external adapter, not a recognizer. It imports only `CursorMain/workingVersion1.py` without running `main()` or writing bytecode in that directory, constructs Ion's imported Whisper model (CPU/int8, local files only), and invokes Ion's `record_voice()`/`transcribe_voice()`. A subprocess-local sounddevice proxy adds early stop; it does not replace Ion's recording/recognition algorithm. Elapsed-time trimming removes most of the fixed buffer's unused tail; exact sample count needs an owner API change. Ion's existing ten-second limit remains.
- `ion_adapter.py` manages a persistent `QProcess`, newline-delimited JSON events and bounded messages. Model load and transcription happen outside Qt's UI process. Startup/transcription timeouts are 120 seconds; device/start/recording watchdog is 15 seconds. Recording is requested only by activation; model warmup never starts the microphone. Release sends stop; cancellation/End Session/exit can terminate the process to stop even blocked work and release audio buffers. After termination, a subsequent press warms the worker; the user must wait for readiness and press again. No credentials are read and no AI client is instantiated.
- `features/interaction/controller.py` serializes activation, actual listening, one-shot capture, release, transcription and prepared context. Generation tokens reject late/duplicate voice messages. Presses during active work are ignored. Silence, missing devices/model/dependencies, capture failures, monitor invalidation and timeouts produce Romanian feedback and discard partial context. Capture and transcript completion can arrive in either order.
- `desktop.py` selects the foreground HWND's monitor by native monitor device name matched to Qt's screen list; cursor monitor/primary is a fallback. This avoids treating Windows physical virtual-desktop coordinates as Qt logical coordinates. Its small input-transparent/no-focus status label and the tray show listening/processing/readiness without reopening the main window.
- Capture reuses `CaptureSession` with an 80 ms compositor delay after hiding Jarvis's visible surfaces. The snapshot is acquired once on actual microphone start. The main window remains hidden; annotations return after capture and the indicator reflects the latest phase. Physical compositor timing and mixed-DPI capture still need manual verification.
- The AI boundary is `InteractionController.prepared(TutorRequest)` and `interaction.context`. It contains text, selected mode, bounded successful history, immutable current annotations, PNG image and monitor geometry. `Session.pending` owns the same request identity; a future AI consumer must honor it. No provider exists or is called. A subsequent activation records an explicit local prepared-without-AI notice for the previous turn, then replaces its context. Diagnostic rendering distinguishes pending preparation from AI answers.
- End Session clears conversation/draft, both capture owners/previews, overlay and Ion worker/audio buffers. Hide/reopen preserves completed context, but opening diagnostics during an active voice operation cancels it. A display change invalidates visual context. The latest prepared context is memory-only and bounded to one image/request.

The owner merge is `6ca704b`, with files under `CursorMain` rather than a literal `Ion` package. Treat that entire folder as read-only. Its PyQt6 cursor, interactive Gemini loop, screenshot-to-disk script and all other demos are not run. See [ION_REVIEW.md](ION_REVIEW.md) for exact APIs, dependencies and required owner changes. `.[voice]` contains imports required by the owner module, including currently unused Google/mss imports; PyQt6 is intentionally excluded. The wheel does not bundle the owner folder; external installs need `JARVIS_ION_SOURCE`.

Shared changes in Part 5: `app.py`, `presentation/main_window.py`, `infrastructure/tray.py` (truthful microphone status), `features/session/panel.py` (pending request display), `pyproject.toml` (optional voice dependencies), and docs. New feature packages/tests are isolated. No files in `CursorMain` were modified. All automated audio/transcription tests are synthetic; live recognition remains unverified without a local model.

## Shell lifecycle

Launch -> per-user/per-login-session mutex -> native tray, global activation and voice warmup -> background operation. Tray double-click / Deschide Jarvis / duplicate launch opens diagnostics; Ascunde/X hides; Ieșire disposes resources and quits. Without a tray the diagnostic window stays visible. `--window` requests it explicitly.

The same `Local\Jarvis.<Windows SID>.Instance` mutex and `.Activate` auto-reset event as the old C# app are retained. Secondary processes signal and exit before creating UI. A worker blocks on activation/stop handles without polling and emits a queued Qt signal; the main thread performs all UI changes. Shutdown wakes/joins the worker before closing handles. Mutex acquire/release stays on the main thread. Late activation cannot reopen a closed controller, and Windows releases ownership on process death. Session-ending requests trigger clean exit.

Without a successfully initialized tray, hiding stays disabled, a Romanian message is shown, and X requests exit. Qt handles normal tray integration; Explorer restart and actual Windows session-ending still need release verification.

Lifecycle events and error types go to `%LOCALAPPDATA%\Jarvis\logs\application.log`, reset near 1 MiB. File errors cannot block the UI. No prompts, screenshots, audio, credentials or conversation content are logged. Idle means no recording, captures or network activity. No automatic startup registration.

## Future pipeline (not implemented)

Hold Ctrl+Shift+Space -> interrupt speech -> listening indicator -> one relevant screen capture + bounded recording -> release -> Romanian STT -> session + screenshot + annotation snapshot -> local AI -> validated structured result -> persistent overlay actions + Romanian text/TTS.

First planned provider remains local Ollama + Gemma 3 4B via HTTP/JSON. Part 4 found no Ollama command on PATH or executable in its usual per-user installation location; no runtime/model was installed. The earlier hardware note recorded about 32 GB RAM and AMD 880M integrated graphics; verify runtime availability and performance before provider integration. Romanian/math quality remains unmeasured. [Model reference](https://ollama.com/library/gemma3).

Speech-to-Text implementation and library selection belong to the teammate. Use their interface or typed input during development. TTS remains a separate future feature; the earlier local Piper idea still needs license and Romanian voice-quality evaluation. No voice packages are installed here.

Annotation commands use stable IDs and normalized geometry. Validate operations, finite coordinates, IDs and limits independently of explanation text. Preserve annotations after speech, maintain multi-turn history, serialize/cancel turns and reject stale responses. Record monitor/DPI context and hide stale overlays under an explicit screen-change rule. AI gets no shell or clicking tools. No permanent screen/audio archive, accounts, telemetry or cloud database.
