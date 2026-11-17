"""Test Qt reference-list auto-scroll logic without requiring PySide6.

From Blender-Dev root:
  python tests/test_reference_autoscroll.py
"""
import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
QT = ROOT / 'scripts/addons/anim_reference_tool/qt_manager_app.py'


def extract(name, cls=None, namespace=None):
    tree = ast.parse(QT.read_text(encoding='utf-8'))
    nodes = tree.body
    if cls:
        matches = [x for x in nodes if isinstance(x, ast.ClassDef) and x.name == cls]
        assert len(matches) == 1, cls
        nodes = matches[0].body
    matches = [x for x in nodes if isinstance(x, ast.FunctionDef) and x.name == name]
    assert len(matches) == 1, name
    module = ast.fix_missing_locations(ast.Module(body=[matches[0]], type_ignores=[]))
    scope = dict(namespace or {})
    exec(compile(module, str(QT), 'exec'), scope)
    return scope[name]


step = extract('_reference_edge_scroll_step')


def check_zones():
    for height in (100, 260, 480, 900):
        assert step(0, height) < 0
        assert step(height - 1, height) > 0
        assert step(height // 2, height) == 0
        assert step(-1, height) == 0
        assert step(height, height) == 0
        assert abs(step(0, height)) > abs(step(12, height))  # edge speeds up
        assert step(height-1, height) > step(height-13, height)
    assert step(0, 0) == 0
    print('PASS: upper/lower edge zones, dead zone, faster near edge')


class FakeTimer:
    def __init__(self):
        self.active = False
    def start(self):
        self.active = True
    def stop(self):
        self.active = False
    def isActive(self):
        return self.active


class FakeScrollBar:
    def __init__(self, v=300, max_v=1000):
        self.v = v
        self.max_v = max_v
    def value(self):
        return self.v
    def setValue(self, value):
        self.v = value
    def minimum(self):
        return 0
    def maximum(self):
        return self.max_v


class FakeList:
    def __init__(self):
        self._drag_autoscroll = FakeTimer()
        self._drag_hover_y = None
        self._viewport = SimpleNamespace(height=lambda: 480)
        self._scrollbar = FakeScrollBar()
    def viewport(self):
        return self._viewport
    def verticalScrollBar(self):
        return self._scrollbar
    def _stop_drag_autoscroll(self):
        return stop_scroll(self)
    def _set_drag_autoscroll(self, y):
        return set_scroll(self, y)
    def _scroll_while_dragging(self):
        return do_scroll(self)


stop_scroll = extract('_stop_drag_autoscroll', 'ReferenceList')
set_scroll = extract('_set_drag_autoscroll', 'ReferenceList', {'_reference_edge_scroll_step': step})
do_scroll = extract('_scroll_while_dragging', 'ReferenceList', {'_reference_edge_scroll_step': step})


def check_timer():
    fake = FakeList()
    fake._set_drag_autoscroll(2)
    assert fake._drag_autoscroll.isActive()
    value_before = fake._scrollbar.value()
    for _ in range(5):
        fake._scroll_while_dragging()
    assert fake._scrollbar.value() < value_before
    fake._set_drag_autoscroll(475)
    value_before = fake._scrollbar.value()
    for _ in range(5):
        fake._scroll_while_dragging()
    assert fake._scrollbar.value() > value_before
    fake._set_drag_autoscroll(240)
    assert not fake._drag_autoscroll.isActive()
    assert fake._drag_hover_y is None
    fake._scrollbar.v = 0
    fake._set_drag_autoscroll(0)
    fake._scroll_while_dragging()
    assert fake._scrollbar.value() == 0 and not fake._drag_autoscroll.isActive()
    print('PASS: timer keeps scrolling while pointer stays put, stops at center/limits')


def check_regression_contract():
    s = QT.read_text(encoding='utf-8')
    assert '# UI_QT_REFERENCE_AUTOSCROLL_V1' in s
    assert 'UI1_EXPLORER_IMAGE_DROP_V1' in s
    assert 'UI_QT_SAVE_REORDER_V1' in s
    assert 'self.reorderRequested.emit(uid, insertion_index)' in s
    assert 'self.imageDropped.emit(uid)' in s
    assert 'self.filePathsDropped.emit(paths)' in s
    assert 'self.command("reorder_reference", index=src, uid=uid, to_index=dest)' in s
    assert 'self.command("save_project", **args)' in s
    assert 'def dragLeaveEvent(self, event):' in s
    assert 'self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)' in s
    print('PASS: reordering, Explorer drop, Save, and edge cleanup paths retained')


if __name__ == '__main__':
    check_zones()
    check_timer()
    check_regression_contract()
    print('=== ALL AUTOSCROLL TESTS PASSED ===')
