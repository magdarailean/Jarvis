"""Romanian shell. No screen capture, microphone or AI services are active here."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

STYLE = """
QWidget { font-family: 'Segoe UI'; font-size: 15px; color: #172b43; }
QWidget#MainWindow { background: #f3f6fa; }
QLabel { background: transparent; }
QLabel#Title { font-size: 32px; font-weight: 600; }
QLabel#Welcome { font-size: 25px; font-weight: 600; }
QLabel#Status { color: #205c41; background: #e1f3ea; border-radius: 14px; padding: 7px 14px; font-weight: 600; }
QLabel#Muted { color: #52647a; }
QLabel#Body { color: #40546b; }
QLabel#Strong { font-weight: 600; }
QLabel#LifetimeHint { color: #52647a; font-size: 12px; }
QLabel#TrayError { color: #9c2727; }
QFrame#Card { background: white; border: 1px solid #dce3ec; border-radius: 12px; }
QFrame#Privacy { background: #eef4fc; border-radius: 8px; }
QScrollArea, QWidget#ScrollContent { background: transparent; border: none; }
QPushButton { padding: 10px 20px; min-height: 20px; font-size: 14px; }
"""


def text(value: str, name: str = "Body") -> QLabel:
    label = QLabel(value)
    label.setObjectName(name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return label


class MainWindow(QWidget):
    exit_requested = Signal()
    hidden_to_tray = Signal()
    overlay_demo_requested = Signal()
    overlay_clear_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._background_enabled = False
        self._allow_close = False
        self.setObjectName("MainWindow")
        self.setWindowTitle("Jarvis — Asistent și tutore")
        self.resize(720, 640)
        self.setMinimumSize(500, 480)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(22)

        header = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(5)
        title.addWidget(text("Jarvis", "Title"))
        title.addWidget(text("Asistent și tutore pentru desktop", "Muted"))
        header.addLayout(title, 1)
        self.status = text("● Gata", "Status")
        self.status.setAccessibleName("Gata")
        self.status.setWordWrap(False)
        header.addWidget(self.status, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("ScrollContent")
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(12)
        card_layout.addWidget(text("Bine ai venit!", "Welcome"))
        card_layout.addWidget(text(
            "Jarvis poate rămâne în fundal, lângă ceas. Pentru a reveni la această "
            "fereastră, fă dublu clic pe pictograma J sau pornește din nou aplicația."
        ))
        card_layout.addSpacing(8)
        privacy = QFrame()
        privacy.setObjectName("Privacy")
        privacy_layout = QVBoxLayout(privacy)
        privacy_layout.setContentsMargins(16, 16, 16, 16)
        privacy_layout.setSpacing(7)
        privacy_layout.addWidget(text("Tu alegi când începe asistența", "Strong"))
        privacy_layout.addWidget(text(
            "Acum microfonul este oprit, ecranul nu este capturat și nu se trimite "
            "nimic către servicii AI."
        ))
        card_layout.addWidget(privacy)
        body.addWidget(card)
        body.addWidget(text("Adnotări pe ecran · Demonstrație", "Strong"))
        body.addWidget(text(
            "Arată forme și un pas numerotat pe monitorul acestei ferestre. "
            "Poți apăsa și scrie în aplicațiile de sub adnotări. Formele sunt exemple fixe; "
            "conversațiile, comanda rapidă și explicațiile vocale nu sunt disponibile încă.", "Muted"
        ))
        self.overlay_demo_button = QPushButton("Arată demonstrația")
        self.overlay_demo_button.clicked.connect(self.overlay_demo_requested.emit)
        self.overlay_clear_button = QPushButton("Șterge adnotările")
        self.overlay_clear_button.clicked.connect(self.overlay_clear_requested.emit)
        body.addWidget(self.overlay_demo_button)
        body.addWidget(self.overlay_clear_button)
        self.overlay_feedback = text("Adnotările rămân până le ștergi sau închizi Jarvis.", "Muted")
        body.addWidget(self.overlay_feedback)
        self.tray_error = text("", "TrayError")
        self.tray_error.hide()
        body.addWidget(self.tray_error)
        body.addStretch(1)
        self.scroll.setWidget(content)
        root.addWidget(self.scroll, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.lifetime_hint = text("Alege Ieșire pentru a opri complet aplicația.", "LifetimeHint")
        footer.addWidget(self.lifetime_hint, 1)
        self.hide_button = QPushButton("Ascunde")
        self.hide_button.setObjectName("HideWindowButton")
        self.hide_button.setEnabled(False)
        self.hide_button.clicked.connect(self.hide_to_tray)
        self.exit_button = QPushButton("Ieșire")
        self.exit_button.setObjectName("ExitApplicationButton")
        self.exit_button.clicked.connect(self.exit_requested.emit)
        for button in (self.hide_button, self.exit_button):
            button.setAutoDefault(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            footer.addWidget(button)
        root.addLayout(footer)

        screen = self.screen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def enable_background_mode(self) -> None:
        self._background_enabled = True
        self.hide_button.setEnabled(True)
        self.lifetime_hint.setText("Butonul X ascunde fereastra. Ieșire oprește aplicația.")

    def show_tray_unavailable(self) -> None:
        self._background_enabled = False
        self.hide_button.setEnabled(False)
        self.tray_error.setText(
            "Pictograma de lângă ceas nu este disponibilă. Jarvis va rămâne în fereastră; "
            "închiderea ferestrei oprește aplicația."
        )
        self.tray_error.show()

    def prepare_exit(self) -> None:
        self._allow_close = True

    def hide_to_tray(self) -> None:
        if self._background_enabled:
            self.hide()
            self.hidden_to_tray.emit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._allow_close and self._background_enabled:
            event.ignore()
            self.hide_to_tray()
        else:
            event.accept()
            if not self._allow_close:
                self._allow_close = True
                self.exit_requested.emit()
