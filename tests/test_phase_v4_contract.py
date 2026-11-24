"""Phase V-4: source contract + Blender API simulation (no bpy/PySide6 install)."""
import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'scripts/addons/anim_reference_tool'


def check_sources():
    names = ('qt_viewer_page.py', 'qt_manager_app.py', 'operators/manager_external.py',
             'timeline_manager.py', 'camera_overlay_manager.py')
    src = {}
    for name in names:
        path = ADDON / name
        value = path.read_text(encoding='utf-8')
        ast.parse(value, filename=str(path))
        src[name] = value
    viewer = src['qt_viewer_page.py']
    manager = src['qt_manager_app.py']
    bridge = src['operators/manager_external.py']
    timeline = src['timeline_manager.py']
    overlay = src['camera_overlay_manager.py']
    assert 'UI_V4_CAMERA_OVERLAY' in viewer and 'UI_V4_CAMERA_OVERLAY' in manager and 'UI_V4_CAMERA_OVERLAY' in bridge
    assert 'overlayRequested = Signal(bool)' in viewer and 'opacityRequested = Signal(int)' in viewer
    assert 'self.overlay_toggle.toggled.connect' in viewer
    assert 'self.opacity_slider.valueChanged.connect' in viewer
    assert 'self._opacity_timer.setInterval(120)' in viewer
    assert 'self._queued_overlay_enabled' in manager and 'self._queued_overlay_opacity' in manager
    assert "'set_overlay_enabled'" in manager and "'set_overlay_opacity'" in manager
    for action in ('set_overlay_enabled', 'set_overlay_opacity', 'refresh_viewer'):
        assert f'"{action}"' in bridge
    assert '"overlay_enabled": scene.animref_overlay_enabled' in bridge
    assert '"overlay_opacity": scene.animref_overlay_opacity' in bridge
    assert 'camera_overlay_manager.register()' in bridge
    assert 'camera_overlay_manager.unregister()' in bridge
    assert 'camera_overlay_manager.sync_overlay(scene)' in bridge
    assert 'frame_changed(scene)' in timeline
    assert 'image.has_data' not in overlay.replace('Do not inspect image.has_data;', '')
    assert "slot.display_depth = 'FRONT'" in overlay
    assert "slot.frame_method = 'FIT'" in overlay
    assert "slot.show_on_foreground = True" in overlay
    assert "check_existing=False" in overlay
    assert 'if _owned(slot, token)' in overlay
    assert "bpy.data.images.remove(image)" in overlay
    print('PASS source/AST/IPC/UI contract')


class FakeImage(dict):
    def __init__(self, path):
        super().__init__()
        self.filepath = path
        self.name = ''
        self.users = 0


class FakeImageStore(list):
    def __init__(self):
        super().__init__()
        self.load_count = 0
    def load(self, path, check_existing=False):
        assert check_existing is False
        self.load_count += 1
        result = FakeImage(path)
        self.append(result)
        return result
    def remove(self, item):
        assert item.users == 0
        super().remove(item)


class FakeSlot:
    def __init__(self):
        self._image = None
        self.alpha = 1.0
    def as_pointer(self):
        return id(self)
    @property
    def image(self):
        return self._image
    @image.setter
    def image(self, value):
        if self._image is not None:
            self._image.users -= 1
        self._image = value
        if value is not None:
            value.users += 1


class FakeSlots(list):
    def new(self):
        slot = FakeSlot()
        self.append(slot)
        return slot
    def remove(self, slot):
        slot.image = None
        super().remove(slot)


class FakeCamera(dict):
    def __init__(self):
        super().__init__()
        self.background_images = FakeSlots()
        self.show_background_images = False
    def as_pointer(self):
        return id(self)


class FakeScene(dict):
    def __init__(self, cam, project):
        super().__init__()
        self.camera = types.SimpleNamespace(type='CAMERA', data=cam)
        self.animref_project = project
        self.animref_overlay_enabled = False
        self.animref_overlay_opacity = 0.5
        self.frame_current = 1
    def as_pointer(self):
        return id(self)


