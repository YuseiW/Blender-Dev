"""Pure Python Phase V-2 contract tests, no PySide6/Blender installation required.

Run after applying from Blender-Dev root:
    python tests/test_phase_v2_contract.py
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'scripts/addons/anim_reference_tool'
PAGE = ADDON / 'qt_viewer_page.py'
MANAGER = ADDON / 'qt_manager_app.py'


def extract_function(name):
    module = ast.parse(PAGE.read_text(encoding='utf-8'))
    function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(PAGE), 'exec'), ns)
    return ns[name]


def check_zoom():
    f = extract_function('next_zoom_scale')
    assert f(1, 120) > 1
    assert f(1, -120) < 1
    assert f(0.5, 0) == 0.5
    for delta in range(-360, 361, 30):
        assert 0.01 <= f(1, delta) <= 32.0
    assert f(31, 2000) == 32.0
    assert f(0.01, -2000) == 0.01
    assert abs(f(f(1, 120), -120) - 1) < 1e-8
    print('PASS: zoom in/out, limits, inverse scale')


def check_reference():
    selector = extract_function('reference_at_current_frame')
    signature = extract_function('reference_list_signature')
    refs = [{'uid': 'r1', 'image_id': 'a', 'start': 1, 'end': 8, 'duration': 8},
            {'uid': 'r2', 'image_id': 'b', 'start': 9, 'end': 20, 'duration': 12}]
    state = {'frame': 9, 'active_cut_index': 0, 'active_category': 'KEYFRAME',
             'images': [{'uid':'a', 'name':'one', 'path':'a.png'},
                        {'uid':'b', 'name':'two', 'path':'b.png'}],
             'cuts': [{'uid': 'cut1', 'name': 'C001', 'categories': {'KEYFRAME': refs}}]}
    cut, current, asset, found = selector(state)
    assert current['uid'] == 'r2' and asset['uid'] == 'b' and found == refs
    lookup = {a['uid']: a for a in state['images']}
    sig1 = signature(cut, 'KEYFRAME', found, lookup)
    state['frame'] = 19
    sig2 = signature(cut, 'KEYFRAME', found, lookup)
    assert sig1 == sig2, 'frame-only changes must not rebuild the list'
    refs[0]['duration'] = 10
    assert signature(cut, 'KEYFRAME', found, lookup) != sig1
    refs[0]['duration'] = 8
    lookup['a']['name'] = 'renamed'
    assert signature(cut, 'KEYFRAME', found, lookup) != sig1
    state['frame'] = 21
    assert selector(state)[1] is None
    assert selector(None) == (None, None, None, [])
    print('PASS: image selection, list fingerprint and empty frames')


def check_compat():
    page = PAGE.read_text(encoding='utf-8')
    manager = MANAGER.read_text(encoding='utf-8')
    ast.parse(page); ast.parse(manager)
    for tag in ('UI_QT_VIEWER_DISPLAY_V2', 'class ViewerPage(QWidget)',
                'class ImageCanvas(QGraphicsView)', 'self.instruction.setReadOnly(True)',
                'self.references.setSelectionMode(QListWidget.SelectionMode.NoSelection)',
                'self.sync_toggle.toggled.connect(self.syncRequested.emit)',
                'def fit_image(self):', 'def actual_size(self):',
                'def wheelEvent(self, event):', 'def _highlight_current(self, refs, current_uid, category, scroll=False):',
                'self._list_signature = signature'):
        assert tag in page, tag
    for tag in ('UI_QT_VIEWER_STACK_V1', 'UI_QT_SAVE_REORDER_V1',
                'UI1_EXPLORER_IMAGE_DROP_V1', 'UI_QT_REFERENCE_AUTOSCROLL_V1',
                'self._viewer_page.set_snapshot(s)'):
        assert tag in manager, tag
    assert ('self.overlay_toggle.setEnabled(False)' in page or
            'self.overlay_toggle.toggled.connect' in page)
    assert 'import bpy' not in page and 'from bpy' not in page
    print('PASS: V-1 integration, Manager features retained, Viewer read only')


if __name__ == '__main__':
    check_zoom()
    check_reference()
    check_compat()
    print('=== ALL PHASE V-2 CONTRACT TESTS PASSED ===')
