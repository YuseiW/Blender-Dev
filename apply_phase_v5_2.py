"""V-5.2: retire legacy Image Editor sync, preserve Qt and camera overlay."""
import argparse
import ast
from pathlib import Path
import subprocess
import sys

BASE = Path('scripts/addons/anim_reference_tool')
MARK = 'UI_V5_2_LEGACY_IMAGE_EDITOR_RETIRED'
TEST = '''"""Legacy Image Editor retirement: no Blender or Qt required."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys
import types

ADDON = Path(__file__).resolve().parents[1] / 'scripts/addons/anim_reference_tool'

def main():
    tree = ast.parse((ADDON/'managers/timeline_manager.py').read_text(encoding='utf-8-sig'))
    names = {'calculate_reference_ranges','find_reference_at_frame','resolve_reference_at_frame','sync_reference_display','on_frame_change'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names
    for n in nodes:
        n.decorator_list = []
    forbidden = {'find_viewer_window','load_blender_image','show_image_in_editors','clear_reference_images_in_editors','iter_target_image_areas'}
    assert not any(isinstance(n, ast.Name) and n.id in forbidden for n in ast.walk(tree))
    assert not any(isinstance(n, ast.ImportFrom) and n.module in {'viewer_manager','image_manager'} for n in ast.walk(tree))
    calls = []
    overlay = types.ModuleType('fake.camera_overlay_manager')
    overlay.frame_changed = lambda scene: calls.append(scene)
    pkg = types.ModuleType('fake'); pkg.__path__ = []
    scope = {'__package__':'fake', 'get_reference_collection':lambda c,k:c.refs, 'find_image_by_uid':lambda p,u:next((a for a in p.images if a.uid==u),None)}
    with patch.dict(sys.modules, {'fake':pkg,'fake.camera_overlay_manager':overlay}):
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])), '<timeline>', 'exec'),scope)
        ref = NS(uid='r', image_id='a', duration=8)
        asset = NS(uid='a')
        cut = NS(timeline_start=10,refs=[ref])
        project = NS(cuts=[cut],active_cut_index=0,active_category='STORYBOARD',images=[asset],auto_sync=True)
        scene = NS(animref_project=project,frame_current=10)
        sync = scope['sync_reference_display']
        assert sync(scene)==dict(status='OK',reference=ref,image_asset=asset,frame_start=10,frame_end=17)
        scene.frame_current=17; assert sync(scene)['status']=='OK'
        scene.frame_current=18; assert sync(scene)['status']=='NO_REFERENCE'
        scene.frame_current=10; project.images=[]; assert sync(scene)['status']=='MISSING_IMAGE_ASSET'
        project.images=[asset]; project.active_cut_index=-1; assert sync(scene)['status']=='INVALID_CUT'
        project.active_cut_index=0; project.cuts=[]; assert sync(scene)['status']=='NO_CUT'
        project.cuts=[cut]
        scope['on_frame_change'](scene); assert calls==[scene]
        project.auto_sync=False; scope['on_frame_change'](scene); assert calls==[scene]
        scope['on_frame_change'](NS()); assert calls==[scene]
    for rel, retired in [('operators/__init__.py','viewer'),('ui/__init__.py','viewer_panel')]:
        t=ast.parse((ADDON/rel).read_text(encoding='utf-8-sig'))
        assert not any(isinstance(n,ast.ImportFrom) and any(a.name==retired for a in n.names) for n in ast.walk(t))
        assert not any(isinstance(n,ast.Name) and n.id==retired for n in ast.walk(t))
    print('PASS: legacy sync retired; frame resolution, overlay handler and registration contracts')

if __name__=='__main__': main()
'''
SYNC = '''# UI_V5_2_LEGACY_IMAGE_EDITOR_RETIRED
# LEGACY_VIEWER_RETIRED: Qt Viewer owns reference display.
def sync_reference_display(scene):
    """Resolve the current reference without writing to any Image Editor.

    Keep the result contract for existing callers. Qt displays its snapshot;
    camera overlay is reconciled by its own handler and the Qt bridge.
    """
    project = scene.animref_project
    reference = image_asset = frame_start = frame_end = None
    if not project.cuts:
        status = "NO_CUT"
    elif not 0 <= project.active_cut_index < len(project.cuts):
        status = "INVALID_CUT"
    else:
        reference, image_asset, frame_start, frame_end = resolve_reference_at_frame(
            project, project.cuts[project.active_cut_index],
            project.active_category, scene.frame_current,
        )
        status = ("NO_REFERENCE" if reference is None else
                  "MISSING_IMAGE_ASSET" if image_asset is None else "OK")
    return dict(status=status, reference=reference, image_asset=image_asset,
                frame_start=frame_start, frame_end=frame_end)
'''
HANDLER = '''@persistent
def on_frame_change(scene, depsgraph=None):
    """Update only the camera overlay; Qt receives live state via IPC."""
    if not hasattr(scene, "animref_project") or not scene.animref_project.auto_sync:
        return
    try:
        from .camera_overlay_manager import frame_changed
        frame_changed(scene)
    except Exception as error:
        print("[AnimRef] Camera overlay sync error:", error)
'''

