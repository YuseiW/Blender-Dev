"""Phase V-3.2 tests; no Blender or PySide6 installation required.

Run from Blender-Dev root after apply_phase_v3_2.py:
    python tests/test_phase_v3_2_contract.py
"""
import ast
import json
from pathlib import Path
import tempfile
import time
from types import MethodType, SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'scripts' / 'addons' / 'anim_reference_tool'
QT = ADDON / 'qt_manager_app.py'
VIEWER = ADDON / 'qt_viewer_page.py'
MAIN_PANEL = ADDON / 'ui' / 'main_panel.py'
UI_INIT = ADDON / 'ui' / '__init__.py'


def extract(path, name, cls=None, namespace=None):
    tree = ast.parse(path.read_text(encoding='utf-8'), str(path))
    nodes = tree.body
    if cls is not None:
        nodes = next(x.body for x in nodes if isinstance(x, ast.ClassDef) and x.name == cls)
    node = next(x for x in nodes if isinstance(x, ast.FunctionDef) and x.name == name)
    scope = dict(namespace or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(path), 'exec'), scope)
    return scope[name]


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


class FakeViewer:
    def __init__(self):
        self._sync_pending = None
        self.states = []
        self.sync_toggle = SimpleNamespace(checked=None)

    def set_snapshot(self, state):
        self.states.append(state.copy())
        self.sync_toggle.checked = (self._sync_pending if self._sync_pending is not None
                                    else state['auto_sync'])


def make_qt(root):
    request_sync = extract(QT, '_request_auto_sync', 'ManagerWindow')
    poll = extract(QT, '_poll', 'ManagerWindow', namespace={
        'time': time, 'read_json': read_json, 'manager_data_key': lambda s: s.get('project', 'test'),
        'QTimer': SimpleNamespace(singleShot=lambda *_: None),
    })
    command = extract(QT, 'command', 'ManagerWindow', namespace={
        'time': time, 'uuid4': uuid4, 'write_json_atomic': write_json,
    })
    viewer = FakeViewer()
    events = []
    ui = SimpleNamespace(
        demo=False, session_dir=root, state={'scene': 'Scene', 'frame': 4, 'auto_sync': False},
        pending=None, pending_since=0.0, last_response=0.0,
        _viewer_page=viewer, _last_live_state_at=0.0, _viewer_probe_pending=False,
        _queued_viewer_command=None, _queued_sync_enabled=None,
        _sync_request_id=None, _manager_data_key='test', _manager_needs_render=False,
        _set_status=lambda msg, err=False: events.append(('status', msg, err)),
        _poll_live_state=lambda: None, _poll_viewer_snapshot_fallback=lambda: None,
    )
    ui._pages = SimpleNamespace(currentWidget=lambda: viewer)
    def _render():
        viewer.set_snapshot(ui.state)
    ui._render = _render
    ui.command = MethodType(command, ui)
    ui._request_auto_sync = MethodType(request_sync, ui)
    return ui, lambda: poll(ui), events


def response(root, ident, auto_sync, ok=True):
    write_json(root / 'responses' / (ident + '.json'),
               {'ok': ok, 'message': 'ok' if ok else 'error',
                'state': {'scene': 'Scene', 'frame': 4, 'auto_sync': auto_sync}} if ok
               else {'ok': False, 'message': 'error'})


def test_sync_intent_survives_snapshot_and_rapid_toggles():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / 'requests').mkdir()
        (root / 'responses').mkdir()
        ui, poll, _ = make_qt(root)
        view = ui._viewer_page
        view.set_snapshot(ui.state)
        ui.pending = 'probe'
        ui._viewer_probe_pending = True
        ui._request_auto_sync(True)
        assert ui._queued_sync_enabled is True
        assert view._sync_pending is True
        assert view.sync_toggle.checked is False  # after user click Qt itself sets True
        view.sync_toggle.checked = True
        response(root, 'probe', False)
        poll()  # Old snapshot arrives; must not discard the queued intent.
        assert ui._queued_sync_enabled is True and view._sync_pending is True
        poll()  # Send the first sync command, after the background probe.
        first_id = ui.pending
        assert first_id and read_json(root / 'requests' / (first_id + '.json')) == {
            'id': first_id, 'action': 'set_auto_sync',
            'args': {'enabled': True}, 'expect_scene': 'Scene'}
        # User changes their mind while the command is in flight.
        ui._request_auto_sync(False)
        assert ui._queued_sync_enabled is False and view._sync_pending is False
        response(root, first_id, True)
        poll()
        assert view._sync_pending is False, 'Older ACK must not discard newer intent'
        poll()  # Send the final OFF toggle.
        second_id = ui.pending
        assert second_id != first_id
        assert read_json(root / 'requests' / (second_id + '.json'))['args'] == {'enabled': False}
        response(root, second_id, False)
        poll()
        assert ui.state['auto_sync'] is False
        assert view._sync_pending is None and view.sync_toggle.checked is False
        assert ui._queued_sync_enabled is None and ui._sync_request_id is None
        print('PASS: pending snapshot, queued user toggle, latest-intent wins, final ACK')


def test_sync_error_and_timeout_restore_authoritative_state():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / 'requests').mkdir()
        (root / 'responses').mkdir()
        ui, poll, _ = make_qt(root)
        view = ui._viewer_page
        view.set_snapshot(ui.state)
        ui._request_auto_sync(True)
        assert ui.pending and view._sync_pending is True
        response(root, ui.pending, False, ok=False)
        poll()
        assert ui._sync_request_id is None
        assert view._sync_pending is None and view.sync_toggle.checked is False
        ui._request_auto_sync(True)
        assert ui.pending
        ui.pending_since = time.monotonic() - 31
        poll()
        assert ui.pending is None and ui._sync_request_id is None
        assert view._sync_pending is None and view.sync_toggle.checked is False
        print('PASS: failure/timeout rollback to Blender-confirmed state')


def test_single_button_n_panel_and_bridge_contract():
    text_main = MAIN_PANEL.read_text(encoding='utf-8')
    text_init = UI_INIT.read_text(encoding='utf-8')
    text_viewer = VIEWER.read_text(encoding='utf-8')
    text_qt = QT.read_text(encoding='utf-8')
    for p in (MAIN_PANEL, UI_INIT, VIEWER, QT):
        ast.parse(p.read_text(encoding='utf-8'), str(p))
    panel = ast.parse(text_main)
    classes = [x for x in panel.body if isinstance(x, ast.ClassDef)]
    assert len(classes) == 1 and classes[0].name == 'ANIMREF_PT_MainPanel'
    assert text_main.count('"animref.open_external_manager"') == 1
    assert '"auto_sync"' not in text_main
    assert 'from . import reference_editor' not in text_init
    assert 'from . import viewer_panel' in text_init, 'legacy Image Editor kept until V-5'
    assert 'UI_V3_2_SYNC_INTENT_QUEUE' in text_qt
    assert 'UI_V3_2_PENDING_SYNC_DISPLAY' in text_viewer
    # Blender's original property remains the single storage location.
    bridge = (ADDON / 'operators' / 'manager_external.py').read_text(encoding='utf-8')
    assert 'project.auto_sync = enabled' in bridge
    print('PASS: launcher-only 3D N-panel, preserved legacy Viewer, Blender sync source-of-truth')


if __name__ == '__main__':
    test_sync_intent_survives_snapshot_and_rapid_toggles()
    test_sync_error_and_timeout_restore_authoritative_state()
    test_single_button_n_panel_and_bridge_contract()
    print('=== PHASE V-3.2 CONTRACT TESTS PASSED ===')
