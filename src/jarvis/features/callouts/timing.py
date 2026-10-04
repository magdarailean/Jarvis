"""One non-blocking Qt timer for text reveal and temporary callout expiry."""
import math
import time
from PySide6.QtCore import QObject, QTimer, Signal


class CalloutTiming(QObject):
    changed = Signal()
    expired = Signal(str)
    LIFETIME_SECONDS = 15.0

    def __init__(self, parent=None, *, clock=time.monotonic, lifetime=LIFETIME_SECONDS):
        super().__init__(parent)
        self.clock, self.lifetime = clock, lifetime
        self.entries = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.tick)

    def start(self, item):
        now = self.clock()
        duration = min(1.2, max(.08, len(item.text)/100))
        self.entries[item.id] = (now, duration, len(item.text),
                                 now+duration+self.lifetime if item.temporary else None)
        self._schedule()

    def count(self, identifier):
        entry = self.entries.get(identifier)
        if entry is None:
            return None  # Render fully when no animation is registered.
        start, duration, length, _ = entry
        return min(length, max(0, int(length * (self.clock()-start)/duration)))

    def remove(self, identifier):
        self.entries.pop(identifier, None)
        self._schedule()

    def clear(self):
        self.entries.clear()
        self.timer.stop()

    def tick(self):
        now = self.clock()
        for identifier, (_, _, _, expires) in tuple(self.entries.items()):
            if expires is not None and now >= expires:
                self.entries.pop(identifier, None)
                self.expired.emit(identifier)
        self.changed.emit()
        self._schedule()

    def _schedule(self):
        self.timer.stop()
        now = self.clock()
        waits = []
        for start, duration, _, expires in self.entries.values():
            if now < start+duration:
                waits.append(.016)
            if expires is not None:
                waits.append(max(.001, expires-now))
        if waits:
            self.timer.start(max(1, math.ceil(min(waits)*1000)))
