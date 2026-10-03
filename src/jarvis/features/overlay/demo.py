"""Static review fixture, never inferred from or aligned to captured content."""

from .model import Annotation, Shape


def demo_annotations() -> tuple[Annotation, ...]:
    return (
        Annotation("demo-heading", Shape.LABEL, (0.08, 0.08, 0.53, 0.16),
                   "Demonstrație Jarvis · Nu se capturează ecranul"),
        Annotation("demo-box", Shape.RECTANGLE, (0.12, 0.25, 0.40, 0.45)),
        Annotation("demo-circle", Shape.ELLIPSE, (0.55, 0.25, 0.73, 0.50)),
        Annotation("demo-arrow", Shape.ARROW, (0.44, 0.60, 0.29, 0.47), highlighted=True),
        Annotation("demo-line", Shape.LINE, (0.55, 0.55, 0.78, 0.55)),
        Annotation("demo-step", Shape.LABEL, (0.35, 0.64, 0.76, 0.74),
                   "1. Poți lucra în continuare sub adnotări."),
    )
