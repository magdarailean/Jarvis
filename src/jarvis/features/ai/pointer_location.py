"""Adapt the tested companion locator to main-app pointer actions only."""
from copy import deepcopy
import json

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

from jarvis.features.callouts.model import VisualKind, VisualPlan
from jarvis.features.interaction.intent import VisualIntent
from jarvis.features.targeting.grounding import build_location_payload, normalized_bounds


def pointer_index(payload, request):
    if request.visual_intent == VisualIntent.EXPLAIN:
        return None
    if request.visual_intent == VisualIntent.GUIDE and payload.get("guide_status") != "next":
        return None
    # Preserve current action eligibility and confidence checks. Location is the
    # only field replaced; routing, text, completion and other visuals are intact.
    actions = payload.get("actions", [])
    if isinstance(actions, list):
        for index, item in enumerate(actions[:32]):
            plan = VisualPlan.parse(dict(payload, actions=[item]),
                                    intent=request.visual_intent, require_grounding=True)
            if any(action.kind == VisualKind.POINTER for action in plan.actions):
                return index
    return None


def location_payload(frame, payload, index, model):
    if frame is None:
        raise ValueError("Pointer has no screenshot")
    image = QImage.fromData(frame.png)
    if image.isNull():
        raise ValueError("Invalid screenshot")
    if max(image.width(), image.height()) > 1920:
        image = image.scaled(1920, 1920, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "JPEG", 85):
        raise ValueError("Image encoding failed")
    buffer.close()
    action = payload["actions"][index]
    instruction = action.get("text", "").strip() or payload["text"]
    wire = build_location_payload(bytes(data), instruction, image.width(), image.height(), model, "image/jpeg")
    return wire, image.width(), image.height()


def decode_location(raw, width, height):
    completion = json.loads(raw)
    choice = completion["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise ValueError("Incomplete location response")
    return normalized_bounds(choice["message"]["content"], width, height)


def replace_pointer(payload, index, target):
    result = deepcopy(payload)
    if target is None:
        # No fallback to the planner's guessed coordinates; retain text/visuals.
        # Remove all pointer candidates so a duplicate cannot become a fallback.
        result["actions"] = [item for item in result["actions"]
                             if not isinstance(item, dict) or item.get("type") != VisualKind.POINTER.value]
    else:
        result["actions"][index]["target"] = [target[key] for key in ("left", "top", "right", "bottom")]
    return result
