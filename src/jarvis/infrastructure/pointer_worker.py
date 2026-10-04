"""PyQt-only worker; calls GuidePointer.point_at with the owner's mapping formula."""
import json
from pathlib import Path
import queue
import sys
import threading


def main():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'CursorMain'))
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from workingVersion4 import GuidePointer
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    pointer = GuidePointer()
    pointer.hide()
    commands = queue.Queue()

    def read():
        for line in sys.stdin:
            try:
                commands.put(json.loads(line))
            except ValueError:
                pass
        commands.put(dict(command='quit'))

    def poll():
        while not commands.empty():
            command = commands.get_nowait()
            if command.get('command') == 'quit':
                app.quit()
            elif command.get('command') == 'hide':
                pointer.hide()
            elif command.get('command') == 'point':
                screen = next((s for s in app.screens() if s.name() == command.get('monitor')), None)
                if screen is None:
                    continue
                # Same public input/mapping as GuideController; no targeting changes.
                left, top, right, bottom = command['target']
                geometry = screen.geometry()
                pointer.show()
                pointer.set_mode('pointing')
                pointer.point_at(geometry.x()+(left+right)*geometry.width()/2,
                                 geometry.y()+(top+bottom)*geometry.height()/2)

    threading.Thread(target=read, daemon=True).start()
    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(10)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
