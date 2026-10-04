# Current Milestone

Milestone 6 — Local OpenRouter configuration and Windows STT setup (2026-10-04). Limited to the requested setup/adapters. No commit created; stop for manual testing.

# Working

- Inspected clean branch continue-magda at 67ee23a, recent Python changes, OpenRouter source and every module in the owner's package. Authorized fast-forward pull from origin/main reported already up to date.
- Local ignored .env contains empty OPENROUTER_API_KEY=. Allowlisted loader uses environment precedence and never logs the key. Tracked .env.example has no credentials.
- Separate Python OpenRouter launcher loads local configuration and checks key/model before startup. Keeps PyQt6 out of the PySide6 Jarvis process.
- Optional dependency groups install all owner-import/STT and companion requirements outside the owner package.
- Explicit model download and microphone diagnostics store models outside the protected package. Jarvis discovers installed large-v3; companion discovers small and blocks its original first-use download into CursorMain.
- Existing shell, sessions, overlay, capture, hotkey and isolated Ion transport regression tests pass.

# Partially Working

- Device enumeration and 16 kHz mono input validation pass on this machine. Live speech recognition awaits explicit model installation and manual recording test.
- Companion demo starts/registers shortcuts and shuts down normally. Real OpenRouter/TTS replies await your key, model and manual test.

# Not Implemented Yet

- Jarvis's main session/AI boundary remains unconnected to OpenRouter. The existing OpenRouter companion is independent and toggle-based; this scope does not implement a unified hold-to-talk tutoring pipeline.
- No new AI provider, TTS implementation or owner-package changes.

# Known Issues

- There is no Ion-named folder in this checkout; actual owner package is CursorMain. Entire folder treated read-only.
- No speech model installed or downloaded during this setup. check returns LocalEntryNotFoundError until installation.
- Jarvis and companion shortcuts overlap; run one application at a time.
- large-v3 CPU speed/memory and real Romanian transcription quality remain unmeasured.
- Owner sources require an editable checkout, not a standalone Jarvis wheel installation.

# How I Tested This Milestone

- Installed editable .[voice,openrouter] successfully in Python 3.12.14 x64 .venv; pip check reports no broken requirements.
- 41 Jarvis tests passed without skips, including real owner STT functions with synthetic microphone/model and new local configuration/setup guards.
- 64 owner companion regression tests passed with -B, preventing bytecode writes.
- Windows companion QApplication/GuideController launched in demo/mute mode, registered native shortcuts and shut down after one second. No microphone, screenshot or API request.
- stt_setup check enumerated microphones and validated default input at 16 kHz mono. CTranslate2 imports successfully; missing model reports failure without downloading/recording.
- OpenRouter launcher with empty key reports the exact local setup path and exits cleanly before AI/microphone startup.
- Every file under CursorMain compared by SHA-256 against pre-change baseline: identical, including untracked files. Owner diff empty.
- git check-ignore confirms .env rule; git ls-files -- .env prints nothing. git diff --check passes.

# How You Can Test It

Follow README's copy/paste installation, key setup, model download, microphone check/test and launcher commands. For real companion use small; for original Jarvis use large-v3. Speak Romanian during the explicit five-second test and verify recognized text. Exit one app before starting the other. Live key/model/microphone behavior is deliberately left to manual testing, not claimed verified.

# Required Configuration

Python 3.12 x64, .venv, .[voice,openrouter] dependencies, Windows microphone permissions/default device, local faster-whisper model. Visual C++ x64 runtime required; CPU path needs no CUDA or external FFmpeg executable. Companion additionally needs OpenRouter key in C:\Users\Magda\Documents\GitHub\Jarvis\.env and internet for AI/TTS. README supplies exact commands and official dependency sources.

# Next Milestone

Wait for manual testing/commit and user direction. Do not automatically integrate AI or modify Ion.

READY FOR MANUAL COMMIT — MILESTONE 6
