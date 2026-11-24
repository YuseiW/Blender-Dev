"""Phase V-3.1 regression: fallback works without live state files or PySide6.

Run from Blender-Dev root: python tests/test_phase_v3_1_contract.py
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


def extracted(file, name, cls=None, namespace=None):
    module = ast.parse(file.read_text(encoding='utf-8'), filename=str(file))
    nodes = module.body
    if cls:
        nodes = next(node.body for node in nodes if isinstance(node, ast.ClassDef) and node.name == cls)
    target = next(node for node in nodes if isinstance(node, ast.FunctionDef) and node.name == name)
    scope = dict(namespace or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[target], type_ignores=[])), str(file), 'exec'), scope)
    return scope[name]


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def test_no_live_file_timeline_fallback_and_queued_cut():
    # Simulate a Blender bridge that handles only its existing snapshot/select_cut
    # requests, with no state/latest.json publisher at all.
    key = extracted(QT, 'manager_data_key', namespace={'json': json})
    probe = extracted(QT, '_poll_viewer_snapshot_fallback', 'ManagerWindow',
                      namespace={'time': time, 'uuid4': uuid4, 'write_json_atomic': write_json})
    command = extracted(QT, 'command', 'ManagerWindow',
                        namespace={'uuid4': uuid4, 'write_json_atomic': write_json,
                                   'time': time})
    poll = extracted(QT, '_poll', 'ManagerWindow',
                     namespace={'time': time, 'read_json': read_json, 'manager_data_key': key,
                                'QTimer': SimpleNamespace(singleShot=lambda *_: None)})
    initial = {'scene': 'Scene', 'frame': 2, 'active_cut_index': 0,
               'active_category': 'KEYFRAME', 'auto_sync': True, 'cuts': []}
    changed = dict(initial, frame=14)
    chosen = dict(changed, active_cut_index=1)
    events = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / 'requests').mkdir()
        (root / 'responses').mkdir()
        viewer = SimpleNamespace(set_snapshot=lambda state: events.append(('viewer', state['frame'], state['active_cut_index'])))
        pages = SimpleNamespace(currentWidget=lambda: viewer)
        ui = SimpleNamespace(
            demo=False, session_dir=root, pending=None,
            state=initial, _viewer_page=viewer, _pages=pages,
            _last_live_state_at=0.0, _last_viewer_probe_at=0.0,
            _live_mtime_ns=None, _viewer_probe_pending=False,
            _queued_viewer_command=None, _manager_data_key=key(initial),
            _manager_needs_render=False, last_response=0.0, pending_since=0.0,
            _set_status=lambda msg, error=False: events.append(('status', msg, error)),
            _render=lambda: events.append(('manager_redraw',)),
            _poll_live_state=lambda: None,
        )
        ui._poll_viewer_snapshot_fallback = MethodType(probe, ui)
        ui.command = MethodType(command, ui)
        # With NO live state directory, background polling must still send request.
        poll(ui)
        assert ui.pending and ui._viewer_probe_pending
        first_request = read_json(root / 'requests' / (ui.pending + '.json'))
        assert first_request['action'] == 'snapshot'
        assert not (root / 'state' / 'latest.json').exists()

        # A user selecting Cut while the silent poll is in flight must not be lost.
        ui.command('select_cut', index=1)
        assert ui._queued_viewer_command == ('select_cut', {'index': 1})
        assert ui.pending == first_request['id']

        # Existing Blender snapshot responds with current frame 14.
        write_json(root / 'responses' / (ui.pending + '.json'),
                   {'ok': True, 'state': changed, 'message': 'snapshot'})
        poll(ui)
        assert ('viewer', 14, 0) in events, 'Timeline frame must update Viewer'
        assert ('manager_redraw',) not in events, 'Automatic update cannot reset Manager editor'
        assert ui._manager_needs_render is False, 'Frame-only change should not redraw Manager later'
        assert ui.pending is None and not ui._viewer_probe_pending

        # Queued Cut command goes out on next timer tick.
        poll(ui)
        assert ui.pending and not ui._viewer_probe_pending
        second_request = read_json(root / 'requests' / (ui.pending + '.json'))
        assert second_request['action'] == 'select_cut'
        assert second_request['args'] == {'index': 1}
        write_json(root / 'responses' / (ui.pending + '.json'),
                   {'ok': True, 'state': chosen, 'message': 'カットを更新'})
        poll(ui)
        assert ui.state['active_cut_index'] == 1
        print('PASS: no live file -> snapshot follows Timeline, cut selection queued, no Manager redraw')


def test_cut_selection_signal_and_static_guards():
    code_qt = QT.read_text(encoding='utf-8')
    code_viewer = VIEWER.read_text(encoding='utf-8')
    assert 'UI_V3_1_VIEWER_POLL_FALLBACK' in code_qt
    assert 'UI_V3_1_VIEWER_CUT_SELECTOR' in code_viewer
    assert 'self.cut_combo.currentIndexChanged.connect(self._cut_selected)' in code_viewer
    assert 'with QSignalBlocker(self.cut_combo):' in code_viewer
    assert 'self._viewer_page.cutRequested.connect(self._request_viewer_cut)' in code_qt
    assert 'self.command(\'select_cut\', index=index)' in code_qt
    emitted = []
    callback = extracted(VIEWER, '_cut_selected', 'ViewerPage')
    receiver = SimpleNamespace(cutRequested=SimpleNamespace(emit=lambda idx: emitted.append(idx)))
    callback(receiver, -1)
    callback(receiver, 2)
    assert emitted == [2]
    for path in (QT, VIEWER):
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    print('PASS: Viewer Cut ComboBox, selection signal, live-state blocker, AST syntax')


if __name__ == '__main__':
    test_no_live_file_timeline_fallback_and_queued_cut()
    test_cut_selection_signal_and_static_guards()
    print('=== ALL PHASE V-3.1 CONTRACT TESTS PASSED ===')
