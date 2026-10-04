"""Completion, bounded loading and repeat protection outside the owner module."""
from copy import deepcopy
from difflib import SequenceMatcher
import json
import unicodedata


PROGRESS_PROMPT = """
PROGRESS CONTRACT (evaluate BEFORE selecting a target):
Return goal_state: achieved, in_progress, loading, or uncertain, and goal_evidence:
a short description of what is actually visible that supports that state.
For 'deschide internetul/browserul/Google/Chrome', interpret the minimal requested
outcome: the browser or requested Google page is visibly open. A non-maximized
browser is still open. Do not require maximizing, opening another tab or clicking
its taskbar icon again. If a particular website was requested, the browser alone
is NOT completion; the requested site must be visible. Do not invent extra tasks.
If the requested outcome is visible, goal_state achieved, status complete,
action none, target null. Say 'Gata' followed by a brief Romanian confirmation.
If a click has launched a window/page but it is still loading, use goal_state
loading, status blocked, action none, target null; do not repeat the launch click.
Use uncertain if evidence is insufficient. Never claim completion merely to avoid
repetition. previous_result must remain honest about the pending attempted action.
For each click include control_name (actual visible label or icon), action_purpose
(the specific intended effect), and page_context (current app/page/dialog).
Keep these identities consistent across rephrased instructions. Different steps
must describe different specific effects, e.g. next wizard page 2 vs page 3.
Do not repeat an effect already verified as succeeded unless the new screenshot
clearly shows it has been undone. Never relaunch an already visible application.
"""


def extend_schema(schema):
    schema = deepcopy(schema)
    fields = {"goal_state": {"type": "string", "enum": ["achieved", "in_progress", "loading", "uncertain"]}}
    fields.update({key: {"type": "string"} for key in (
        "goal_evidence", "control_name", "action_purpose", "page_context")})
    schema["properties"].update(fields)
    schema["required"].extend(fields)
    return schema


def identity(data):
    return {key: data.get(key, "") for key in ("control_name", "action_purpose", "page_context")}


def text_key(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c if c.isalnum() else " " for c in text
                            if not unicodedata.combining(c)).split())


def similar(a, b):
    a, b = text_key(a), text_key(b)
    # Different numbered wizard pages/steps must remain different effects.
    if [s for s in a.split() if s.isdigit()] != [s for s in b.split() if s.isdigit()]:
        return False
    return bool(a and b) and SequenceMatcher(None, a, b).ratio() >= .82


def same_effect(a, b):
    return (similar(a.get("control_name", ""), b.get("control_name", ""))
            and similar(a.get("action_purpose", ""), b.get("action_purpose", "")))


def repeated_effect(data, context):
    previous = list(context.get("verified_steps", []))
    pending = context.get("pending_attempt")
    if pending and data.get("previous_result") == "succeeded":
        previous.append(pending)
    if any(same_effect(item, data) for item in previous[-8:]):
        return True
    attempts = list(context.get("attempt_history", []))
    if pending and data.get("previous_result") in ("succeeded", "failed", "uncertain"):
        attempts.append(pending)
    recent = attempts[-4:]
    return ((len(recent) >= 2 and all(same_effect(item, data) for item in recent[-2:]))
            or (len(recent) == 4 and same_effect(recent[0], recent[2])
                and same_effect(recent[1], recent[3]) and same_effect(recent[2], data)))


def block(data, message):
    return dict(data, status="blocked", action="none", target=None,
                instruction=message, expected_result="")


def evaluate(response, context):
    data = json.loads(response)
    state = data.get("goal_state")
    evidence = data.get("goal_evidence", "")
    waiting = False
    if state not in ("achieved", "in_progress", "loading", "uncertain") or not isinstance(evidence, str) or not evidence.strip():
        data = block(data, "Nu pot confirma progresul. Reîmprospătează ecranul.")
    elif state == "achieved":
        if context.get("pending_attempt") and data.get("previous_result") != "succeeded":
            data = block(data, "Nu pot confirma că ultimul pas a reușit. Reîmprospătează ecranul.")
        else:
            data.update(status="complete", action="none", target=None,
                        instruction="Gata, sarcina este îndeplinită.", expected_result="")
    elif state == "loading":
        waiting = True
        data = block(data, "Aștept să se încarce pagina.")
    elif state == "uncertain" or data.get("status") == "complete":
        data = block(data, "Nu pot confirma finalizarea. Reîmprospătează ecranul.")
    elif data.get("status") == "action":
        if not all(isinstance(value, str) and value.strip() for value in identity(data).values()):
            data = block(data, "Nu pot identifica sigur controlul. Reîmprospătează ecranul.")
        elif repeated_effect(data, context):
            data = block(data, "Am oprit repetarea acestui pas. Reformulează dacă mai ai nevoie de ceva.")
    return json.dumps(data, ensure_ascii=False), waiting, identity(data)


def install_progress(owner):
    owner.SCHEMA = extend_schema(owner.SCHEMA)
    owner.GUIDE_PROMPT += PROGRESS_PROMPT

    class ProgressController(owner.GuideController):
        def __init__(self, *args, **kwargs):
            self.action_identity = {}
            self.loading_checks = 0
            super().__init__(*args, **kwargs)

        def action_data(self, decision):
            data = super().action_data(decision)
            return dict(data, **self.action_identity) if data is not None else None

        def accept_decision(self, token, decision):
            if token != self.generation or self.closing:
                return
            worker = self.sender()
            if getattr(worker, "awaiting_page", False):
                if self.loading_checks < 2:
                    self.loading_checks += 1
                    self.current = None
                    self.armed_at = float("inf")
                    self.reminder_timer.stop()
                    self.caption.hide()
                    self.output.stop()
                    self.pointer.resume_following()
                    self.set_state("settling")
                    self.explain("Aștept să se încarce pagina.")
                    self.settle_timer.start()
                    return  # Keep pending evidence until the next snapshot verifies it.
                decision = owner.Decision("blocked", "none",
                    "Pagina încă se încarcă. Apasă Control Shift Spațiu când este gata.",
                    "", "uncertain" if self.pending else "none", None)
            else:
                self.loading_checks = 0
            self.action_identity = getattr(worker, "action_identity", {})
            super().accept_decision(token, decision)

        def cancel_session(self):
            self.loading_checks = 0
            self.action_identity = {}
            super().cancel_session()

    owner.GuideController = ProgressController
