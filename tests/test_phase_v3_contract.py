"""Phase V-3 logic + transport contract tests. Requires neither bpy nor PySide6.
Run in Blender-Dev root, after apply_phase_v3.py:
    python tests/test_phase_v3_contract.py
"""
import ast
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'scripts' / 'addons' / 'anim_reference_tool'
VIEWER = ADDON / 'qt_viewer_page.py'
QT = ADDON / 'qt_manager_app.py'
BRIDGE = ADDON / 'operators' / 'manager_external.py'


def extract(path, name, cls=None, namespace=None):
    tree = ast.parse(path.read_text(encoding='utf-8'), str(path))
    nodes = tree.body
    if cls is not None:
        nodes = next(x.body for x in nodes if isinstance(x, ast.ClassDef) and x.name == cls)
    fn = next(x for x in nodes if isinstance(x, ast.FunctionDef) and x.name == name)
    scope = dict(namespace or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), str(path), 'exec'), scope)
    return scope[name], scope


def sample_state(frame=9, category='KEYFRAME', scene_token='sceneA', cut='cut1', sync=True):
    return {'scene': 'Scene', 'scene_token': scene_token, 'frame': frame,
            'project': 'test', 'project_filepath': '', 'auto_sync': sync,
            'active_category': category, 'active_cut_index': 0,
            'images': [{'uid': 'i1', 'name': 'A', 'path': ''}, {'uid': 'i2', 'name': 'B', 'path': ''}],
            'cuts': [{'name': 'C1', 'uid': cut, 'categories': {'KEYFRAME': [
                {'uid': 'r1', 'image_id': 'i1', 'duration': 8, 'start': 1, 'end': 8, 'instruction': '一枚目'},
                {'uid': 'r2', 'image_id': 'i2', 'duration': 12, 'start': 9, 'end': 20, 'instruction': '二枚目'}
            ]}}]}


def test_hold_and_scope():
    choose, _ = extract(VIEWER, 'select_display_frame')
    select, _ = extract(VIEWER, 'reference_at_current_frame')
    pinned, _ = extract(VIEWER, 'pinned_reference')
    s = sample_state(frame=9, sync=True)
    frame, scope = choose(s)
    assert frame == 9 and select(dict(s, frame=frame))[1]['uid'] == 'r2'
    s['auto_sync'] = False
    s['frame'] = 17
    frame, scope2 = choose(s, frame, scope)
    assert frame == 9 and scope2 == scope, 'OFF must hold original reference/frame'
    s['frame'] = 3
    frame, scope2 = choose(s, frame, scope2, force=True)
    assert frame == 3 and select(dict(s, frame=frame))[1]['uid'] == 'r1'
    s['frame'] = 19
    s['active_category'] = 'LAYOUT'
    frame, scope2 = choose(s, frame, scope2)
    assert frame == 19, 'category switch must adopt current frame'
    s['frame'] = 20
    s['active_cut_index'] = 0
    s['cuts'][0]['uid'] = 'cut2'
    frame, scope2 = choose(s, frame, scope2)
    assert frame == 20, 'cut switch must adopt current frame'
    s['frame'] = 32
    s['scene_token'] = 'sceneB'
    frame, scope2 = choose(s, frame, scope2)
    assert frame == 32, 'scene switch must not retain old scene reference'
    s['frame'] = 50
    s['auto_sync'] = True
    frame, scope2 = choose(s, frame, scope2)
    assert frame == 50
    assert choose(None) == (None, None)
    # Reordering changes frame ranges, but a locked Viewer must retain the
    # reference's UID rather than silently switching to another picture.
    refs = sample_state()['cuts'][0]['categories']['KEYFRAME']
    original = pinned(refs, sample_state()['images'], 'r2')
    refs[:] = list(reversed(refs))
    refs[0]['start'], refs[0]['end'] = 1, 12
    refs[1]['start'], refs[1]['end'] = 13, 20
    after_move = pinned(refs, sample_state()['images'], 'r2')
    assert original[0]['uid'] == after_move[0]['uid'] == 'r2'
    assert original[1]['uid'] == after_move[1]['uid'] == 'i2'
    assert pinned(refs, sample_state()['images'], 'missing') == (None, None)
    print('PASS: live follow, OFF hold, manual refresh, category/cut/scene rebind, resume')


def test_nonblocking_publisher():
    recorded = []
    current = sample_state()
    def writer(path, data):
        recorded.append((Path(path), json.loads(json.dumps(data))))
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')
    func, scope = extract(BRIDGE, '_publish_viewer_state', namespace={
        '_last_live_signature': None, '_last_live_error': None,
        '_snapshot': lambda: current,
        'json': json, 'Path': Path,
        'write_json_atomic': writer,
    })
    with tempfile.TemporaryDirectory() as directory:
        func(Path(directory))
        assert len(recorded) == 1 and recorded[-1][0].name == 'latest.json'
        assert recorded[-1][1]['state']['frame'] == 9
        func(Path(directory))
        assert len(recorded) == 1, 'identical state must not cause a second write'
        current['frame'] = 12
        func(Path(directory))
        assert len(recorded) == 2 and recorded[-1][1]['state']['frame'] == 12
        current['auto_sync'] = False
        func(Path(directory))
        assert len(recorded) == 3
        assert scope['_last_live_error'] is None
    print('PASS: Blender publishes only changes, including frame and sync flag')


