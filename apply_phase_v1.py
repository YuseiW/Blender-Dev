"""Phase V-1: add a read-only Qt Viewer page to the existing AnimRef Manager.

Copy this script and phase_v1_payload/ into your Blender-Dev repo root,
then run `python apply_phase_v1.py`.

Only qt_manager_app.py is patched. Blender bridge/manager functions remain intact.
Existing files are backed up outside the repo before changes.
"""
from pathlib import Path
from datetime import datetime
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
ADDON = ROOT / 'scripts' / 'addons' / 'anim_reference_tool'
TARGET = ADDON / 'qt_manager_app.py'
NEW = ADDON / 'qt_viewer_page.py'
PAYLOAD = ROOT / 'phase_v1_payload' / 'qt_viewer_page.py'
SPEC = ROOT / 'docs' / 'CURRENT_SPEC.md'
DECISIONS = ROOT / 'docs' / 'DECISIONS.md'
LOG = ROOT / 'docs' / 'DEVELOPMENT_LOG.md'
MARKER = '# UI_QT_VIEWER_STACK_V1'


def replace_once(src, old, new, label):
    count = src.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, found {count}; no files changed')
    return src.replace(old, new, 1)


def transform(src):
    if MARKER in src:
        return src
    for required in (
        'UI1_EXPLORER_IMAGE_DROP_V1',
        'UI_QT_SAVE_REORDER_V1',
        'UI_QT_REFERENCE_AUTOSCROLL_V1',
    ):
        if required not in src:
            raise RuntimeError(f'Missing previous Qt feature: {required}')
    src = replace_once(
        src,
        '    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,\n',
        '    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QStackedWidget,\n',
        'Qt stack import',
    )
    src = replace_once(
        src,
        'from manager_ipc import read_json, write_json_atomic\n',
        'from manager_ipc import read_json, write_json_atomic\nfrom qt_viewer_page import ViewerPage\n',
        'Viewer import',
    )
    src = replace_once(
        src,
        '        self._setup_ui()\n        self.poller = QTimer(self)\n',
        '        self._setup_ui()\n        self._setup_page_switcher()\n        self.poller = QTimer(self)\n',
        'Install page switcher',
    )
    src = replace_once(
        src,
        '    def _set_status(self, text, error=False):\n',
        '''    # UI_QT_VIEWER_STACK_V1
    def _setup_page_switcher(self):
        """Wrap the existing manager widget without recreating its controls.

        The manager's original central widget remains alive in the stack; this
        protects reference-list scroll position, D&D connections and form state.
        """
        manager_page = self.takeCentralWidget()
        if manager_page is None:
            raise RuntimeError("Manager page not initialized")
        shell = QWidget()
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        navigation = QFrame()
        nav_layout = QHBoxLayout(navigation)
        nav_layout.setContentsMargins(16, 8, 16, 8)
        nav_layout.addWidget(QLabel("AnimRef"))
        self.viewer_nav = QPushButton("閲覧（Viewer）")
        self.manager_nav = QPushButton("登録・編集（Manager）")
        for button in (self.viewer_nav, self.manager_nav):
            button.setCheckable(True)
            nav_layout.addWidget(button)
        nav_layout.addStretch(1)
        outer.addWidget(navigation)

        self._viewer_page = ViewerPage()
        self._viewer_page.categoryRequested.connect(
            lambda category: self.command("select_category", category=category)
        )
        self._viewer_page.refreshRequested.connect(
            lambda: self.command("snapshot")
        )
        self._pages = QStackedWidget()
        self._pages.addWidget(self._viewer_page)
        self._pages.addWidget(manager_page)
        outer.addWidget(self._pages, 1)
        self.setCentralWidget(shell)
        self._manager_page = manager_page
        self.viewer_nav.clicked.connect(lambda: self._set_page("viewer"))
        self.manager_nav.clicked.connect(lambda: self._set_page("manager"))
        # Initially retain the familiar registration screen during migration.
        self._set_page("manager", refresh=False)
        self.setWindowTitle("AnimRef — Viewer / Manager")

    def _set_page(self, page, refresh=True):
        """Switch views without destroying Manager state or losing unsaved edits."""
        if page == "viewer":
            # A response snapshot re-renders the manager editor. Do not silently
            # replace unsaved duration/instruction text as we switch pages.
            if self._editor_update_for_save() is not None:
                QMessageBox.information(
                    self,
                    "未保存の編集内容",
                    "表示尺・指示文の変更を先に保存してからViewerへ切り替えてください。",
                )
                self.manager_nav.setChecked(True)
                self.viewer_nav.setChecked(False)
                return
            self._pages.setCurrentWidget(self._viewer_page)
            self.viewer_nav.setChecked(True)
            self.manager_nav.setChecked(False)
            if self.state is not None:
                self._viewer_page.set_snapshot(self.state)
            if refresh and not self.demo and not self.pending:
                self.command("snapshot")
        else:
            self._pages.setCurrentWidget(self._manager_page)
            self.viewer_nav.setChecked(False)
            self.manager_nav.setChecked(True)
        
    def _set_status(self, text, error=False):
''',
        'Page shell implementation',
    )
    src = replace_once(
        src,
        '        self._ref_changed(self.ref_list.currentRow())\n\n    def _cut_changed(self, index):\n',
        '        self._ref_changed(self.ref_list.currentRow())\n'
        '        if hasattr(self, "_viewer_page"):\n'
        '            self._viewer_page.set_snapshot(s)\n\n'
        '    def _cut_changed(self, index):\n',
        'Sync viewer after normal Manager state updates',
    )
    return src


