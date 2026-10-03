# Current Part

**Part 2 — Screen overlay foundation.** Implemented on 2026-10-03; ready for manual desktop review and commit. Development stops here until the user writes `continue`. No commits created.

The earlier session-first roadmap is superseded by the latest product priorities. Overlay was selected because the repository contained only a clean desktop shell and no other feature implementations. Speech-to-Text remains exclusively owned by the teammate.

# Working

- Existing Python/PySide6 Romanian shell, Gata status, tray, hide/reopen, duplicate activation, explicit exit and tray-unavailable fallback.
- Isolated `features/overlay` package with immutable, validated, monitor-normalized annotations and stable IDs.
- Rectangle/highlight, ellipse (circle with square logical bounds), arrow, line, plain Romanian label and numbered step.
- Add/update by ID, highlight, hide/show individual items, remove and clear; bounded to 64 items and 200 characters per label.
- Transparent, topmost, input-transparent/no-focus Qt overlay targeting the monitor containing Jarvis when the demo is requested.
- Static **Arată demonstrația** and **Șterge adnotările** controls. Marks persist when Jarvis hides; another demo replaces them; exit clears/disposes them.
- Monitor geometry/DPI changes and target-monitor removal clear stale marks.
- Romanian display-failure feedback; diagnostic events without annotation content. No screenshots, microphone use or network requests at runtime.

# Validation

- Restored missing `.venv` using Python 3.12.14 and the existing pinned PySide6-Essentials/shiboken6 6.11.2. No project dependency changes.
- Full Windows/Qt unittest suite: **14 tests passed**, including the existing 10 shell/logging tests and 4 focused overlay tests. The 4 overlay tests also passed after strengthening native-style and error-recovery assertions.
- Tested invalid geometry/text/IDs, immutable snapshots, capacity, replacement, visibility/highlight/removal/clear, transparent widget rendering, Qt input/focus flags and native Windows transparent/layered/topmost styles.
- Tested static demo persistence, replacement, clear, simulated display changes/removal, display-failure feedback and shutdown cleanup.
- Syntax compilation, `pip check` and `git diff --check` pass.
- Visually inspected app-only overlay and shell renders in ignored `.artifacts/`; no desktop screenshots taken.

# Manual Review

```powershell
.\.venv\Scripts\python.exe -m jarvis
```

Click **Arată demonstrația** (scroll down if necessary), hide Jarvis, and click/type/scroll in another application under the marks and labels. Reopen Jarvis and clear them. Repeat on another monitor if available, at your normal Windows scaling. Exit with marks visible and confirm none remain.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Close existing Jarvis before testing the installed launcher. Tests open temporary native windows/tray icons. README includes full setup and review steps.

# Limits / Not Implemented

- Physical cross-application click-through, multi-monitor mixed DPI, disconnect/reconnect, Windows 10, Explorer restart and session-ending checks remain manual release verification. Automated display-change tests simulate notifications.
- Marks are fixed to their monitor; scrolling/changing underlying content does not reposition or invalidate them yet. Clear manually. No secure-desktop or exclusive-fullscreen guarantee.
- Label layout is bounded by caller-provided geometry; long text in small bounds can clip.
- No screen capture, AI, typed conversations, session memory, TTS, hotkey or barge-in yet. STT is reserved for the teammate.
- No standalone Windows installer, settings persistence, model downloads or provider credentials.

# Shared Files Changed

- `src/jarvis/app.py`: demo/clear composition, ownership, cleanup and event logging.
- `src/jarvis/presentation/main_window.py`: Romanian demo/clear controls and signals.
- `README.md`, `ARCHITECTURE.md`, `STATUS.md`: current scope, interface, review steps and boundaries.
- New isolated files: `src/jarvis/features/overlay/`, feature package marker and `tests/test_overlay.py`.

# Next Available Part

One-shot in-memory screen capture with explicit activation, monitor geometry and screenshot-to-overlay coordinate mapping. Then a replaceable multimodal AI provider and bounded tutoring sessions/typed fallback. Keep STT external; TTS and global hold/release shortcut are independent later parts.

READY FOR MANUAL REVIEW AND COMMIT — PART 2
