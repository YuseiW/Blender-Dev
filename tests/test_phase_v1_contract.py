"""Static and simulated Phase V-1 tests; PySide6/Blender are not required.

From the Blender-Dev repo root after applying the patch:
    python tests/test_phase_v1_contract.py
"""
import ast
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'scripts/addons/anim_reference_tool'
QT = ADDON / 'qt_manager_app.py'
PAGE = ADDON / 'qt_viewer_page.py'
PATCHER = ROOT / 'apply_phase_v1.py'


def source_function(path, name, cls=None, globals_dict=None):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = tree.body
    if cls:
        nodes = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == cls).body
    fn = next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = globals_dict or {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), str(path), 'exec'), scope)
    return scope[name]


def check_selector():
    f = source_function(PAGE, 'reference_at_current_frame')
    state = {
        'frame': 9, 'active_cut_index': 0, 'active_category': 'KEYFRAME',
        'images': [{'uid': 'im1', 'name': 'one.png', 'path': 'a.png'},
                   {'uid': 'im2', 'name': 'two.png', 'path': 'b.png'}],
        'cuts': [{'name': 'C01', 'categories': {
            'KEYFRAME': [
                {'uid': 'r1', 'image_id': 'im1', 'start': 1, 'end': 8, 'duration': 8},
                {'uid': 'r2', 'image_id': 'im2', 'start': 9, 'end': 20, 'duration': 12}
            ], 'LAYOUT': [], 'STORYBOARD': []}}],
    }
    for frame, expected in [(1, 'r1'), (8, 'r1'), (9, 'r2'), (20, 'r2'), (21, None)]:
        state['frame'] = frame
        cut, current, image, refs = f(state)
        assert cut['name'] == 'C01' and len(refs) == 2
        assert (current['uid'] if current else None) == expected
        if expected == 'r2':
            assert image['uid'] == 'im2'
    state['frame'] = 9
    state['images'].pop()
    cut, current, image, refs = f(state)
    assert current['uid'] == 'r2' and image is None
    state['active_cut_index'] = -1
    assert f(state) == (None, None, None, [])
    assert f(None) == (None, None, None, [])
    print('PASS: frame range boundaries, missing images, missing cut')


class FakeButton:
    def __init__(self):
        self.checked = False
    def setChecked(self, v):
        self.checked = v


class FakeStack:
    def __init__(self):
        self.selected = None
    def setCurrentWidget(self, widget):
        self.selected = widget


class FakePage:
    def __init__(self):
        self.snapshots = []
    def set_snapshot(self, state):
        self.snapshots.append(state)


class FakeMessage:
    count = 0
    @staticmethod
    def information(*args):
        FakeMessage.count += 1


class FakeWindow:
    def __init__(self, edited=False, demo=False):
        self._pages = FakeStack()
        self._viewer_page = FakePage()
        self._manager_page = object()
        self.viewer_nav = FakeButton()
        self.manager_nav = FakeButton()
        self.state = {'frame': 9}
        self.pending = None
        self.demo = demo
        self.edited = edited
        self.commands = []
    def _editor_update_for_save(self):
        return {'pending': True} if self.edited else None
    def command(self, action):
        self.commands.append(action)


def check_page_switch():
    change = source_function(QT, '_set_page', 'ManagerWindow', {'QMessageBox': FakeMessage})
    ui = FakeWindow()
    change(ui, 'viewer')
    assert ui._pages.selected == ui._viewer_page
    assert ui.viewer_nav.checked and not ui.manager_nav.checked
    assert ui.commands == ['snapshot']
    assert ui._viewer_page.snapshots == [ui.state]
    change(ui, 'manager')
    assert ui._pages.selected is ui._manager_page
    assert ui.manager_nav.checked and not ui.viewer_nav.checked
    ui2 = FakeWindow(edited=True)
    change(ui2, 'viewer')
    assert ui2._pages.selected is None and ui2.commands == []
    assert ui2.manager_nav.checked and FakeMessage.count > 0
    ui3 = FakeWindow(demo=True)
    change(ui3, 'viewer')
    assert ui3.commands == []
    ui4 = FakeWindow()
    ui4.pending = 'request_1'
    change(ui4, 'viewer')
    assert ui4.commands == []
    print('PASS: tab switching, dirty-editor guard, pending/demo snapshot guards')


def check_contract():
    qt = QT.read_text(encoding='utf-8')
    page = PAGE.read_text(encoding='utf-8')
    ast.parse(qt)
    ast.parse(page)
    assert 'UI_QT_VIEWER_STACK_V1' in qt
    for tag in ['UI1_EXPLORER_IMAGE_DROP_V1',
                'UI_QT_SAVE_REORDER_V1', 'UI_QT_REFERENCE_AUTOSCROLL_V1']:
        assert tag in qt, tag
    assert 'self._viewer_page.set_snapshot(s)' in qt
    assert 'self._pages = QStackedWidget()' in qt
    assert 'self._pages.addWidget(manager_page)' in qt
    assert 'self._pages.addWidget(self._viewer_page)' in qt
    assert 'self.instruction.setReadOnly(True)' in page
    assert 'self.references.setSelectionMode(QListWidget.SelectionMode.NoSelection)' in page
    assert ('self.overlay_toggle.setEnabled(False)' in page or
            'self.overlay_toggle.toggled.connect' in page)
    assert 'self.sync_toggle.toggled.connect(self.syncRequested.emit)' in page
    assert 'self.setWindowTitle("AnimRef — Viewer / Manager")' in qt
    print('PASS: Manager features retained; Viewer is read-only with staged controls')


def check_patcher_idempotent():
    if not PATCHER.is_file():
        print('SKIP: historical V-1 installer has been cleaned up')
        return
    spec = importlib.util.spec_from_file_location('phasev1', PATCHER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    qt = QT.read_text(encoding='utf-8')
    assert mod.transform(qt) == qt
    assert mod.transform(qt) == mod.transform(mod.transform(qt))
    print('PASS: patcher idempotence')


if __name__ == '__main__':
    check_selector()
    check_page_switch()
    check_contract()
    check_patcher_idempotent()
    print('=== ALL PHASE V-1 CONTRACT TESTS PASSED ===')
