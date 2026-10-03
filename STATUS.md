# Current Milestone

**Milestone 1 — Python migration of the existing background/tray application.** Completed and verified on 2026-10-03. Ready for manual review/commit. Milestone 2 has not started.

# Working

- Python 3.12 / PySide6 implementation, preserving the Romanian shell, Gata state, blue J icon, text and general layout.
- Ascunde/X hides; tray double-click / Deschide Jarvis / duplicate launch reopens; Ieșire terminates.
- Per-user/per-login-session single instance with the same Windows mutex/event names. Verified an actual C# launcher notified the Python primary before removing the old implementation.
- Minimized-window restoration; queued activation on the UI thread; no idle polling.
- Tray-unavailable fallback: visible Romanian explanation, hiding disabled, X exits.
- App-only normal/minimum-size renders, wrapping/scrolling content and keyboard-accessible buttons.
- Same best-effort diagnostic path and approximately 1 MiB bound; denied disk access/missing console tolerated.
- Clean event-loop exit/restart, worker stop, handle release, late-activation rejection and recovery after abrupt child-process termination.
- Editable package, pinned Qt dependencies, console and no-console Python launchers, standard-library unittest suite.
- C# solution/source/test runner/build outputs removed. No .NET runtime or SDK required. Existing staged generated-file removals remain for the manual commit.

# Partially Working

- None within implemented migration scope. This remains a background shell, not yet an AI tutor.

# Not Implemented Yet

- Push-to-talk shortcut, microphone, Romanian STT/TTS and interruption.
- Screen capture, click-through overlay and persistent annotations.
- Typed questions, AI pipeline, sessions, multi-turn history and tutoring modes.
- Animated processing state, request timeouts and settings persistence.
- Standalone Windows installer; Windows 10 and mixed-monitor/DPI release verification.

# Known Issues

- Tested on Windows 11 build 26200, x64, Python 3.12.14 and PySide6-Essentials/shiboken6 6.11.2. Other supported Python/Windows combinations are not yet verified.
- Qt widget mouse/keyboard events and native tray callbacks are tested. Physical Windows tray clicks, Explorer restart and logoff/reboot remain manual checks; no system settings or Windows session were changed.
- Windows may put J under hidden icons. Relaunching also reopens the window.
- Local AI latency and Romanian/math quality are unmeasured; no AI/voice dependencies were installed.
- The prepared `.venv` uses the available local Python runtime. Each teammate must create their own environment; virtual environments are not portable.
- Logging is best-effort; simultaneous short-lived duplicate processes may skip a log entry if the file is locked.

# How I Tested This Milestone

- Installed editable package and pinned Qt runtime into `.venv`; syntax compilation and `pip check` pass.
- Built `dist/jarvis_desktop-0.1.0-py3-none-any.whl`, installed it into an isolated `.artifacts/wheel-check` directory, verified imports came from that wheel, and reran the full suite: **10 tests passed** against the built package as well.
- `python -m unittest discover -s tests -v`: **10 tests passed**, no skips, exit code 0.
- Real Qt app/dispatcher, visible loaded shell and Romanian locale; normal/minimum layouts rendered and visually reviewed.
- QtTest mouse click hides, Tab changes focus and Enter invokes exit. Real duplicate Python processes exit successfully and reopen/restore the same primary window.
- Tray menu actions and double-click activation signal dispatch correctly; exit removes the icon and releases the instance lock.
- Simulated missing-tray/initialization-error paths keep the window usable and close correctly.
- Real child event loops exit and restart; abrupt interpreter death without cleanup permits a new primary. Test was corrected to terminate the interpreter, not only Windows' virtual-environment redirector.
- Installed `jarvis.exe` GUI launcher and `python -m jarvis` both notified a primary using the actual production namespace and exited with code 0.
- Legacy C# executable -> Python primary activation passed before legacy removal.
- Disk-denied/missing-console logging and log size reset pass. No screenshots/audio/network requests are part of application runtime.

# How You Can Test It

The current machine's environment is already installed. From PowerShell at the Jarvis root:

```powershell
.\.venv\Scripts\python.exe -m jarvis
```

Check Gata and J near the clock. Ascunde/X should hide; double-click J or choose Deschide Jarvis to reopen. Start Jarvis again to restore the same instance. Resize, use Tab/Enter, and choose Ieșire to exit completely. For a console-free launch, double-click `.venv\Scripts\jarvis.exe`.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Close existing Jarvis first to include the installed-launcher test. See README for fresh-machine setup, package build and full manual steps.

# Required Configuration

- Windows 10/11 x64 and Python 3.12+; verified baseline is 3.12.
- `pip install -e .` installs pinned PySide6-Essentials 6.11.2 and matching shiboken6. Initial installation/build may need network access; application use does not.
- No API keys, app-specific environment variables, microphone permissions, models or backend services.

# Next Milestone

**Milestone 2 — In-memory session and typed fallback.** Introduce domain/application state and typed questions with honest unavailable-service feedback until the AI milestone. Wait for the user's manual migration commit and `continue` first.

Roadmap (12 milestones; each built/run/tested/documented, then stopped):

| Milestone | Scope |
| --- | --- |
| 0 | Initialization and runnable Romanian shell. |
| 1 | Tray/background lifecycle and single instance; migrated to Python at user request. |
| 2 | In-memory sessions and typed fallback; introduce Domain/Application. |
| 3 | Persistent overlay shapes/text with stable IDs and normalized geometry. |
| 4 | Explicit one-shot screen capture, monitor/DPI mapping and stale-context rule. |
| 5 | First real local vision pipeline, Romanian text, validated annotations, busy state and cancellation/timeouts. |
| 6 | Hold/release shortcut, bounded microphone recording and Romanian STT. |
| 7 | Romanian TTS/playback with text fallback and persistent annotations. |
| 8 | Follow-ups, interruption, annotation updates and stale-response protection. |
| 9 | Explain, solve & explain, tutor and guide modes; Romanian quality scenarios. |
| 10 | Shortcut/device settings, minimal persistence and robustness/DPI/privacy tests. |
| 11 | Python/Qt release baseline, Windows 10/11 verification, standalone distribution, licenses and end-to-end checks. |

No agent-created commits. Suggested description: `refactor: migrate desktop shell to Python and PySide6`

READY FOR MANUAL COMMIT — MILESTONE 1
