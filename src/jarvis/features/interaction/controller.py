from PySide6.QtCore import QObject, Signal

from jarvis.features.screen_capture.session import CaptureSession


class InteractionController(QObject):
    """One hold at a time. Emits context to the AI composition root."""

    state_changed = Signal(str, bool)  # Romanian state, microphone actually active
    prepared = Signal(object)  # TutorRequest dispatched by the composition root.
    failed = Signal(str)
    capture_started = Signal()
    capture_finished = Signal()

    def __init__(self, session, voice, parent=None, *, capture=None):
        super().__init__(parent)
        self.session = session
        self.voice = voice
        self.capture = capture or CaptureSession(self)
        self.token = 0
        self.active = False
        self.held = False
        self.context = None
        self._frame = None
        self._text = None
        self._annotations = ()
        self._screen = None
        self._starting_capture = False
        voice.listening.connect(self._listening)
        voice.stopped.connect(self._stopped)
        voice.transcribed.connect(self._transcribed)
        voice.failed.connect(self._fail)
        self.capture.frame_changed.connect(self._frame_changed)
        self.capture.finished.connect(self._capture_finished)
        self.capture.failed.connect(lambda _: self._fail("Ecranul nu a putut fi capturat."))

    def press(self, screen, annotations=()):
        if self.active:
            return  # No overlap while transcribing; a fresh press is needed afterward.
        if not self.voice.available:
            self.failed.emit("Vocea se pregătește sau nu este configurată. Verifică panoul Jarvis.")
            self.voice.warmup()
            return
        self.reset(stop_voice=False)
        self.token += 1
        self.active = self.held = True
        self._screen = screen
        self._annotations = annotations
        self.state_changed.emit("Pregătesc microfonul...", False)
        try:
            self.voice.start(self.token)
        except Exception:
            self._fail("Microfonul nu a putut fi pornit.")

    def release(self):
        if self.active and self.held:
            self.held = False
            self.voice.stop()
            self.state_changed.emit("Opresc microfonul...", True)

    def _listening(self, token):
        if not self.active or token != self.token:
            return
        if not self.held:
            self.voice.stop()
            return
        self.state_changed.emit("Ascult...", True)
        self.capture_started.emit()
        try:
            self._starting_capture = True
            self.capture.begin(self._screen, delay_ms=80)
        except Exception:
            self._fail("Ecranul nu a putut fi capturat.")
        finally:
            self._starting_capture = False

    def _stopped(self, token):
        if self.active and token == self.token:
            self.held = False
            self.state_changed.emit("Procesez...", False)

    def _frame_changed(self, frame):
        if frame is None and self._frame is not None and not self._starting_capture:
            self.reset()
            self.state_changed.emit("Gata · Contextul de ecran a fost eliberat", False)
            return
        self._frame = frame
        self.session.set_frame(frame)
        self._prepare()

    def _capture_finished(self):
        self.capture_finished.emit()
        if self.active and self._frame is None and not self.capture.pending:
            self._fail("Captura a fost anulată sau monitorul nu mai este disponibil.")

    def _transcribed(self, token, text):
        if not self.active or token != self.token:
            return
        self.held = False
        self.state_changed.emit("Procesez...", False)
        if not text.strip():
            self._fail("Nu am auzit o întrebare. Ține apăsată comanda rapidă și încearcă din nou.")
            return
        if self._frame is None and not self.capture.pending:
            self._fail("Activarea a fost prea scurtă. Încearcă din nou.")
            return
        self._text = text
        self._prepare()

    def _prepare(self):
        if not self.active or self._frame is None or self._text is None:
            return
        try:
            request = self.session.begin(self._text, self._annotations)
        except (ValueError, RuntimeError):
            self._fail("Întrebarea nu poate fi pregătită. Încearcă o întrebare mai scurtă.")
            return
        self.context = request
        self.active = False
        self._text = None
        self.state_changed.emit("Context pregătit", False)
        self.prepared.emit(request)

    def _fail(self, message):
        self.reset()
        self.state_changed.emit("Eroare", False)
        self.failed.emit(message)

    def reset(self, *, stop_voice=True):
        was_active = self.active
        if self.context is not None:
            self.session.fail(self.context.id, "Context pregătit; niciun furnizor AI conectat.")
        self.active = self.held = False
        self.token += 1
        self.context = self._frame = self._text = None
        self._annotations = ()
        self._screen = None
        if was_active and stop_voice:
            self.voice.close()  # Ends microphone/transcription even if Ion is blocked.
        self.capture.clear(notify_finished=False)
        self.session.set_frame(None)
        self.capture_finished.emit()

    def close(self):
        self.reset()
        self.voice.close()