def git(*args):
    return subprocess.check_output(['git',*args],text=True,encoding='utf-8',errors='replace').strip('\n')

def replace_once(s,a,b):
    if s.count(a)!=1: raise RuntimeError('Unexpected source: '+repr(a))
    return s.replace(a,b,1)

def main():
    ap=argparse.ArgumentParser(); g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--check',action='store_true');g.add_argument('--apply',action='store_true');args=ap.parse_args()
    if not (BASE/'qt/qt_manager_app.py').is_file() or not (BASE/'ipc/manager_ipc.py').is_file(): raise RuntimeError('Phase R layout required')
    dirty=[x for x in git('status','--porcelain','--untracked-files=all','--','scripts/addons/anim_reference_tool','tests','docs').splitlines() if '__pycache__' not in x and '.pyc' not in x]
    if dirty: raise RuntimeError('Commit or stash source/test/docs changes first:\n'+'\n'.join(dirty))
    changes={}; original={}
    def read(p): return p.read_text(encoding='utf-8-sig')
    def put(p,s):
        original[p]=p.read_bytes() if p.exists() else None
        if p.suffix=='.py': ast.parse(s,filename=str(p))
        changes[p]=s
    p=BASE/'managers/timeline_manager.py'; s=read(p)
    if MARK in s: raise RuntimeError('Already applied')
    start=s.index('def sync_reference_display(scene):'); end=s.index('# ============================================================\n# Timeline Handler',start)
    s=s[:start]+SYNC+'\n\n'+s[end:]
    s=replace_once(s,'from .viewer_manager import find_viewer_window\n','')
    s=replace_once(s,'from .image_manager import (\n    load_blender_image,\n    show_image_in_editors,\n    clear_reference_images_in_editors,\n)\n','')
    start=s.index('@persistent\ndef on_frame_change(');end=s.index('# ============================================================\n# Handler Registration',start)
    put(p,s[:start]+HANDLER+'\n\n'+s[end:])
    for rel,name in [('operators/__init__.py','viewer'),('ui/__init__.py','viewer_panel')]:
        p=BASE/rel;s=read(p);s=replace_once(s,f'from . import {name}\n','');s=replace_once(s,f'    {name},\n','');put(p,s)
    # Manual legacy sync operator is retained as a compatibility command; no Image Editor writes.
    p=BASE/'operators/timeline.py';s=read(p);s=replace_once(s,'現在フレームに対応する制作資料を表示します','現在フレームに対応する制作資料を確認します');s=replace_once(s,'        elif status == "NO_IMAGE_EDITOR":\n\n            self.report(\n                {\'WARNING\'},\n                "Image Editorがありません"\n            )\n\n','');put(p,s)
    p=Path('tests/test_legacy_sync_retired.py');
    if p.exists(): raise RuntimeError('Test already exists')
    put(p,TEST)
    p=Path('tests/run_regression.py');s=read(p);s=replace_once(s,'"test_qt_shutdown_overlay.py")','"test_qt_shutdown_overlay.py", "test_legacy_sync_retired.py")');put(p,s)
    notes={
      'CURRENT_SPEC.md':'旧Image Editorへの自動・手動画像同期を廃止。Qt Viewerとカメラ重畳を表示経路とする。旧Viewer Operator/Panelの登録を停止し、ファイル削除はV-5.3へ分離。sync_reference_displayは資料解決のみ（OKは画像表示成功を意味しない）。',
      'DECISIONS.md':'旧Image Editorの画像を上書きしない。旧Viewer登録を停止し、データモデル、JSON、IPC、カメラ重畳およびR-7.1終了処理を維持する。',
      'DEVELOPMENT_LOG.md':'事前確認: cf31df16、現行仕様・判断履歴・ログを確認。Phase R完了およびR-7.1成功はユーザー報告。V-5.2で旧同期と旧Viewer登録を停止。新規非GUI契約試験を追加。ローカル回帰試験・Blender実機確認は適用後に実施。V-5.3で未使用ファイルを削除予定。'}
    for name,note in notes.items():
        p=Path('docs')/name;put(p,read(p).rstrip()+'\n\n## Phase V-5.2 (2026-11-25 JST)\n\n'+note+'\n')
    for p in changes: print('CHANGE',p)
    if args.check: print('PASS: preflight and Python syntax');return
    try:
        for p,s in changes.items(): p.write_text(s,encoding='utf-8')
        subprocess.run([sys.executable,'-B','tests/test_legacy_sync_retired.py'],check=True)
    except BaseException:
        for p,b in original.items():
            if b is None: p.unlink(missing_ok=True)
            else: p.write_bytes(b)
        raise
    print('PASS: applied; new contract test passed. Run full regression next.')

if __name__=='__main__': main()
