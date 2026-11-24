"""R-7.1: remove owned camera overlays when the external Qt session ends."""
import argparse
import ast
import subprocess
from pathlib import Path

BASE = Path('scripts/addons/anim_reference_tool')
HELPER = '''def end_session():
    """Disable overlay for all Scenes and retire only AnimRef-owned slots."""
    for scene in bpy.data.scenes:
        if getattr(scene, 'animref_overlay_enabled', False):
            scene.animref_overlay_enabled = False
    for camera in bpy.data.cameras:
        _retire_foreign_slots(camera, None)
        _restore_visibility_if_empty(camera)
    _RUNTIME.clear()


'''
TEST = '''"""Qt shutdown regression; no Blender or Qt required."""
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
'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--check',action='store_true'); g.add_argument('--apply',action='store_true')
    a=p.parse_args()
    dirty=subprocess.check_output(['git','status','--porcelain','--','scripts','tests','docs'],text=True)
    dirty=[s for s in dirty.splitlines() if '__pycache__' not in s and not s.endswith(('.pyc','.pyo'))]
    if dirty: raise SystemExit('Commit relevant changes first:\n'+'\n'.join(dirty))
    changes={}
    def edit(path,old,new):
        s=path.read_text(encoding='utf-8-sig')
        if s.count(old)!=1: raise SystemExit('Unexpected baseline: '+str(path))
        changes[path]=s.replace(old,new,1)
    overlay=BASE/'managers/camera_overlay_manager.py'
    bridge=BASE/'operators/manager_external.py'
    edit(overlay,'def unregister():\n',HELPER+'def unregister():\n')
    edit(bridge,'    _last_live_signature = None\n    _last_live_error = None\n    _process = None\n    _source_window_pointer = None\n    if _session_dir is not None:\n        shutil.rmtree(_session_dir, ignore_errors=True)\n        _session_dir = None', '''    try:
        if _process is not None or _session_dir is not None:
            camera_overlay_manager.end_session()
    finally:
        _last_live_signature = None
        _last_live_error = None
        _process = None
        _source_window_pointer = None
        if _session_dir is not None:
            shutil.rmtree(_session_dir, ignore_errors=True)
            _session_dir = None''')
    test=Path('tests/test_qt_shutdown_overlay.py')
    if test.exists(): raise SystemExit('Test already exists: '+str(test))
    changes[test]=TEST
    runner=Path('tests/run_regression.py')
    edit(runner,'"test_reference_autoscroll.py")','"test_reference_autoscroll.py", "test_qt_shutdown_overlay.py")')
    note='\n\n## R-7.1 — Qt session shutdown\n\nQt process exit disables camera overlay for all Scenes and removes only AnimRef-owned slots, including orphaned slots. Opacity and project data are preserved. Reopening Qt starts with overlay OFF. Mock and Blender verification pending.\n'
    for name in ('CURRENT_SPEC.md','DEVELOPMENT_LOG.md','DECISIONS.md'):
        path=Path('docs')/name
        changes[path]=path.read_text(encoding='utf-8-sig')+note
    for path,s in changes.items():
        if path.suffix=='.py': ast.parse(s,filename=str(path))
        print('WRITE',path)
    if a.check: print('PASS: preflight / syntax; no changes'); return
    backups={p:p.read_bytes() if p.exists() else None for p in changes}
    try:
        for path,s in changes.items(): path.write_bytes(s.encode('utf-8'))
    except BaseException:
        for path,b in backups.items():
            if b is None: path.unlink(missing_ok=True)
            else: path.write_bytes(b)
        raise
    print('PASS: applied. Run python tests/run_regression.py')
if __name__=='__main__': main()
