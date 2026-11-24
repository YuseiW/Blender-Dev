"""AnimRef Phase V-5.3: safely retire *unregistered* legacy UI modules.

Default mode is READ-ONLY. Run --apply after reviewing the planned changes.
No bpy/PySide6 dependencies. Operates on the local working tree, never GitHub.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
from pathlib import Path
import os
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
ADDON = ROOT / 'scripts' / 'addons' / 'anim_reference_tool'
FLAG = 'UI_V5_2_LEGACY_IMAGE_EDITOR_RETIRED'
RETIRED = (
    'ui/viewer_panel.py',
    'ui/reference_editor.py',
    'ui/manager_panels.py',
    'operators/viewer.py',
    'operators/manager_workspace.py',
)
IGNORE = ('__pycache__/', '*.py[cod]', '.venv/', 'venv/', '.pytest_cache/', '.ruff_cache/', 'Thumbs.db', '.DS_Store')
NOTES = {
    'docs/CURRENT_SPEC.md': (
        '### Phase V-5.3：旧UIソース整理（2026-11-18）',
        '''### Phase V-5.3：旧UIソース整理（2026-11-18）
- 3DビューのNパネルはAnimRef起動ボタンのみ。
- Qt Viewerは閲覧・Timeline同期・カメラ重畳、Qt Managerは登録・編集・JSON保存を担当。
- V-5.2の旧Image Editorビュアー登録解除・自動書換停止は実機確認済み（ユーザー報告7項目PASS）。
- V-5の重点試験8項目は実機確認済み（ユーザー報告）。ただし詳細16項目の個別PASSは別途記録する。
- V-5.3で未登録の旧UIモジュールだけを削除。viewer_manager.py等の旧互換ロジックは残るため、未使用コードの全面撤去とは区別する。
- Projectのデータ構造とJSON保存仕様は変更しない。
'''),
    'docs/DEVELOPMENT_LOG.md': (
        '### V-5.3：旧UIファイル整理・リリース候補',
        '''### V-5.3：旧UIファイル整理・リリース候補（2026-11-18）
- ユーザー報告：Phase V-5.2の退役確認7項目 PASS。
- ユーザー報告：V-5重点実機確認8項目 PASS。
- 未登録の旧UI Pythonファイルを依存関係検査後に退役させるパッチを準備。
- 旧Image Editorへの同期はV-5.2で停止済み。Qt側の同期・カメラ重畳は維持する。
- V-5詳細16項目の個別結果は未報告。完了判定はその確認後に行う。
- Python静的・模擬テストとBlender実機テストを区別して記録する。
'''),
    'docs/DECISIONS.md': (
        '### D-V5-3：旧UIソースの段階的削除',
        '''### D-V5-3：旧UIソースの段階的削除（2026-11-18）
- 判断：Nパネル起動ボタンのみ残し、Viewer・Managerの本体UIはPySide6へ集約する。
- 理由：旧UIの二重登録・二重同期による競合を避けるため。
- 適用条件：V-5.2退役済み、旧モジュールを参照する稼働中のPythonコードがないこと。
- 範囲：未登録の旧パネル／オペレーターのファイルだけを削除し、その他の旧互換関数は保留する。
- 安全策：変更前のバックアップ、読み取り専用の事前検査、想定外の参照があれば中止する。
'''),
}


def read(path: Path) -> tuple[str, bytes]:
    raw = path.read_bytes()
    text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    return text, raw


def preflight() -> tuple[list[Path], dict[Path, bytes]]:
    needed = {
        'ui/__init__.py', 'operators/__init__.py', 'ui/main_panel.py',
        'timeline_manager.py', 'qt_viewer_page.py', 'camera_overlay_manager.py',
        'operators/manager_external.py', 'image_manager.py', 'viewer_manager.py'
    }
    for rel in needed:
        if not (ADDON / rel).is_file():
            raise RuntimeError(f'必要な現行ファイルがありません: {rel}。V-5.2が導入済みか確認してくれ')
    ui, _ = read(ADDON / 'ui/__init__.py')
    ops, _ = read(ADDON / 'operators/__init__.py')
    panel, _ = read(ADDON / 'ui/main_panel.py')
    timeline, _ = read(ADDON / 'timeline_manager.py')
    overlay, _ = read(ADDON / 'camera_overlay_manager.py')
    viewer, _ = read(ADDON / 'qt_viewer_page.py')
    bridge, _ = read(ADDON / 'operators/manager_external.py')
    if (FLAG not in timeline or 'UI_V3_2_LAUNCHER_ONLY' not in panel
            or panel.count('"animref.open_external_manager"') != 1
            or '"animref.open_viewer"' in panel
            or 'def _retire_foreign_slots(' not in overlay
            or 'UI_V4_CAMERA_OVERLAY' not in viewer
            or 'UI_V4_CAMERA_OVERLAY' not in bridge
            or 'frame_changed(scene)' not in timeline):
        raise RuntimeError('V-5.2の機能／登録状態と一致しない。旧UI削除を中止する')
    forbidden_ui = ('reference_editor', 'viewer_panel', 'manager_panels')
    forbidden_ops = ('viewer', 'manager_workspace')
    ui_mods = ast.parse(ui, filename='ui/__init__.py')
    ops_mods = ast.parse(ops, filename='operators/__init__.py')
    def registry_names(tree):
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.update(a.name for a in node.names)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                names.add(node.id)
        return names
    if any(x in registry_names(ui_mods) for x in forbidden_ui):
        raise RuntimeError('旧UIモジュールがui/__init__.pyからまだ参照されている')
    if any(x in registry_names(ops_mods) for x in forbidden_ops):
        raise RuntimeError('旧オペレーターがoperators/__init__.pyからまだ参照されている')
    removed = [ADDON / r for r in RETIRED if (ADDON / r).is_file()]
    # Fail if any remaining addon source still refers to retired modules.
    names = {Path(r).stem for r in RETIRED}
    for path in ADDON.rglob('*.py'):
        if path in removed:
            continue
        text, _ = read(path)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as e:
            raise RuntimeError(f'構文エラーがあるため処理を停止: {path}: {e}')
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if any(alias.name in names for alias in node.names):
                    raise RuntimeError(f'退役ファイルを参照するimportが残っている: {path}:{node.lineno}')
                if node.module and any(node.module == n or node.module.endswith('.'+n) for n in names):
                    raise RuntimeError(f'退役ファイルへの相対importが残っている: {path}:{node.lineno}')
            if isinstance(node, ast.Import):
                if any(any(a.name.endswith('.'+n) for n in names) for a in node.names):
                    raise RuntimeError(f'退役ファイルをimportするコードがある: {path}:{node.lineno}')
    # The active bridge must stay present and unmodified.
    for path in removed:
        ast.parse(read(path)[0], filename=str(path))
    return removed, {p: p.read_bytes() for p in removed}


def merged_docs() -> dict[Path, bytes]:
    changes = {}
    for rel, (marker, note) in NOTES.items():
        path = ROOT / rel
        if not path.is_file():
            continue
        current, raw = read(path)
        if marker in current:
            continue
        ending = '\r\n' if b'\r\n' in raw else '\n'
        updated = (current.rstrip() + '\n\n' + note.rstrip() + '\n').replace('\n', ending)
        changes[path] = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + updated.encode('utf-8')
    ignore = ROOT / '.gitignore'
    raw = ignore.read_bytes() if ignore.is_file() else b''
    old = raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
    missing = [pattern for pattern in IGNORE if pattern not in old.splitlines()]
    if missing:
        newline = '\r\n' if b'\r\n' in raw else '\n'
        updated = (old.rstrip() + ('\n\n' if old.strip() else '') + '# Python / local workspace artifacts\n' + '\n'.join(missing) + '\n').replace('\n', newline)
        changes[ignore] = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + updated.encode('utf-8')
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--check', action='store_true', help='変更を表示するだけ（既定）')
    choice.add_argument('--apply', action='store_true', help='確認・バックアップ後に適用する')
    args = parser.parse_args()
    try:
        removed, backups = preflight()
        updates = merged_docs()
    except (RuntimeError, UnicodeError, SyntaxError) as e:
        raise SystemExit('V-5.3安全検査NG: ' + str(e))
    print('Phase V-5.3 source cleanup')
    print('削除予定（未登録の旧UIのみ）:')
    for p in removed:
        print('  -', p.relative_to(ROOT))
    if not removed:
        print('  （なし：旧UIは既に削除済み）')
    print('更新予定:')
    for p in updates:
        print('  -', p.relative_to(ROOT))
    if not updates:
        print('  （なし）')
    print('維持: viewer_manager.py / image_manager.py / timeline_manager.py / Qt Viewer・Manager / Camera overlay')
    if not args.apply:
        print('読み取り専用検査を完了。変更する場合は --apply を指定してくれ。')
        return
    if not removed and not updates:
        print('既に適用済み。変更なし。')
        return
    folder = Path(tempfile.gettempdir()) / 'animref_backups' / ('phase_v5_3_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    folder.mkdir(parents=True, exist_ok=False)
    old_values = {}
    for p in [*removed, *updates]:
        if p.exists():
            old_values[p] = p.read_bytes()
            dest = folder / p.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
        else:
            old_values[p] = None
    modified = []
    try:
        for p in removed:
            if p.read_bytes() != backups[p]:
                raise RuntimeError('検査後に変更されたファイルがある: ' + str(p))
            p.unlink()
            modified.append(p)
        for p, data in updates.items():
            # Check no external edits since audit.
            if (p.read_bytes() if p.exists() else None) != old_values[p]:
                raise RuntimeError('検査後に変更されたドキュメントがある: ' + str(p))
            p.parent.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix='.animref-v53-', dir=p.parent)
            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write(data)
                os.replace(temp, p)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
            modified.append(p)
    except Exception:
        for p in reversed(modified):
            value = old_values[p]
            if value is None:
                p.unlink(missing_ok=True)
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(value)
        raise
    print('V-5.3適用成功。変更前バックアップ:', folder)
    print('Blender / AnimRefを完全終了してから再起動し、Viewer・Managerの動作を再確認してくれ。')


if __name__ == '__main__':
    main()
