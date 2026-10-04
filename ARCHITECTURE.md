# Architecture

Python 3.12 x64 / PySide6 desktop, Windows 10/11. Domain/session models are independent of Qt and concrete providers. Active state stays in memory. No database, .NET or continuous capture.

## Real runtime flow

Global shortcut hold → isolated read-only Ion recorder + one Qt screen capture → release → Romanian local STT → TutorRequest → DesktopController → asynchronous OpenRouterProvider → validated VisualPlan → session text + existing OverlayWindow. Requests include bounded history and current annotation/callout descriptions. Replies require a current request ID; cancellation, session end and stale context prevent late application.

New spoken requests inherit an active GUIDE goal only when the entire normalized
utterance matches a contextual follow-up in `interaction/intent.py`. Otherwise
the controller stops the old observer, clears its prior step/loading state and
routes the new question normally. New GUIDE requests start their own goal;
click-driven rechecks retain their explicit guide context. Conversation history
is retained, with provider instructions that old tasks cannot override the active
goal. This is bounded phrase matching, not a general semantic intent classifier;
unrecognized follow-up wording is sent as a fresh request with history.

`features/ai/openrouter.py` adapts the generic endpoint/auth/multimodal/strict JSON protocol from the owner's request_openrouter function into a PySide QtNetwork transport. It does not import the cursor companion or modify its provider. Its schema/prompt are for tutoring and VisualPlan, rather than the companion's cursor-specific decision format. One request, no paid retries, bounded response, 45-second inactivity timeout and controller 60-second deadline. No credentials/content logged. HTTP auth/credit/rate errors and malformed responses have Romanian feedback. Environment/.env configuration is unchanged.

## AI-selected visuals

The model decides semantically whether to request none, callout, pointer/cursor, highlight, arrow, rectangle, circle, line or combinations. There are no keyword routing rules and no automatic callout for every answer. The strict wire schema is `{text, actions:[{type,id,text,target,placement}]}`; target is a normalized monitor-local region/point, or arrow/line endpoints. Null target is accepted for unattached callouts/none. Invalid/unsupported actions are ignored individually. Text is committed independently before rendering, so an overlay failure cannot lose an answer.

The prompt prefers minimal relevant guidance, normally 0–3 short callouts, and requires a question-specific reason to exceed that guideline. No keyword rules or hard semantic truncation are used. Callouts are temporary by default: `callouts/timing.py` owns one single-shot Qt timer per overlay, uses monotonic deadlines for 20-second expiry and 16-ms updates only while text is revealing. Reveal completes within 1.2 seconds. The complete document layout stays fixed; a transparent text selection hides unrevealed glyphs (Qt UTF-16 cursor positions are handled). Removal/update/clear cancels or replaces the corresponding timing entry. Completed persistent entries need no timer.

The accepted push-to-talk path clears only temporary callouts before starting speech; it does not clear shape scenes or emit cursor-clear signals. Expiry never re-shows a surface hidden for capture. `Callout.temporary=False` is an internal future lifecycle option; AI-produced callouts currently always use temporary=True. Their answer text remains in conversation history after expiry. The retained isolated demo shares the same timing behavior.

`features/callouts/model.py`: immutable Callout, generalized VisualAction/VisualPlan, bounded CalloutScene. A semantic callout owns ID, text, target and its leader; no model-specified bubble geometry. `layout.py` measures content up to a maximum width, wraps text, tries preferred/right/left/above/below positions, protects the target and monitor bounds, and tries nearby alternatives to avoid other bubbles. No safe fit omits the visual. `window.py` retains the reusable painter and isolated test surface. Production `features/overlay/window.py` reuses that painter and scene inside the existing transparent input-transparent overlay. No automatic target rectangles or background window.

The main `DesktopController.accept_ai_response` is now called by the live provider completion. It validates request identity, retains text, matches the captured display and applies the plan. Session ending clears shapes/callouts/pointer; capture temporarily hides surfaces. Stable IDs replace prior visuals. Empty plans do not erase existing conversation annotations. Current visual descriptions are included in subsequent provider requests.

## Frozen cursor and Ion boundary

