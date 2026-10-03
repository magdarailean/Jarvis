from datetime import datetime
from pathlib import Path

import mss
import mss.tools

folder = Path(__file__).resolve().parent / "screenshots"
folder.mkdir(exist_ok=True)

input("Apasă Enter pentru captura de ecran...")

with mss.mss() as screen:
    image = screen.grab(screen.monitors[1])
    filename = folder / f"screen_{datetime.now():%Y%m%d_%H%M%S_%f}.png"

    mss.tools.to_png(image.rgb, image.size, output=str(filename))

print("Imagine salvată:", filename)