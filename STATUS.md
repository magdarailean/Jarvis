# Current Milestone

**Milestone 0 — Initialization.** Implementation complete; final UI verification in progress. No later milestone has been implemented.

# Working

- C# / WPF solution using the installed .NET 8 SDK; no external NuGet dependencies.
- Romanian welcome screen and visible `Gata` status, with an accurate initial-version notice.
- Native resizable window, wrapping text, scrollable content, keyboard-accessible close button.
- Explicit close and window close terminate the app (no hidden background process intended in milestone 0).
- Per-monitor DPI-awareness manifest; normal user privileges.
- Best-effort bounded startup/window-loaded/shutdown diagnostics at `%LOCALAPPDATA%\Jarvis\logs\application.log`.
- Architecture, current run instructions, SDK pin, editor configuration, and build/IDE/secrets ignores.

# Partially Working

- None within the initialization scope. This is a runnable shell, not yet a functioning AI tutor.

# Not Implemented Yet

- Tray/background lifetime and global push-to-talk shortcut.
- Microphone, Romanian STT/TTS, speech interruption.
- Screen capture, transparent click-through overlay, persistent annotations.
- Typed questions, actual AI provider, structured action validation, sessions and follow-ups.
- Animated processing state, timeouts/cancellation, subsystem recovery, modes, settings.
- Packaging/installer and Windows 10 / mixed-DPI / multiple-monitor verification.

# Known Issues

- .NET 8 support ends **2026-11-10**. Upgrade to .NET 10 before that date and before release; move this work earlier if the calendar requires it.
- Windows 10 and multiple DPI scales are targets, not yet tested configurations.
- Local-model latency and Romanian/math quality are unmeasured. Inspected hardware: about 32 GB RAM, AMD Radeon 880M integrated graphics; dedicated VRAM figures do not represent total available shared GPU memory. Ollama was not found on PATH.
- Log files are diagnostic only; concurrent app instances can skip log entries if another process locks the file. Single-instance/tray lifetime is reserved for milestone 1.

# How I Tested This Milestone

- Environment: Windows 11 build 26200, x64, SDK 8.0.424, Windows desktop runtime 8.0.30.
- `dotnet build Jarvis.sln --configuration Debug --nologo`: passed, 0 warnings / 0 errors.
- `dotnet build Jarvis.sln --configuration Release --nologo --no-restore`: passed, 0 warnings / 0 errors.
- Launched the actual Release executable and inspected the rendered window and accessibility tree: Romanian diacritics, `Gata`, accurate availability/privacy notices, and close control present.
- Confirmed startup and window-loaded events in the diagnostic file.
- Remaining UI exit checks will be recorded before marking ready.

# How You Can Test It

From PowerShell at the repository root:

```powershell
dotnet restore Jarvis.sln
dotnet build Jarvis.sln --configuration Debug --no-restore
dotnet run --project src/Jarvis.Desktop/Jarvis.Desktop.csproj --configuration Debug --no-build
```

Verify `Gata` and Romanian text; resize/maximize; close using `Închide`. Relaunch and close with the X. The process should exit both times. See README for the log and process checks.

# Required Configuration

- Windows 10/11 x64 and .NET SDK 8.0.424 or a newer 8.0.4xx patch.
- No environment variables, API credentials, microphone permissions, model downloads, or network service required by this version.

# Next Milestone

**Milestone 1 — Background lifetime and tray.** Implement a single-instance application, Romanian tray actions/status, reopen/hide window behavior, and an explicit exit action. Do not implement it until the user has manually committed milestone 0 and says `continue`.

Planned roadmap (12 milestones total; each independently built, run, tested, documented, then stopped):

| Milestone | Scope and acceptance focus |
| --- | --- |
| 0 | Initialization: runnable Romanian shell, architecture, documentation. |
| 1 | Background lifetime: single instance, tray, reopen/hide/exit and visible idle status. |
| 2 | In-memory session and typed fallback: start/end, messages, honest service-unavailable feedback; introduce Core boundaries. |
| 3 | Overlay engine: persistent rectangle/circle/arrow/line/text with IDs, normalized geometry, clear action, click-through and deterministic sample annotations. |
| 4 | Explicit screen context: one capture per activation, monitor/DPI mapping, stale-overlay rule and no idle capture/archive. |
| 5 | First real AI pipeline: local Ollama vision + typed question -> Romanian answer + validated annotation actions; session history, animated busy state, cancellation/timeouts, malformed-output recovery. |
| 6 | Push-to-talk input: Ctrl+Shift+Space hold/release, bounded recording, listening indicator, conflict/error handling, local Romanian Whisper STT; typed fallback retained. |
| 7 | Romanian speech output: local TTS, playback lifecycle, text fallback; annotations remain after speech. |
| 8 | Follow-ups and interruption: stop speech on new activation, stable annotation references/updates, context budget and stale-response protection. |
| 9 | Tutoring modes and answer quality: explain, solve & explain, tutor, guide; Romanian math/document/interface scenarios and missing-context behavior. |
| 10 | Settings and robustness: configurable shortcut, device/service preferences, minimal JSON persistence, timeout/error and privacy regression tests, mixed-DPI/multi-monitor checks. |
| 11 | Release preparation: supported .NET 10 baseline (earlier if required), Windows 10/11 verification, distributable package, third-party notices/model licenses, final end-to-end checks. |

No commits have been created by the agent. Manual review/commit remains the user's responsibility.