def test_bridge_auto_sync():
    state = sample_state(sync=True)
    proj = SimpleNamespace(auto_sync=True)
    scene = SimpleNamespace(name='Scene', animref_project=proj)
    calls = []
    fn, _ = extract(BRIDGE, '_process_request', namespace={
        '_current_window_and_scene': lambda: (None, scene),
        '_snapshot': lambda: {'scene': 'Scene', 'auto_sync': proj.auto_sync},
        '_refresh_display': lambda s: calls.append('sync'),
        'camera_overlay_manager': SimpleNamespace(sync_overlay=lambda *_: None),
        'bpy': SimpleNamespace(context=SimpleNamespace(scene=scene)),
    })
    result = fn({'action': 'set_auto_sync', 'args': {'enabled': False}, 'expect_scene': 'Scene'})
    assert result['ok'] and not proj.auto_sync and not calls
    result = fn({'action': 'set_auto_sync', 'args': {'enabled': True}, 'expect_scene': 'Scene'})
    assert result['ok'] and proj.auto_sync and calls == ['sync']
    for args in ({'enabled': 'yes'}, {'enabled': 1}, {'enabled': None}, {}):
        try:
            fn({'action': 'set_auto_sync', 'args': args, 'expect_scene': 'Scene'})
        except ValueError:
            pass
        else:
            raise AssertionError('bad sync flag must be rejected')
    try:
        fn({'action': 'set_auto_sync', 'args': {'enabled': False}, 'expect_scene': 'Other'})
    except ValueError:
        pass
    else:
        raise AssertionError('cross-scene sync command must be rejected')
    print('PASS: toggling ON/OFF, visual refresh on ON, validation and scene guard')


def test_qt_watcher():
    key, _ = extract(QT, 'manager_data_key', namespace={'json': json})
    s1 = sample_state(frame=9)
    s2 = sample_state(frame=20)
    assert key(s1) == key(s2), 'frame-only changes must not require Manager redraw'
    s2['cuts'][0]['categories']['KEYFRAME'][0]['instruction'] = '変更'
    assert key(s1) != key(s2)
    with tempfile.TemporaryDirectory() as directory:
        p = Path(directory) / 'state' / 'latest.json'
        p.parent.mkdir(parents=True, exist_ok=True)
        view = SimpleNamespace(states=[], set_snapshot=lambda state: view.states.append(state))
        pages = SimpleNamespace(active=view, currentWidget=lambda: pages.active)
        ui = SimpleNamespace(session_dir=Path(directory), pending=None, _pages=pages,
                             _viewer_page=view, _live_mtime_ns=None, state=s1,
                             _manager_data_key=key(s1), _manager_needs_render=False)
        fn, _ = extract(QT, '_poll_live_state', cls='ManagerWindow', namespace={
            'read_json': lambda path: json.loads(Path(path).read_text(encoding='utf-8')),
            'manager_data_key': key, 'time': __import__('time'),
        })
        fn(ui)
        assert not view.states, 'missing state file must be ignored'
        p.write_text(json.dumps({'schema': 1, 'state': s2}), encoding='utf-8')
        fn(ui)
        assert view.states[-1]['frame'] == 20 and ui._manager_needs_render
        fn(ui)
        assert len(view.states) == 1, 'unchanged mtime must not re-render'
        ui.pending = 'request'
        ui._live_mtime_ns = None
        fn(ui)
        assert len(view.states) == 1, 'never race with a pending edit command'
        ui.pending = None
        pages.active = object()
        fn(ui)
        assert len(view.states) == 1, 'Manager screen must never be redrawn by live data'
    print('PASS: Qt independent state reader, pending-command guard, Manager noninterference')


def test_regression_static():
    for p in (VIEWER, QT, BRIDGE):
        ast.parse(p.read_text(encoding='utf-8'), str(p))
    a, b, c = (p.read_text(encoding='utf-8') for p in (VIEWER, QT, BRIDGE))
    assert 'UI_V3_TIMELINE_VIEWER_HOLD' in a
    assert "pinned_reference(refs, state.get('images', []), self._held_uid)" in a
    assert 'UI_V3_TIMELINE_LIVE_CLIENT' in b
    assert 'UI_V3_TIMELINE_LIVE_PUBLISH' in c
    assert 'self.sync_toggle.toggled.connect(self.syncRequested.emit)' in a
    assert 'with QSignalBlocker(self.sync_toggle):' in a
    assert ('self.overlay_toggle.setEnabled(False)' in a or
            'self.overlay_toggle.toggled.connect' in a)
    assert 'self._viewer_page.syncRequested.connect(self._request_auto_sync)' in b
    assert 'self._manager_needs_render' in b
    assert ("self.command('set_auto_sync', enabled=bool(enabled))" in b or
            "self.command('set_auto_sync', enabled=wanted)" in b)
    assert '_publish_viewer_state(root)' in c
    assert '"scene_token"' in c
    assert '"set_auto_sync"' in c
    assert 'UI_QT_VIEWER_DISPLAY_V2' in a
    for tag in ('UI_QT_REFERENCE_AUTOSCROLL_V1', 'UI_QT_SAVE_REORDER_V1',
                'UI1_EXPLORER_IMAGE_DROP_V1', 'UI_QT_VIEWER_STACK_V1'):
        assert tag in b
    assert 'import bpy' not in a and 'import bpy' not in b
    print('PASS: V-2 features and Manager/Viewer separation retained')


if __name__ == '__main__':
    test_hold_and_scope()
    test_nonblocking_publisher()
    test_bridge_auto_sync()
    test_qt_watcher()
    test_regression_static()
    print('=== ALL PHASE V-3 CONTRACT TESTS PASSED ===')
