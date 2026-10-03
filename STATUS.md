# Current Part

**Part 3 — One-shot screen capture.** Ready for manual desktop review and commit. Development stops here until the user writes `continue`. No commits created.

Started from clean commit `b2f21ad` (overlay). Speech-to-Text remains owned by the teammate and untouched.

# Working

- Existing Python/PySide6 shell, tray/background lifecycle, single instance and persistent annotation overlay.
- Isolated `features/screen_capture` package: memory-only PNG, unique frame ID, timestamp, monitor bounds, logical/pixel dimensions and DPI ratio.
- Explicit **Capturează peste 3 secunde** activation; the target is the monitor containing Jarvis when pressed. No idle capture or microphone/network activity.
- Shell and annotations hide during the delay, then return with a reduced preview. Annotation contents are preserved. Reopening Jarvis while waiting cancels acquisition.
- Exactly one owned frame. A new request releases the old image; **Eliberează captura**, display geometry/DPI changes, monitor removal and exit release image/preview references.
- Pixel-to-normalized and normalized-to-logical-desktop mapping, including negative monitor origins and fractional DPI.
- Romanian failure feedback, tray/UI state and metadata-free capture event logging. Errors restore the shell, including when the tray is unavailable.
- Capture size bounded to 40 million pixels. No new dependencies.

# Validation

- Full Windows/Qt suite: **21 tests passed** (14 existing + 7 capture tests), no skips.
- Synthetic pixmap encoding/decoding and actual pixel dimensions; invalid/oversized captures; fractional-DPI/negative-origin mapping.
- No idle/repeated acquisition, pending request rejection, replacement, release, cancellation and simulated display invalidation/removal.
- Shell/overlay hidden at the adapter call; restoration, preview release, shutdown cancellation, sanitized errors and retry with no tray.
- Syntax compilation, `pip check` and `git diff --check` pass.
- App-only shell render visually reviewed. Tests use synthetic images and never capture the desktop.

# Manual Review

```powershell
.\.venv\Scripts\python.exe -m jarvis
```

Scroll to **Capturează peste 3 secunde**, click, and switch to the application to capture. Jarvis should return with a preview and original pixel dimensions. Check the preview excludes Jarvis/annotations. Clear with **Eliberează captura**. Repeat with the overlay visible, try canceling by reopening from the tray, and exit while waiting. README contains full steps and mixed-monitor checks.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Close existing Jarvis before testing the installed launcher. Tests briefly open native windows/tray icons.

# Limits / Not Implemented

- Real Windows screen acquisition, compositor timing when hiding Jarvis, protected content, and mixed-monitor/DPI alignment require manual verification. Automated capture tests inject synthetic data.
- Screen images and annotations do not follow underlying scrolling/content changes. Clear or capture again. No secure-desktop/exclusive-fullscreen guarantee or protected/black-image detection.
- Only one selected monitor per capture. No foreground-window detection or image resizing for an AI provider yet.
- Releasing drops owned references; it does not promise secure memory erasure. PNG encoding runs synchronously on the GUI thread and can briefly pause very large captures.
- Existing overlay manual checks still apply: physical click-through, mixed DPI, Windows 10, Explorer restart and session-ending behavior. Long labels may clip in small caller-supplied bounds.
- AI, typed tutoring conversations/session memory, TTS, global hotkey, STT integration and interruption are not implemented. STT implementation remains exclusively the teammate's responsibility.

# Shared Files Changed

- `src/jarvis/app.py`: capture composition, hide/restore, cancellation, release, status and sanitized logging.
- `src/jarvis/presentation/main_window.py`: explicit capture/release controls, privacy text and temporary preview.
- `src/jarvis/infrastructure/tray.py`: status setter.
- `README.md`, `ARCHITECTURE.md`, `STATUS.md`: current scope, interfaces and review steps.
- New isolated files: `src/jarvis/features/screen_capture/` and `tests/test_screen_capture.py`.
- Existing overlay and STT code are untouched.

# Next Available Part

A bounded tutoring session and typed-question path with a replaceable multimodal AI provider, using the captured image and validated annotation model. Inspect repository and available provider/runtime configuration first. Keep STT external; TTS and global hold/release activation can follow independently.

READY FOR MANUAL REVIEW AND COMMIT — PART 3
