"""Read-only/dry-run and safe legacy cleanup tests, no bpy or PySide6."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT / 'apply_phase_v5_3_1.py'


def fixture(root: Path, eol='\n'):
    addon=root/'scripts/addons/anim_reference_tool'
    def put(name, source, base=addon):
        p=base/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(source.replace('\n',eol).encode('utf-8'))
        return p
    put('ui/__init__.py','from . import main_panel\nmodules=(main_panel,)\n')
    put('operators/__init__.py','from . import manager_external\nmodules=(manager_external,)\n')
    put('ui/main_panel.py','''def draw(self):
    self.layout.operator('animref.open_external_manager')
''')
    put('timeline_manager.py','''def resolve_reference_at_frame(project,cut,category,frame):
    return None

def sync_reference_display(scene):
    """Old compatibility function."""
    return {'status':'LEGACY_VIEWER_RETIRED','reference':None,'image_asset':None,'frame_start':None,'frame_end':None}

def on_frame_change(scene):
    frame_changed(scene)
''')
    put('qt_viewer_page.py',"class Viewer:\n    overlayRequested='signal'\n")
    put('camera_overlay_manager.py','def _retire_foreign_slots(camera, token):\n    pass\n')
    put('operators/manager_external.py',"def process(action):\n    if action == 'set_overlay_enabled': pass\n    if action == 'set_overlay_opacity': pass\n")
    put('image_manager.py','def load_blender_image(asset): pass\n')
    put('viewer_manager.py','def find_viewer_window(wm): pass\n')
    for name in ('ui/viewer_panel.py','ui/reference_editor.py','ui/manager_panels.py',
                 'operators/viewer.py','operators/manager_workspace.py'):
        put(name, 'def old(): pass\n')
    for name in ('docs/CURRENT_SPEC.md','docs/DECISIONS.md','docs/DEVELOPMENT_LOG.md'):
        put(name,'# Baseline\n',root)
    shutil.copy2(SCRIPT,root/SCRIPT.name)
    return addon


def run(root,*args):
    return subprocess.run([sys.executable,str(root/SCRIPT.name),*args],cwd=root,
                          capture_output=True,text=True)


def test_success_no_marker_both_line_endings():
    for eol in ('\n','\r\n'):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            addon=fixture(root,eol)
            initial=(addon/'ui/viewer_panel.py').read_bytes()
            chk=run(root,'--check')
            assert chk.returncode == 0, chk.stdout+chk.stderr
            assert (addon/'ui/viewer_panel.py').read_bytes() == initial
            assert not (root/'.gitignore').exists()
            applied=run(root,'--apply')
            assert applied.returncode == 0,applied.stdout+applied.stderr
            assert 'V-5.3.1適用成功' in applied.stdout
            assert not (addon/'ui/viewer_panel.py').exists()
            assert (addon/'viewer_manager.py').is_file()
            assert 'Phase V-5.3' in (root/'docs/CURRENT_SPEC.md').read_text()
            assert '__pycache__/' in (root/'.gitignore').read_text()
            again=run(root,'--apply')
            assert again.returncode == 0, again.stdout+again.stderr
            assert '既に適用済み' in again.stdout
            if eol=='\r\n':
                assert b'\r\n' in (root/'docs/CURRENT_SPEC.md').read_bytes()
    print('PASS: marker-independent V5.2 structure, LF CRLF, dry run, apply, idempotency')


def test_fail_closed():
    cases = [
      ('old import', 'ui/__init__.py', 'from . import main_panel, viewer_panel\n'),
      ('no retired guard', 'timeline_manager.py', '''def resolve_reference_at_frame(*args): return None

def sync_reference_display(scene):
    return {'status':'OK'}

def on_frame_change(scene):
    frame_changed(scene)
'''),
      ('hidden import', 'extra.py','from .ui import viewer_panel\n'),
      ('dynamic import', 'extra.py','import importlib\nx=importlib.import_module("anim_reference_tool.ui.viewer_panel")\n'),
    ]
    for title,rel,source in cases:
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            addon=fixture(root)
            p=addon/rel
            p.write_text(source, encoding='utf8')
            res=run(root,'--apply')
            assert res.returncode != 0,(title,res.stdout,res.stderr)
            assert (addon/'ui/viewer_panel.py').is_file(),title
            assert not (root/'.gitignore').exists(),title
            assert ('旧' in res.stderr or '旧' in res.stdout or '不一致' in res.stderr),title
    print('PASS: stale registrations, missing V5.2 guard, static/dynamic imports all block deletion')

if __name__ == '__main__':
    test_success_no_marker_both_line_endings()
    test_fail_closed()
    print('=== V5.3.1 TESTS PASSED ===')
