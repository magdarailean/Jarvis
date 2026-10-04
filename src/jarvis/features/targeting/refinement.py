"""Magnify a small proposed control, then remap its refined box exactly."""
import json
import math

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PyQt6.QtGui import QImage

from .grounding import locate, normalized_bounds


def crop_bounds(target, width, height):
    cx = (target["left"]+target["right"])/2
    cy = (target["top"]+target["bottom"])/2
    half_w = max(.10, (target["right"]-target["left"])*2)
    half_h = max(.10, (target["bottom"]-target["top"])*2)
    return (max(0, math.floor((cx-half_w)*width)), max(0, math.floor((cy-half_h)*height)),
            min(width, math.ceil((cx+half_w)*width)), min(height, math.ceil((cy+half_h)*height)))


def locate_precisely(api_key, image, instruction, width, height, model, mime,
                     *, cancelled=lambda: False, locator=locate):
    coarse_response = locator(api_key, image, instruction, width, height, model, mime)
    coarse = normalized_bounds(coarse_response, width, height)
    if coarse is None or cancelled():
        return '{"found":false,"box_2d":null}'
    if (coarse["right"]-coarse["left"])*(coarse["bottom"]-coarse["top"]) > .03:
        return coarse_response
    source = QImage.fromData(image)
    if source.isNull() or source.width() != width or source.height() != height:
        raise ValueError("Image dimensions do not match location context")
    left, top, right, bottom = crop_bounds(coarse, width, height)
    zoom = source.copy(left, top, right-left, bottom-top).scaled(
        1280, 1280, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not zoom.save(buffer, "PNG"):
        raise ValueError("Crop encoding failed")
    buffer.close()
    if cancelled():
        return '{"found":false,"box_2d":null}'
    response = locator(api_key, bytes(data), instruction, zoom.width(), zoom.height(), model, "image/png")
    fine = normalized_bounds(response, zoom.width(), zoom.height())
    if fine is None:
        return '{"found":false,"box_2d":null}'
    mapped = dict(left=(left+fine["left"]*(right-left))/width,
                  right=(left+fine["right"]*(right-left))/width,
                  top=(top+fine["top"]*(bottom-top))/height,
                  bottom=(top+fine["bottom"]*(bottom-top))/height)
    # Disagreement is not a reason to silently jump to another nearby control.
    cx, cy = (mapped["left"]+mapped["right"])/2, (mapped["top"]+mapped["bottom"])/2
    if not (coarse["left"] <= cx <= coarse["right"] and coarse["top"] <= cy <= coarse["bottom"]):
        return '{"found":false,"box_2d":null}'
    return json.dumps(dict(found=True, box_2d=[round(mapped[k]*1000)
                      for k in ("top", "left", "bottom", "right")]))
