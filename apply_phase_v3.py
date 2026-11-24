"""Install Phase V-3 Timeline live state updates on a working V-2 AnimRef repo.

Usage from Blender-Dev root: python apply_phase_v3.py
Never changes the data model, JSON save format, image import, or Blender viewer.
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
QT = ADDON / 'qt_manager_app.py'
VIEWER = ADDON / 'qt_viewer_page.py'
BRIDGE = ADDON / 'operators' / 'manager_external.py'
DOCS = ROOT / 'docs'
MARKERS = {
    QT: 'UI_V3_TIMELINE_LIVE_CLIENT',
    VIEWER: 'UI_V3_TIMELINE_VIEWER_HOLD',
    BRIDGE: 'UI_V3_TIMELINE_LIVE_PUBLISH',
}


def replace_once(source: str, old: str, new: str, where: str) -> str:
    occurrences = source.count(old)
    if occurrences != 1:
        raise RuntimeError(f'{where}: expected one insertion anchor; found {occurrences}: {old[:120]!r}')
    return source.replace(old, new, 1)


def patch_viewer(source: str) -> str:
    if 'UI_QT_VIEWER_DISPLAY_V2' not in source:
        raise RuntimeError('Phase V-2 Viewer was not found; apply V-2 first')
    s = source
    s = replace_once(s, 'from PySide6.QtCore import Qt, QSize, Signal, QRectF',
                     'from PySide6.QtCore import Qt, QSize, Signal, QRectF, QSignalBlocker', 'viewer imports')
    s = replace_once(s, '\ndef next_zoom_scale(', '''
# UI_V3_TIMELINE_VIEWER_HOLD

def select_display_frame(state, previous_frame=None, previous_scope=None, force=False):
    """Return (display frame, context scope) without disturbing Blender's timeline.

    When auto sync is OFF, retain the last display context as long as Scene,
    Cut, and Category stay the same. The Viewer also pins ReferenceItem UID. Explicit refresh or switching those
    contexts selects the new Blender frame immediately.
    """
    if not state:
        return None, None
    cuts = state.get('cuts', [])
    index = state.get('active_cut_index', -1)
    cut = cuts[index] if isinstance(index, int) and 0 <= index < len(cuts) else None
    cut_id = cut.get('uid', cut.get('name')) if cut else None
    scope = (state.get('scene_token', state.get('scene')), cut_id,
             state.get('active_category'))
    frame = state.get('frame', 0)
    if force or state.get('auto_sync', True) or previous_frame is None or scope != previous_scope:
        return frame, scope
    return previous_frame, scope


def pinned_reference(refs, images, uid):
    """Resolve pinned ReferenceItem by UID, immune to timeline reordering."""
    reference = next((r for r in refs if r.get('uid') == uid), None) if uid else None
    asset = next((a for a in images if reference and
                  a.get('uid') == reference.get('image_id')), None)
    return reference, asset


def next_zoom_scale(''', 'display-frame helper')
    s = replace_once(s, '    refreshRequested = Signal()\n',
                     '    refreshRequested = Signal()\n    syncRequested = Signal(bool)\n', 'Viewer signal')
    s = replace_once(s, '''        self._highlight_uid = None
        self._build()
''', '''        self._highlight_uid = None
        self._held_frame = None
        self._held_scope = None
        self._held_uid = None
        self._force_refresh = False
        self._build()
''', 'Viewer init')
    s = replace_once(s, '        refresh.clicked.connect(self.refreshRequested.emit)\n',
                     '        refresh.clicked.connect(self._manual_refresh)\n', 'manual refresh')
    s = replace_once(s, '''        self.sync_toggle = QCheckBox("自動同期（Phase V-3）")
        self.sync_toggle.setEnabled(False)
        setting_lay.addWidget(self.sync_toggle)
''', '''        self.sync_toggle = QCheckBox("自動同期")
        self.sync_toggle.setToolTip("OFF: 現在の資料を固定。カテゴリ切替と手動更新は可能")
        self.sync_toggle.toggled.connect(self.syncRequested.emit)
        setting_lay.addWidget(self.sync_toggle)
''', 'enable sync UI')
    s = replace_once(s, '''        self.status = QLabel("V-2：ホイールズーム・パン・全体表示。常時同期は次工程。")
''', '''        self.status = QLabel("V-3：Blenderのフレーム変更に追従。自動同期OFFで表示を固定します。")
''', 'status caption')
    s = replace_once(s, '''    def _zoom_changed(self, scale):
''', '''    def _manual_refresh(self):
        """Even if auto-sync is OFF, a user refresh adopts the current frame."""
        self._force_refresh = True
        self.refreshRequested.emit()

    def _zoom_changed(self, scale):
''', 'manual refresh handler')
    s = replace_once(s, '''    def set_snapshot(self, state):
        self._snapshot = state
        cut, current, asset, refs = reference_at_current_frame(state)
''', '''    def set_snapshot(self, state):
        self._snapshot = state
        previous_scope = self._held_scope
        forced = self._force_refresh
        self._held_frame, self._held_scope = select_display_frame(
            state, self._held_frame, self._held_scope, forced
        )
        self._force_refresh = False
        display_state = dict(state, frame=self._held_frame) if state else None
        cut, current, asset, refs = reference_at_current_frame(display_state)
        # Hold the reference UID, not just the old frame. Reordering or
        # duration edits must not silently switch the pinned image.
        locked = bool(state and not state.get('auto_sync', True)
                      and previous_scope == self._held_scope and not forced)
        if locked:
            current, asset = pinned_reference(refs, state.get('images', []), self._held_uid)
        else:
            self._held_uid = current.get('uid') if current else None
''', 'snapshot freeze behavior')
    s = replace_once(s, '''                f" / Frame {state.get('frame', 0)}"
            )
''', '''                f" / Frame {state.get('frame', 0)}"
                + (f" / 固定表示 {self._held_frame}f" if not state.get('auto_sync', True) else "")
            )
''', 'header freeze label')
    s = replace_once(s, '''        self.sync_toggle.setChecked(bool(state and state.get("auto_sync")))
''', '''        with QSignalBlocker(self.sync_toggle):
            self.sync_toggle.setChecked(bool(state and state.get("auto_sync")))
''', 'signal feedback guard')
    return s


def patch_qt(source: str) -> str:
    if 'UI_QT_VIEWER_STACK_V1' not in source:
        raise RuntimeError('Phase V-1 Manager/Viewer stack was not found')
    s = source
    s = replace_once(s, 'import argparse\n', 'import argparse\nimport json\n', 'qt import')
    s = replace_once(s, '\nclass ManagerWindow(QMainWindow):\n', '''
# UI_V3_TIMELINE_LIVE_CLIENT

def manager_data_key(state):
    """Ignore playback-only changes when deciding to redraw Manager widgets."""
    if not state:
        return None
    return json.dumps({k: v for k, v in state.items()
                       if k not in ('frame', 'auto_sync')},
                      ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class ManagerWindow(QMainWindow):
''', 'manager fingerprint')
    s = replace_once(s, '''        self.state = None
        self.pending = None
''', '''        self.state = None
        self._live_mtime_ns = None
        self._manager_data_key = None
        self._manager_needs_render = False
        self.pending = None
''', 'manager state')
    s = replace_once(s, '''        self._viewer_page.refreshRequested.connect(
            lambda: self.command("snapshot")
        )
''', '''        self._viewer_page.refreshRequested.connect(
            lambda: self.command("snapshot")
        )
        self._viewer_page.syncRequested.connect(self._request_auto_sync)
''', 'sync signal connect')
    s = replace_once(s, '''        else:
            self._pages.setCurrentWidget(self._manager_page)
            self.viewer_nav.setChecked(False)
            self.manager_nav.setChecked(True)
        
    def _set_status''', '''        else:
            self._pages.setCurrentWidget(self._manager_page)
            self.viewer_nav.setChecked(False)
            self.manager_nav.setChecked(True)
            if self.state is not None and getattr(self, '_manager_needs_render', False):
                # Restore new Blender-side changes only when data changed;
                # Timeline ticks alone must not reset Manager scrolling.
                self._render()

    def _request_auto_sync(self, enabled):
        if self.demo:
            return
        if self.pending:
            # Don't leave a visually toggled checkbox when the command was not sent.
            with QSignalBlocker(self._viewer_page.sync_toggle):
                self._viewer_page.sync_toggle.setChecked(bool(self.state and self.state.get('auto_sync')))
            self._set_status('前の操作の完了後に切り替えてください', True)
            return
        self.command('set_auto_sync', enabled=bool(enabled))

    def _set_status''', 'manager return & toggle')
    s = replace_once(s, '''    def _poll(self):
        if self.demo or not self.pending:
            return
''', '''    def _poll(self):
        if self.demo:
            return
        if not self.pending:
            self._poll_live_state()
            return
''', 'qt polling')
    # Insert watcher independent from command/response channel. Never commandeer
    # the pending request slot, or Manager edits may be discarded.
    s = replace_once(s, '''    def _current_cut(self):
''', '''    def _poll_live_state(self):
        """Read the Blender-published snapshot only while Viewer is visible."""
        if (self.session_dir is None or self.pending or
                self._pages.currentWidget() is not self._viewer_page):
            return
        path = self.session_dir / 'state' / 'latest.json'
        try:
            mtime = path.stat().st_mtime_ns
            if mtime == self._live_mtime_ns:
                return
            result = read_json(path)
            new_state = result.get('state') if isinstance(result, dict) else None
            if not isinstance(new_state, dict):
                return
        except (OSError, ValueError):
            # The state file may not yet exist, or may be replaced by Blender.
            return
        self._live_mtime_ns = mtime
        self.state = new_state
        self._manager_needs_render = manager_data_key(new_state) != self._manager_data_key
        self._viewer_page.set_snapshot(new_state)

    def _current_cut(self):
''', 'live state reader')
    s = replace_once(s, '''        if hasattr(self, "_viewer_page"):
            self._viewer_page.set_snapshot(s)
''', '''        if hasattr(self, "_viewer_page"):
            self._viewer_page.set_snapshot(s)
        self._manager_data_key = manager_data_key(s)
        self._manager_needs_render = False
''', 'manager render stamp')
    return s


def patch_bridge(source: str) -> str:
    if 'def _snapshot():' not in source or 'def _pump():' not in source:
        raise RuntimeError('Expected Blender bridge was not found')
    s = source
    s = replace_once(s, 'import os\n', 'import json\nimport os\n', 'bridge import')
    s = replace_once(s, '''_source_window_pointer = None


def _python_commands''', '''_source_window_pointer = None
_last_live_signature = None
_last_live_error = None


def _python_commands''', 'live globals')
    s = replace_once(s, '''        "scene": scene.name,
        "frame": scene.frame_current,
''', '''        "scene": scene.name,
        "scene_token": str(scene.as_pointer()) if hasattr(scene, "as_pointer") else scene.name,
        "frame": scene.frame_current,
''', 'scene identity')
    s = replace_once(s, '''    elif action == "select_cut":
''', '''    elif action == "set_auto_sync":
        enabled = args.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("自動同期はON/OFFで指定してください")
        project.auto_sync = enabled
        if enabled:
            _refresh_display(scene)
        message = "自動同期をONにしました" if enabled else "自動同期をOFFにしました"
    elif action == "select_cut":
''', 'auto sync command')
    s = replace_once(s, '''def _pump():
''', '''# UI_V3_TIMELINE_LIVE_PUBLISH

def _publish_viewer_state(root):
    """Publish only changed state. The main-thread Blender timer owns bpy.

    This independent, atomic file doesn't occupy Qt's command slot and does
    not trigger redraws of the Manager editor while a Viewer is visible.
    """
    global _last_live_signature, _last_live_error
    try:
        state = _snapshot()
        signature = json.dumps(state, sort_keys=True, ensure_ascii=False,
                               separators=(',', ':'))
        if signature != _last_live_signature:
            write_json_atomic(Path(root) / 'state' / 'latest.json',
                              {'schema': 1, 'state': state})
            _last_live_signature = signature
        _last_live_error = None
    except Exception as exc:
        error = str(exc)
        if error != _last_live_error:
            print('[AnimRef][Qt Viewer] Live state warning:', error)
            _last_live_error = error


def _pump():
''', 'live publisher')
    s = replace_once(s, '''        finally:
            req_file.unlink(missing_ok=True)
    return 0.25
''', '''        finally:
            req_file.unlink(missing_ok=True)
    _publish_viewer_state(root)
    return 0.25
''', 'pump publish')
    s = replace_once(s, '''def _cleanup():
    global _process, _session_dir, _source_window_pointer
    _process = None
''', '''def _cleanup():
    global _process, _session_dir, _source_window_pointer
    global _last_live_signature, _last_live_error
    _last_live_signature = None
    _last_live_error = None
    _process = None
''', 'publisher reset')
    return s


SECTION_SPEC = '''### Phase V-3：Timeline継続同期（2026-11-17）

- Phase V-2の6項目はユーザーがWindows/Blender上で全件成功を報告した。
- Blender側timerでProjectスナップショットを定期検査し、変更時のみ `state/latest.json` にアトミック書き込みする。
- Qt Viewerは表示中のみ通知ファイルを監視し、資料画像・指示文・強調表示を更新する。
- Manager入力画面は自動フレーム更新で再描画しない。復帰時に資料データが変更された場合のみ再描画する。
- Viewer左下の自動同期ON/OFFを接続し、OFF中は同Scene・Cut・カテゴリの最後の表示資料をUIDで保持する（資料順変更に対しても安定）。
- OFF中にカテゴリ・Cut・Sceneが変わるか、手動更新した場合は現在のBlenderフレームを採用する。
- 対応する旧Blender標準ビュアーは維持。カメラ重畳の統合はPhase V-4に残す。
- Phase V-3の実機検証は適用後に行う。
'''
SECTION_LOG = '''## 2026-11-17
### Phase V-3 / Blender Timeline 継続同期

事前確認：V-0カメラ重畳POCの画像表示・透明度、V-1画面統合、V-2表示操作6項目について実機PASS（ユーザー報告）。

変更予定/実装：`qt_viewer_page.py` に停止中の表示フレーム保持と自動同期スイッチ、`qt_manager_app.py` にライブ通知読取とManager非干渉更新、`operators/manager_external.py` に定期状態配信とset_auto_syncコマンドを追加。

通信：既存JSON要求/応答経路を維持し、独立した `state/latest.json` をアトミック更新する。Blender timerからのみbpyにアクセスする。

テスト：Phase V-3の契約テストを実行。実機結果はユーザー確認後追記する。

未対応：Phase V-4のカメラ重畳本体連携。旧標準ビュアー削除判断はV-5まで保留。
'''


def main():
    for path in MARKERS:
        if not path.is_file():
            raise FileNotFoundError('Missing source; confirm V-2 has been installed: ' + str(path))
    before = {path: path.read_text(encoding='utf-8') for path in MARKERS}
    existing = [MARKERS[p] in before[p] for p in MARKERS]
    if any(existing) and not all(existing):
        raise RuntimeError('Partially applied V-3; inspect git diff and restore before retrying')
    if all(existing):
        print('Phase V-3 already installed; no additional code changes')
        after = before
    else:
        after = {
            QT: patch_qt(before[QT]),
            VIEWER: patch_viewer(before[VIEWER]),
            BRIDGE: patch_bridge(before[BRIDGE]),
        }
        for path, source in after.items():
            ast.parse(source, str(path))
            assert MARKERS[path] in source, str(path)
        backup_root = (Path(tempfile.gettempdir()) / 'animref_backups' /
                       ('phase_v3_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f')))
        backup_root.mkdir(parents=True, exist_ok=False)
        for path in MARKERS:
            backup_path = backup_root / path.relative_to(ROOT)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path)
        try:
            for path, source in after.items():
                replacement = path.with_name(path.name + '.animref-v3-tmp')
                try:
                    replacement.write_text(source, encoding='utf-8')
                    os.replace(replacement, path)
                finally:
                    replacement.unlink(missing_ok=True)
                print('Patched', path.relative_to(ROOT))
        except Exception:
            for path in MARKERS:
                shutil.copy2(backup_root / path.relative_to(ROOT), path)
            raise
        print('Backup:', backup_root)
    # Update only the obsolete V-2 assertion; other regression checks stay intact.
    v2_test = ROOT / 'tests' / 'test_phase_v2_contract.py'
    if v2_test.is_file():
        check = v2_test.read_text(encoding='utf-8')
        old_assertion = "'self.sync_toggle.setEnabled(False)',"
        new_assertion = "'self.sync_toggle.toggled.connect(self.syncRequested.emit)',"
        if old_assertion in check and new_assertion not in check:
            v2_test.write_text(check.replace(old_assertion, new_assertion, 1), encoding='utf-8')
            print('Updated outdated V-2 toggle assertion:', v2_test.relative_to(ROOT))
    # Bring old V-1 assertions in line with the V-3 control that is now active.
    v1_test = ROOT / 'tests' / 'test_phase_v1_contract.py'
    if v1_test.is_file():
        check = v1_test.read_text(encoding='utf-8')
        original = check
        check = check.replace(
            "assert 'self.sync_toggle.setEnabled(False)' in page",
            "assert 'self.sync_toggle.toggled.connect(self.syncRequested.emit)' in page",
        )
        old_patcher_check = "def check_patcher_idempotent():\n    spec = importlib.util.spec_from_file_location('phasev1', PATCHER)"
        new_patcher_check = (
            "def check_patcher_idempotent():\n"
            "    if not PATCHER.is_file():\n"
            "        print('SKIP: historical V-1 installer has been cleaned up')\n"
            "        return\n"
            "    spec = importlib.util.spec_from_file_location('phasev1', PATCHER)"
        )
        check = check.replace(old_patcher_check, new_patcher_check)
        if check != original:
            v1_test.write_text(check, encoding='utf-8')
            print('Updated outdated V-1 test assumptions:', v1_test.relative_to(ROOT))
    for path, marker, section in ((DOCS / 'CURRENT_SPEC.md', '### Phase V-3：Timeline継続同期', SECTION_SPEC),
                                  (DOCS / 'DEVELOPMENT_LOG.md', '### Phase V-3 / Blender Timeline 継続同期', SECTION_LOG)):
        if path.is_file():
            current = path.read_text(encoding='utf-8')
            if marker not in current:
                path.write_text(current.rstrip() + '\n\n' + section + '\n', encoding='utf-8')
                print('Documented', path.relative_to(ROOT))
    decisions = DOCS / 'DECISIONS.md'
    if decisions.is_file():
        content = decisions.read_text(encoding='utf-8')
        if '## D-006 Viewerライブ状態通知チャネル' not in content:
            content += ("\n\n## D-006 Viewerライブ状態通知チャネル\n\n"
                        "決定日：2026-11-17\n状態：採用・Phase V-3実機検証待ち\n\n"
                        "- Blender timerが最新スナップショットをstate/latest.jsonへアトミックに発行する。\n"
                        "- データ変更時のみ更新し、Qt Viewerだけがライブ通知で表示を更新する。\n"
                        "- Managerの資料編集UIをフレーム変更で再描画しない。\n"
                        "- 既存JSON要求/応答チャネルとBlender標準ビュアーを維持する。\n"
                        "- Blenderのカメラ重畳接続はV-4へ分離。\n")
            decisions.write_text(content, encoding='utf-8')
            print('Documented', decisions.relative_to(ROOT))
    print('Phase V-3 installed. Restart Blender AND the PySide6 application.')


if __name__ == '__main__':
    main()
