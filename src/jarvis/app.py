"""Composition root. All UI lifetime decisions run on the Qt application thread."""

import sys

from PySide6.QtCore import QLocale, QObject, Qt, Signal, Slot
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from jarvis.infrastructure.app_log import AppLog
from jarvis.infrastructure.single_instance import SingleInstance
from jarvis.infrastructure.tray import TrayIcon, create_icon
from jarvis.presentation.main_window import MainWindow
from jarvis.features.overlay.demo import demo_annotations
from jarvis.features.overlay.window import OverlayWindow
from jarvis.features.screen_capture.session import CaptureSession
from jarvis.features.session import Session


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
        self.overlay: OverlayWindow | None = None
        self.session = Session()
        self.capture = CaptureSession(self)
        self.capture.frame_changed.connect(self._capture_changed)
        self.capture.finished.connect(self._capture_finished)
        self.capture.failed.connect(self._capture_failed)
        self._capture_hidden = False
        self._overlay_was_visible = False
        self.exit_code = 0
        self._closed = False
        self.activation_requested.connect(self.reopen_window, Qt.ConnectionType.QueuedConnection)
        app.setQuitOnLastWindowClosed(False)
        app.aboutToQuit.connect(self.close)
        app.commitDataRequest.connect(self.request_exit)

    def start(self) -> bool:
        self.log.write("Application starting; feature=session; runtime=python; capture=idle; microphone=false.")
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
        self.window.overlay_demo_requested.connect(self.show_overlay_demo)
        self.window.overlay_clear_requested.connect(self.clear_overlay)
        self.window.capture_requested.connect(self.start_capture)
        self.window.capture_clear_requested.connect(self.capture.clear)
        self.window.session_panel.question_submitted.connect(self.submit_question)
        self.window.session_panel.end_requested.connect(self.end_session)
        self.window.session_panel.mode_changed.connect(self._session_mode_changed)
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

    def _session_mode_changed(self, mode) -> None:
        self.session.mode = mode

    @Slot(str)
    def submit_question(self, question: str) -> None:
        if self._closed or self.window is None:
            return
        panel = self.window.session_panel
        if self.capture.pending:
            panel.feedback.setText("Așteaptă finalizarea capturii înainte de a trimite întrebarea.")
            return
        annotations = ()
        frame = self.session.frame
        if frame is not None and self.overlay is not None:
            geometry = frame.geometry
            if self.overlay.geometry().getRect() == (
                geometry.left, geometry.top, geometry.logical_width, geometry.logical_height
            ):
                annotations = self.overlay.annotations
        try:
            request = self.session.begin(question, annotations)
        except (ValueError, RuntimeError) as error:
            # Validation messages are local, never provider exception details.
            panel.feedback.setText(str(error))
            return
        self.log.write("Typed interaction submitted; provider=unavailable.")
        self.session.fail(request.id, "AI nu este conectat încă. Întrebarea nu a fost trimisă unui serviciu AI.")
        panel.question.clear()
        panel.render(self.session)
        panel.feedback.setText("AI indisponibil · Întrebarea este păstrată doar în sesiunea curentă.")

    @Slot()
    def end_session(self) -> None:
        if self._closed:
            return
        self.session.end()
        self.clear_overlay()
        self.capture.clear()
        if self.window is not None:
            self.window.session_panel.reset(self.session)
        self._set_capture_status("Gata")
        self.log.write("Tutoring session ended; temporary context released.")

    @Slot()
    def start_capture(self) -> None:
        if self._closed or self.window is None or self.capture.pending:
            return
        try:
            self.capture.begin(self.window.screen())
        except (ValueError, RuntimeError) as error:
            self._capture_failed(type(error).__name__)
            return
        self.window.capture_button.setEnabled(False)
        self._set_capture_status("Captură în 3 secunde...")
        self._overlay_was_visible = self.overlay is not None and self.overlay.isVisible()
        self._capture_hidden = True
        self.window.hide()
        if self.overlay is not None:
            self.overlay.hide()
        self.log.write("Screen capture requested; one-shot=true.")

    def _set_capture_status(self, status: str) -> None:
        if self.window is not None:
            self.window.status.setText(f"● {status}")
            self.window.status.setAccessibleName(status)
        if self.tray is not None:
            self.tray.set_status(status)

    def _capture_changed(self, frame) -> None:
        self.session.set_frame(frame)
        if self.window is not None:
            self.window.show_capture(frame)
        self.log.write("Screen context acquired." if frame is not None else "Screen context released.")

    def _capture_finished(self) -> None:
        if self._closed or self.window is None:
            return
        if self._capture_hidden:
            self._capture_hidden = False
            self.window.show()
            if (self._overlay_was_visible and self.overlay is not None
                    and any(item.visible for item in self.overlay.annotations)):
                self.overlay.show()
        self.window.capture_button.setEnabled(True)
        self._set_capture_status("Gata")

    def _capture_failed(self, error_type: str) -> None:
        self._set_capture_status("Eroare")
        if self.window is not None:
            self.window.capture_feedback.setText(
                "Ecranul nu a putut fi capturat. Încearcă din nou pe un desktop deblocat."
            )
        self.log.write(f"Screen capture failed; error={error_type}.")

    @Slot()
    def show_overlay_demo(self) -> None:
        if self._closed or self.window is None or self.capture.pending:
            return
        self.clear_overlay()
        try:
            self.overlay = OverlayWindow(self.window.screen())
            for annotation in demo_annotations():
                self.overlay.upsert(annotation)
            self.window.overlay_feedback.setText(
                "Demonstrația este vizibilă. Ascunde Jarvis pentru a lucra în altă aplicație."
            )
            self.log.write("Overlay updated; source=static-demo.")
        except (RuntimeError, ValueError, OSError) as error:
            self.clear_overlay()
            self.window.overlay_feedback.setText(
                "Adnotările nu pot fi afișate acum. Încearcă din nou."
            )
            self.log.write(f"Overlay failed; error={type(error).__name__}.")

    @Slot()
    def clear_overlay(self) -> None:
        if self.overlay is not None:
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None
            self.log.write("Overlay cleared.")
        if self.window is not None:
            self.window.overlay_feedback.setText("Adnotările au fost șterse.")

    @Slot()
    def reopen_window(self) -> None:
        if self._closed or self.window is None:
            return
        if self.capture.pending:
            self.capture.clear()
            self.window.capture_feedback.setText("Captura a fost anulată.")
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
        self.session.end()
        self.capture.clear(notify_finished=False)
        self.clear_overlay()
        if self.window is not None:
            self.window.session_panel.reset(self.session)
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
