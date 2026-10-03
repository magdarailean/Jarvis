# Architecture

## Stack and rationale

- C# / WPF on Windows 10/11, x64. WPF provides native windows, vector drawing, accessibility, and a small deployment surface. Win32 interop will handle global input and click-through overlays; Windows Forms `NotifyIcon` will provide the tray icon.
- Milestone 0 uses the installed .NET SDK 8.0.424 and `net8.0-windows` so the repository runs immediately. .NET 8 support ends **2026-11-10**: upgrade to .NET 10 LTS before that date and before distributing a release (release gate, not an optional enhancement). [Microsoft support policy](https://dotnet.microsoft.com/en-us/platform/support/policy).
- No external NuGet packages in the bootstrap. No web view, server, database, accounts, or dependency injection framework.
- First AI provider: local **Ollama + Gemma 3 4B**, via `HttpClient` and `System.Text.Json`. The inspected computer has approximately 32 GB RAM. This is a practical starting point for image input without API fees or sending screenshots to a cloud service. CPU latency and Romanian/math accuracy need measurement in the AI milestone; no performance claim is made yet. [Model information](https://ollama.com/library/gemma3).
- A cloud multimodal free tier was considered, but quota limits and data-use terms are a poor default for private desktop screenshots. Paid cloud APIs conflict with the zero-API-cost preference. No second provider will be implemented before the local pipeline works. [Example free-tier tradeoffs](https://ai.google.dev/gemini-api/docs/pricing).
- Planned voice: NAudio for microphone/playback, Whisper.net with a multilingual local Whisper model for Romanian STT, and a local Piper Romanian voice for TTS. Verify the selected package/model licenses and Romanian quality before bundling; typed input and text output remain fallbacks. These are decisions for later implementation, not installed dependencies.

## Project boundaries

Current repository: `src/Jarvis.Desktop` is the WPF executable. `Presentation` owns the Romanian shell; `Infrastructure` contains best-effort diagnostic logging. `App` is the composition root. There is no domain behavior yet, so no empty abstraction projects are created.

As the relevant milestones introduce behavior:

- **Jarvis.Core / Domain**: session, messages, assistant modes/states, annotation IDs and normalized geometry. No WPF, Win32, or provider references.
- **Jarvis.Core / Application**: activation/turn orchestration, cancellation, validation, and ports such as `IAiProvider`, `ISpeechRecognizer`, `ISpeechSynthesizer`, `IScreenCapture`. References Domain only.
- **Jarvis.Infrastructure**: concrete local AI/voice services, Windows adapters, optional JSON settings persistence. References Core.
- **Jarvis.Desktop / Presentation**: WPF views/view models, tray, status indicator, overlay. Composes Infrastructure and Core.
- **Persistence**: active sessions stay in memory; add a settings file only when settings exist. No screenshot/audio archive or conversation database by default.

Introduce those projects/interfaces when used, not as speculative scaffolding. Tests focus on state transitions, annotation validation and failure recovery, then Windows integration smoke checks.

## Target data flow (not implemented in milestone 0)

Hold Ctrl+Shift+Space -> stop current speech -> show listening state -> capture the selected monitor once and record microphone -> release any shortcut key -> stop recording -> Romanian STT -> session + screenshot + annotation snapshot -> local multimodal request -> validated structured response -> persist annotation changes in the in-memory session -> show Romanian text and speak it.

- Register the shortcut and report conflicts; support reconfiguration later. Do not log unrelated keystrokes. No idle capture, microphone recording, or AI requests.
- Annotation commands use stable IDs and `add/update/highlight/remove` operations on rectangle, circle, arrow, line, and text. Validate version, operation, finite normalized coordinates, text length, IDs, and limits independently; retain a valid explanation if visual actions fail.
- Store each capture's monitor bounds/DPI with its annotations; convert normalized coordinates at the Windows rendering boundary. Hide stale overlays on an explicit context change, preserving the session with a visible explanation. Never clear annotations just because speech ended.
- Serialize turns; cancellation and generation IDs prevent late responses from modifying a newer or ended session. End session clears transient content; explicit clear removes annotations.
- Visible Romanian states and an animated busy indicator accompany asynchronous work. Use bounded recording, request timeouts and cancellation. Log lifecycle events and durations, never screenshots, audio, transcripts, prompts, credentials, or model responses by default.
- Treat visible screen text as untrusted content, not instructions to operate the machine. AI can explain and annotate; it gets no clicking, shell, or execution tools.

## Milestone 0 behavior

Launch -> Romanian window with `Gata` and an explicit initial-version notice -> close button or window close -> process exits. The shell cannot capture, record, call AI, or run in the tray yet. Startup/shutdown events go to a bounded local diagnostic file, with debugger-only fallback if file access fails.
