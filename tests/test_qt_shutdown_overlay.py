"""Qt shutdown regression; no Blender or Qt required."""
import ast
from pathlib import Path
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[1] / 'scripts/addons/anim_reference_tool'

def load_function(path, name, scope):
    node = next(n for n in ast.parse(path.read_text(encoding='utf-8-sig')).body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
    return scope[name]

def main():
    scenes = [SimpleNamespace(animref_overlay_enabled=True, animref_overlay_opacity=.4),
              SimpleNamespace(animref_overlay_enabled=False, animref_overlay_opacity=.7)]
    camera = SimpleNamespace(slots=['user', 'animref'], visibility=True)
    runtime = {1: 'cached'}
    def retire(cam, token):
        assert token is None
        assert not any(s.animref_overlay_enabled for s in scenes)
        cam.slots.remove('animref') if 'animref' in cam.slots else None
    def restore(cam):
        cam.visibility = False
    overlay = load_function(BASE/'managers/camera_overlay_manager.py', 'end_session', {
        'bpy': SimpleNamespace(data=SimpleNamespace(scenes=scenes,cameras=[camera])),
        '_retire_foreign_slots': retire, '_restore_visibility_if_empty': restore,
        '_RUNTIME': runtime})
    removed = []
    scope = dict(_process=object(), _session_dir='session', _source_window_pointer=1,
                 _last_live_signature=1, _last_live_error=1,
                 camera_overlay_manager=SimpleNamespace(end_session=overlay),
                 shutil=SimpleNamespace(rmtree=lambda p, **kw: removed.append(p)))
    cleanup = load_function(BASE/'operators/manager_external.py', '_cleanup', scope)
    cleanup()
    assert camera.slots == ['user'] and not camera.visibility and not runtime
    assert [s.animref_overlay_opacity for s in scenes] == [.4,.7]
    assert not any(s.animref_overlay_enabled for s in scenes)
    assert scope['_process'] is None and scope['_session_dir'] is None
    assert removed == ['session']
    scenes[0].animref_overlay_enabled = True
    cleanup()  # No active Qt session: do not touch scene state.
    assert scenes[0].animref_overlay_enabled
    print('PASS: session cleanup, overlay disable, user layer preservation (mock), idle guard')

if __name__ == '__main__':
    main()
