"""Child-process scenarios for integration tests; not a production command interface."""

import sys
import os

from PySide6.QtCore import QTimer
from jarvis.app import DesktopController, create_application


def main() -> int:
    mode, key = sys.argv[1:]
    app = create_application()
    controller = DesktopController(app, instance_key=key)
    try:
        if not controller.start():
            return controller.exit_code
        if mode == "duplicate":
            return 3  # A second primary is a failure.
        if mode == "cycle":
            QTimer.singleShot(100, controller.window.exit_button.click)
            return app.exec()
        if mode == "crash":
            print("READY", flush=True)
            sys.stdin.readline()
            os._exit(23)  # Deliberately skip finally/cleanup in this test process.
        return 2
    finally:
        controller.close()


if __name__ == "__main__":
    raise SystemExit(main())
