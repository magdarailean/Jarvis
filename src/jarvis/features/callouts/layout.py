"""Qt logical-pixel layout; never sacrifice target visibility to fit text."""
from dataclasses import dataclass
import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QFont, QTextDocument, QTextOption

from .model import Callout

PAD = 16
MARGIN = 12
GAP = 28


def document(text, width):
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    font = QFont("Segoe UI")
    font.setPixelSize(17)
    doc.setDefaultFont(font)
    option = doc.defaultTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    doc.setDefaultTextOption(option)
    doc.setPlainText(text)
    doc.setTextWidth(width)
    return doc


@dataclass
class CalloutLayout:
    bubble: QRectF
    target: QRectF | None
    start: QPointF | None
    end: QPointF | None
    text: QTextDocument


def arrange(item: Callout, width: float, height: float, occupied=()):
    if width <= 2 * MARGIN or height <= 2 * MARGIN:
        return None
    screen = QRectF(MARGIN, MARGIN, width - 2 * MARGIN, height - 2 * MARGIN)
    target = None
    if item.target is not None:
        x1, y1, x2, y2 = item.target
        target = QRectF(x1 * width, y1 * height, (x2-x1) * width, (y2-y1) * height)
    sides = ["right", "left", "above", "below"]
    if item.placement != "auto":
        sides.remove(item.placement)
        sides.insert(0, item.placement)
    for side in sides:
        area = QRectF(screen)
        if target is not None:
            if side == "right":
                area.setLeft(max(screen.left(), target.right() + GAP))
            elif side == "left":
                area.setRight(min(screen.right(), target.left() - GAP))
            elif side == "above":
                area.setBottom(min(screen.bottom(), target.top() - GAP))
            else:
                area.setTop(max(screen.top(), target.bottom() + GAP))
        if area.width() < 180 or area.height() < 60:
            continue
        natural = document(item.text, -1).idealWidth() + 2 * PAD
        bubble_width = min(max(96, math.ceil(natural)), 360, area.width())
        doc = document(item.text, bubble_width - 2 * PAD)
        bubble_height = math.ceil(doc.size().height()) + 2 * PAD
        if bubble_height > area.height():
            continue
        center = target.center() if target is not None else screen.center()
        x = min(max(center.x() - bubble_width/2, area.left()), area.right()-bubble_width)
        y = min(max(center.y() - bubble_height/2, area.top()), area.bottom()-bubble_height)
        if target is not None:
            if side == "right": x = area.left()
            elif side == "left": x = area.right() - bubble_width
            elif side == "above": y = area.bottom() - bubble_height
            else: y = area.top()
        bubble = QRectF(x, y, bubble_width, bubble_height)
        if any(bubble.intersects(other) for other in occupied):
            candidates = []
            for other in occupied:
                for offset in (-1, 1):
                    candidate = QRectF(bubble)
                    if side in ("left", "right"):
                        candidate.moveTop(other.top()-bubble_height-8 if offset < 0 else other.bottom()+8)
                    else:
                        candidate.moveLeft(other.left()-bubble_width-8 if offset < 0 else other.right()+8)
                    if area.contains(candidate) and not any(candidate.intersects(r) for r in occupied):
                        candidates.append(candidate)
            if not candidates:
                continue
            bubble = min(candidates, key=lambda r: (r.center()-center).manhattanLength())
        start = end = None
        if target is not None:
            if side in ("right", "left"):
                sy = min(max(center.y(), bubble.top()+12), bubble.bottom()-12)
                start = QPointF(bubble.left() if side == "right" else bubble.right(), sy)
                end = QPointF(target.right() if side == "right" else target.left(), center.y())
            else:
                sx = min(max(center.x(), bubble.left()+12), bubble.right()-12)
                start = QPointF(sx, bubble.bottom() if side == "above" else bubble.top())
                end = QPointF(center.x(), target.top() if side == "above" else target.bottom())
        return CalloutLayout(bubble, target, start, end, doc)
    # No safe fit: caller retains answer/state, but suppresses this visual.
    return None
