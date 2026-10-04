# workingVersion3_Codex

The voice companion using **Codex App Server with ChatGPT authentication**.
`workingVersion2.py` remains the Gemini version. Both variants share the original
pointer drawing (`test.py`), local speech worker (`voice_input_v2.py`) and sanitized
console diagnostics (`diagnostics_v2.py`).

## Run

Close any other companion instance first with **Ctrl + Shift + Q** so the global
shortcuts are available. From the repository root:

```powershell
.venv\Scripts\python.exe -u CursorMain\workingVersion3_Codex.py --debug
```

Without a console:

```powershell
.venv\Scripts\pythonw.exe CursorMain\workingVersion3_Codex.pyw
```

No Gemini key or OpenAI API key is read. The installed `codex.exe` must be on PATH
and signed in **with ChatGPT**. Check with `codex login status`; if needed, run
`codex login` to use Codex's browser login flow. An API-key-only Codex login is
rejected to avoid silently switching to separately billed API usage. The machine's
CLI was already signed in with ChatGPT during implementation.

Dependencies are listed in `requirements-workingVersion3_Codex.txt`; the existing
environment already contains them. The bridge uses Python's standard library and
the installed Codex executable, so no extra SDK installation is necessary.

## Interaction

- **Ctrl + Space:** capture the monitor under the mouse and start voice input.
  A second press while listening ends recording manually.
- **Microphone:** listening. Silence ends recording automatically.
- **Spinner:** speech transcription or Codex analysis.
- **Pointer:** click the indicated target yourself. A matching left-button release
  triggers a fresh screenshot and verification of the previous action.
- **Esc:** cancel. The Codex worker terminates its dedicated app-server process;
  late results cannot affect a newer session.
- **Ctrl + Shift + Space:** refresh/retry the current target.
- **Ctrl + Shift + Q:** quit.

There is no panel, transcript window, target rectangle, spoken response or automatic
click. It currently guides clickable controls on one monitor. Non-click actions
are blocked. Voice recordings/transcripts are not written to files or printed;
the local speech model can cache under `CursorMain/models`.

## Codex integration

Each analysis launches a hidden app-server sidecar using the existing Codex login,
checks `account/read` for ChatGPT auth, and starts an **ephemeral** analysis thread.
No visible Codex chat or persisted conversation history is created. A fresh image
is taken after transcription to avoid guiding from an old pre-recording screenshot.
The screenshot is encoded in memory and sent as an image data URL; no temporary
screenshot file is created. Each next step includes the original task, previous
verified steps and pending click evidence.

Codex receives a strict JSON output schema. It uses a read-only sandbox, no
environment tools, no MCP servers, and explicit instructions to analyze only the
supplied screenshot. The bridge rejects interactive tool/approval requests. It
consumes the final assistant message only after a successful `turn/completed`.
The returned coordinates go to the same independent Qt animation.

Usage consumes the signed-in ChatGPT/Codex allowance. It is not unlimited and
service/model failures remain possible. The default model is the configured Codex
model; the live smoke test selected `gpt-6.1-sol`. Override with:

```powershell
.venv\Scripts\python.exe -u CursorMain\workingVersion3_Codex.py --debug --model gpt-6.1-sol
```

`--model` (or `JARVIS_CODEX_MODEL`) requires access on the signed-in account.
`--codex-bin` / `JARVIS_CODEX_BIN` selects a particular executable. No token files
are read/copied by this app; authentication and renewal belong to Codex itself.
Codex can maintain its own normal runtime/authentication metadata in its existing
user directory. The companion's added source files remain inside `CursorMain`.

The default **120-second total deadline** includes sidecar startup, authentication
and inference. It is enforced locally, regardless of server retry behavior; change
it with `--codex-timeout 90`. Cancellation stops the sidecar within the worker, so
the UI does not wait for it. Local Whisper model loading/inference may finish in
the background after cancellation.

## Diagnostics and demo

Console diagnostics retain the V2 capture/click/decision messages and add:

- `codex.auth.ready`: ChatGPT login accepted.
- `codex.thread.ready`: selected model and ephemeral status.
- `codex.request.start` / `codex.response.ready`: request and duration.
- `codex.request.error`: actual failed stage and sanitized exception.
- `codex.request.cancelled`: cancellation acknowledged.

The AI instruction/blocked reason appears only in the debugging console; raw
screenshots, audio, full user transcripts and credentials are excluded.

```powershell
.venv\Scripts\python.exe CursorMain\workingVersion3_Codex.py --demo --debug
.venv\Scripts\python.exe -m unittest discover -s CursorMain -p "test_workingVersion3_Codex.py" -v
```

Demo simulates voice and two targets without opening a microphone, contacting
Codex, or consuming allowance. The live implementation check used a synthetic
image, not the user's screen. It returned the correct blue-button rectangle in
approximately 6.6 seconds using ChatGPT authentication.

Official protocol documentation: https://learn.chatgpt.com/docs/app-server
