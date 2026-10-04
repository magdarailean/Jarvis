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
    # Explicit pointing requests win even when explanation words also occur.
    if re.search(r"\b(arata|aratami|arati|unde)\b", text):
        return VisualIntent.GUIDE
    # Without pointing words, an explicit explanation remains an opt-out.
    # A bare "cum" is deliberately not a guide trigger.
    if re.search(r"\b(explica|explicami|explici|verifica|lamureste|clarifica|"
                 r"rezolv|rezolva|rezolvam|rezolvare|calculeaza|calculez|calculam)\b|\bde ce\b", text):
        return VisualIntent.EXPLAIN
    if re.search(r"\b(arata|aratami|arati|unde)\b|\bcum (?:(?:pot|as putea)(?: eu)? )?(?:sa (?:l |o )?)?(?:deschid|deschide|intru|selectez|apas|"
                 r"accesez|gasesc|salvez|inchid|inchide|adaug|incarc|descarc|navighez|dau click)\b", text):
        return VisualIntent.GUIDE
    # Creation workflows are UI guidance too. Qualify generic "fac" with an
    # editable artifact so homework such as "cum fac problema" stays semantic.
    creation = r"(?:prezentare|prezentarea|document|documentul|tabel|tabelul|slide|diapozitiva|proiect|proiectul|design|designul|formular|formularul|cont|contul|fisier|fisierul)"
    if re.search(r"\b(?:fac|face|creez|crea|creeaza|realizez|realiza) "
                 r"(?:(?:o|un|nou|noua|aceasta|acest) ){0,3}" + creation + r"\b", text):
        return VisualIntent.GUIDE
    return VisualIntent.AUTO
