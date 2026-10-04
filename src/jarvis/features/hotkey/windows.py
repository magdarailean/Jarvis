import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QTimer, Signal


def parse_shortcut(value: str) -> tuple[int, int, tuple[int, ...]]:
    parts = value.upper().replace(" ", "").split("+")
    modifiers = {"CTRL": (2, 0x11), "ALT": (1, 0x12), "SHIFT": (4, 0x10)}
    if len(parts) < 2 or len(set(parts)) != len(parts) or any(p not in modifiers for p in parts[:-1]):
        raise ValueError("Use Ctrl/Alt/Shift plus Space, A–Z or F1–F24")
    key = parts[-1]
    if key == "SPACE":
        vk = 0x20
    elif len(key) == 1 and "A" <= key <= "Z":
        vk = ord(key)
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError("Unsupported shortcut key")
    return sum(modifiers[p][0] for p in parts[:-1]), vk, tuple(modifiers[p][1] for p in parts[:-1]) + (vk,)


class _Filter(QAbstractNativeEventFilter):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def nativeEventFilter(self, event_type, message):
        msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
        if msg.message == 0x0312 and msg.wParam == self.owner.ID:
            self.owner.activate()
            return True, 0
        return False, 0


class GlobalHotkey(QObject):
    pressed = Signal()
    released = Signal()
    ID = 0x4A56

    def __init__(self, app, shortcut="Ctrl+Shift+Space"):
        super().__init__(app)
        self.app = app
        self.shortcut = shortcut
        self.modifiers, self.key, self.keys = parse_shortcut(shortcut)
        self.native = ctypes.WinDLL("user32", use_last_error=True)
        self.native.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        self.native.RegisterHotKey.restype = wintypes.BOOL
        self.native.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self.native.UnregisterHotKey.restype = wintypes.BOOL
        self.native.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.native.GetAsyncKeyState.restype = ctypes.c_short
        self.held = False
        self.registered = False
        self.filter = _Filter(self)
        self.timer = QTimer(self)
        self.timer.setInterval(15)
        self.timer.timeout.connect(self.check_release)

    def start(self):
        if self.registered:
            return
        if not self.native.RegisterHotKey(None, self.ID, self.modifiers | 0x4000, self.key):
            raise OSError("Shortcut registration failed or already in use")
        self.registered = True
        self.app.installNativeEventFilter(self.filter)

    def down(self):
        return all(self.native.GetAsyncKeyState(key) & 0x8000 for key in self.keys)

    def activate(self):
        if self.registered and not self.held and self.down():
            self.held = True
            self.timer.start()  # Poll only during a hold; no idle keyboard polling.
            self.pressed.emit()

    def check_release(self):
        if self.held and not self.down():
            self.held = False
            self.timer.stop()
            self.released.emit()

    def close(self):
        self.timer.stop()
        self.held = False
        if self.registered:
            self.app.removeNativeEventFilter(self.filter)
            self.native.UnregisterHotKey(None, self.ID)
            self.registered = False