All CursorMain/Ion files remain read-only. `infrastructure/pointer_bridge.py` manages a separate process; `pointer_worker.py` imports the existing GuidePointer with bytecode disabled. It calls its public point_at API using the companion's existing center-to-monitor coordinate mapping, without modifying its drawing, animation or targeting. PyQt6 and PySide6 never share a process. Worker failure retains the textual answer. One pointer target at a time.

Ion uses the existing isolated worker and model functions; only outside-owner model discovery falls back to installed small when no explicit override/installed large-v3 exists. No first-use model download. No changes to owner microphone or cursor code.

## Limits and verification

Main-runtime speech uses replaceable `features/speech/SpeechService`, injected into DesktopController. A cancellable QProcess runs edge-tts Romanian Alina plus PyQt audio playback with in-memory audio. PyQt remains isolated from the main PySide UI. Speech starts after visual application, using only rendered callout text in the painter's order; GUIDE retains its spoken instruction. Spoken temporary callouts suspend expiry while synthesis/playback runs. Completion/failure releases them with a five-second deadline. Identity tokens prevent stale releases from affecting replaced/removed callouts; reveal timing is unchanged. Unspoken callouts retain their fallback lifetime. Romanian Alina uses +10% rate. PTT kills the worker without waiting; process identity rejects stale events. Timeouts/errors preserve visuals and history. The older companion's TTS remains separate. Captures are monitor-based and may become stale after scroll/window movement. Basic bubble collision avoidance does not optimize all arrows or protect every other callout's target. Tests cover request construction, hold/release delivery, validation, cancellation, timeout, history, transparency and rendering failure. Live provider, native pointer and normal STT warmup are tested separately without recording private audio. Optional developer callout demo is never part of the normal request flow.

## Optional cursor accuracy adapter retained on test

`python -m jarvis.cursor_guide` runs Ion's version 4 prototype in a separate PyQt6
process, outside the PySide6 shell. `features/targeting/grounding.py` adds a
framework-independent location request after planning and maps validated
`[ymin, xmin, ymax, xmax]` bounds on the explicit 0..1000 scale to normalized
screenshot coordinates. Optional `--inspect-target` shows only the latest encoded
image with both rectangles, clears on cancellation and hides before capture.
The owner still handles cropping,
monitor mapping, pointer animation, speech and request lifetime. The launcher
adapts the owner module in memory without editing CursorMain. Calibration uses
the real owner pointer on a synthetic grid. See CURSOR_TARGETING.md for coupling,
privacy, request costs and remaining accuracy limitations.

`targeting/progress.py` extends only the runtime planner contract with goal-state
evidence and control/effect identities. It intercepts loading responses without
consuming pending click evidence, schedules at most two rechecks through the
owner's existing single-shot settle timer, and blocks repeated effects independently
of exact screenshot hashes. Completion still requires model evidence and honest
pending-action verification. Experimental `refinement.py` is no longer connected
to the launcher after a reported rejection regression. Normal location uses the
full image only. Fixed diagnostic categories distinguish absent targets from
transport or response-validation failures without exposing request/response data.
No changes to owner source, STT, the main PySide6 shell, or idle capture behavior.

This adapter remains a separate entry point. The main runtime's VisualPlan
provider now shares `targeting/grounding.build_location_payload` and
`normalized_bounds` through `ai/pointer_location.py`. After the unchanged planning
request, an eligible pointer triggers a second cancellable Qt network request:
the same captured image, aspect-preserving JPEG at maximum edge 1920 and quality
85, and the pointer instruction without the planner's guessed coordinates.
Only the pointer target is replaced. Other visuals, explanation text, GUIDE
completion/loading decisions and existing confidence validation remain unchanged.
Location failures omit the pointer while retaining the answer. Both phases share
the existing overall request deadline; cancellation releases context and rejects
late replies. No crop refinement or new screenshot acquisition is introduced.
The pointer bridge still calls Ion's original `point_at` animation and maps the
normalized target center into the captured monitor's logical geometry exactly
once. Speech, captions, click dismissal and pointer expiry remain unchanged.
