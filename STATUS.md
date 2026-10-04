# Current Milestone

Immediate click dismissal of temporary visual assistance in the real runtime. Existing pointer guidance and EXPLAIN callout behavior preserved. Existing TTS/callout behavior preserved; no commit created.

# Working

- Left/right click clears temporary callouts and their leaders, speech caption and pointer, stops speech, and cancels outstanding visual holds. This also works outside GUIDE, without starting automatic screen capture. GUIDE still captures after release/settling for the next step. Persistent annotations are preserved.

- GUIDE now displays the exact spoken text in a separate caption. Status updates do not overwrite it. It remains through speech plus five seconds, then hides; click/next-step/PTT clears it immediately. Cursor guidance remains independent.

- “Ajuta-ma cum sa fac o prezentare in canva” now routes to GUIDE instead of AUTO. Creation requests for editable artifacts share this routing; homework/recipe requests are not classified by the generic verb “fac” alone. AI chooses target geometry from the actual screen.

- GUIDE pointer is held during TTS, then hidden after five seconds. Click/PTT clears it immediately and cancels the old timer. Expiry preserves the active goal and click observer. Speech failure also releases the pointer after five seconds.
- Navigation variants such as “Cum pot închide site-ul?” and “Cum să-l închid?” route to GUIDE. Provider instructions prioritize the spoken task over unrelated screenshot content.

- Explicit arată-mi/arata-mi/unde wins over explanation terms. Active GUIDE survives recognized contextual PTT follow-ups; new tasks replace the old guide goal. The dispatched request and pending response-validation request share the same GUIDE context.

- Online edge-tts Romanian Alina synthesis and in-memory audio playback through a cancellable isolated worker.
- TTS reads exactly the final rendered callout text, in painting order for multiple callouts. No separate longer spoken answer. Existing bubble text selection is preserved.
- GUIDE keeps cursor instructions and routing. EXPLAIN keeps callouts/typewriter.
- Preparing/speaking/ready states; PTT interrupts speech without waiting and preserves conversation history.
- Spoken bubbles remain during synthesis/playback and expire five seconds after speech finishes or fails; typewriter timing is unchanged. Romanian Alina speaks at +10% rate. New PTT clears temporary callouts as before.
- Speech errors/timeouts retain answer and visuals. No Ion or CursorMain changes.

# Partially Working

- Physical hold/speak/release, human assessment of Romanian pronunciation and GUIDE cursor acceptance remain manual checks.
- TTS is online and depends on the Edge speech service being available.

# Not Implemented Yet

- Offline TTS and configurable voice selection.

# Known Issues

- Multiple spoken bubbles remain together until the combined utterance finishes, then expire together five seconds later.
- Existing single-callout selection may expand a bubble to the full explanation. Speech follows the resulting visible text exactly.
- Normal startup uses the existing voice-only background interface.

# Incoming main milestone verification (reported before merge)

- 101 tests passed (including an actual five-second Qt timer expiry): click dismissal outside GUIDE, real GUIDE mouse-sampling callback cleanup and next-step settling, GUIDE caption text equality, survival through speaking/ready status, real five-second caption expiry and PTT cleanup, exact Canva phrase, pointer-only provider schema, controller delivery, rejected bubble response and preserved creation goal after a click, pointer speech lifetime, click/PTT timer cancellation, next-step replacement, speech failure, mixed keyword priority, GUIDE schema restriction, actual controller voice-follow-up routing, rejection of AI callouts in GUIDE, click invalidation/capture, multi-step progression and completion evidence, plus TTS and overlay regressions.
- No CursorMain or Ion files changed. Pointer positioning/implementation remains unchanged; accuracy still depends on AI identifying the correct visible target.
- Live Canva/microphone acceptance remains manual; automated checks use the real controller/provider payload path with simulated AI responses.
- Previous native startup check encountered hotkey registration failure under sandbox; unrestricted startup exited through the single-instance gate. No claim of a new live microphone/AI acceptance run. Restart the existing Jarvis instance for manual validation.

# How You Can Test It

Exit existing Jarvis through its tray, then run:

```powershell
.\.venv\Scripts\python.exe -m jarvis
```

Hold Ctrl+Shift+Space and say “Ajuta-ma cum sa fac o prezentare in canva” while Canva is visible. Release: expect cursor guidance, no bubble. Click the indicated control; expect the old pointer to disappear and a fresh-screen next step. Try “Și acum?” through PTT: GUIDE should persist. Try the mixed request “Arată-mi butonul și explică-mi ce face”: GUIDE wins. “Explică-mi acest buton” explicitly exits GUIDE. Click while a bubble is visible or being read: it and its leader must disappear immediately and speech must stop. Repeat outside GUIDE; no automatic next request should occur. Wait through the guidance speech: its complete text must be visible in a separate caption, alongside cursor guidance. Caption and pointer remain through speech and disappear five seconds later. Click before or after expiry to continue; the next pointer gets its own lifetime. New PTT must hide it immediately. Continue until the requested task is visibly complete.

