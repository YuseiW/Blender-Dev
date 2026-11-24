"""Pure-Python V-5.3 install safety tests, no Blender/PySide6 required."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / 'apply_phase_v5_3.py'


def fixture(root: Path, eol='\n'):
    addon = root / 'scripts/addons/anim_reference_tool'
    def put(rel, contents, base=addon):
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents.replace('\n', eol).encode('utf8'))
    put('ui/__init__.py', 'from . import main_panel\nmodules = (main_panel,)\n')
    put('operators/__init__.py', 'from . import manager_external\nmodules = (manager_external,)\n')
    put('ui/main_panel.py', '''# UI_V3_2_LAUNCHER_ONLY
def draw():
    self.layout.operator("animref.open_external_manager")
''')
    put('timeline_manager.py', '''# UI_V5_2_LEGACY_IMAGE_EDITOR_RETIRED
def resolve_reference_at_frame(*args):
    return None

def on_frame_change(scene):
    frame_changed(scene)
''')
    put('qt_viewer_page.py', '# UI_V4_CAMERA_OVERLAY\n')
    put('camera_overlay_manager.py', 'def _retire_foreign_slots(camera, current_token):\n    pass\n')
    put('operators/manager_external.py', '# UI_V4_CAMERA_OVERLAY\n')
    put('image_manager.py', 'def load_blender_image(asset):\n    pass\n')
    put('viewer_manager.py', 'def find_viewer_window(wm):\n    pass\n')
    for name in ('ui/viewer_panel.py','ui/reference_editor.py','ui/manager_panels.py',
                 'operators/viewer.py','operators/manager_workspace.py'):
        put(name, 'def legacy():\n    pass\n')
    for rel in ('docs/CURRENT_SPEC.md','docs/DECISIONS.md','docs/DEVELOPMENT_LOG.md'):
        put(rel, '# Baseline\n', root)
    shutil.copy2(INSTALLER, root / 'apply_phase_v5_3.py')
    return addon


def run(root, *args):
    return subprocess.run([sys.executable, str(root / 'apply_phase_v5_3.py'), *args],
                          cwd=root, capture_output=True, text=True)


def test_check_apply_idempotent():
    for eol in ('\n', '\r\n'):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            addon = fixture(root, eol=eol)
            before = (addon / 'ui/viewer_panel.py').read_bytes()
            result = run(root)
            assert result.returncode == 0, result.stdout + result.stderr
            assert (addon / 'ui/viewer_panel.py').read_bytes() == before, 'CHECK must never edit'
            applied = run(root, '--apply')
            assert applied.returncode == 0, applied.stdout + applied.stderr
            assert 'V-5.3適用成功' in applied.stdout
            assert not (addon / 'ui/viewer_panel.py').exists()
            assert not (addon / 'operators/viewer.py').exists()
            assert (addon / 'viewer_manager.py').exists(), 'still needed by legacy importers'
            assert (addon / 'image_manager.py').exists()
            assert (root / '.gitignore').exists()
            assert '__pycache__/' in (root / '.gitignore').read_text(encoding='utf8')
            assert 'Phase V-5.3' in (root / 'docs/CURRENT_SPEC.md').read_text(encoding='utf8')
            if eol == '\r\n':
                assert b'\r\n' in (root / 'docs/CURRENT_SPEC.md').read_bytes()
            # A second application is a no-op.
            again = run(root, '--apply')
            assert again.returncode == 0, again.stdout + again.stderr
            assert '既に適用済み' in again.stdout
    print('PASS: --check read-only, LF+CRLF, backup, targeted deletion, idempotency')


def test_stale_registration_and_references_fail_closed():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        addon = fixture(root)
        (addon / 'ui/__init__.py').write_text('from . import main_panel, viewer_panel\n', encoding='utf8')
        result = run(root, '--apply')
        assert result.returncode != 0
        assert (addon / 'ui/viewer_panel.py').exists()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        addon = fixture(root)
        (addon / 'helper.py').write_text('from .ui import viewer_panel\n', encoding='utf8')
        result = run(root, '--apply')
        assert result.returncode != 0
        assert (addon / 'ui/viewer_panel.py').exists()
        assert not (root / '.gitignore').exists()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        addon = fixture(root)
        (addon / 'timeline_manager.py').write_text('def old(): pass\n', encoding='utf8')
        result = run(root, '--apply')
        assert result.returncode != 0
        assert (addon / 'ui/viewer_panel.py').exists()
    print('PASS: unexpected registration, imports and baseline block all edits')


if __name__ == '__main__':
    test_check_apply_idempotent()
    test_stale_registration_and_references_fail_closed()
    print('=== V-5.3 INSTALLER TESTS PASSED ===')
