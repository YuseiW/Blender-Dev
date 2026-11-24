"""Post-install source contracts: run from BlenderDev root after --apply."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / 'scripts/addons/anim_reference_tool'
RETIRED = (
    'ui/viewer_panel.py', 'ui/reference_editor.py', 'ui/manager_panels.py',
    'operators/viewer.py', 'operators/manager_workspace.py',
)


def test_legacy_files_retired():
    for rel in RETIRED:
        assert not (ADDON / rel).exists(), f'{rel} was not retired'
    ui = (ADDON / 'ui/__init__.py').read_text(encoding='utf-8-sig')
    ops = (ADDON / 'operators/__init__.py').read_text(encoding='utf-8-sig')
    timeline = (ADDON / 'managers/timeline_manager.py').read_text(encoding='utf-8-sig')
    panel = (ADDON / 'ui/main_panel.py').read_text(encoding='utf-8-sig')
    assert 'from . import main_panel' in ui
    assert 'from . import manager_external' in ops
    assert 'from . import viewer\n' not in ops
    assert 'UI_V5_2_LEGACY_IMAGE_EDITOR_RETIRED' in timeline
    assert 'def resolve_reference_at_frame(' in timeline
    assert 'frame_changed(scene)' in timeline
    assert panel.count('"animref.open_external_manager"') == 1
    assert '"animref.open_viewer"' not in panel
    for rel in ('qt/qt_manager_app.py','qt/qt_viewer_page.py','operators/manager_external.py',
                'managers/camera_overlay_manager.py','managers/image_manager.py','managers/viewer_manager.py',
                'managers/timeline_manager.py','operators/__init__.py','ui/__init__.py'):
        f = ADDON / rel
        assert f.is_file(), rel
        ast.parse(f.read_text(encoding='utf-8-sig'), filename=str(f))
    print('PASS: old UI files absent; Qt, camera, timeline and launcher sources preserved')


if __name__ == '__main__':
    test_legacy_files_retired()
    print('=== V-5.3 CONTRACT TESTS PASSED ===')
