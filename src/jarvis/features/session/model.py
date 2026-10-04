"""In-memory conversation ownership and response identity checks; no I/O or Qt."""

from dataclasses import dataclass, field, replace
from enum import Enum
from uuid import uuid4

from jarvis.features.overlay import Annotation
from jarvis.features.screen_capture import ScreenFrame
from jarvis.features.interaction.intent import route_intent, VisualIntent


class AssistantMode(Enum):
    EXPLAIN = "Explică"
    SOLVE = "Rezolvă și explică"
    TUTOR = "Îndrumă-mă să găsesc răspunsul"
    GUIDE = "Arată-mi pașii în aplicație"


@dataclass(frozen=True)
class Turn:
    question: str
    mode: AssistantMode
    frame_id: str | None
    explanation: str | None = None
    notice: str | None = None  # Local service feedback, never an AI answer.


@dataclass(frozen=True)
class TutorRequest:
    id: str
    session_id: str
    question: str
    mode: AssistantMode
    history: tuple[Turn, ...]
    frame: ScreenFrame | None = field(repr=False)
    annotations: tuple[Annotation, ...] = ()

    guide_context: dict | None = None

    @property
    def visual_intent(self):
        return VisualIntent.GUIDE if self.guide_context is not None else route_intent(self.question)


class Session:
    MAX_TURNS = 12
    MAX_HISTORY_CHARS = 96_000
    MAX_QUESTION_CHARS = 2_000
    MAX_EXPLANATION_CHARS = 12_000

    def __init__(self) -> None:
        self.id = uuid4().hex
        self.mode = AssistantMode.EXPLAIN
        self._turns: list[Turn] = []
        self._frame: ScreenFrame | None = None
        self._pending: TutorRequest | None = None

    @property
    def turns(self) -> tuple[Turn, ...]:
        return tuple(self._turns)

    @property
    def pending(self) -> TutorRequest | None:
        return self._pending

    @property
    def frame(self) -> ScreenFrame | None:
        return self._frame

    def set_frame(self, frame: ScreenFrame | None) -> None:
        """Replacing/releasing visual context invalidates any unfinished response."""
        if frame is not None and not isinstance(frame, ScreenFrame):
            raise TypeError("Expected a screen frame")
        self._pending = None
        self._frame = frame

    def begin(self, question: str, annotations: tuple[Annotation, ...] = (), *, guide_context=None) -> TutorRequest:
        if self._pending is not None:
            raise RuntimeError("A turn is already pending")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Scrie o întrebare înainte de a trimite.")
        if len(question) > self.MAX_QUESTION_CHARS:
            raise ValueError("Întrebarea poate avea cel mult 2000 de caractere.")
        if not isinstance(self.mode, AssistantMode):
            raise ValueError("Invalid assistant mode")
        if (not isinstance(annotations, tuple) or len(annotations) > 64
                or any(not isinstance(item, Annotation) for item in annotations)
                or len({item.id for item in annotations}) != len(annotations)):
            raise ValueError("Invalid annotation snapshot")
        request = TutorRequest(
            uuid4().hex, self.id, question.strip(), self.mode,
            tuple(turn for turn in self._turns if turn.explanation is not None),
            self._frame, annotations, guide_context,
        )
        self._pending = request
        return request

    def set_guide_context(self, request_id, context):
        """Keep dispatched routing and response validation on the same request."""
        if not self._matches(request_id):
            raise ValueError("Request is no longer pending")
        self._pending = replace(self._pending, guide_context=context)
        return self._pending

    def complete(self, request_id: str, explanation: str) -> bool:
        if not self._matches(request_id):
            return False
        if (not isinstance(explanation, str) or not explanation.strip()
                or len(explanation) > self.MAX_EXPLANATION_CHARS):
            raise ValueError("Invalid explanation")
        self._finish(explanation=explanation.strip())
        return True

    def fail(self, request_id: str, notice: str) -> bool:
        if not self._matches(request_id):
            return False
        if not isinstance(notice, str) or not notice.strip() or len(notice) > 500:
            raise ValueError("Invalid service notice")
        self._finish(notice=notice.strip())
        return True

    def _matches(self, request_id: str) -> bool:
        return self._pending is not None and self._pending.id == request_id

    def _finish(self, *, explanation: str | None = None, notice: str | None = None) -> None:
        request = self._pending
        self._turns.append(Turn(request.question, request.mode,
                                request.frame.id if request.frame else None, explanation, notice))
        self._pending = None
        while len(self._turns) > self.MAX_TURNS or sum(
            len(turn.question) + len(turn.explanation or "") + len(turn.notice or "")
            for turn in self._turns
        ) > self.MAX_HISTORY_CHARS:
            self._turns.pop(0)

    def end(self) -> None:
        """Start a fresh identity, dropping history, in-flight state and screen references."""
        self.id = uuid4().hex
        self.mode = AssistantMode.EXPLAIN
        self._turns.clear()
        self._pending = None
        self._frame = None
