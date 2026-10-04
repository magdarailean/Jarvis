# Current Milestone

Real OpenRouter / AI-selected VisualPlan integration in normal Jarvis, built on the existing uncommitted callout foundation. No Git commit created. Branch continue-magda began at 62c867f with the prior callout changes present; those changes were preserved/refined.

# Working

- Normal `python -m jarvis`: hold Ctrl+Shift+Space → real isolated Ion recording plus current-screen capture → release/transcription → actual OpenRouter multimodal request → validated answer/visual plan → existing transparent production overlay.
- AI chooses semantic actions: none, callout, highlight, arrow, rectangle, circle, line, pointer/cursor and combinations. No keyword rules, automatic callout or production demo targets.
- Main provider adapts the existing generic OpenRouter protocol outside CursorMain: same endpoint/auth/image/schema approach, tutoring prompt and generalized response schema. Actual live key/request/response verified. No second vendor or simulated runtime path.
- Compact content-sized dark callouts with white wrapped text, automatic leader and target avoidance. Basic bubble collision avoidance. Stable IDs, clear/highlight/update support. Real overlay remains transparent outside requested annotations.
- Existing GuidePointer is called unchanged through an external PyQt worker. No cursor algorithm, positioning implementation or owner file changed. One pointer target at a time.
- Animated AI waiting status, 45-second transport timeout, 60-second overall deadline, cancellation/interruption, stale-response rejection, Romanian missing-key/auth/credit/rate/network feedback. Invalid visuals or unavailable rendering do not discard the textual answer.
- Follow-up requests contain bounded prior answers and current visual descriptions. End Session/exit clears context/visuals and aborts transport. Display invalidation also clears pointer.
- Main speech adapter now discovers installed small when large-v3 is absent and no explicit model override is set. Actual Ion worker reports ready on this machine. Explicit user overrides remain authoritative.
- Normal UI remains available through --window/tray. Typed fallback now sends real requests too. Prior standalone demo remains developer-only; no additional standalone preview deliverable.

# Partially Working

- Complete physical hold/speak/release exercise with a human speaking Romanian remains a manual acceptance check. Automated transport/controller tests use synthetic audio; actual model readiness and microphone format were checked separately.
- Main-runtime TTS is not connected in this milestone. Complete answers are available in the main UI; the old separate companion retains its own TTS.

# Not Implemented Yet

- Tracking targets through scrolling/window movement, sophisticated global layout/arrow routing, streaming responses, main-runtime speech playback and automatic action execution.

# Known Issues

- Screenshot is captured near the start of recording; changing the underlying content later can make targets stale.
- Very large targets/text can leave no safe bubble placement; visuals are then omitted while answer text remains available.
- Bubble collision avoidance does not guarantee protection of every other callout's target or noncrossing arrows. Limited to 16 callouts / 32 inspected incoming actions.
- Separate companion and main Jarvis have overlapping shortcuts. Run normal Jarvis only for this acceptance test.
- Cursor source remains externally owned; API changes require adapter review. Owner source is loaded from the editable checkout with bytecode writes disabled.

# How I Tested This Milestone

- 55 Jarvis tests passed: previous shell/overlay/STT/session regressions plus hold/capture/release/transcript/provider delivery, real screenshot bytes in multimodal payload, semantic combinations, text preservation, pointer boundary, compact sizing/collision avoidance, follow-up context, missing key, cancellation, timeout and late replies.
- 64 frozen companion regression tests passed with -B. Dependency check passed.
- Real OpenRouter request using the configured key and a generated equation image succeeded. The AI independently returned two callout actions; the normal controller accepted the actual response and created the production overlay. No private desktop content was sent in this network check.
- Native pointer adapter ran the existing GuidePointer process, indicated a target, hid and shut down with zero errors.
- Normal background Jarvis startup: actual STT warmup ready=True; idle capture=False; idle AI request=None. No microphone recording during this startup check.
- Full read-only CursorMain/Ion SHA-256 baseline remained identical. No owner source or cursor implementation changed. git diff --check passed.

# How You Can Test It

```powershell
cd C:\Users\Magda\Documents\GitHub\Jarvis
.\.venv\Scripts\python.exe -m jarvis
```

Keep the configured key in .env; installed small is sufficient. Wait for Gata, open a visible problem/document, hold Ctrl+Shift+Space, say a Romanian question, release. Expect animated processing then the AI-selected annotations on the real desktop. No blue synthetic rectangle should appear unless a highlight/rectangle was requested by the AI. Ask a follow-up; verify retained context. Ask a general question and confirm no forced callout. Ask where to click and let the AI choose pointer/arrow/highlight. Inspect full answers through tray Deschide Jarvis or --window. End Session clears visuals and pending work. Exit with Ieșire.

```powershell
.\.venv\Scripts\python.exe -m jarvis --window
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Main-runtime answers are currently textual/visual; there is no spoken answer playback in this milestone. No commit was made.

# Required Configuration

Python 3.12 x64, .[voice,openrouter], installed local speech model, desktop microphone permission, OpenRouter API key and network/available credit. No CUDA or external FFmpeg executable. README contains copy/paste setup and exact local key handling. No secret/config value was printed or committed.

# Next Milestone

Stop for manual testing and commit. Follow user direction after review.

READY FOR MANUAL TEST — CALLOUT BUBBLE
