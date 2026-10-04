import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest


class RefinementTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("PyQt6"), "Optional Ion dependencies missing")
    def test_refinement_mapping_cancellation_and_disagreement(self):
        script = r'''
import json
from unittest.mock import Mock
from PyQt6.QtCore import QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import QImage
from jarvis.features.targeting.refinement import locate_precisely, crop_bounds
from jarvis.features.targeting.grounding import normalized_bounds
for width, height in ((1920,1080), (1080,1920), (1280,720)):
    image = QImage(width,height,QImage.Format.Format_RGB32)
    image.fill(0xffffffff)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer,"PNG")
    buffer.close()
    coarse = '{"found":true,"box_2d":[100,800,200,900]}'
    target = normalized_bounds(coarse,width,height)
    left,top,right,bottom = crop_bounds(target,width,height)
    fine = [round((.12*height-top)/(bottom-top)*1000),
            round((.82*width-left)/(right-left)*1000),
            round((.18*height-top)/(bottom-top)*1000),
            round((.88*width-left)/(right-left)*1000)]
    locator = Mock(side_effect=[coarse, json.dumps(dict(found=True,box_2d=fine))])
    result = locate_precisely("fake",bytes(data),"Create",width,height,"fake","image/png",locator=locator)
    mapped = normalized_bounds(result,width,height)
    for field,expected in dict(left=.82,top=.12,right=.88,bottom=.18).items():
        assert abs(mapped[field]-expected) <= .002, mapped
    assert locator.call_count == 2
    zoom = QImage.fromData(locator.call_args.args[1])
    assert max(zoom.width(),zoom.height()) == 1280
    assert (zoom.width(),zoom.height()) == locator.call_args.args[3:5]
    locator = Mock(return_value=coarse)
    result = locate_precisely("fake",bytes(data),"Create",width,height,"fake","image/png",
                              locator=locator,cancelled=lambda:True)
    assert json.loads(result)["found"] is False and locator.call_count == 1
    for fine_response in ('{"found":false,"box_2d":null}', '{"found":true,"box_2d":[0,0,10,10]}'):
        locator = Mock(side_effect=[coarse,fine_response])
        result = locate_precisely("fake",bytes(data),"Create",width,height,"fake","image/png",locator=locator)
        assert json.loads(result)["found"] is False
    large = '{"found":true,"box_2d":[0,0,800,800]}'
    locator = Mock(return_value=large)
    assert locate_precisely("fake",bytes(data),"Panel",width,height,"fake","image/png",locator=locator) == large
    assert locator.call_count == 1
print("Crop mapping, dimensions, cancellation and disagreement passed for three resolutions")
'''
        result = subprocess.run([sys.executable, "-B", "-c", script],
                                cwd=Path(__file__).resolve().parents[1],
                                env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


if __name__ == "__main__":
    unittest.main()
