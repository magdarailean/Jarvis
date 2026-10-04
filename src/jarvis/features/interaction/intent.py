"""Deterministic Romanian routing, independent of Qt and provider output."""
from enum import Enum
import re
import unicodedata


class VisualIntent(str, Enum):
    GUIDE = "guide"
    EXPLAIN = "explain"
    AUTO = "auto"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def route_intent(text: str) -> VisualIntent:
    text = normalize(text)
    # Explicit understanding/solving wins, including mixed requests and
    # "explică-mi cum...". A bare "cum" is deliberately not a guide trigger.
    if re.search(r"\b(explica|explicami|explici|verifica|lamureste|clarifica|"
                 r"rezolv|rezolva|rezolvam|rezolvare|calculeaza|calculez|calculam)\b|\bde ce\b", text):
        return VisualIntent.EXPLAIN
    if re.search(r"\b(arata|aratami|arati|unde)\b|\bcum (?:sa |pot (?:sa )?|as putea (?:sa )?)?(?:deschid|deschide|intru|selectez|apas|"
                 r"accesez|gasesc|salvez|inchid|adaug|incarc|descarc|navighez|dau click)\b", text):
        return VisualIntent.GUIDE
    return VisualIntent.AUTO
