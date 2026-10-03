"""Composition root. All UI lifetime decisions run on the Qt application thread."""

import sys

from PySide6.QtCore import QLocale, QObject, Qt, Signal, Slot
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from jarvis.infrastructure.app_log import AppLog
from jarvis.infrastructure.single_instance import SingleInstance
from jarvis.infrastructure.tray import TrayIcon, create_icon
from jarvis.presentation.main_window import MainWindow


class DesktopController(QObject):
    activation_requested = Signal()

    def __init__(self, app: QApplication, *, instance_key: str | None = None,
                 tray_factory=TrayIcon, log: AppLog | None = None) -> None:
        super().__init__()
        self.app = app
        self.instance_key = instance_key
        self.tray_factory = tray_factory
        self.log = log or AppLog()
        self.window: MainWindow | None = None
        self.tray: TrayIcon | None = None
        self.instance: SingleInstance | None = None
        self.exit_code = 0
        self._closed = False
        self.activation_requested.connect(self.reopen_window, Qt.ConnectionType.QueuedConnection)
        app.setQuitOnLastWindowClosed(False)
        app.aboutToQuit.connect(self.close)
        app.commitDataRequest.connect(self.request_exit)

    def start(self) -> bool:
        self.log.write("Application starting; milestone=1; runtime=python; capture=false; microphone=false.")
        try:
            self.instance = SingleInstance(self.instance_key)
            if not self.instance.is_primary:
                self.instance.notify_primary()
                self.log.write("Existing instance notified; duplicate exiting.")
                self.close()
                return False
        except OSError as error:
            self.exit_code = 1
            self.log.write(f"Single-instance initialization failed; error={type(error).__name__}.")
            QMessageBox.critical(None, "Jarvis — Eroare",
                                 "Jarvis nu a putut verifica dacă aplicația este deja deschisă. Încearcă din nou.")
            self.close()
            return False

        self.window = MainWindow()
        self.window.setWindowIcon(create_icon())
        self.window.exit_requested.connect(self.request_exit)
        self.window.hidden_to_tray.connect(
            lambda: self.log.write("Main window hidden; tray remains active.")
        )
        try:
            self.tray = self.tray_factory(self.reopen_window, self.request_exit)
            self.window.enable_background_mode()
            self.log.write("Tray created; state=Ready.")
        except (OSError, RuntimeError) as error:
            self.log.write(f"Tray initialization failed; error={type(error).__name__}.")
            self.window.show_tray_unavailable()

        self.window.show()
        self.log.write("Main window loaded; state=Ready.")
        self.instance.listen(self.activation_requested.emit)
        return True

    @Slot()
    def reopen_window(self) -> None:
        if self._closed or self.window is None:
            return
        if self.window.isMinimized():
            self.window.showNormal()
        else:
            self.window.show()
        self.window.raise_()
        self.window.activateWindow()
        self.log.write("Main window reopened.")

    @Slot()
    def request_exit(self) -> None:
        if self._closed:
            return
        self.log.write("Explicit exit requested.")
        self.close()
        self.app.quit()

    @Slot()
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.window is not None:
            self.window.prepare_exit()
            self.window.close()
        if self.tray is not None:
            self.tray.close()
        if self.instance is not None:
            self.instance.close()
        self.log.write(f"Application stopped; exitCode={self.exit_code}.")


def create_application() -> QApplication:
    QLocale.setDefault(QLocale("ro_RO"))
    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis")
    app.setOrganizationName("Jarvis")
    app.setStyle("Fusion")
    # Preserve the existing light shell even when Windows uses dark controls.
    palette = app.style().standardPalette()
    for role, color in (
        (QPalette.ColorRole.Window, "#f3f6fa"),
        (QPalette.ColorRole.WindowText, "#172b43"),
        (QPalette.ColorRole.Base, "#ffffff"),
        (QPalette.ColorRole.Text, "#172b43"),
        (QPalette.ColorRole.Button, "#e0e0e0"),
        (QPalette.ColorRole.ButtonText, "#172b43"),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    return app


def main() -> int:
    app = create_application()
    controller = DesktopController(app)
    try:
        if not controller.start():
            return controller.exit_code
        return app.exec()
    finally:
        controller.close()
