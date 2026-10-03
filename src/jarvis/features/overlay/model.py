"""Bounded in-memory annotations in normalized, monitor-local coordinates."""

from dataclasses import dataclass, replace
from enum import Enum
import math
import re


class Shape(Enum):
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"
    ARROW = "arrow"
    LINE = "line"
    LABEL = "label"


@dataclass(frozen=True)
class Annotation:
    """Bounds are (left, top, right, bottom); lines/arrows use start/end instead.

    All coordinates are in [0, 1] relative to ONE target monitor. Text is plain
    text in the supplied bounds; it can include a numbered step. IDs survive
    replacement. Screenshot pixel conversion belongs to screen capture.
    """

    id: str
    shape: Shape
    bounds: tuple[float, float, float, float]
    text: str = ""
    visible: bool = True
    highlighted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", self.id):
            raise ValueError("Annotation ID must contain 1–64 letters, digits, dots, dashes or underscores")
        if not isinstance(self.shape, Shape):
            raise ValueError("Unknown annotation shape")
        if not isinstance(self.bounds, tuple) or len(self.bounds) != 4:
            raise ValueError("Bounds must be a tuple of four normalized coordinates")
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
               for v in self.bounds):
            raise ValueError("Coordinates must be finite numbers in [0, 1]")
        x1, y1, x2, y2 = self.bounds
        if self.shape in (Shape.LINE, Shape.ARROW):
            if (x1, y1) == (x2, y2):
                raise ValueError("A line needs distinct endpoints")
        elif x2 <= x1 or y2 <= y1:
            raise ValueError("Annotation bounds must have positive width and height")
        if not isinstance(self.text, str) or len(self.text) > 200:
            raise ValueError("Text must contain at most 200 characters")
        if self.shape == Shape.LABEL and not self.text.strip():
            raise ValueError("A label needs text")
        if type(self.visible) is not bool or type(self.highlighted) is not bool:
            raise ValueError("Visibility and highlight must be booleans")


class AnnotationScene:
    """Stable insertion order; upsert replaces by ID without accumulating shapes."""

    MAX_ANNOTATIONS = 64

    def __init__(self) -> None:
        self._items: dict[str, Annotation] = {}

    @property
    def annotations(self) -> tuple[Annotation, ...]:
        return tuple(self._items.values())

    def upsert(self, annotation: Annotation) -> None:
        if not isinstance(annotation, Annotation):
            raise TypeError("Expected a validated Annotation")
        if annotation.id not in self._items and len(self._items) >= self.MAX_ANNOTATIONS:
            raise ValueError("Annotation limit reached")
        self._items[annotation.id] = annotation

    def set_visible(self, annotation_id: str, visible: bool) -> None:
        self.upsert(replace(self._items[annotation_id], visible=visible))

    def highlight(self, annotation_id: str, enabled: bool = True) -> None:
        self.upsert(replace(self._items[annotation_id], highlighted=enabled))

    def remove(self, annotation_id: str) -> None:
        self._items.pop(annotation_id, None)

    def clear(self) -> None:
        self._items.clear()
