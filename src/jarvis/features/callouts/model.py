"""Validated semantic input. Coordinates are normalized to one monitor."""
from dataclasses import dataclass, replace
from enum import Enum
import math
import re


class VisualKind(str, Enum):
    NONE = "none"
    CALLOUT = "callout"
    POINTER = "pointer/cursor"
    ARROW = "arrow"
    HIGHLIGHT = "highlight"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    LINE = "line"


@dataclass(frozen=True)
class Callout:
    id: str
    text: str
    target: tuple[float, float, float, float] | None = None
    placement: str = "auto"
    visible: bool = True
    highlighted: bool = False
    temporary: bool = True

    def __post_init__(self):
        if not isinstance(self.id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", self.id):
            raise ValueError("Invalid callout ID")
        if not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 2000:
            raise ValueError("Callout text must contain 1–2000 characters")
        if self.placement not in ("auto", "right", "left", "above", "below"):
            raise ValueError("Invalid preferred placement")
        if any(type(flag) is not bool for flag in (self.visible, self.highlighted, self.temporary)):
            raise ValueError("Invalid lifecycle flags")
        if self.target is not None:
            if not isinstance(self.target, tuple) or len(self.target) != 4:
                raise ValueError("Expected normalized region or repeated point")
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in self.target):
                raise ValueError("Invalid coordinates")
            x1, y1, x2, y2 = self.target
            if x2 < x1 or y2 < y1:
                raise ValueError("Reversed region")


@dataclass(frozen=True)
class VisualAction:
    kind: VisualKind
    id: str = ""
    target: tuple[float, float, float, float] | None = None
    text: str = ""
    placement: str = "auto"

    def __post_init__(self):
        if not isinstance(self.kind, VisualKind):
            raise ValueError("Unknown visual action")
        if self.kind == VisualKind.NONE:
            return
        if self.kind == VisualKind.CALLOUT:
            self.callout  # Validate the semantic callout, without computing layout.
        elif self.kind == VisualKind.POINTER:
            if self.target is None:
                raise ValueError("Pointer needs a target")
            Callout(self.id, "target", self.target)
        else:
            self.annotation

    @property
    def callout(self):
        return Callout(self.id, self.text, self.target, self.placement)

    @property
    def annotation(self):
        from jarvis.features.overlay.model import Annotation, Shape
        shapes = {VisualKind.HIGHLIGHT: Shape.RECTANGLE, VisualKind.RECTANGLE: Shape.RECTANGLE,
                  VisualKind.CIRCLE: Shape.ELLIPSE, VisualKind.ARROW: Shape.ARROW, VisualKind.LINE: Shape.LINE}
        return Annotation(self.id, shapes[self.kind], self.target,
                          highlighted=self.kind == VisualKind.HIGHLIGHT)


@dataclass(frozen=True)
class VisualPlan:
    """Explanation survives malformed/unsupported visuals. No automatic bubbles.

    Wire format: {text: str, actions: [{type, id, text, target?, placement?}]}.
    Pointer actions are validated and forwarded to an independent consumer.
    An empty actions list (or type none) means no visual assistance.
    """
    text: str
    actions: tuple[VisualAction, ...] = ()

    @classmethod
    def parse(cls, payload):
        if not isinstance(payload, dict):
            return cls("")
        text = payload.get("text", "")
        result = []
        raw = payload.get("actions", [])
        if isinstance(raw, list):
            for item in raw[:32]:
                if not isinstance(item, dict):
                    continue
                try:
                    target = item.get("target")
                    result.append(VisualAction(VisualKind(item.get("type")), item.get("id", ""),
                                              tuple(target) if isinstance(target, list) else target,
                                              item.get("text", ""), item.get("placement", "auto")))
                except (ValueError, TypeError):
                    continue
        return cls(text if isinstance(text, str) else "", tuple(result))


class CalloutScene:
    MAX_ITEMS = 16

    def __init__(self):
        self._items = {}

    @property
    def items(self):
        return tuple(self._items.values())

    def upsert(self, item):
        if not isinstance(item, Callout):
            raise TypeError("Expected validated Callout")
        if item.id not in self._items and len(self._items) >= self.MAX_ITEMS:
            raise ValueError("Callout capacity reached")
        self._items[item.id] = item

    def highlight(self, identifier, enabled=True):
        if identifier in self._items:
            self.upsert(replace(self._items[identifier], highlighted=enabled))

    def remove(self, identifier):
        self._items.pop(identifier, None)

    def clear(self):
        self._items.clear()
