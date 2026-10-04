"""Developer-only demo: python -m jarvis.features.callouts.demo."""
import argparse
from dataclasses import replace
from pathlib import Path
import sys

from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from jarvis.features.overlay.model import Annotation, Shape
from jarvis.features.overlay.window import OverlayWindow
from jarvis.infrastructure.tray import create_icon
from .model import Callout
from .layout import arrange
from .window import CalloutOverlay, paint_callout


CASES = (
    Callout("center", "Aici calculăm mai întâi discriminantul: Δ = b² − 4ac.", (.44, .43, .56, .56)),
    Callout("right", "Ținta este lângă marginea dreaptă. Explicația rămâne aproape de ea.", (.91, .4, .99, .53)),
    Callout("left", "Această valoare este cea pe care o comparăm.", (.01, .42, .10, .55)),
    Callout("top", "Pasul întâi: identificăm valorile cunoscute.", (.43, .01, .57, .09), "above"),
    Callout("bottom", "Rezultatul se citește aici, fără a ascunde formula.", (.43, .91, .57, .99), "below"),
    Callout("long", "Mai întâi identificăm coeficienții ecuației. Apoi înlocuim valorile în formulă, păstrând semnele. "
            "Verificăm fiecare operație înainte să continuăm. Dacă discriminantul este pozitiv, avem două soluții reale distincte. "
            "Explicația rămâne vizibilă și poate fi actualizată folosind același identificator.", (.47, .45, .55, .53)),
    Callout("point", "Un punct precis poate fi ținta explicației.", (.5, .5, .5, .5)),
)


def render_sheet(path):
    """Synthetic backgrounds only: never capture the user's screen."""
    width, height = 960, 640
    image = QImage(width * 2, height * 4, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#edf1f5"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for index, item in enumerate(CASES):
        painter.save()
        painter.translate((index % 2)*width, (index // 2)*height)
        painter.setPen(QColor("#39485b"))
        painter.drawText(24, 30, f"{index+1}. {item.id} · ținta albastră trebuie să rămână vizibilă")
        layout = arrange(item, width, height)
        painter.setPen(QPen(QColor("#1685e6"), 2))
        painter.setBrush(QColor("#cce5ff"))
        painter.drawRect(layout.target)
        paint_callout(painter, item, layout)
        painter.restore()
    painter.end()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path)):
        raise RuntimeError("Cannot save rendering")


def main():
    parser = argparse.ArgumentParser(description="Demonstrație separată pentru explicații vizuale.")
    parser.add_argument("--case", type=int, choices=range(1, len(CASES)+1), default=1)
    parser.add_argument("--seconds", type=int, default=0, help="Închidere automată; implicit rămâne deschis.")
    parser.add_argument("--render", help="Salvează exemple sintetice PNG, fără captură de ecran.")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    if args.render:
        render_sheet(args.render)
        return 0
    screen = app.primaryScreen()
    overlay = CalloutOverlay(screen)
    targets = OverlayWindow(screen)
    menu = QMenu()
    tray = QSystemTrayIcon(create_icon())
    tray.setToolTip("Jarvis — Demonstrație callout")
    tray.setContextMenu(menu)
    current = [args.case - 1]

    def show_case(index):
        current[0] = index
        overlay.clear()
        targets.clear()
        item = CASES[index]
        region = item.target
        if region[0] == region[2]:
            region = (region[0]-.003, region[1]-.003, region[2]+.003, region[3]+.003)
        targets.upsert(Annotation("demo-target", Shape.RECTANGLE, region))
        overlay.upsert(item)

    for index, item in enumerate(CASES):
        action = menu.addAction(f"Exemplul {index+1}: {item.id}")
        action.triggered.connect(lambda checked=False, index=index: show_case(index))
    def show_pair():
        overlay.clear()
        targets.clear()
        for item in (replace(CASES[2], target=(.05, .15, .15, .25)),
                     replace(CASES[1], target=(.85, .7, .95, .8))):
            targets.upsert(Annotation(item.id, Shape.RECTANGLE, item.target))
            overlay.upsert(item)

    menu.addAction("Două explicații simultan", show_pair)
    menu.addSeparator()
    menu.addAction("Evidențiază explicația", lambda: overlay.highlight(CASES[current[0]].id))
    menu.addAction("Actualizează textul", lambda: overlay.upsert(replace(CASES[current[0]], text="Explicație actualizată. Același ID, aceeași țintă.")))
    menu.addAction("Șterge explicația", lambda: overlay.remove(CASES[current[0]].id))
    menu.addAction("Ieșire", app.quit)
    app.aboutToQuit.connect(overlay.close)
    app.aboutToQuit.connect(targets.close)
    app.aboutToQuit.connect(tray.hide)
    tray.show()
    show_case(current[0])
    if args.seconds > 0:
        QTimer.singleShot(args.seconds * 1000, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
