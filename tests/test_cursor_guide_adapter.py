"""Keep Ion/PyQt6 in a subprocess, isolated from the shell's PySide6 tests."""
import os
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest


class CursorAdapterTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("PyQt6"), "Optional Ion cursor dependencies not installed")
    def test_owner_worker_and_pointer_integration(self):
        script = r'''
import json
from unittest.mock import Mock, patch
from jarvis.cursor_guide import load_owner, install_grounding
owner = load_owner()
app = owner.QApplication([])
decision = dict(status="action", action="click", instruction="Create", expected_result="Editor",
                previous_result="none", target=dict(left=.1, top=.1, right=.2, bottom=.2),
                goal_state="in_progress", goal_evidence="Create button is visible",
                control_name="Create", action_purpose="Open a new editor", page_context="Dashboard")
planner = Mock(return_value=json.dumps(decision))
owner.request_openrouter = planner
install_grounding(owner, inspect_targets=True)
image = owner.QImage(3840, 2160, owner.QImage.Format.Format_RGB32)
image.fill(owner.QColor("white"))
context = dict(verified_steps=[], pending_attempt=None, screenshot={})
request = owner.AIRequest(7, image, context, False, "fake")
results, errors = [], []
request.result.connect(lambda token, value: results.append((token, value)))
request.error.connect(lambda *args: errors.append(args))
def ground(response, image, context, key, model, mime, **kwargs):
    assert context["screenshot"] == dict(width=1920, height=1080)
    assert mime == "image/jpeg"
    parsed = json.loads(response)
    parsed["target"] = dict(left=.5, top=.25, right=.6, bottom=.3)
    return json.dumps(parsed)
with patch.object(owner, "load_api_key", return_value="fake"), patch("jarvis.cursor_guide.ground_response", side_effect=ground):
    request.start()
    assert request.wait(5000)
    app.processEvents()
assert not errors, errors
assert results[0][0] == 7 and results[0][1].target.left == .5
assert len(request.target_review) == 3
# A malformed planner result must reach the owner's existing one-repair path.
planner.side_effect = ["bad json", json.dumps(decision)]
with patch.object(owner, "load_api_key", return_value="fake"), patch("jarvis.cursor_guide.ground_response", side_effect=ground):
    request.start()
    assert request.wait(5000)
    app.processEvents()
assert len(results) == 2 and not errors
assert planner.call_args.args[2]["validation_feedback"]
# Default path uses the full-image locator once even for tiny controls. A failed
# crop refinement can no longer veto the working full-image result.
planner.side_effect = None
with patch.object(owner, "load_api_key", return_value="fake"), patch(
        "jarvis.cursor_guide.locate", return_value='{"found":true,"box_2d":[100,800,120,820]}') as locator:
    request.start()
    assert request.wait(5000)
    app.processEvents()
    locator.assert_called_once()
assert len(results) == 3 and not errors
assert results[-1][1].target.left == .8
# Exercise actual owner's normalized crop conversion and animation tip anchor.
target = owner.monitor_target(owner.Target(.5, .25, .6, .3), owner.Target(.2, .1, .8, .9))
assert abs(target.left - .5) < 1e-9 and abs(target.top - .3) < 1e-9
pointer = owner.GuidePointer()
geometry = app.primaryScreen().geometry()
for x in (.2, .5, .8):
    for y in (.2, .5, .8):
        px, py = geometry.x()+x*geometry.width(), geometry.y()+y*geometry.height()
        pointer.point_at(px, py)
        pointer.animation.setCurrentTime(pointer.animation.duration())
        assert abs(pointer.x()+pointer.pointer_tip.x()*pointer.cursor_scale-px) <= .5
        assert abs(pointer.y()+pointer.pointer_tip.y()*pointer.cursor_scale-py) <= .5
pointer.close()
from jarvis.features.targeting.inspector import TargetInspector, install_inspector
data = owner.QByteArray()
buffer = owner.QBuffer(data)
buffer.open(owner.QIODevice.OpenModeFlag.WriteOnly)
image.save(buffer, "PNG")
buffer.close()
inspector = TargetInspector()
inspector.present(bytes(data), json.dumps(decision), json.dumps(decision))
app.processEvents()
assert inspector.isVisible() and inspector.image.size() == image.size()
rect = inspector.image_rect()
assert abs(rect.width()/rect.height() - 3840/2160) < 1e-9
assert not inspector.grab().isNull()  # Exercise actual painting without desktop capture.
inspector.clear()
assert not inspector.isVisible() and inspector.image.isNull()
from jarvis.features.targeting.progress import install_progress
install_progress(owner)
install_inspector(owner)
controller = owner.GuideController(demo=True, start_observer=False, spoken=False)
controller.target_inspector.present(bytes(data), json.dumps(decision), json.dumps(decision))
controller.cancel_session()
assert controller.target_inspector.image.isNull()
controller.target_inspector.present(bytes(data), json.dumps(decision), json.dumps(decision))
with patch.object(owner.GuideController.__bases__[0], "begin_capture") as capture:
    controller.begin_capture("decision")
    assert not controller.target_inspector.isVisible()
    assert controller.target_inspector.image.isNull()
    capture.assert_called_once_with("decision")
controller.shutdown()
# Drive actual Qt signals through the progress controller. No captures or API.
progress = owner.GuideController(demo=True, start_observer=False, spoken=False)
progress.goal = "Deschide internetul"
progress.pending = dict(decision, step=1)
progress.screen = app.primaryScreen()
progress.state = "thinking"
pending = progress.pending
worker = owner.AIRequest(progress.generation, image, context, True, "fake")
worker.awaiting_page = True
worker.result.connect(progress.accept_decision)
waiting = owner.Decision("blocked", "none", "Loading", "", "uncertain", None)
with patch.object(progress, "explain") as explain:
    for _ in range(2):
        progress.settle_timer.stop()
        worker.result.emit(progress.generation, waiting)
        assert progress.state == "settling" and progress.settle_timer.isActive()
        assert progress.pending is pending and progress.current is None
    progress.settle_timer.stop()
    worker.result.emit(progress.generation, waiting)
    assert progress.state == "blocked" and not progress.settle_timer.isActive()
    assert progress.pending is None
    worker.awaiting_page = False
    token = progress.generation
    worker.result.emit(token, owner.Decision("complete", "none", "Gata.", "", "none", None))
    assert progress.state == "idle" and progress.goal == "" and progress.current is None
    assert not progress.settle_timer.isActive()
    explain.assert_called_with("Gata.")
    worker.result.emit(token, waiting)  # stale results cannot restart a completed task.
    assert progress.state == "idle"
progress.shutdown()
print("worker, repair, crop mapping, and nine pointer anchors passed")
'''
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        result = subprocess.run([sys.executable, "-B", "-c", script],
                                cwd=Path(__file__).resolve().parents[1], env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