# Required Configuration

Python 3.12 Windows environment with existing voice/openrouter extras, local STT model, microphone permission, OpenRouter key and internet. edge-tts and PyQt6 are already declared in the openrouter extra. No additional TTS key, environment variable or model download.

# Next Milestone

Stop for manual testing and user commit. No further development until instructed.

# Cursor adapter retained from test

The independent `python -m jarvis.cursor_guide --prompt-key` entry point remains
available alongside the newly merged main-app flow. Its full-image locator uses a
1920-pixel image limit and 0..1000 `[ymin, xmin, ymax, xmax]` coordinates, followed by
the existing Ion pointer movement. Experimental crop refinement is disabled after
manual regression feedback. Completion/repeat protection, bounded loading
rechecks, calibration, optional target inspection and key diagnostics remain.

The last adapter verification reported 27 focused tests passing before this merge;
this is not a claim that the merged application's combined suite has been rerun.
Live cursor accuracy remains a manual acceptance check. Earlier implementation
history and owner issues are documented in [CURSOR_TARGETING.md](CURSOR_TARGETING.md)
and [ION_REVIEW.md](ION_REVIEW.md). The old Part 5 'AI not connected' status is
superseded for the normal main application by the incoming milestone above.

# Documentation merge resolution

Resolved README, STATUS and ARCHITECTURE on `test`, preserving the incoming runtime
instructions and the separate cursor adapter's documentation. No application,
cursor, targeting or owner source was edited during conflict resolution. Test
commands/results above belong to their respective pre-merge milestones; this
resolution checks documentation and Git conflict state only. No commit created.
The requested cursor/location integration review remains separate work.

# Restored main-app pointer localization on test

- Reviewed the merged runtime changes against test's pre-merge cursor adapter.
  The main pointer worker already uses Ion's original drawing, movement and
  monitor mapping; the missing part was the independent target-location pass.
- Normal `python -m jarvis` now shares the earlier adapter's full-image locator:
  maximum 1920-pixel JPEG, explicit 0..1000 boxes and normalized coordinates.
  No crop-refinement pass or diagnostic window is enabled.
- Only eligible pointer targets are replaced. Existing TTS, callouts, captions,
  click dismissal, five-second pointer expiry, routing and GUIDE completion logic
  remain unchanged. Locator failure retains the answer and omits guessed pointers.
- Both requests remain cancellable under the existing overall deadline. The
  extra location request adds API cost and latency per pointer step.
- Verification: 137 tests passed on Windows outside the restricted sandbox,
  including nine new locator/transport regression tests. The initial sandbox run
  failed temporary-directory cleanup and native hotkey access. No paid API call
  or live Canva accuracy assessment was performed.
- Shared production files changed: `features/ai/openrouter.py` and
  `features/targeting/grounding.py`. Added `features/ai/pointer_location.py` and
  `tests/test_main_pointer_location.py`. Documentation changed: README, STATUS,
  ARCHITECTURE and CURSOR_TARGETING. CursorMain/Ion remains untouched. No commit.
- Manual check: exit the current Jarvis instance, run
  `.\.venv\Scripts\python.exe -B -m jarvis`, hold Ctrl+Shift+Space over the target
  application and request navigation. Verify the arrow tip identifies the named
  control, click to continue, and check explanations still use callouts and speech.
  Stop here for user review and manual commit.

# New task replaces previous guide goal

- Fixed old GUIDE context being attached to every non-explanation request.
  Canva guidance now yields to a request such as “Arată-mi cum să deschid
  internetul”; the previous step, loading counter and observer are reset.
- Whole-utterance contextual follow-ups such as “Și acum?” retain the goal.
  Unrecognized wording becomes a fresh request with retained conversation history.
  Direct navigation commands such as “Deschide internetul” route to GUIDE.
- Shared source changed in this part: `app.py`, `features/interaction/intent.py`
  and the provider's history instructions in `features/ai/openrouter.py`.
  Regression coverage added in `test_guide.py` and `test_visual_intent.py`.
  README, ARCHITECTURE and STATUS updated. No owner/STT, targeting or movement
  changes in this part. Branch remains `test`; no commit.
- Verification: all 140 tests passed on Windows, including goal replacement,
  fresh AUTO routing, follow-up classification, next-click context and stale
  response rejection. Live speech/model interpretation remains a manual check.