def mock_blender():
    bpy = types.ModuleType('bpy')
    bpy.path = types.SimpleNamespace(abspath=lambda path: path)
    bpy.data = types.SimpleNamespace(images=FakeImageStore(), cameras=[], window_managers=[], scenes=[])
    bpy.types = types.SimpleNamespace(Scene=type('BlenderScene', (), {}))
    props = types.ModuleType('bpy.props')
    props.BoolProperty = lambda **kw: kw
    props.FloatProperty = lambda **kw: kw
    bpy.props = props
    sys.modules['bpy'] = bpy
    sys.modules['bpy.props'] = props
    pkg = types.ModuleType('phase_v4_fake_pkg')
    pkg.__path__ = [str(ADDON)]
    sys.modules[pkg.__name__] = pkg
    timeline = types.ModuleType('phase_v4_fake_pkg.timeline_manager')
    def resolve(project, cut, category, frame):
        items = cut.categories.get(category, [])
        ref = next((r for r in items if r.start <= frame <= r.end), None)
        asset = next((a for a in project.images if ref and a.uid == ref.image_id), None)
        return (ref, asset, ref.start if ref else None, ref.end if ref else None)
    timeline.resolve_reference_at_frame = resolve
    sys.modules[timeline.__name__] = timeline
    spec = importlib.util.spec_from_file_location('phase_v4_fake_pkg.camera_overlay_manager', ADDON/'camera_overlay_manager.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return bpy, mod


def test_overlay_lifecycle():
    bpy, mod = mock_blender()
    with tempfile.TemporaryDirectory() as tmp:
        a = Path(tmp)/'a.png'
        b = Path(tmp)/'b.png'
        for path in (a,b):
            path.write_bytes(b'fake image: mock Blender loader')
        images = [types.SimpleNamespace(uid='assetA', filepath=str(a)),
                  types.SimpleNamespace(uid='assetB', filepath=str(b))]
        refs = [types.SimpleNamespace(uid='refA', image_id='assetA', start=1, end=8),
                types.SimpleNamespace(uid='refB', image_id='assetB', start=9, end=20)]
        cut = types.SimpleNamespace(uid='cut1', categories={'KEYFRAME': refs, 'LAYOUT': [refs[1]]})
        project = types.SimpleNamespace(images=images, cuts=[cut], active_cut_index=0,
                                        active_category='KEYFRAME', auto_sync=True)
        cam = FakeCamera()
        bpy.data.cameras.append(cam)
        scene = FakeScene(cam, project)
        bpy.data.scenes.append(scene)
        # User-supplied background must remain unchanged through full lifecycle.
        original = FakeImage('user-background.png')
        user_slot = cam.background_images.new()
        user_slot.image = original
        user_slot.alpha = 0.85
        mod.register()
        assert mod.set_enabled(scene, True) == 'OK'
        token = scene[mod.TOKEN_KEY]
        owned = [s for s in cam.background_images if mod._owned(s, token)]
        assert len(owned) == 1 and len(cam.background_images) == 2
        assert owned[0].image.filepath == str(a)
        assert owned[0].display_depth == 'FRONT' and owned[0].show_on_foreground
        assert owned[0].frame_method == 'FIT' and owned[0].alpha == 0.5
        assert cam.show_background_images
        assert bpy.data.images.load_count == 1
        # Same ref, many timeline ticks: do NOT leak Blender Image datablocks.
        for i in range(1, 8):
            scene.frame_current = i
            assert mod.frame_changed(scene) == 'OK'
        assert bpy.data.images.load_count == 1
        # OFF: freeze held reference without changing Blender current frame.
        project.auto_sync = False
        scene.frame_current = 10
        assert mod.sync_overlay(scene) == 'HELD'
        assert mod.frame_changed(scene) == 'NO_CHANGE'
        assert bpy.data.images.load_count == 1
        mod.set_opacity(scene, 0.8)
        assert abs(owned[0].alpha - 0.8) < 1e-8
        assert abs(scene.animref_overlay_opacity - 0.8) < 1e-8
        assert mod.sync_overlay(scene, explicit=True) == 'OK'
        assert bpy.data.images.load_count == 2
        assert len([s for s in cam.background_images if mod._owned(s, token)]) == 1
        assert [s for s in cam.background_images if mod._owned(s, token)][0].image.filepath == str(b)
        # Changing category explicitly while sync off must switch scope.
        project.active_category = 'LAYOUT'
        assert mod.sync_overlay(scene) == 'OK'
        assert len([s for s in cam.background_images if mod._owned(s, token)]) == 1
        # No reference at current frame means no stale overlay.
        scene.frame_current = 200
        assert mod.sync_overlay(scene, explicit=True) == 'NO_REFERENCE'
        assert list(cam.background_images) == [user_slot]
        # Enable again, then turn OFF. Restore original camera visibility.
        scene.frame_current = 10
        assert mod.sync_overlay(scene, explicit=True) == 'OK'
        assert mod.set_enabled(scene, False) == 'DISABLED'
        assert cam.show_background_images is False
        assert cam.background_images == [user_slot]
        assert user_slot.image is original and user_slot.alpha == 0.85
        assert not bpy.data.images
        mod.unregister()
    print('PASS Blender background-layer ownership, sync hold, opacity, cleanup')


def test_qt_overlay_queue():
    """Qt overlay commands must survive an in-flight snapshot probe."""
    import json
    import time
    from uuid import uuid4
    from types import MethodType
    code = ast.parse((ADDON / 'qt_manager_app.py').read_text(encoding='utf-8'))
    node = next(n for n in code.body if isinstance(n, ast.ClassDef) and n.name == 'ManagerWindow')
    def method(name, namespace=None):
        fn = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == name)
        g = dict(namespace or {})
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), str(ADDON / 'qt_manager_app.py'), 'exec'), g)
        return g[name]
    def write(path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj), encoding='utf-8')
    def read(path):
        return json.loads(path.read_text(encoding='utf-8'))
    cmd = method('command', {'uuid4': uuid4, 'write_json_atomic': write, 'time': time})
    poll = method('_poll', {'time': time, 'read_json': read,
                            'manager_data_key': lambda s: s.get('frame'),
                            'QTimer': types.SimpleNamespace(singleShot=lambda *_: None)})
    toggle = method('_request_overlay_enabled')
    opacity = method('_request_overlay_opacity')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'requests').mkdir()
        (root / 'responses').mkdir()
        view = types.SimpleNamespace(_overlay_pending=None, _opacity_pending=None, _sync_pending=None,
                                     states=[], status=types.SimpleNamespace(setText=lambda *_: None))
        def view_update(state):
            view.states.append(dict(state))
        view.set_snapshot = view_update
        ui = types.SimpleNamespace(demo=False, session_dir=root,
            state={'scene': 'Scene', 'frame': 1, 'auto_sync': True,
                   'overlay_enabled': False, 'overlay_opacity': 0.5},
            pending='probe', pending_since=time.monotonic(), last_response=0,
            _viewer_probe_pending=True, _viewer_page=view,
            _queued_viewer_command=None, _queued_sync_enabled=None, _sync_request_id=None,
            _queued_overlay_enabled=None, _queued_overlay_opacity=None,
            _overlay_request_id=None, _overlay_request_kind=None,
            _set_status=lambda *args: None,
            _poll_live_state=lambda: None, _poll_viewer_snapshot_fallback=lambda: None,
            _render=lambda: None, _manager_data_key=None)
        ui._pages = types.SimpleNamespace(currentWidget=lambda: view)
        ui.command = MethodType(cmd, ui)
        ui._request_overlay_enabled = MethodType(toggle, ui)
        ui._request_overlay_opacity = MethodType(opacity, ui)
        ui._request_overlay_enabled(True)
        assert ui._queued_overlay_enabled is True
        write(root/'responses/probe.json', {'ok': True, 'state': dict(ui.state)})
        poll(ui)
        assert ui.pending is None and ui._queued_overlay_enabled is True
        poll(ui)
        ident = ui.pending
        assert read(root/'requests'/f'{ident}.json')['action'] == 'set_overlay_enabled'
        # Latest intent must win while an earlier command is outstanding.
        ui._request_overlay_enabled(False)
        assert ui._queued_overlay_enabled is False
        reply = dict(ui.state, overlay_enabled=True)
        write(root/'responses'/f'{ident}.json', {'ok': True, 'state': reply})
        poll(ui)
        assert view._overlay_pending is False
        poll(ui)
        ident2 = ui.pending
        assert ident2 != ident
        assert read(root/'requests'/f'{ident2}.json')['args']['enabled'] is False
        write(root/'responses'/f'{ident2}.json', {'ok': True,
            'state': dict(ui.state, overlay_enabled=False)})
        poll(ui)
        assert view._overlay_pending is None
        assert ui.pending is None
        # Slider changes should coalesce: request the most recent percentage.
        ui._request_overlay_opacity(20)
        ui._request_overlay_opacity(70)
        ui._request_overlay_opacity(90)
        poll(ui)
        ident3 = ui.pending
        req = read(root/'requests'/f'{ident3}.json')
        assert req['action'] == 'set_overlay_opacity' and req['args']['percent'] == 90
        write(root/'responses'/f'{ident3}.json', {'ok': True,
            'state': dict(ui.state, overlay_opacity=0.9)})
        poll(ui)
        assert view._opacity_pending is None
        assert ui.state['overlay_opacity'] == 0.9
    print('PASS Qt pending snapshot / latest-toggle / opacity coalescing / ACK')


