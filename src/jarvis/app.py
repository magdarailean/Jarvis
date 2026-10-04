"""Composition root. All UI lifetime decisions run on the Qt application thread."""

import sys
import os
from dataclasses import replace

from PySide6.QtCore import QLocale, QObject, Qt, Signal, Slot, QTimer
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
from jarvis.features.hotkey.windows import GlobalHotkey
from jarvis.features.voice_input.ion_adapter import IonAdapter
from jarvis.features.interaction.controller import InteractionController
from jarvis.features.interaction.intent import VisualIntent
from jarvis.features.interaction.guide import GuideSession
from jarvis.features.interaction.desktop import StatusIndicator, foreground_screen
from jarvis.features.callouts.model import VisualPlan
from jarvis.features.ai.openrouter import OpenRouterProvider
from jarvis.infrastructure.pointer_bridge import PointerBridge


class DesktopController(QObject):
    activation_requested = Signal()
    pointer_requested = Signal(object)  # Cursor teammate's consumer boundary.
    answer_ready = Signal(str)  # Text survives visual failures; future TTS consumer.

    def __init__(self, app: QApplication, *, instance_key: str | None = None,
                 tray_factory=TrayIcon, log: AppLog | None = None, enable_voice=False,
                 background=False, voice_only=False, voice_factory=IonAdapter, hotkey_factory=GlobalHotkey,
                 provider_factory=OpenRouterProvider) -> None:
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
        self.guide = GuideSession(self)
        self.guide_capture = CaptureSession(self)
        self.guide.changed.connect(self._guide_input)
        self.guide.inspect.connect(self._guide_capture)
        self.guide_capture.frame_changed.connect(self._guide_frame)
        self.guide_capture.failed.connect(lambda _: self._guide_stop("Captura a eșuat. Repetă cererea vocală."))
        self.pointer_bridge = PointerBridge(self)
        self.pointer_requested.connect(self._show_pointer)
        self.pointer_bridge.failed.connect(self._pointer_failed)
        self.pointer_bridge.shown.connect(lambda: self.log.write("visual.pointer = shown"))
        self.provider = provider_factory(self)
        self.provider.succeeded.connect(self._ai_complete)
        self.provider.failed.connect(self._ai_failed)
        self.provider.diagnostic.connect(
            lambda identifier, details: self.log.write(f"AI diagnostic; request={identifier}; {details}."))
        self._ai_pending = None
        self._ai_tick = 0
        self._ai_progress = QTimer(self)
        self._ai_progress.setInterval(400)
        self._ai_progress.timeout.connect(self._animate_ai)
        self._ai_deadline = QTimer(self)
        self._ai_deadline.setSingleShot(True)
        self._ai_deadline.timeout.connect(self._ai_timeout)
        self.capture = CaptureSession(self)
        self.capture.frame_changed.connect(self._capture_changed)
        self.capture.finished.connect(self._capture_finished)
        self.capture.failed.connect(self._capture_failed)
        self._capture_hidden = False
        self._overlay_was_visible = False
        self.exit_code = 0
        self._closed = False
        self.enable_voice = enable_voice
        self.background = background
        self.voice_only = voice_only
        self.voice_factory = voice_factory
        self.hotkey_factory = hotkey_factory
        self.interaction = self.hotkey = self.indicator = None
        self._voice_screen = None
        self._voice_capture_hidden = False
        self._voice_overlay_visible = False
        self._voice_status = "Gata"
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

        if not self.voice_only:
            self.window = MainWindow()
            self.window.setWindowIcon(create_icon())
            self.window.exit_requested.connect(self.request_exit)
            self.window.overlay_demo_requested.connect(self.show_overlay_demo)
            self.window.overlay_clear_requested.connect(self.clear_overlay)
            self.window.capture_requested.connect(self.start_capture)
            self.window.capture_clear_requested.connect(self.release_capture)
            self.window.session_panel.question_submitted.connect(self.submit_question)
            self.window.session_panel.end_requested.connect(self.end_session)
            self.window.session_panel.mode_changed.connect(self._session_mode_changed)
            self.window.hidden_to_tray.connect(
                lambda: self.log.write("Main window hidden; tray remains active.")
            )
        try:
            self.tray = self.tray_factory(None if self.voice_only else self.reopen_window, self.request_exit)
            if self.window is not None:
                self.window.enable_background_mode()
            self.log.write("Tray created; state=Ready.")
        except (OSError, RuntimeError) as error:
            self.log.write(f"Tray initialization failed; error={type(error).__name__}.")
            if self.window is not None:
                self.window.show_tray_unavailable()

        if self.enable_voice:
            self._start_voice_pipeline()
        if self.window is not None and (not self.background or self.tray is None):
            self.window.show()
        self.log.write(f"Runtime ready; voice_only={self.voice_only}; state=Ready; pid={os.getpid()}; visual_pipeline=5.")
        self.instance.listen(self.activation_requested.emit)
        return True

    def _start_voice_pipeline(self):
        self.indicator = StatusIndicator()
        voice = self.voice_factory(self)
        self.interaction = InteractionController(self.session, voice, self)
        if self.window is not None:
            self.interaction.capture.frame_changed.connect(self.window.show_capture)
        self.interaction.state_changed.connect(self._voice_state)
        self.interaction.failed.connect(self._voice_failed)
        self.interaction.prepared.connect(self._voice_prepared)
        self.interaction.capture_started.connect(self._hide_for_voice_capture)
        self.interaction.capture_finished.connect(self._restore_after_voice_capture)
        voice.ready.connect(lambda: self._voice_state("Gata", False))
        try:
            self.hotkey = self.hotkey_factory(self.app, os.environ.get("JARVIS_HOTKEY", "Ctrl+Shift+Space"))
            if self.window is not None:
                self.window.activation_hint.setText(
                    f"Ține apăsat {os.environ.get('JARVIS_HOTKEY', 'Ctrl+Shift+Space')} în aplicația ta, "
                    "vorbește și eliberează. Întrebarea și captura sunt trimise către OpenRouter."
                )
            self.hotkey.pressed.connect(self._push_to_talk)
            self.hotkey.released.connect(self.interaction.release)
            self.hotkey.start()
        except (OSError, ValueError) as error:
            self._voice_failed("Comanda rapidă nu este disponibilă. Verifică JARVIS_HOTKEY sau altă aplicație.")
            self.log.write(f"Hotkey registration failed; error={type(error).__name__}.")
            return
        if self.tray is not None:
            action = self.tray.menu.addAction("Încheie sesiunea")
            action.triggered.connect(self.end_session)
        self._voice_state("Pregătesc serviciul vocal...", False)
        voice.warmup()
        self.log.write("Global push-to-talk registered; voice initialization requested.")

    def _push_to_talk(self):
        if self._closed or self.interaction.active or self.capture.pending:
            return
        self._guide_stop()
        if self.overlay is not None:
            self.overlay.clear_temporary_callouts()
        self._cancel_ai()
        if self.capture.frame is not None:
            self.capture.clear()
        self._voice_screen = foreground_screen(self.app)
        annotations = ()
        if self.overlay is not None and self.overlay.screen() is self._voice_screen:
            annotations = self.overlay.annotations
        self.interaction.press(self._voice_screen, annotations)

    def _hide_for_voice_capture(self):
        self.pointer_bridge.hide()
        self._voice_capture_hidden = True
        self._voice_overlay_visible = self.overlay is not None and self.overlay.isVisible()
        if self.window is not None:
            self.window.hide()
        self.indicator.hide()
        if self.overlay is not None:
            self.overlay.hide()

    def _restore_after_voice_capture(self):
        if self._voice_capture_hidden:
            self._voice_capture_hidden = False
            if (not self._closed and self._voice_overlay_visible and self.overlay is not None
                    and self.overlay.has_visuals):
                self.overlay.show()
            if not self._closed:
                self.indicator.display(self._voice_status, foreground_screen(self.app))
        # The main window stays hidden; the user remains in their application.

    def _voice_state(self, status, microphone):
        if self._closed:
            return
        self._voice_status = status
        if self.window is not None:
            self.window.session_panel.render(self.session)
        self._set_capture_status(status)
        if self.tray is not None:
            self.tray.set_status(status, microphone)
        if self.indicator is not None and not self._voice_capture_hidden:
            self.indicator.display(status, foreground_screen(self.app))
        self.log.write(f"Interaction state changed; microphone={microphone}.")

    def _voice_failed(self, message):
        if self._closed:
            return
        self._voice_state("Eroare", False)
        if self.window is not None:
            self.window.session_panel.feedback.setText(message)
        self.indicator.display(message, foreground_screen(self.app))
        self.log.write("Voice interaction failed; see local configuration and device status.")

    def _voice_prepared(self, request):
        if self.window is not None:
            self.window.session_panel.render(self.session)
            self.window.show_capture(request.frame)
        self._submit_ai(request)

    def _guide_stop(self, notice=None):
        self.guide.stop()
        self.guide_capture.clear(notify_finished=False)
        self.pointer_bridge.hide()
        if notice:
            self._ai_status(notice)

    def _guide_input(self):
        # Any click invalidates an in-flight prediction, even outside the target.
        self.pointer_bridge.hide()
        self._cancel_ai()
        self.guide_capture.clear(notify_finished=False)

    def _guide_capture(self):
        if not self.guide.active or self._closed:
            return
        self._guide_input()
        if self.indicator is not None:
            self.indicator.hide()
        if self.overlay is not None:
            self.overlay.hide()
        try:
            self.guide_capture.begin(foreground_screen(self.app), delay_ms=100)
        except (ValueError, RuntimeError, OSError):
            self._guide_stop("Monitorul nu este disponibil. Repetă cererea vocală.")

    def _guide_frame(self, frame):
        if frame is None or not self.guide.active or self._closed:
            return
        self.session.set_frame(frame)
        context = self.guide.context(frame)
        self.log.write(f"Guide screen rechecked; unchanged={context['screen_unchanged']}.")
        request = self.session.begin(self.guide.goal, guide_context=context)
        self._submit_ai(request)

    def _guide_result(self, payload, plan):
        status = payload.get("guide_status") if isinstance(payload, dict) else None
        pointers = [a for a in plan.actions if a.kind.value == "pointer/cursor"]
        self.log.write(f"Guide decision; status={status if status in ('next', 'wait', 'complete', 'blocked') else 'invalid'}.")
        if (status == "complete" and payload.get("actions") == []
                and isinstance(payload.get("completion_evidence"), str)
                and payload["completion_evidence"].strip()):
            self.log.write("Guide completed; visible evidence supplied.")
            self._guide_stop("Gata")
            return False
        if status == "next" and len(pointers) == 1:
            self.guide.previous_step = plan.text
            self.guide.waits = 0
            self._ai_status("Urmează indicatorul · " + plan.text[:240])
            return True
        if status == "wait" and not pointers and self.guide.wait_for_screen():
            self._ai_status("Aștept actualizarea ecranului...")
            return False
        # Keep the goal while awaiting a user correction; do not spend requests
        # indefinitely on loading screens or invent an unsafe next target.
        self.pointer_bridge.hide()
        self.guide.settle.stop()
        self._ai_status("Ghidare în așteptare · " + (plan.text[:240] or "Corectează ecranul sau repetă cererea vocală."))
        return False

    def _ai_status(self, text):
        if self.indicator is not None:
            self._voice_state(text, False)
        else:
            self._set_capture_status(text)

    def _show_pointer(self, action):
        if self.overlay is not None:
            self.pointer_bridge.show(action, self.overlay.screen())

    def _pointer_failed(self, message):
        if self.guide.active:
            self._guide_stop()
        self.log.write("Pointer adapter unavailable; answer retained.")
        if self.window is not None:
            self.window.session_panel.feedback.setText(message)
        if self.indicator is not None:
            self.indicator.display(message, foreground_screen(self.app))

    def _animate_ai(self):
        self._ai_tick += 1
        self._ai_status(("Verific următorul pas" if self.guide.active else "Pregătesc explicația") + "." * (1 + self._ai_tick % 3))

    def _submit_ai(self, request):
        if request.guide_context is None and self.guide.active:
            self._guide_stop()
        if request.visual_intent == VisualIntent.GUIDE and not self.guide.active and request.frame is not None:
            self.guide.start(request.question)
            if self.overlay is not None:
                self.overlay.clear_temporary_callouts()
            request = replace(request, guide_context=self.guide.context(request.frame))
        self._ai_pending = request.id
        self.log.write(f"visual.intent = {request.visual_intent.value}")
        if request.visual_intent == VisualIntent.EXPLAIN:
            self.pointer_bridge.hide()
        visuals = []
        if self.overlay is not None:
            for item in self.overlay.callouts:
                visuals.append(dict(type="callout", id=item.id, text=item.text, target=item.target))
            for item in self.overlay.annotations:
                visuals.append(dict(type=item.shape.value, id=item.id, target=item.bounds, text=item.text))
        self._ai_progress.start()
        self._ai_deadline.start(60000)
        self._animate_ai()
        self.log.write(f"AI request dispatched; request={request.id}; screenshot={request.frame is not None}.")
        try:
            self.provider.send(request, visuals)
        except (ValueError, RuntimeError, OSError):
            self._ai_failed(request.id, "Cererea AI nu a putut fi trimisă. Verifică configurarea OpenRouter.")

    def _stop_ai_timers(self):
        self._ai_progress.stop()
        self._ai_deadline.stop()
        self._ai_pending = None

    def _cancel_ai(self):
        identifier = self._ai_pending
        self._stop_ai_timers()
        self.provider.cancel()
        if identifier:
            self.session.fail(identifier, "Cererea AI a fost anulată.")

    def _ai_timeout(self):
        identifier = self._ai_pending
        self.provider.cancel()
        if identifier:
            self._ai_failed(identifier, "OpenRouter a depășit timpul de așteptare. Încearcă din nou.")

    @Slot(str, str)
    def _ai_failed(self, identifier, message):
        if self._closed or identifier != self._ai_pending:
            return
        self._stop_ai_timers()
        self._guide_stop()
        if self.session.fail(identifier, message):
            if self.window is not None:
                self.window.session_panel.render(self.session)
                self.window.session_panel.feedback.setText(message)
            self._ai_status("Eroare")
            if self.indicator is not None:
                self.indicator.display(message, foreground_screen(self.app))
        self.log.write(f"AI request failed; request={identifier}.")

    @Slot(str, object)
    def _ai_complete(self, identifier, payload):
        if self._closed or identifier != self._ai_pending:
            return
        self._stop_ai_timers()
        was_guiding = self.guide.active
        accepted = self.accept_ai_response(identifier, payload)
        if not accepted:
            if was_guiding:
                self._guide_stop("Răspunsul nu a putut fi verificat. Repetă cererea vocală.")
            self.session.fail(identifier, "Răspunsul AI nu a putut fi acceptat.")
            if self.window is not None:
                self.window.session_panel.render(self.session)
        if not was_guiding and not self.guide.active:
            self._ai_status("Gata" if accepted else "Eroare")
        self.log.write(f"AI response received; request={identifier}; accepted={accepted}.")

    @Slot(str, object)
    def accept_ai_response(self, request_id, payload):
        """GUI-thread completion boundary for the live provider transport.

        The request's captured monitor determines placement. No demo targets,
        screenshot inference, provider call, or cursor implementation lives here.
        """
        request = self.session.pending
        if self._closed or request is None or request.id != request_id:
            return False
        plan = VisualPlan.parse(payload, intent=request.visual_intent, require_grounding=True)
        self.log.write(f"Visual plan validated; intent={request.visual_intent.value}; "
                       f"pointers={sum(a.kind.value == 'pointer/cursor' for a in plan.actions)}; "
                       f"callouts={sum(a.kind.value == 'callout' for a in plan.actions)}.")
        try:
            if not self.session.complete(request_id, plan.text):
                return False
        except ValueError:
            return False
        if self.window is not None:
            self.window.session_panel.render(self.session)
        self.answer_ready.emit(plan.text)
        self._set_capture_status("Gata")
        if (not self.guide.active and request.visual_intent == VisualIntent.AUTO
                and request.frame is not None
                and any(a.kind.value == "pointer/cursor" for a in plan.actions)):
            # Semantic AUTO may select a cursor too; lock all following steps to GUIDE.
            self.guide.start(request.question)
            self.guide.context(request.frame)
            plan = VisualPlan.parse(payload, intent=VisualIntent.GUIDE, require_grounding=True)
            payload = {**payload, "guide_status": "next"}
        if self.guide.active:
            if not self._guide_result(payload, plan):
                return True
        if request.visual_intent == VisualIntent.EXPLAIN:
            self.pointer_bridge.hide()
        if self.overlay is not None and (self.guide.active or request.visual_intent != VisualIntent.AUTO):
            self.overlay.clear_temporary_callouts()
        if request.frame is None or not any(action.kind.value != "none" for action in plan.actions):
            return True
        geometry = request.frame.geometry
        screen = next((screen for screen in self.app.screens()
                       if screen.name() == geometry.monitor_name
                       and screen.geometry().getRect() == (geometry.left, geometry.top,
                           geometry.logical_width, geometry.logical_height)
                       and abs(screen.devicePixelRatio()-geometry.device_pixel_ratio) < .001), None)
        if screen is None:
            if self.guide.active:
                self._guide_stop("Monitorul s-a schimbat. Repetă cererea vocală.")
            self.log.write("Visual plan skipped; captured display no longer matches.")
            return True
        try:
            if self.overlay is None or self.overlay.screen() is not screen:
                self.clear_overlay()
                self.overlay = OverlayWindow(screen)
                self.overlay.pointer_requested.connect(self.pointer_requested.emit)
                self.overlay.pointer_cleared.connect(self.pointer_bridge.close)
            self.overlay.apply_visual_plan(plan)
            self.log.write("Visual plan applied; source=response.")
        except (RuntimeError, ValueError, OSError):
            if self.guide.active:
                self._guide_stop("Indicatorul nu a putut fi afișat. Repetă cererea vocală.")
            self.log.write("Visual rendering failed; textual answer retained.")
        return True

    def _session_mode_changed(self, mode) -> None:
        self.session.mode = mode

    @Slot()
    def release_capture(self):
        self._cancel_ai()
        if self.interaction is not None:
            self.interaction.reset()
            self._voice_state("Gata", False)
        self.capture.clear()

    @Slot(str)
    def submit_question(self, question: str) -> None:
        if self._closed or self.window is None:
            return
        panel = self.window.session_panel
        if self._ai_pending:
            panel.feedback.setText("Așteaptă răspunsul AI sau încheie sesiunea.")
            return
        if self.interaction is not None:
            if self.interaction.active:
                panel.feedback.setText("Interacțiunea vocală este în curs.")
                return
            self.interaction.reset()
            self.session.set_frame(self.capture.frame)
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
        panel.question.clear()
        panel.render(self.session)
        self._submit_ai(request)

    @Slot()
    def end_session(self) -> None:
        if self._closed:
            return
        self._guide_stop()
        self._cancel_ai()
        if self.interaction is not None:
            self.interaction.close()  # Release Ion/sounddevice's own retained audio buffers too.
        self.session.end()
        self.clear_overlay()
        self.capture.clear()
        if self.window is not None:
            self.window.session_panel.reset(self.session)
        self._set_capture_status("Gata")
        if self.indicator is not None:
            self.indicator.hide()
        self.log.write("Tutoring session ended; temporary context released.")

    @Slot()
    def start_capture(self) -> None:
        if self._closed or self.window is None or self.capture.pending:
            return
        self._cancel_ai()
        if self.interaction is not None:
            if self.interaction.active:
                return
            self.interaction.reset()
        try:
            self.capture.begin(self.window.screen())
        except (ValueError, RuntimeError) as error:
            self._capture_failed(type(error).__name__)
            return
        self.window.capture_button.setEnabled(False)
        self.pointer_bridge.hide()
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
        self._cancel_ai()
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
                    and self.overlay.has_visuals):
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
        if self.interaction is not None and self.interaction.active:
            return
        self.clear_overlay()
        try:
            self.overlay = OverlayWindow(self.window.screen())
            self.overlay.pointer_requested.connect(self.pointer_requested.emit)
            self.overlay.pointer_cleared.connect(self.pointer_bridge.close)
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
        self.pointer_bridge.close()
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
        if self.interaction is not None and self.interaction.active:
            self.interaction.reset()
            self._voice_state("Gata · Interacțiune anulată", False)
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
        self._guide_stop()
        self._closed = True
        self._cancel_ai()
        if self.hotkey is not None:
            self.hotkey.close()
        if self.interaction is not None:
            self.interaction.close()
        if self.indicator is not None:
            self.indicator.close()
            self.indicator.deleteLater()
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
    from jarvis.local_config import load_local_config
    load_local_config()
    app = create_application()
    controller = DesktopController(app, enable_voice=True, background=True, voice_only=True)
    try:
        if not controller.start():
            return controller.exit_code
        return app.exec()
    finally:
        controller.close()
