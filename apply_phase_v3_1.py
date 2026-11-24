"""AnimRef Phase V-3.1: robust Viewer Timeline polling and Viewer Cut selector.

Run in Blender-Dev root after Phase V-3: python apply_phase_v3_1.py
Requires no change to Blender data/save format or Manager editor behavior.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
import os
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
ADDON = ROOT / 'scripts' / 'addons' / 'anim_reference_tool'
VIEWER = ADDON / 'qt_viewer_page.py'
MANAGER = ADDON / 'qt_manager_app.py'
MARKER_VIEWER = 'UI_V3_1_VIEWER_CUT_SELECTOR'
MARKER_MANAGER = 'UI_V3_1_VIEWER_POLL_FALLBACK'


def replace_once(text: str, before: str, after: str, label: str) -> str:
    count = text.count(before)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 anchor, found {count}: {before[:90]!r}')
    return text.replace(before, after, 1)


def patch_viewer(src: str) -> str:
    if 'UI_V3_TIMELINE_VIEWER_HOLD' not in src:
        raise RuntimeError('Phase V-3 Viewer not found; install V-3 first')
    s = src
    s = replace_once(s,
        'QCheckBox, QSlider, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,',
        'QCheckBox, QSlider, QComboBox, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,',
        'cut combo import')
    s = replace_once(s,
        '    syncRequested = Signal(bool)\n',
        '    syncRequested = Signal(bool)\n    cutRequested = Signal(int)\n',
        'cut signal')
    s = replace_once(s,
        '''        right_lay.addWidget(QLabel("登録資料一覧"))
        catbar = QHBoxLayout()
''',
        '''        # UI_V3_1_VIEWER_CUT_SELECTOR
        cut_bar = QHBoxLayout()
        cut_bar.addWidget(QLabel("カット"))
        self.cut_combo = QComboBox()
        self.cut_combo.setToolTip("Viewerから表示カットを選択（Managerと共通）")
        self.cut_combo.setMinimumWidth(125)
        self.cut_combo.currentIndexChanged.connect(self._cut_selected)
        cut_bar.addWidget(self.cut_combo, 1)
        right_lay.addLayout(cut_bar)
        right_lay.addWidget(QLabel("登録資料一覧"))
        catbar = QHBoxLayout()
''',
        'right panel cut placement')
    s = replace_once(s,
        '''    def _manual_refresh(self):
''',
        '''    def _cut_selected(self, index):
        # Snapshot-driven model: Qt never edits Project state locally.
        if index >= 0:
            self.cutRequested.emit(index)

    def _manual_refresh(self):
''',
        'cut callback')
    s = replace_once(s,
        '''        cat = state.get("active_category") if state else None
        for key, button in self.category_buttons.items():
''',
        '''        # Block selection signals during incoming Blender state updates.
        with QSignalBlocker(self.cut_combo):
            self.cut_combo.clear()
            for cut_info in (state.get("cuts", []) if state else []):
                self.cut_combo.addItem(cut_info.get("name", "Cut"), cut_info.get("uid"))
            selected_cut = state.get("active_cut_index", -1) if state else -1
            if not isinstance(selected_cut, int) or not 0 <= selected_cut < self.cut_combo.count():
                selected_cut = -1
            self.cut_combo.setCurrentIndex(selected_cut)
        cat = state.get("active_category") if state else None
        for key, button in self.category_buttons.items():
''',
        'snapshot cut update')
    return s


def patch_manager(src: str) -> str:
    if 'UI_V3_TIMELINE_LIVE_CLIENT' not in src:
        raise RuntimeError('Phase V-3 Qt Manager not found; install V-3 first')
    s = src
    s = replace_once(s,
        '''        self._live_mtime_ns = None
        self._manager_data_key = None
''',
        '''        self._live_mtime_ns = None
        self._last_live_state_at = 0.0
        self._last_viewer_probe_at = 0.0
        self._viewer_probe_pending = False
        self._queued_viewer_command = None
        self._manager_data_key = None
''',
        'Qt state initialization')
    s = replace_once(s,
        '''        self._viewer_page.syncRequested.connect(self._request_auto_sync)
''',
        '''        self._viewer_page.syncRequested.connect(self._request_auto_sync)
        self._viewer_page.cutRequested.connect(self._request_viewer_cut)
''',
        'Viewer cut signal connection')
    s = replace_once(s,
        '''    def _request_auto_sync(self, enabled):
''',
        '''    def _request_viewer_cut(self, index):
        if not self.state:
            return
        cuts = self.state.get('cuts', [])
        if not isinstance(index, int) or not 0 <= index < len(cuts):
            self._set_status('カットを選択できませんでした', True)
            return
        if index != self.state.get('active_cut_index'):
            self.command('select_cut', index=index)

    def _request_auto_sync(self, enabled):
''',
        'Viewer cut request')
    s = replace_once(s,
        '        if self.pending:\n            self._set_status("前の操作を処理中です")\n            return\n        ident = uuid4().hex\n',
        '        if self.pending:\n            if self._viewer_probe_pending and self._queued_viewer_command is None:\n                # User commands take priority over the background snapshot probe.\n                # Run them after its response without dropping the user\'s click.\n                self._queued_viewer_command = (action, args)\n                return\n            self._set_status("前の操作を処理中です")\n            return\n        ident = uuid4().hex\n',
        'queue user command during silent poll')
    s = replace_once(s,
        '''        if not self.pending:
            self._poll_live_state()
            return
''',
        '''        if not self.pending:
            if self._queued_viewer_command is not None:
                action, args = self._queued_viewer_command
                self._queued_viewer_command = None
                self.command(action, **args)
                return
            self._poll_live_state()
            self._poll_viewer_snapshot_fallback()
            return
''',
        'poll branch')
    s = replace_once(s,
        '''                self.pending = None
                self.last_response = time.monotonic()
                if data.get("ok") and isinstance(data.get("state"), dict):
                    self.state = data["state"]
                    self._render()
                    self._set_status(data.get("message", "更新しました"))
                else:
                    self._set_status(data.get("message", "処理に失敗しました"), True)
                    if self.state and "Scene" in data.get("message", ""):
                        QTimer.singleShot(100, lambda: self.command("snapshot"))
''',
        '''                self.pending = None
                self.last_response = time.monotonic()
                was_probe = self._viewer_probe_pending
                self._viewer_probe_pending = False
                if data.get("ok") and isinstance(data.get("state"), dict):
                    incoming = data["state"]
                    if was_probe and self._pages.currentWidget() is self._viewer_page:
                        # Silent fallback poll must NEVER reset Manager edit controls.
                        if incoming != self.state:
                            self.state = incoming
                            self._manager_needs_render = (
                                manager_data_key(incoming) != self._manager_data_key
                            )
                            self._viewer_page.set_snapshot(incoming)
                            status_label = getattr(self._viewer_page, 'status', None)
                            if status_label is not None:
                                status_label.setText('同期経路：Snapshot補完（V-3.1）')
                    else:
                        self.state = incoming
                        self._render()
                        self._set_status(data.get("message", "更新しました"))
                else:
                    self._set_status(data.get("message", "処理に失敗しました"), True)
                    if not was_probe and self.state and "Scene" in data.get("message", ""):
                        QTimer.singleShot(100, lambda: self.command("snapshot"))
''',
        'response handler')
    s = replace_once(s,
        '''            except (ValueError, OSError) as exc:
                self.pending = None
                self._set_status(f"応答の読み取り失敗: {exc}", True)
        elif time.monotonic() - self.pending_since > 30:
            self.pending = None
            self._set_status("Blenderから応答がありません。Blenderが起動中か確認してください。", True)

    def _poll_live_state(self):
''',
        '''            except (ValueError, OSError) as exc:
                self.pending = None
                self._viewer_probe_pending = False
                self._set_status(f"応答の読み取り失敗: {exc}", True)
        elif time.monotonic() - self.pending_since > 30:
            self.pending = None
            self._viewer_probe_pending = False
            self._set_status("Blenderから応答がありません。Blenderが起動中か確認してください。", True)

    # UI_V3_1_VIEWER_POLL_FALLBACK
    def _poll_viewer_snapshot_fallback(self):
        """Request a fresh Blender snapshot if the live notification is stalled.

        Keeps compatibility with older Blender bridge modules that only support
        the existing request/response protocol. Only used while Viewer is visible.
        It is intentionally silent and never redraws the Manager form.
        """
        if (self.demo or self.session_dir is None or self.pending or
                self._pages.currentWidget() is not self._viewer_page):
            return
        now = time.monotonic()
        if now - self._last_live_state_at < 0.9:
            return
        if now - self._last_viewer_probe_at < 0.75:
            return
        self._last_viewer_probe_at = now
        ident = uuid4().hex
        request = {"id": ident, "action": "snapshot", "args": {}}
        try:
            write_json_atomic(self.session_dir / "requests" / (ident + ".json"), request)
        except (OSError, ValueError) as exc:
            self._set_status(f"同期確認の送信に失敗: {exc}", True)
            return
        self.pending = ident
        self.pending_since = now
        self._viewer_probe_pending = True

    def _poll_live_state(self):
''',
        'fallback poll')
    s = replace_once(s,
        '''        self._live_mtime_ns = mtime
        self.state = new_state
''',
        '''        self._live_mtime_ns = mtime
        self._last_live_state_at = time.monotonic()
        self.state = new_state
''',
        'live signal timing')
    s = replace_once(s,
        '''        self._viewer_page.set_snapshot(new_state)

    def _current_cut''',
        '''        self._viewer_page.set_snapshot(new_state)
        status_label = getattr(self._viewer_page, 'status', None)
        if status_label is not None:
            status_label.setText('同期経路：ライブ通知（V-3.1）')

    def _current_cut''',
        'live diagnostics')
    return s


def main():
    for target in (VIEWER, MANAGER):
        if not target.is_file():
            raise FileNotFoundError(f'Cannot find {target}. Apply the patch in Blender-Dev root.')
    src = {p: p.read_text(encoding='utf-8') for p in (VIEWER, MANAGER)}
    done = (MARKER_VIEWER in src[VIEWER], MARKER_MANAGER in src[MANAGER])
    if any(done):
        if all(done):
            print('Phase V-3.1 already installed. No changes made.')
            return
        raise RuntimeError('V-3.1 was only partially installed; restore from Git first')
    dest = {VIEWER: patch_viewer(src[VIEWER]), MANAGER: patch_manager(src[MANAGER])}
    for path, value in dest.items():
        ast.parse(value, filename=str(path))
    backup = (Path(tempfile.gettempdir()) / 'animref_backups' /
              ('phase_v3_1_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f')))
    backup.mkdir(parents=True, exist_ok=False)
    for path in dest:
        copy = backup / path.relative_to(ROOT)
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, copy)
    try:
        for path, value in dest.items():
            temporary = path.with_suffix(path.suffix + '.animref-v3-1-tmp')
            try:
                temporary.write_text(value, encoding='utf-8')
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            print('Updated', path.relative_to(ROOT))
    except Exception:
        for path in dest:
            shutil.copy2(backup / path.relative_to(ROOT), path)
        raise
    # V-3's AST-extracted tests execute isolated methods without their module imports.
    # Inject time into that test-only namespace for the additional timing guard.
    v3_test = ROOT / 'tests' / 'test_phase_v3_contract.py'
    if v3_test.is_file():
        test_text = v3_test.read_text(encoding='utf-8')
        old_test_namespace = "            'manager_data_key': key,\n        })"
        new_test_namespace = "            'manager_data_key': key, 'time': __import__('time'),\n        })"
        if old_test_namespace in test_text:
            v3_test.write_text(test_text.replace(old_test_namespace, new_test_namespace, 1), encoding='utf-8')
            print('Updated V-3 isolated AST contract test to include time')
    # Document the change without marking Windows/Blender validation as passed.
    records = (
        (ROOT / 'docs' / 'CURRENT_SPEC.md', '### Phase V-3.1：同期復旧とViewerカット切替',
         "\n\n### Phase V-3.1：同期復旧とViewerカット切替（2026-11-17）\n"
         "- V-3のライブ通知だけに依存したViewerを改善。通知が停止した場合、既存のsnapshot要求で現在Scene/Frame/Cutを再取得する。\n"
         "- 自動更新ではManager編集欄を描画し直さず、Viewerだけを更新する。\n"
         "- Viewer右側にカット選択ComboBoxを追加。Blenderのselect_cut要求を利用する。\n"
         "- 通信中のViewer操作はスナップショット応答後に処理する。\n"
         "- 実機検証：未確認（Python契約/回帰試験のみPASS）。\n"),
        (ROOT / 'docs' / 'DEVELOPMENT_LOG.md', '### Phase V-3.1 / Viewer同期不具合修正',
         "\n\n## 2026-11-17\n### Phase V-3.1 / Viewer同期不具合修正\n"
         "- ユーザー報告：Phase V-3でTimelineを動かしてもViewerが追従しない。追加要件：Viewerからカットを切替可能にする。\n"
         "- 点検結果：Qtライブ受信がstate/latest.jsonに依存しており、通知が来ない場合の復旧経路がなかった。原因の特定にはBlender実機ログが必要。\n"
         "- 修正：snapshotを低頻度で再要求する補完経路、Viewerカット選択、通知経路の表示。\n"
         "- 検証：通知ファイルが存在しない状態でsnapshotによりフレーム更新可能な模擬試験PASS。V-1/V-2/V-3既存契約テストPASS。\n"
         "- 実機検証：未実施。ユーザー報告を待つ。\n"),
    )
    for path, marker, addition in records:
        if path.is_file():
            body = path.read_text(encoding='utf-8')
            if marker not in body:
                path.write_text(body.rstrip() + addition + '\n', encoding='utf-8')
                print('Documented', path.relative_to(ROOT))
    print('Backup:', backup)
    print('Restart the external Viewer / Manager. Blender restart is recommended if bridge changes are pending.')


if __name__ == '__main__':
    main()
