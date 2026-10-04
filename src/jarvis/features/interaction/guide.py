"""User-driven guide lifecycle; observes clicks, never generates input."""
import ctypes
from PySide6.QtCore import QObject, QTimer, Signal


class GuideSession(QObject):
    changed = Signal()  # Hide stale pointer and cancel outstanding analysis.
    inspect = Signal()  # Capture after user input has settled.

    def __init__(self, parent=None, *, buttons=None):
        super().__init__(parent)
        self.buttons = buttons or self._buttons
        self.goal = None
        self.previous_step = ""
        self.previous_png = None
        self.waits = 0
        self.held = False
        self.poll = QTimer(self)
        self.poll.setInterval(20)
        self.poll.timeout.connect(self.sample)
        self.settle = QTimer(self)
        self.settle.setSingleShot(True)
        self.settle.timeout.connect(self.inspect.emit)

    @staticmethod
    def _buttons():
        return any(ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000 for key in (1, 2))

    @property
    def active(self):
        return self.goal is not None

    def start(self, goal):
        self.stop()
        self.goal = goal
        self.held = self.buttons()
        self.poll.start()

    def stop(self):
        self.poll.stop()
        self.settle.stop()
        self.goal = None
        self.previous_step = ""
        self.previous_png = None
        self.waits = 0
        self.held = False

    def sample(self):
        if not self.active:
            return
        held = self.buttons()
        if held and not self.held:
            self.settle.stop()
            self.waits = 0
            self.changed.emit()
        elif self.held and not held:
            self.settle.start(700)  # Includes double-clicks and normal UI transitions.
        self.held = held

    def context(self, frame):
        unchanged = self.previous_png == frame.png if self.previous_png is not None else False
        self.previous_png = frame.png
        return {"original_goal": self.goal, "previous_step": self.previous_step,
                "screen_unchanged": unchanged,
                "instruction": "Re-evaluate the actual screen; a click is not proof of progress."}

    def wait_for_screen(self):
        self.waits += 1
        if self.waits > 3:
            return False
        self.settle.start(1500)
        return True
