"""Post-application verification for the V-5.3.1 AnimRef cleanup."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ADDON=ROOT/'scripts/addons/anim_reference_tool'
OLD=(
 'ui/viewer_panel.py','ui/reference_editor.py','ui/manager_panels.py',
 'operators/viewer.py','operators/manager_workspace.py',
)
REQUIRED=(
 'ui/__init__.py','operators/__init__.py','ui/main_panel.py',
 'qt_manager_app.py','qt_viewer_page.py','operators/manager_external.py',
 'managers/camera_overlay_manager.py','managers/timeline_manager.py','managers/image_manager.py',
 'managers/viewer_manager.py',
)


def main():
    for rel in OLD:
        assert not (ADDON/rel).exists(), f'legacy file remains: {rel}'
    for rel in REQUIRED:
        path=ADDON/rel
        assert path.is_file(),f'missing active file: {rel}'
        ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
    ui=(ADDON/'ui/__init__.py').read_text(encoding='utf-8-sig')
    ops=(ADDON/'operators/__init__.py').read_text(encoding='utf-8-sig')
    panel=(ADDON/'ui/main_panel.py').read_text(encoding='utf-8-sig')
    tl=(ADDON/'managers/timeline_manager.py').read_text(encoding='utf-8-sig')
    assert 'from . import main_panel' in ui
    assert 'from . import manager_external' in ops
    assert 'from . import viewer_panel' not in ui
    assert 'from . import viewer\n' not in ops
    assert ('animref.open_external_manager' in panel and 'animref.open_viewer' not in panel)
    assert 'LEGACY_VIEWER_RETIRED' in tl and 'frame_changed(scene)' in tl
    print('PASS: retired sources removed and Qt / camera / timeline / launcher preserved')

if __name__=='__main__':
    main()
