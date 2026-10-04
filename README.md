# Jarvis

Python-only Romanian Windows desktop tutor. **Normal Jarvis now connects push-to-talk to OpenRouter and the production transparent overlay.** The AI chooses zero or more visual actions semantically; no keyword rules or automatic explanation bubble. CursorMain/Ion are read-only.

## Install

Windows 10/11, Python 3.12 x64, microphone. In PowerShell:

```powershell
# Run from your Jarvis repository directory.
# Only if .venv does not exist:
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -e ".[voice,openrouter]"
.\.venv\Scripts\python.exe -m pip check
```

Activation is optional; skip it if execution policy blocks it. These commands use the venv executable directly. Base desktop uses PySide6-Essentials; voice adds sounddevice, NumPy, faster-whisper, google-genai and mss (the last two are imports required by the frozen owner module, not services called by STT). The openrouter extra supplies PyQt6 for the existing cursor process, plus edge-tts for Romanian speech in the main application. No additional install inside CursorMain is needed.

CPU/int8 recognition needs no CUDA, NVIDIA GPU, PyTorch or separate FFmpeg executable. [PyAV bundles FFmpeg](https://github.com/SYSTRAN/faster-whisper); sounddevice's Windows wheel bundles PortAudio. [CTranslate2 requires the Visual C++ x64 runtime](https://opennmt.net/CTranslate2/installation.html). If DLL imports fail, install it:

```powershell
Invoke-WebRequest https://aka.ms/vc14/vc_redist.x64.exe -OutFile "$env:TEMP\jarvis-vc-redist.x64.exe"
Start-Process -FilePath "$env:TEMP\jarvis-vc-redist.x64.exe" -ArgumentList '/install','/passive','/norestart' -Wait
```

The installer may request elevation. Enable Windows microphone access for desktop apps and choose the intended default input in Windows Sound settings.

## Local configuration

Key file: **`.env` in the repository root**. On a fresh clone copy `.env.example` to `.env`. Paste the key after the equals sign:

```dotenv
OPENROUTER_API_KEY=your-key-here
```

To change/remove the key, replace/empty that value and restart Jarvis. No source edits. Existing environment variables override the file. Optional settings: OPENROUTER_MODEL (default google/gemini-2.5-flash-lite), JARVIS_ION_MODEL (local model directory or cached model name), JARVIS_SPEECH_MODEL (separate companion). JARVIS_HOTKEY can be set in the shell (default Ctrl+Shift+Space).

```powershell
git check-ignore -v -- .env
# Must print nothing:
git ls-files -- .env
```

Secrets and models are ignored. Never force-add .env. Network requests use your OpenRouter account and may incur charges. The provider uses OpenRouter's [structured output protocol](https://openrouter.ai/docs/guides/features/structured-outputs), with local validation as well.

## Speech model

```powershell
.\.venv\Scripts\python.exe -m jarvis.stt_setup download --model small
.\.venv\Scripts\python.exe -m jarvis.stt_setup check --model small
# Records five seconds ONLY when you run this explicit test:
.\.venv\Scripts\python.exe -m jarvis.stt_setup test --model small
```

Models download explicitly into ignored `models\stt`, outside CursorMain. The main adapter uses installed large-v3 when present; if no explicit JARVIS_ION_MODEL override is set and large-v3 is absent, it uses the installed small model. Otherwise it tries the cached large-v3 name with local-files-only loading. It never downloads during activation. For the larger/slower CPU model: `python -m jarvis.stt_setup download --model large-v3`. An explicit override is always respected.

## Normal use — real AI integration

```powershell
.\.venv\Scripts\python.exe -m jarvis
# Open the retained main UI immediately:
.\.venv\Scripts\python.exe -m jarvis --window
```

1. Wait for **Gata**. Open an exercise, document or application.
2. Hold **Ctrl+Shift+Space**, wait for **Ascult...**, speak Romanian, then release. Maximum recording is ten seconds.
3. Jarvis transcribes locally and sends the question, one real screen capture, bounded conversation history and existing visual descriptions to OpenRouter.
4. **Pregătesc explicația...** animates while waiting. The AI returns Romanian text plus its chosen visual plan.
5. Callouts, arrows, highlights and shapes render over the real application. There are no artificial target rectangles unless the AI requested a rectangle/highlight. A callout's own leader is automatic; no full-screen opaque background is painted.
6. `pointer/cursor` invokes the existing GuidePointer through an external process adapter. CursorMain, the pointer drawing and its point_at behavior are unchanged.
7. Jarvis speaks the displayed callout text using Romanian Alina; GUIDE speaks its cursor instruction. Follow-up questions include prior answers and current visuals. Callouts reveal text quickly (up to 1.2 seconds), remain throughout speech and expire five seconds after speech finishes, and clear immediately on the next accepted push-to-talk activation. Other annotations keep their existing lifecycle. Pressing the shortcut during an AI request cancels it and starts another interaction.
8. **Încheie sesiunea** clears context/annotations and stops pending work. **Ieșire** exits.

Normal startup currently uses the voice-only background interface. TTS uses online `edge-tts` with `ro-RO-AlinaNeural` at +10% speed and needs internet, but no extra API key or local voice model. The visible callout text is the speech source; multiple rendered callouts are read in display order, without an additional spoken summary. GUIDE retains spoken cursor instructions. `Pregătesc vocea...` precedes `Vorbesc...`, then `Gata`. Spoken temporary bubbles are held during synthesis/playback and removed five seconds after speech completes (or fails). Unspoken callouts retain their existing fallback lifetime. PTT stops synthesis/playback immediately and starts the next interaction. A speech failure shows Romanian feedback while retaining the answer and visuals. Audio is kept in memory in an isolated worker and discarded afterwards. No new environment variables are required.

No idle recording, screenshot stream, automatic clicking or screenshot archive. The screenshot is taken near recording start; moving/scrolling the application afterwards can make an annotation stale. Geometry/DPI changes clear stale overlays. Internet is needed for AI requests; a 45-second transport timeout and 60-second overall deadline bound requests. No automatic paid retries.

## Cursor ownership / optional separate companion

The adapter imports `CursorMain/workingVersion4.GuidePointer` in a separate PyQt process with bytecode writing disabled. It calls the existing public point_at API using the same normalized-to-monitor mapping as the companion. No mouse automation, new accuracy algorithm or owner source change. One pointer target can be shown at a time.

`python -m jarvis.openrouter` still launches the older independent companion, not the main Jarvis flow. Run only one: global shortcuts overlap. Use `python -m jarvis` for this milestone.

## Developer verification only

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m unittest discover -s CursorMain -p 'test_workingVersion*.py' -v
# Optional retained isolated layout demo (not the production AI path):
.\.venv\Scripts\python.exe -m jarvis.features.callouts.demo
```

The old demo uses synthetic blue targets and its own tray menu. None are imported as targets by the production response path. Production has compact content-sized callouts, safe target avoidance, basic bubble collision avoidance, stable IDs and per-action validation. If no safe placement fits, that callout is omitted while text remains available. No OCR/scroll tracking or arrow-crossing optimization yet.

## Temporary, selective callouts

The AI prompt explicitly prefers the smallest useful plan, normally zero to three short callouts (often one), and allows more only when the question genuinely needs simultaneous comparison of more sources. This is semantic guidance, not keyword routing or a hard three-item truncation. The full answer remains in conversation history after a callout expires.

Manual check: run normal Jarvis, ask about a visible item, observe the fast progressive text, and wait until speech finishes, then five more seconds without further interaction. The callout and its leader disappear. Ask again, then start another voice request while the bubble is appearing: the old callout should vanish immediately. Existing highlights/shapes and cursor behavior should be unaffected by this callout-only cleanup. Repeated requests, removal or ending the session during animation must not crash.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_callout_timing.py -v
```

## GUIDE routing priority

Explicit `arată-mi` / `arata-mi` / `unde` requests take priority over explanation terms in the same request. GUIDE restricts AI output and local validation to pointer actions. Clicks hide the previous pointer; after the UI settles Jarvis captures a fresh screen and asks for the next action until visible completion evidence is returned. A click alone is not treated as success.

PTT pauses the guide observer while listening and retains the original goal. Follow-ups such as “Și acum?” continue GUIDE. An explicit explanation-only request such as “Explică-mi acest buton” switches to EXPLAIN. Restart Jarvis after updating the checkout; an already-running process keeps its old code.

GUIDE pointers now stay visible during guidance speech and disappear five seconds after speech finishes or fails. Pointer expiry does not end the task: a subsequent click still triggers fresh-screen analysis. A click or new PTT immediately hides the old pointer and cancels its expiry timer. Next-step pointers receive a fresh speech lifetime. CursorMain and positioning are unchanged.

Creation requests such as “Ajută-mă cum să fac o prezentare în Canva” now enter GUIDE directly. Presentation/document/table creation uses pointer-only guidance and the existing multi-step observer; the AI still identifies the next target from the current screenshot. Explicit explanation-only requests retain EXPLAIN. No Canva-specific coordinates or automated clicks are introduced.

GUIDE speech also has a separate on-screen transcript. It displays exactly the spoken instruction, remains while speech plays and for five seconds afterward, and is not replaced by the status indicator. It is cleared on new PTT or the next step. This caption accompanies cursor guidance; it does not switch the AI to EXPLAIN or change pointer targeting.

Click dismissal: a left/right mouse press clears temporary callout bubbles (including their leaders), GUIDE captions and pointers, and stops old speech. Outside GUIDE this only dismisses assistance; it does not capture or send a new screen. During GUIDE, the existing settled-click flow continues to the next step. Unrelated persistent annotations are retained.

## Cursor adapter retained on test

The separately launched adapter from this branch is still available:

```powershell
.\.venv\Scripts\python.exe -B -m jarvis.cursor_guide --prompt-key
```

This is separate from both normal `python -m jarvis` and `python -m jarvis.openrouter`.
Run only one assistant at a time; their shortcuts overlap. The cursor adapter uses
**Ctrl+Space** to start/stop speech, **Ctrl+Shift+Space** to refresh and
**Ctrl+Shift+Q** to exit. It retains the 1920-pixel full-image locator, explicit
0..1000 bounding-box mapping, completion/repeat checks and existing Ion animation.
Crop refinement is disabled. The hidden key prompt is memory-only; do not assume
this launcher loads the main application's `.env` configuration.

Optional `--calibrate` tests nine pointer positions without AI; `--inspect-target`
shows an in-memory diagnostic preview; `--check-key` checks authentication without
a model request. See [CURSOR_TARGETING.md](CURSOR_TARGETING.md) for details, API
costs, limitations and the adapter's owner review. These targeting changes are not
integrated into the normal main-app provider by this documentation merge.
