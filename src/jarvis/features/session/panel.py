"""Typed development fallback; no speech recognition or network calls."""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout,
)

from .model import AssistantMode, Session


class SessionPanel(QFrame):
    question_submitted = Signal(str)
    end_requested = Signal()
    mode_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Conversație · Introducere prin text")
        title.setObjectName("Strong")
        layout.addWidget(title)
        notice = QLabel(
            "Întrebarea, istoricul conversației și ultima captură disponibilă sunt trimise către OpenRouter. "
            "Răspunsurile și explicațiile vizuale rămân în sesiunea curentă."
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.mode = QComboBox()
        self.mode.setAccessibleName("Mod de asistență")
        for mode in AssistantMode:
            self.mode.addItem(mode.value, mode)
        self.mode.currentIndexChanged.connect(lambda _: self.mode_changed.emit(self.mode.currentData()))
        layout.addWidget(self.mode)
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setAccessibleName("Conversația temporară")
        self.history.setMinimumHeight(160)
        self.history.setMaximumHeight(220)
        layout.addWidget(self.history)
        self.question = QLineEdit()
        self.question.setMaxLength(Session.MAX_QUESTION_CHARS)
        self.question.setAccessibleName("Întrebarea ta")
        self.question.setPlaceholderText("De exemplu: Explică-mi problema aceasta.")
        self.question.returnPressed.connect(self.submit)
        layout.addWidget(self.question)
        self.send = QPushButton("Trimite întrebarea")
        self.send.clicked.connect(self.submit)
        layout.addWidget(self.send)
        self.feedback = QLabel("Sesiune goală · Cel mult 12 schimburi păstrate în memorie.")
        self.feedback.setTextFormat(Qt.TextFormat.PlainText)
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        self.end_button = QPushButton("Încheie sesiunea")
        self.end_button.clicked.connect(self.end_requested.emit)
        layout.addWidget(self.end_button)

    def submit(self) -> None:
        self.question_submitted.emit(self.question.text())

    def render(self, session: Session) -> None:
        blocks = []
        for turn in session.turns:
            context = "cu captură" if turn.frame_id else "fără captură"
            blocks.append(f"Tu · {turn.mode.value} · {context}\n{turn.question}")
            if turn.explanation is not None:
                blocks.append(f"Jarvis\n{turn.explanation}")
            elif turn.notice is not None:
                blocks.append(f"Stare serviciu\n{turn.notice}")
        if session.pending is not None:
            blocks.append(f"Tu\n{session.pending.question}\n\nPregătesc explicația...")
        self.history.setPlainText("\n\n".join(blocks))
        self.history.verticalScrollBar().setValue(self.history.verticalScrollBar().maximum())
        self.feedback.setText(f"{len(session.turns)} / {Session.MAX_TURNS} schimburi în memorie.")

    def reset(self, session: Session) -> None:
        self.question.clear()
        self.mode.setCurrentIndex(0)
        self.render(session)
        self.feedback.setText("Sesiunea a fost încheiată. Conversația și contextul au fost șterse.")
