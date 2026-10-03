# Current Part

**Part 5 — Background push-to-talk through the AI boundary.** Implemented 2026-10-04; ready for code/manual review. No commits created. Stop after this part for the user's review/commit.

`git pull --ff-only` confirmed the branch was up to date at `6ca704b`. The working tree was initially clean. Inspected all owner additions, project docs, session/capture/overlay and lifecycle flow before editing. Ion's merged folder is named `CursorMain`, not `Ion`; the entire folder was treated as read-only and has no diff.

# Implemented

- Normal application entry starts in the background, with tray and small input-transparent status indicator. `--window` opens diagnostics. No main-window opening, typing or capture button is needed for the voice path.
- Native global **Ctrl+Shift+Space** hold/release activation; configurable through `JARVIS_HOTKEY`. Registration conflicts are visible. Auto-repeat is suppressed; release checks run only during a hold. Key registration is cleaned up at exit.
- Outside-owner Ion adapter, running in an isolated process. Uses the actual `record_voice()` and `transcribe_voice(model, audio)` functions in `workingVersion1.py`. No competing recognizer, PyQt6 cursor import, Gemini client or AI request.
- Ion sounddevice recording begins only after activation. Release stops it early; Ion's existing ten-second maximum remains. The unused buffer tail is trimmed by elapsed time, pending an exact sample-count API from the owner.
- Actual microphone start triggers **Ascult...** and one automatic capture of the foreground application's monitor. Jarvis surfaces hide briefly; the main window stays hidden afterward. **Procesez...** follows recording stop.
- Transcript and screenshot are combined with session history, mode and annotation snapshot into `TutorRequest`. `InteractionController.prepared` / `.context` is the explicit future-AI boundary. The indicator shows **Context pregătit · AI neconectat**. No AI implemented.
- Serialized interactions, startup/transcription watchdogs, silence/error feedback, cancellation, display invalidation and stale-result rejection. End Session/exit clear image/conversation/overlay and terminate the worker to release audio buffers.
- Typed input, manual capture and overlay demo remain optional diagnostic tools. Tray End Session is available without opening diagnostics.

# Environment / Important Remaining Setup

- Installed optional `.[voice]` dependencies in `.venv`: sounddevice, faster-whisper, google-genai and mss plus their dependencies. PyQt6 was not installed by this work.
- **No Whisper model found/downloaded.** The model-download/local-path question remains unanswered. The adapter uses local-files-only loading, default `large-v3`; set `JARVIS_ION_MODEL` to an existing faster-whisper/CTranslate2 model directory or cached model name.
- Therefore live microphone-to-transcript behavior is **not verified**, and this machine cannot transcribe until the model is supplied. Missing setup produces a Romanian error, not a fake answer or idle recording.
- The owner module imports Google/mss even though Jarvis does not call those services. No API key is needed for this pipeline.

# Validation

- Full Windows suite: **36 tests passed**, no skips. Focused interaction tests also pass after final native-event and preview cleanup changes.
- Real Win32 hotkey registration, conflict detection, posted WM_HOTKEY dispatch through Qt, repeat suppression, release and unregistration. Physical keyboard operation in another application still needs manual verification.
- Real QProcess transport with fake Ion fixture: readiness, recording start, release, stopped/text events and forced cancellation. No microphone used.
- Imported the actual read-only owner module and called its recorder with a fake sounddevice plus its transcription function with a fake model. Verified Romanian options and joined text. Confirmed source bytes unchanged.
- Simulated full hold → capture → release → transcript → prepared context, both capture/transcript completion orders, duplicate/late responses, silence, missing configuration, screen invalidation, background startup and shutdown.
- Prior shell, capture, overlay and session regression tests passed. `pip check`, syntax compilation and `git diff --check` pass. Owner-folder diff is empty.
- No desktop screenshots or real speech were collected for automated testing. AI was never called.

# Manual Review

Read README's Part 5 setup first. With an installed model:

```powershell
$env:JARVIS_ION_MODEL = 'C:\path\to\faster-whisper-large-v3'
.\.venv\Scripts\python.exe -m jarvis
```

Wait for **Gata**. Work in another application, hold **Ctrl+Shift+Space**, wait for **Ascult...**, speak Romanian, then release. Confirm **Procesez...** followed by **Context pregătit · AI neconectat**. Open diagnostics only if you want to inspect text/preview. Verify foreground-monitor selection, no Jarvis surfaces in capture, unchanged application focus, early release, the ten-second limit, silence, repeated presses, End Session and exit.

Opening diagnostics during active voice work cancels it. End Session/cancellation kills the worker when needed; a following press can warm it up without recording. Wait for **Gata**, then press again. Transcription quality/latency, physical microphone behavior and mixed-monitor compositor timing remain manual checks.

# ION REVIEW

Detailed owner report: [ION_REVIEW.md](ION_REVIEW.md).

- High: fixed-duration recorder has no start/stop handle or exact returned sample count. Owner should expose explicit recording lifecycle.
- High: large-v3 CPU loading/transcription has no exposed cancellation/readiness contract; latency/memory are unmeasured. Owner should expose configuration and lifecycle.
- Medium: voice module imports AI/capture dependencies; publish a focused, import-safe STT API.
- Medium: cursor uses PyQt6 rather than Jarvis's PySide6; agree on a compatible public interface.
- Medium: some demo scripts execute prompts/network/file capture at import time; owner should add guarded entry points.
- Medium: owner code is outside the Jarvis wheel; define packaging or configure `JARVIS_ION_SOURCE` for external installs.

No owner fixes were made.

# Shared Files Changed

- `src/jarvis/app.py`: background entry, composition, statuses, activation/capture cleanup and prepared context display.
- `src/jarvis/presentation/main_window.py`: correct normal-flow/privacy instructions.
- `src/jarvis/infrastructure/tray.py`: truthful microphone status.
- `src/jarvis/features/session/panel.py`: pending prepared-context display.
- `pyproject.toml`: optional owner-import dependencies.
- README/ARCHITECTURE/STATUS and new ION_REVIEW documentation.
- New isolated packages: `features/hotkey`, `features/voice_input`, `features/interaction`; new tests and synthetic fixture outside the owner folder.

# Boundary / Next Work

No AI provider, TTS, cursor rewrite or owner STT changes. Next review should configure the local speech model and exercise physical push-to-talk/recording/foreground capture on Windows, then address owner-reported contracts collaboratively. Do not implement AI until the user authorizes that next scope.

READY FOR MANUAL REVIEW — PART 5; LIVE SPEECH REQUIRES LOCAL MODEL
