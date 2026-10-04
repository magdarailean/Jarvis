# Cursor targeting adapter — test branch

This optional launcher improves the separate `CursorMain/workingVersion4.py`
prototype. It does not change the main `python -m jarvis` shell. Close any old
cursor prototype before starting this one so its global shortcuts do not conflict.

```powershell
.\.venv\Scripts\python.exe -B -m jarvis.cursor_guide
```

Existing OpenRouter credentials and prototype dependencies are reused. No new
packages are required on this development machine. Other machines need the
owner's `CursorMain/requirements-workingVersion4.txt` dependencies installed.
The adapter requires an editable checkout and is not a standalone packaged app.

If Jarvis says it cannot load the key, close the old cursor process and run:

```powershell
.\.venv\Scripts\python.exe -B -m jarvis.cursor_guide --prompt-key --inspect-target
```

Paste only the API key at the hidden prompt and press Enter. The key is retained
only by that Python process, not saved to disk or inherited from another terminal.
The launcher confirms local loading before registering shortcuts. Missing keys
now fail immediately with a clear console message. Local loading does not prove
that the key is accepted by OpenRouter.

To check authentication separately without sending screenshots or a model request:

```powershell
.\.venv\Scripts\python.exe -B -m jarvis.cursor_guide --prompt-key --check-key
```

This uses OpenRouter's read-only `GET /api/v1/key` endpoint and exits with a
sanitized status: accepted, rejected (401), another HTTP failure, or connection
failure. It never prints the key, account metadata or server response bodies.
A successful check does not validate model availability or sufficient credits.

Use **Ctrl+Space** to start/stop speaking, **Ctrl+Shift+Space** to refresh the
current step, **Escape** to cancel, and **Ctrl+Shift+Q** to quit. Normal recording,
transcription, TTS, captures and pointer animation still belong to Ion.

## What changed

- Screenshot maximum edge increases from 1280 to 1920 pixels, preserving aspect
  ratio and the owner's in-memory encoding. This can retain more small UI detail.
- The existing model first plans the next action. A separate structured request
  locates the control named in that instruction, using the same screenshot and
  a fixed 0..1000 coordinate space. It does not receive the planner's target rectangle.
- Bounds use `[ymin, xmin, ymax, xmax]`, following the
  [Gemini bounding-box convention](https://ai.google.dev/gemini-api/docs/image-understanding).
  Both axes are divided by 1000, never by screenshot dimensions. The previous
  adapter requested pixels, which could misinterpret model outputs on this scale.
  This was a plausible failure mechanism, not verified against the user's failed response.
- Bounds are strictly validated and normalized before the existing crop
  and monitor mapping. Missing, invalid or failed location results block pointing;
  the adapter never falls back to the unverified planner rectangle.
- Completed/blocked responses skip location requests. History verification is
  preserved. Cancellation before location skips the extra request; the owner
  discards cancelled in-flight results.
- The launcher uses the full-image locator that previously improved targeting.
  Crop refinement is disabled after a reported regression: a crop could reject
  an otherwise usable full-image location. Its experimental helper remains unused.
- Console `target.location` events distinguish `located`, `not_found`,
  `http_error`, `network_error`, `invalid_response` and `internal_error`. Provider
  response bodies and credentials are not logged. User messages now distinguish
  connection/response failures from a genuinely missing visual target.
- Planning now explicitly reports goal state and visible evidence before any
  click. Opening the browser does not require maximizing it or relaunching it.
  A request for a specific website still requires that website, not just a browser.
- A loading decision waits 2.5 seconds and captures again, at most twice per
  consecutive loading sequence. Pending click evidence is retained for verification.
  After that limit Jarvis pauses for manual refresh. No idle capture is added.
- Stable control/effect identities supplement screenshot hashes: verified effects,
  two failed attempts at the same effect, and A→B→A→B loops cannot keep producing
  the same suggested click. Distinct numbered wizard steps remain distinguishable.
- On an evidenced completion Jarvis says **Gata, sarcina este îndeplinită**, clears
  the task, and rejects late results. A loop stop says it stopped repetition; it
  does not falsely claim that the task succeeded.

Each actionable step costs **two API requests**,
with more image tokens
and latency than the original. Malformed planning output retains the owner's
single repair request. Each network request has a 45-second timeout. The locator
uses the selected planning model unless `JARVIS_TARGET_MODEL` specifies another
OpenRouter model supporting image input and structured JSON output.
Loading rechecks use up to two additional planning requests. These add latency/cost
and are bounded, not background monitoring. No crop-refinement request is sent.

This is independent localization, **not proof that the target is correct**. The
same model may repeat an error or choose the wrong control named by the planner.
Live Canva accuracy has not been measured. Screen changes during processing can
still invalidate a location; keep the page steady and refresh after scrolling.
No screenshots are saved by this adapter and it adds no idle capture.
Progress still depends on the model recognizing visible completion/loading and
consistently naming effects. The repeat guard uses text similarity, not perfect
semantic understanding, and can conservatively pause a legitimate retry.

## Inspect an incorrect target

```powershell
.\.venv\Scripts\python.exe -B -m jarvis.cursor_guide --inspect-target
```

This opt-in diagnostic displays the exact encoded screenshot sent to the model,
with the planner's box in blue and the final locator's box in red. The preview
preserves image proportions and does not take focus or accept clicks. It is for
diagnosis: it can cover part of your application. Escape ends the session and
clears the preview. The next capture hides and releases it before taking a new
image. Nothing is saved to disk; normal launches do not show the preview.

If the red box misses the named button in this screenshot, localization remains
wrong. If it fits the button but the desktop pointer misses it, check calibration,
monitor/crop mapping and whether the actual page moved after capture. Do not click
buttons inside the preview: it is a static picture with click-through behavior.

## Alignment check (no AI, microphone or capture)

Move the mouse to the monitor to test, then run:

```powershell
.\.venv\Scripts\python.exe -B -m jarvis.cursor_guide --calibrate
```

A synthetic grid cycles through nine positions. After each animation finishes,
the blue arrow's **tip** should touch the green cross center. Escape closes it.
Repeat on each monitor at your usual Windows scale. This tests the actual Ion
pointer anchor and Qt positioning, not screenshot crop acquisition or model
accuracy. A consistent visible offset needs investigation before model tuning.

Then retry the same Canva task using the new launcher. Check both the named
control and the pointed location. If the instruction names the wrong button,
planning is wrong; if it names the right one but points elsewhere, localization
or stale screen context remains wrong. No live paid API calls were made in tests.

## ION REVIEW

- Issue: valid planner coordinates were accepted without separate localization.
- Why it matters: syntactically valid coordinates can refer to another control.
- Severity: high for reliable visual guidance.
- Suggested owner change: expose injectable planner/locator interfaces and
  review the two-stage adapter with real UI tasks before adopting it upstream.

- Issue: original loop matching requires identical screenshot hashes and exact
  instruction/effect wording, with no explicit loading state.
- Why it matters: animation or rephrasing can bypass repeat detection and suggest
  relaunching a browser that is already opening.
- Severity: high for reliable task completion.
- Suggested owner change: expose goal-state/evidence and stable action identities;
  keep bounded loading rechecks separate from click decisions. The outside-owner
  adapter implements these contracts for review without editing owner files.

The adapter imports the owner module without writing bytecode and substitutes
its request boundary and image-size setting only in its own process. This is a
temporary integration seam, coupled to version 4. All files under `CursorMain`
remain unchanged; no STT implementation was added. Main shell production files
are unchanged. Shared documentation changed: README, STATUS and ARCHITECTURE.
