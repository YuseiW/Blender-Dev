"""Install the Phase V-2 read-only viewer display into an existing V-1 repo.

Place this script and phase_v2_payload/ next to scripts/ and docs/ and run:
    python apply_phase_v2.py
Safe to rerun. Does not alter Blender bridge, ManagerWindow, data or tests.
"""
from pathlib import Path
from datetime import datetime
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / 'scripts/addons/anim_reference_tool/qt_viewer_page.py'
PAYLOAD = ROOT / 'phase_v2_payload/qt_viewer_page.py'
SPEC = ROOT / 'docs/CURRENT_SPEC.md'
DECISIONS = ROOT / 'docs/DECISIONS.md'
LOG = ROOT / 'docs/DEVELOPMENT_LOG.md'
V2_MARKER = 'UI_QT_VIEWER_DISPLAY_V2'


def verify_existing(source):
    # Reject unknown or partially updated versions rather than silently
    # overwriting user's independent edits or the Manager's live code.
    required = (
        'class ImageCanvas(QLabel)',
        'class ViewerPage(QWidget)',
        'def reference_at_current_frame(state):',
        'self.overlay_toggle.setEnabled(False)',
        'self.sync_toggle.setEnabled(False)',
        'self.references.setSelectionMode(QListWidget.SelectionMode.NoSelection)',
    )
    missing = [fragment for fragment in required if fragment not in source]
    if missing:
        raise RuntimeError('Expected Phase V-1 viewer not found; refusing to overwrite: ' + ', '.join(missing))


def append_section(original, marker, content):
    return original if marker in original else original.rstrip() + '\n\n' + content + '\n'


def main():
    if not TARGET.is_file():
        raise FileNotFoundError('Phase V-1 qt_viewer_page.py not found: ' + str(TARGET))
    if not PAYLOAD.is_file():
        raise FileNotFoundError('phase_v2_payload/qt_viewer_page.py is missing')
    before = TARGET.read_text(encoding='utf-8')
    after = PAYLOAD.read_text(encoding='utf-8')
    compile(after, str(TARGET), 'exec')
    if V2_MARKER not in after:
        raise RuntimeError('Incorrect V-2 payload')
    if V2_MARKER not in before:
        verify_existing(before)
    elif before != after:
        raise RuntimeError('Existing V-2 source differs; refusing to discard local changes')

    if before != after:
        backup_dir = (Path(tempfile.gettempdir()) / 'animref_backups' /
                      ('phase_v2_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f')))
        backup_dir.mkdir(parents=True, exist_ok=False)
        shutil.copy2(TARGET, backup_dir / TARGET.name)
        TARGET.write_text(after, encoding='utf-8')
        print('Updated:', TARGET.relative_to(ROOT))
        print('Backup:', backup_dir)
    else:
        print('Viewer already at Phase V-2; no source changes')

    sections = (
        (SPEC, '### Phase V-2：Viewerの基本表示・操作性', '''### Phase V-2：Viewerの基本表示・操作性

- Qt Viewerの画像表示をQGraphicsViewで実装し、ホイールズーム、ドラッグパン、全体表示、100%表示を提供。
- 原画・レイアウト・絵コンテ切替を継続し、現在フレームの登録資料をカテゴリカラーで強調する。
- 資料一覧の構成が変わらない更新では一覧を作り直さず、現在資料が切り替わるときだけ該当行へスクロールする。
- Viewerは閲覧専用。資料登録・編集・JSON保存は既存Managerが担当。
- カメラ重畳と自動同期の操作部品は、まだ無効（V-3/V-4で接続）。
- Phase V-1の画面切替はユーザー実機で動作成功（2026-11-17）。
- Phase V-2のWindows/PySide6実機動作は適用後に確認。'''),
        (LOG, '### Phase V-2 / Viewer表示と操作性', '''## 2026-11-17
### Phase V-2 / Viewer表示と操作性

実装前: Phase V-1 同一ウィンドウ切替をユーザーが実機で動作確認済み。Blenderカメラ重畳POCも表示・透明度変更に成功。

変更: qt_viewer_page.pyのみ。QGraphicsViewの拡大縮小・パン・全体表示・100%表示、カテゴリ色による現在資料の強調、一覧の無駄な再構築防止、必要時のみ自動スクロール。
維持: 既存Manager GUI、JSON IPC、Blenderアドオンのデータモデル・Timeline同期・標準ビュアー。
未実装: Phase V-3の継続Timeline同期、Phase V-4のカメラ重畳接続。

検証: Python構文・選択ロジック・ズーム境界・更新署名・後方互換の静的テストを実施。Windows実機でのViewer操作は適用後の確認待ち。
'''),
    )
    for path, marker, section in sections:
        if path.is_file():
            src = path.read_text(encoding='utf-8')
            updated = append_section(src, marker, section)
            if updated != src:
                path.write_text(updated, encoding='utf-8')
                print('Updated:', path.relative_to(ROOT))
    print('Phase V-2 installed. Close and reopen the Qt window to load the new code.')


if __name__ == '__main__':
    main()