def test_bridge_overlay_actions():
    src = ast.parse((ADDON / 'operators/manager_external.py').read_text(encoding='utf-8'))
    fn = next(n for n in src.body if isinstance(n, ast.FunctionDef) and n.name == '_process_request')
    overlay_calls = []
    scene = types.SimpleNamespace(name='Scene', animref_project=types.SimpleNamespace(auto_sync=True))
    api = types.SimpleNamespace(
        set_enabled=lambda _s, value: (overlay_calls.append(('enabled', value)), 'OK')[1],
        set_opacity=lambda _s, value: overlay_calls.append(('opacity', value)),
        sync_overlay=lambda _s, explicit=False: overlay_calls.append(('sync', explicit)))
    scope = {'_current_window_and_scene': lambda: (None, scene),
             '_snapshot': lambda: {'scene':'Scene'},
             '_refresh_display': lambda _: None,
             'camera_overlay_manager': api}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 str(ADDON/'operators/manager_external.py'), 'exec'), scope)
    dispatch = scope['_process_request']
    def req(action, **args):
        return dispatch({'action':action,'args':args,'expect_scene':'Scene'})
    assert req('set_overlay_enabled', enabled=True)['ok']
    assert req('set_overlay_opacity', percent=25)['ok']
    assert req('refresh_viewer')['ok']
    assert overlay_calls == [('enabled', True), ('opacity', 0.25), ('sync', True)]
    for bad in (None, 'true', 1):
        try: req('set_overlay_enabled', enabled=bad)
        except ValueError: pass
        else: raise AssertionError(f'Unexpected valid enabled={bad!r}')
    for bad in (True, -1, 101, 40.1, '75'):
        try: req('set_overlay_opacity', percent=bad)
        except ValueError: pass
        else: raise AssertionError(f'Unexpected valid percent={bad!r}')
    print('PASS Blender overlay actions: validation, IPC, manual refresh')


if __name__ == '__main__':
    check_sources()
    test_overlay_lifecycle()
    test_qt_overlay_queue()
    test_bridge_overlay_actions()
    print('PASS Phase V-4 contract / mock smoke')