def append_section(original, marker, section):
    return original if marker in original else original.rstrip() + '\n\n' + section + '\n'


def main():
    if not TARGET.is_file():
        raise FileNotFoundError('Cannot find current Qt Manager: ' + str(TARGET))
    if not PAYLOAD.is_file():
        raise FileNotFoundError('phase_v1_payload/qt_viewer_page.py is missing')
    old = TARGET.read_text(encoding='utf-8')
    new = transform(old)
    payload_text = PAYLOAD.read_text(encoding='utf-8')
    # Verify source syntax and all target paths before any writes.
    compile(new, str(TARGET), 'exec')
    compile(payload_text, str(NEW), 'exec')
    if NEW.exists() and NEW.read_text(encoding='utf-8') != payload_text:
        raise RuntimeError(f'{NEW} exists with different contents. No files changed')

    if old != new or not NEW.exists():
        backup_dir = (Path(tempfile.gettempdir()) / 'animref_backups'
                      / ('phase_v1_' + datetime.now().strftime('%Y%m%d_%H%M%S')))
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TARGET, backup_dir / TARGET.name)
        if old != new:
            TARGET.write_text(new, encoding='utf-8')
            print('Modified:', TARGET.relative_to(ROOT))
        if not NEW.exists():
            NEW.write_text(payload_text, encoding='utf-8')
            print('Created:', NEW.relative_to(ROOT))
        print('Backup:', backup_dir)
    else:
        print('Qt sources already updated (no changes)')

    if SPEC.is_file():
        marker = '### Phase V-1：Viewer/Manager同一ウィンドウ切替'
        section = '''### Phase V-1：Viewer/Manager同一ウィンドウ切替

- V-0: Blenderカメラ背景画像の前面表示、不透明度変更はユーザー実機確認済み（POC）。本体への組み込みはV-4で実施。
- V-1: PySide6のQStackedWidgetで閲覧画面と既存Manager画面を切替。Managerの登録・保存・D&D等は維持。
- Viewerは読み取り専用・現在のSnapshotからプレビュー表示。画面切替時と「更新」でBlender最新状態を取得。
- Timelineに対する継続的な自動更新・表示設定トグル・カメラ重畳との接続はV-3/V-4の予定。
- 状態: コード準備済み。Blender/Windows実機での画面切替テスト待ち。'''
        text = SPEC.read_text(encoding='utf-8')
        updated = append_section(text, marker, section)
        updated = updated.replace(
            '- UI-1 PySide6方式はBlender実機テスト待ち。',
            '- UI-1 PySide6方式はユーザー実機確認済み（D&D取り込み・並べ替え・上書き保存・自動スクロール）。',
        ).replace(
            '状態：コード準備済み、Blender 5.2実機テスト待ち。',
            '状態：Manager UIはユーザー実機確認済み。',
        )
        if updated != text:
            SPEC.write_text(updated, encoding='utf-8')
            print('Updated:', SPEC.relative_to(ROOT))
    if DECISIONS.is_file():
        marker = '## D-006 Qt内Viewer/Manager画面切替'
        section = '''## D-006 Qt内Viewer/Manager画面切替

決定日: 2026-11-17
状態: 採用・V-1実機検証待ち

- Viewerと既存Managerは同一PySide6ウィンドウで切替える。
- 編集はManager側のみで行う。Viewerは読み取り専用。
- Qt Managerが一元的にJSON通信・状態管理し、ViewerはそのSnapshotを参照する。
- 既存Blender標準ビュアーは新Viewer完成まで削除しない。
- カメラ重畳はBlender側機能として別工程で実装する。'''
        text = DECISIONS.read_text(encoding='utf-8')
        updated = append_section(text, marker, section)
        updated = updated.replace(
            '状態: 採用・初期実装（Blender実機確認待ち）',
            '状態: 採用・Manager GUI実機確認済み',
        )
        if updated != text:
            DECISIONS.write_text(updated, encoding='utf-8')
            print('Updated:', DECISIONS.relative_to(ROOT))
    if LOG.is_file():
        marker = '### Phase V-1 / QtのViewerとManager画面統合'
        section = '''## 2026-11-17
### Phase V-1 / QtのViewerとManager画面統合

実装前確認: Blender Phase2-AのViewer/Timeline同期は動作済み。Qt ManagerのExplorer D&D・並べ替え・上書き保存・自動スクロールはユーザー動作確認済み。
V-0実機確認: カメラ重畳の表示・透明度調整に成功（ユーザー報告）。

変更予定／変更内容:
- qt_manager_app.pyにQStackedWidgetと画面ナビゲーションを追加。
- qt_viewer_page.pyを新規作成。閲覧専用のメイン画像・指示文・登録資料一覧・カテゴリ切替を初期表示。
- Managerの既存UIとIPC、Blender側Bridge、Blender標準ビュアーは維持。

状態: Python構文・ロジックテスト済み／Blender + Windows Qt実機確認待ち。
未実装: V-3継続Timeline同期、V-4カメラ重畳接続、不透明度スライダー操作。
'''
        text = LOG.read_text(encoding='utf-8')
        updated = append_section(text, marker, section)
        if updated != text:
            LOG.write_text(updated, encoding='utf-8')
            print('Updated:', LOG.relative_to(ROOT))
    print('Phase V-1 installed. Reopen AnimRef Manager to test the page switch.')


if __name__ == '__main__':
    main()
