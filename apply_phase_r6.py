"""R-6: repair test infrastructure and document the R-5 layout."""
import argparse
import ast
import subprocess
from pathlib import Path

BASE = Path('scripts/addons/anim_reference_tool')
TEST = Path('tests')
HISTORY = '2cbdf30a6bc967e39dd4a44343ffbf63c432e3a9'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true')
    g.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    def fail(msg): raise SystemExit(msg)
    for rel in ('core/properties.py','storage/project_io.py','managers/timeline_manager.py','ipc/manager_ipc.py','qt/qt_manager_app.py','qt/qt_viewer_page.py'):
        if not (BASE/rel).is_file(): fail('Missing R-5 file: '+rel)
    dirty = subprocess.check_output(['git','status','--porcelain','--','scripts','tests','tools','docs','README.md','DEVELOPMENT_LOG_ENTRY.md'], text=True)
    dirty = [s for s in dirty.splitlines() if '__pycache__' not in s and not s.endswith(('.pyc','.pyo'))]
    if dirty: fail('Commit or stash relevant changes first:\n'+'\n'.join(dirty))
    changes = {}
    def read(p): return p.read_text(encoding='utf-8-sig')
    def edit(p, pairs):
        s=read(p)
        for a,b in pairs:
            if a not in s: fail(f'Unexpected baseline: {p}: {a}')
            s=s.replace(a,b)
        changes[p]=s
    def create(p,s):
        if p.exists(): fail('Already exists: '+str(p))
        changes[p]=s
    # Recover only the historical fake API, not its outdated source assertions.
    try:
        old=subprocess.check_output(['git','show',HISTORY+':tests/test_phase_v4_contract.py']).decode('utf-8-sig')
    except subprocess.CalledProcessError:
        fail('Historical test unavailable. Run git fetch origin, then retry.')
    tree=ast.parse(old)
    wanted={'FakeImage','FakeImageStore','FakeSlot','FakeSlots','FakeCamera','FakeScene','mock_blender'}
    nodes=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in wanted]
    if {n.name for n in nodes} != wanted: fail('Historical mock structure differs')
    lines=old.splitlines()
    support='import importlib.util\nfrom pathlib import Path\nimport sys\nimport types\n\nADDON = Path(__file__).resolve().parents[1] / "scripts/addons/anim_reference_tool/managers"\n\n'+'\n\n'.join('\n'.join(lines[n.lineno-1:n.end_lineno]) for n in nodes)+'\n'
    create(TEST/'overlay_test_support.py',support)
    edit(TEST/'test_phase_v5_contract.py',[("tests/test_phase_v4_contract.py","tests/overlay_test_support.py"),("Uses the mock Blender API from the V-4 tests.","Uses the recovered mock Blender API from overlay_test_support.py.")])
    p=TEST/'test_bridge_mock.py'
    edit(p,[("self.active_cut_index=0","self.active_cut_index=0\n        self.project_filepath=''"),("frame_current=1,animref_project=project)","frame_current=1,animref_project=project, animref_overlay_enabled=False, animref_overlay_opacity=0.5)"),("# Import pure IPC and operator module with package-qualified name","# Isolate camera overlay; its actual logic is tested separately.\noverlay=ModuleType('anim_reference_tool.managers.camera_overlay_manager')\noverlay.sync_overlay=lambda *args, **kwargs: None\nsys.modules[overlay.__name__]=overlay\n\n# Import pure IPC and operator module with package-qualified name")])
    s=changes[p]
    if 'anim_reference_tool.ipc.manager_ipc' not in s: fail('Bridge mock IPC path not migrated')
    # The save/reorder test extracts the dispatch function, which now invokes overlay.
    edit(TEST/'test_qt_save_reorder_contract.py', [('"_refresh_display": lambda s: None,','"_refresh_display": lambda s: None,\n            "camera_overlay_manager": SimpleNamespace(sync_overlay=lambda s: None),')])
    # Preserve future acceptance tests; do not weaken assertions or report PASS.
    for name in ('test_phase_v5_3_contract.py','test_phase_v5_3_1_contract.py'):
        p=TEST/name
        s=read(p).replace('Path(__file__).resolve().parents[1]','Path(__file__).resolve().parents[2]')
        create(TEST/'pending'/name,s)
        changes[p]=None
    create(TEST/'run_regression.py','''"""Run independent non-GUI tests in fresh processes."""\nfrom pathlib import Path\nimport subprocess\nimport sys\nROOT=Path(__file__).resolve().parents[1]\nTESTS=("test_bridge_mock.py", "test_phase_v5_contract.py", "test_qt_save_reorder_contract.py", "test_reference_autoscroll.py")\nif __name__ == "__main__":\n    failed=[]\n    for name in TESTS:\n        print("RUN:",name,flush=True)\n        if subprocess.run([sys.executable,str(ROOT/"tests"/name)],cwd=ROOT).returncode:\n            failed.append(name)\n    print("FAIL:",failed) if failed else print("PASS: all non-GUI regression scripts")\n    print("NOT RUN: Blender integration_smoke.py; pending legacy retirement contracts")\n    raise SystemExit(bool(failed))\n''')
    note='''\n\n## Phase R — package layout (2026-11-25 JST)\n\n- R-1 through R-5: user reported successful local checks. Exact per-test evidence not recorded.\n- `core/`: properties, utils; `storage/`: project_io, validation; `managers/`: six manager modules; `ipc/`: manager_ipc; `qt/`: external PySide6 Viewer and Manager.\n- `operators/` and `ui/` remain Blender-side. The root `__init__.py` remains the addon entry point.\n- Qt runs in an external Python process; shared IPC is imported without loading the Blender addon entry point.\n- No intended changes to UI, data model, JSON format or communication protocol in Phase R.\n- Legacy Image Editor viewer retirement is separate; its acceptance tests are pending, not PASS.\n- R-6: test infrastructure repair; local regression and Blender integration results pending.\n'''
    for p in (Path('docs/CURRENT_SPEC.md'),Path('docs/DEVELOPMENT_LOG.md')):
        changes[p]=read(p)+note
    p=Path('docs/DECISIONS.md'); changes[p]=read(p)+'\n\n## Phase R: package separation\n\nAdopt the responsibility-based package layout described in CURRENT_SPEC.md. Preserve runtime behavior and JSON format. Keep legacy viewer retirement separate.\n'
    create(Path('README.md'),'''# AnimRef — Blender Animation Reference Tool\n\nBlenderのTimelineと絵コンテ・レイアウト・原画を連携する制作支援アドオン。\n\n## 動作環境・起動\n\n開発環境はWindows、Blender、外部PythonとPySide6。既存のアドオン導入方法を維持する。外部Pythonに `python -m pip install PySide6` で依存を導入し、必要なら環境変数 `ANIMREF_PYTHON` で実行ファイルを指定する。Blenderでアドオンを有効化し、3D ViewのNパネルから「AnimRefを開く」。\n\n## 構成\n\n`scripts/addons/anim_reference_tool/`: `core/`, `storage/`, `managers/`, `ipc/`, `qt/`, `operators/`, `ui/`。\n\n## テスト\n\n`python tests/run_regression.py` は非GUI回帰試験。`tests/integration_smoke.py` はBlender内で実行する。`tests/pending/` は旧UI撤去後に実行する受入試験であり、通常回帰試験から除外する。\n\n仕様と開発履歴は `docs/` を参照。\n''')
    for p,s in changes.items():
        if s is not None and p.suffix=='.py': ast.parse(s,filename=str(p))
    for p,s in changes.items(): print(('REMOVE' if s is None else 'WRITE'),p)
    if args.check: print('PASS: preflight and syntax; no files modified.'); return
    backups={p:p.read_bytes() if p.exists() else None for p in changes}
    created_dirs=[]
    try:
        for p,s in changes.items():
            if s is None: p.unlink(); continue
            if not p.parent.exists(): p.parent.mkdir(); created_dirs.append(p.parent)
            p.write_bytes(s.encode('utf-8'))
    except BaseException:
        for p,b in backups.items():
            if b is None: p.unlink(missing_ok=True)
            else: p.write_bytes(b)
        for p in reversed(created_dirs): p.rmdir()
        raise
    print('PASS: R-6 files updated. Run python tests/run_regression.py; results not yet verified.')
if __name__=='__main__': main()
