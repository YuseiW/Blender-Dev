import ast
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'payload' / 'scripts' / 'addons' / 'anim_reference_tool'

for path in [ROOT / 'apply_animref_qt_ui1.py', *PAYLOAD.rglob('*.py')]:
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    print('AST OK', path.name)

ipc_path = PAYLOAD / 'manager_ipc.py'
spec = importlib.util.spec_from_file_location('manager_ipc', ipc_path)
ipc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ipc)
with tempfile.TemporaryDirectory() as temp:
    target = Path(temp)/'テスト.json'
    ipc.write_json_atomic(target, {'message': '日本語', 'data': [1, 2, 3]})
    assert ipc.read_json(target) == {'message': '日本語', 'data': [1, 2, 3]}
    assert list(Path(temp).glob('*.tmp')) == []
    print('IPC unicode/atomic OK')

for variant in ('old', 'fresh'):
    with tempfile.TemporaryDirectory() as temp:
        repo = Path(temp)
        addon = repo/'scripts'/'addons'/'anim_reference_tool'
        op_dir, ui_dir = addon/'operators', addon/'ui'
        op_dir.mkdir(parents=True)
        ui_dir.mkdir(parents=True)
        (op_dir/'__init__.py').write_text(
            'from . import viewer\n'+('from . import manager_workspace\n' if variant=='old' else '')+
            '\nmodules = (\n    viewer,\n'+('    manager_workspace,\n' if variant=='old' else '')+' )\n', encoding='utf-8')
        (ui_dir/'__init__.py').write_text(
            'from . import main_panel\nfrom . import reference_editor\n'+('from . import manager_panels\n' if variant=='old' else '')+
            '\nmodules = (\n    main_panel,\n    reference_editor,\n'+('    manager_panels,\n' if variant=='old' else '')+' )\n', encoding='utf-8')
        (ui_dir/'main_panel.py').write_text(
            'import bpy\n\n# Reference Viewer\n' +
            ('        layout.operator(\n            "animref.open_manager_workspace",\n            text="AnimRef Manager（別ウィンドウ）",\n        )\n' if variant=='old' else '')+
            '        # Image Pool\n', encoding='utf-8')
        (repo/'docs').mkdir()
        (repo/'docs'/'DECISIONS.md').write_text('## D-001 Blenderアドオンへの統合\n\n状態: 採用\n\n### 旧仕様\n', encoding='utf-8')
        (repo/'docs'/'CURRENT_SPEC.md').write_text('開発段階: Phase 1完了 / Phase 2開始前\n- Blenderアドオン単体で実装する。\n- 独立したWindows GUIアプリは制作しない。\n', encoding='utf-8')
        (repo/'docs'/'DEVELOPMENT_LOG.md').write_text('old log\n', encoding='utf-8')
        shutil.copytree(ROOT/'payload', repo/'animref_qt_ui1_payload')
        shutil_script = repo/'apply_animref_qt_ui1.py'
        shutil_script.write_bytes((ROOT/'apply_animref_qt_ui1.py').read_bytes())
        for i in range(2):
            result = subprocess.run([sys.executable,str(shutil_script)],cwd=repo,capture_output=True,text=True)
            assert result.returncode == 0, (variant,i,result.stdout,result.stderr)
        actual = (op_dir/'__init__.py').read_text(encoding='utf-8')
        assert actual.count('manager_external,') == 1
        assert 'manager_workspace' not in actual
        actual_ui = (ui_dir/'__init__.py').read_text(encoding='utf-8')
        assert 'manager_panels' not in actual_ui
        actual_main = (ui_dir/'main_panel.py').read_text(encoding='utf-8')
        assert actual_main.count('"animref.open_external_manager"') == 1
        assert '"animref.open_manager_workspace"' not in actual_main
        assert (repo/'docs'/'DECISIONS.md').read_text(encoding='utf-8').count('D-005 PySide6管理GUIの採用') == 1
        assert (repo/'docs'/'DEVELOPMENT_LOG.md').read_text(encoding='utf-8').count('### UI-1 / PySide6独立GUIへの設計変更') == 1
        print('Patcher idempotent OK:', variant)
print('=== ALL PACKAGE TESTS PASSED ===')
