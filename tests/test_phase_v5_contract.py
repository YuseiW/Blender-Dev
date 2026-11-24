"""Phase V-5 stabilization / shared Camera data smoke tests.

Uses the mock Blender API from the V-4 tests. The mock tests do not replace
an actual Blender 5.2 integration run.
"""
import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'scripts/addons/anim_reference_tool'


def load_v4_fakes():
    path = ROOT / 'tests/test_phase_v4_contract.py'
    if not path.is_file():
        raise RuntimeError('tests/test_phase_v4_contract.py が必要です（V-4を先に適用してください）')
    spec = importlib.util.spec_from_file_location('_animref_v4_test_support', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_project(tmp, item='A'):
    asset = types.SimpleNamespace(uid='asset'+item, filepath=str(Path(tmp)/(item+'.png')))
    Path(asset.filepath).write_bytes(b'fake blender loaded image')
    ref = types.SimpleNamespace(uid='ref'+item, image_id=asset.uid, start=1, end=10)
    cut = types.SimpleNamespace(uid='cut'+item, categories={'KEYFRAME':[ref]})
    return types.SimpleNamespace(images=[asset], cuts=[cut], active_cut_index=0,
                                 active_category='KEYFRAME', auto_sync=True)


def assert_user_image_survives(support, cam):
    user = support.FakeImage('existing-user-background.png')
    slot = cam.background_images.new()
    slot.image = user
    slot.alpha = 0.87
    return slot, user


def test_duplicate_scene_different_cameras():
    f = load_v4_fakes()
    bpy, mod = f.mock_blender()
    with tempfile.TemporaryDirectory() as tmp:
        ca, cb = f.FakeCamera(), f.FakeCamera()
        bpy.data.cameras.extend([ca, cb])
        a = f.FakeScene(ca, make_project(tmp,'A'))
        b = f.FakeScene(cb, make_project(tmp,'B'))
        bpy.data.scenes.extend([a,b])
        mod.register()
        slot_a, user_a = assert_user_image_survives(f,ca)
        slot_b, user_b = assert_user_image_survives(f,cb)
        assert mod.set_enabled(a,True)=='OK'
        ta = a[mod.TOKEN_KEY]
        b[mod.TOKEN_KEY] = ta  # Blender Scene duplication copies ID props.
        assert mod._token(b) is None
        assert mod.set_enabled(b,True)=='OK'
        tb = b[mod.TOKEN_KEY]
        assert ta != tb
        assert mod._any_owned(ca,ta)
        assert mod._any_owned(cb,tb)
        assert not mod._any_owned(ca,tb)
        assert not mod._any_owned(cb,ta)
        assert mod.set_enabled(b,False)=='DISABLED'
        assert mod._any_owned(ca,ta), 'Disabling B must never erase A'
        assert len(cb.background_images)==1
        assert cb.background_images[0] is slot_b and slot_b.image is user_b
        assert ca.background_images[0] is slot_a and slot_a.image is user_a
        mod.unregister()
        assert ca.background_images == [slot_a]
        assert cb.background_images == [slot_b]
    print('PASS duplicated token, separate camera data remain isolated')


def test_shared_camera_switch_restore():
    f = load_v4_fakes()
    bpy, mod = f.mock_blender()
    with tempfile.TemporaryDirectory() as tmp:
        cam = f.FakeCamera()
        bpy.data.cameras.append(cam)
        a = f.FakeScene(cam, make_project(tmp,'A'))
        b = f.FakeScene(cam, make_project(tmp,'B'))
        bpy.data.scenes.extend([a,b])
        mod.register()
        slot, user = assert_user_image_survives(f,cam)
        assert mod.set_enabled(a,True)=='OK'
        ta = a[mod.TOKEN_KEY]
        b[mod.TOKEN_KEY] = ta
        assert mod.set_enabled(b,True)=='OK'
        tb = b[mod.TOKEN_KEY]
        assert ta != tb
        assert mod._any_owned(cam,tb) and not mod._any_owned(cam,ta)
        assert len(cam.background_images)==2
        assert mod.sync_overlay(a)=='OK'
        assert mod._any_owned(cam,ta) and not mod._any_owned(cam,tb)
        assert len(cam.background_images)==2
        # B is the newly selected Scene but its overlay is OFF: no A leak.
        assert mod.set_enabled(b,False)=='DISABLED'
        assert len(cam.background_images)==1 and cam.background_images[0] is slot
        assert cam.show_background_images is False
        assert mod.sync_overlay(a)=='OK'
        assert mod._any_owned(cam,ta) and not mod._any_owned(cam,tb)
        mod.unregister()
        assert cam.background_images==[slot] and slot.image is user
        assert abs(slot.alpha - 0.87) < 1e-8
        assert cam.show_background_images is False
        assert not bpy.data.images
    print('PASS shared camera Scene switching, disable, visibility restore, user layer')


def test_orphan_cleanup():
    f = load_v4_fakes()
    bpy, mod = f.mock_blender()
    with tempfile.TemporaryDirectory() as tmp:
        cam = f.FakeCamera()
        bpy.data.cameras.append(cam)
        scene = f.FakeScene(cam, make_project(tmp,'A'))
        bpy.data.scenes.append(scene)
        mod.register()
        original, user = assert_user_image_survives(f,cam)
        assert mod.set_enabled(scene, True)=='OK'
        bpy.data.scenes.clear()  # Scene deleted before addon unregister.
        mod.unregister()
        assert cam.background_images==[original]
        assert original.image is user
        assert cam.show_background_images is False
        assert not bpy.data.images
    print('PASS orphan overlay cleanup after Scene deletion')


def test_source_contract():
    p = ADDON/'camera_overlay_manager.py'
    code = p.read_text(encoding='utf-8')
    ast.parse(code, filename=str(p))
    assert 'def _retire_foreign_slots(' in code
    assert 'def _restore_visibility_if_empty(' in code
    assert 'first_owner' in code
    assert 'old.get' in code  # hold semantics retained
    assert 'slot.display_depth = \'FRONT\'' in code
    assert "slot.frame_method = 'FIT'" in code
    assert 'bpy.data.images.remove(image)' in code
    assert 'camera.show_background_images' in code
    assert "def frame_changed(scene):" in code
    for filename in ('qt_manager_app.py','qt_viewer_page.py','operators/manager_external.py'):
        src = (ADDON/filename).read_text(encoding='utf-8')
        ast.parse(src, filename=str(ADDON/filename))
    print('PASS V5 source/AST contract')


if __name__ == '__main__':
    test_source_contract()
    test_duplicate_scene_different_cameras()
    test_shared_camera_switch_restore()
    test_orphan_cleanup()
    print('PASS Phase V-5 stabilization mock tests')
