"""AnimRef Phase V-3.2: robust Qt auto-sync ownership + launcher-only 3D N-panel.

Usage (Blender-Dev root, after V-3.1): python apply_phase_v3_2.py
No Blender/PySide6 import is required to apply this patch.
"""
from __future__ import annotations

import ast
from datetime import datetime
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
ADDON = ROOT / "scripts" / "addons" / "anim_reference_tool"
QT = ADDON / "qt_manager_app.py"
VIEWER = ADDON / "qt_viewer_page.py"
BRIDGE = ADDON / "operators" / "manager_external.py"
MAIN_PANEL = ADDON / "ui" / "main_panel.py"
UI_INIT = ADDON / "ui" / "__init__.py"
MARK_QT = "UI_V3_2_SYNC_INTENT_QUEUE"
MARK_VIEWER = "UI_V3_2_PENDING_SYNC_DISPLAY"
MARK_PANEL = "UI_V3_2_LAUNCHER_ONLY"


def one(src: str, before: str, after: str, label: str) -> str:
    count = src.count(before)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, got {count}: {before[:80]!r}")
    return src.replace(before, after, 1)


def patch_viewer(src: str) -> str:
    if "UI_V3_1_VIEWER_CUT_SELECTOR" not in src or "UI_V3_TIMELINE_VIEWER_HOLD" not in src:
        raise RuntimeError("Viewer requires applied Phase V-3.1")
    s = one(src,
            "        self._force_refresh = False\n        self._build()\n",
            "        self._force_refresh = False\n        self._sync_pending = None  # UI_V3_2_PENDING_SYNC_DISPLAY\n        self._build()\n",
            "Viewer init")
    s = one(s,
            '        with QSignalBlocker(self.sync_toggle):\n            self.sync_toggle.setChecked(bool(state and state.get("auto_sync")))\n',
            '        # A pending Qt command must not be undone by an older live snapshot.\n'
            '        sync_value = (self._sync_pending if self._sync_pending is not None\n'
            '                      else bool(state and state.get("auto_sync")))\n'
            '        with QSignalBlocker(self.sync_toggle):\n'
            '            self.sync_toggle.setChecked(sync_value)\n',
            "Viewer checkbox refresh")
    return s


def patch_qt(src: str) -> str:
    if "UI_V3_1_VIEWER_POLL_FALLBACK" not in src:
        raise RuntimeError("Manager requires applied Phase V-3.1")
    s = one(src,
            "        self._queued_viewer_command = None\n        self._manager_data_key = None\n",
            "        self._queued_viewer_command = None\n"
            "        self._queued_sync_enabled = None  # UI_V3_2_SYNC_INTENT_QUEUE\n"
            "        self._sync_request_id = None\n"
            "        self._manager_data_key = None\n",
            "Manager init")
    s = one(s,
            '''    def _request_auto_sync(self, enabled):
        if self.demo:
            return
        if self.pending:
            # Don't leave a visually toggled checkbox when the command was not sent.
            with QSignalBlocker(self._viewer_page.sync_toggle):
                self._viewer_page.sync_toggle.setChecked(bool(self.state and self.state.get('auto_sync')))
            self._set_status('前の操作の完了後に切り替えてください', True)
            return
        self.command('set_auto_sync', enabled=bool(enabled))
''',
            '''    def _request_auto_sync(self, enabled):
        """Qt owns sync *interaction*; Blender Project is the source of truth.

        Queue the most recent user intent across all in-flight requests,
        including V-3.1's background snapshot probe. Never silently discard a
        toggle or let a stale notification flip it back before acknowledgement.
        """
        if self.demo:
            return
        if self.state is None:
            self._set_status('Blenderへの接続を確認してください', True)
            return
        wanted = bool(enabled)
        self._viewer_page._sync_pending = wanted
        if self.pending:
            self._queued_sync_enabled = wanted
            self._set_status('自動同期の切替を予約しました')
            return
        self.command('set_auto_sync', enabled=wanted)
        if self.pending:
            self._sync_request_id = self.pending
            self._set_status('自動同期の設定をBlenderへ反映中…')
        else:
            # Request creation failed; do not leave an unconfirmed setting.
            self._viewer_page._sync_pending = None
            self._viewer_page.set_snapshot(self.state)
''',
            "Sync command routing")
    s = one(s,
            '''        if not self.pending:
            if self._queued_viewer_command is not None:
''',
            '''        if not self.pending:
            if getattr(self, '_queued_sync_enabled', None) is not None:
                wanted = self._queued_sync_enabled
                self._queued_sync_enabled = None
                # A prior command may already have applied the final intent.
                if self.state is not None and bool(self.state.get('auto_sync')) == wanted:
                    self._viewer_page._sync_pending = None
                    self._viewer_page.set_snapshot(self.state)
                else:
                    self._request_auto_sync(wanted)
                return
            if self._queued_viewer_command is not None:
''',
            "Queued sync dispatch")
    s = one(s,
            '''                self.pending = None
                self.last_response = time.monotonic()
''',
            '''                is_sync_response = self.pending == getattr(self, '_sync_request_id', None)
                self.pending = None
                self.last_response = time.monotonic()
''',
            "Identify response")
    s = one(s,
            '''                    if not was_probe and self.state and "Scene" in data.get("message", ""):
                        QTimer.singleShot(100, lambda: self.command("snapshot"))
            except (ValueError, OSError) as exc:
''',
            '''                    if not was_probe and self.state and "Scene" in data.get("message", ""):
                        QTimer.singleShot(100, lambda: self.command("snapshot"))
                if is_sync_response:
                    self._sync_request_id = None
                    if not data.get('ok'):
                        self._queued_sync_enabled = None
                        self._viewer_page._sync_pending = None
                        if self.state is not None:
                            self._viewer_page.set_snapshot(self.state)
                    elif self._queued_sync_enabled is None:
                        # Only clear the optimistic state after Blender ACK.
                        self._viewer_page._sync_pending = None
                        self._viewer_page.set_snapshot(self.state)
            except (ValueError, OSError) as exc:
''',
            "Resolve sync acknowledgement")
    s = one(s,
            '''            except (ValueError, OSError) as exc:
                self.pending = None
                self._viewer_probe_pending = False
                self._set_status(f"応答の読み取り失敗: {exc}", True)
        elif time.monotonic() - self.pending_since > 30:
            self.pending = None
            self._viewer_probe_pending = False
            self._set_status("Blenderから応答がありません。Blenderが起動中か確認してください。", True)
''',
            '''            except (ValueError, OSError) as exc:
                if self.pending == getattr(self, '_sync_request_id', None):
                    self._sync_request_id = None
                    self._queued_sync_enabled = None
                    self._viewer_page._sync_pending = None
                    if self.state is not None:
                        self._viewer_page.set_snapshot(self.state)
                self.pending = None
                self._viewer_probe_pending = False
                self._set_status(f"応答の読み取り失敗: {exc}", True)
        elif time.monotonic() - self.pending_since > 30:
            if self.pending == getattr(self, '_sync_request_id', None):
                self._sync_request_id = None
                self._queued_sync_enabled = None
                self._viewer_page._sync_pending = None
                if self.state is not None:
                    self._viewer_page.set_snapshot(self.state)
            self.pending = None
            self._viewer_probe_pending = False
            self._set_status("Blenderから応答がありません。Blenderが起動中か確認してください。", True)
''',
            "Sync failure rollback")
    return s


LAUNCHER_PANEL = '''"""3D View N-panel: only the entry point to the external AnimRef application.

All editing and display controls live in PySide6 Viewer / Manager.
The old Blender Image Editor Viewer remains registered separately until V-5.
"""
import bpy

# UI_V3_2_LAUNCHER_ONLY
class ANIMREF_PT_MainPanel(bpy.types.Panel):
    bl_label = "AnimRef"
    bl_idname = "ANIMREF_PT_MainPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AnimRef"

    def draw(self, context):
        self.layout.operator(
            "animref.open_external_manager",
            text="AnimRefを開く",
            icon='IMAGE_DATA',
        )


classes = (ANIMREF_PT_MainPanel,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
'''


def patch_panel(src: str) -> str:
    if 'class ANIMREF_PT_MainPanel(bpy.types.Panel)' not in src or '"animref.open_external_manager"' not in src:
        raise RuntimeError("Expected existing AnimRef 3D N-panel was not found")
    return LAUNCHER_PANEL


def patch_ui_init(src: str) -> str:
    # Keep legacy Image Editor panel operational, but prevent old 3D editor
    # controls from being registered. No deletions of original source files.
    s = one(src, 'from . import reference_editor\n', '', 'unregister legacy Reference Editor import')
    s = one(s, '    reference_editor,\n', '', 'unregister legacy Reference Editor panel')
    return s


def main() -> None:
    files = (QT, VIEWER, MAIN_PANEL, UI_INIT)
    for path in (*files, BRIDGE):
        if not path.is_file():
            raise FileNotFoundError(f"Expected repo file is missing: {path}")
    original = {p: p.read_text(encoding='utf-8') for p in files}
    already = (MARK_QT in original[QT], MARK_VIEWER in original[VIEWER],
               MARK_PANEL in original[MAIN_PANEL], 'from . import reference_editor' not in original[UI_INIT])
    if all(already):
        print('Phase V-3.2 is already applied. No changes made.')
        return
    if any(already):
        raise RuntimeError('Partial V-3.2 patch detected; restore or reconcile before retrying')
    bridge_code = BRIDGE.read_text(encoding='utf-8')
    if ('elif action == "set_auto_sync":' not in bridge_code or
            'project.auto_sync = enabled' not in bridge_code):
        raise RuntimeError('Blender bridge lacks V-3 set_auto_sync action. Apply V-3 first.')
    dest = {
        QT: patch_qt(original[QT]),
        VIEWER: patch_viewer(original[VIEWER]),
        MAIN_PANEL: patch_panel(original[MAIN_PANEL]),
        UI_INIT: patch_ui_init(original[UI_INIT]),
    }
    # V-3's original static contract expects the old direct, unqueued call.
    # Update that assertion to accept both the legacy and the queued implementation.
    v3_test = ROOT / 'tests' / 'test_phase_v3_contract.py'
    if v3_test.is_file():
        test_src = v3_test.read_text(encoding='utf-8')
        before = '    assert "self.command(\'set_auto_sync\', enabled=bool(enabled))" in b'
        after = ('    assert ("self.command(\'set_auto_sync\', enabled=bool(enabled))" in b or\n'
                 '            "self.command(\'set_auto_sync\', enabled=wanted)" in b)')
        if before in test_src:
            dest[v3_test] = one(test_src, before, after, 'Update old V-3 static contract')
    for path, code in dest.items():
        ast.parse(code, filename=str(path))
    additions = (
        (ROOT / 'docs' / 'CURRENT_SPEC.md', '### Phase V-3.2：Qt同期制御とNパネル整理',
         '\n\n### Phase V-3.2：Qt同期制御とNパネル整理（2026-11-17）\n'
         '- 3D ViewのAnimRef Nパネルは「AnimRefを開く」ボタンのみ。登録/編集はQt Manager、表示制御はQt Viewer。\n'
         '- auto_syncの真値はScene.animref_project.auto_sync（Blender側）に一本化。Qt側の操作を既存set_auto_sync要求へ送信。\n'
         '- 通信中の自動同期操作は最後の要求をキューに保持し、応答後に送信する。応答前のライブ状態でチェック表示を巻き戻さない。\n'
         '- 旧Image Editorビュアーは回帰試験完了まで維持。V-5で最終整理する。\n'
         '- Blender 5.2実機検証は未実施。\n'),
        (ROOT / 'docs' / 'DEVELOPMENT_LOG.md', '### Phase V-3.2 / 同期操作の一本化と旧UI整理',
         '\n\n## 2026-11-17\n### Phase V-3.2 / 同期操作の一本化と旧UI整理\n'
         '- V-3.1実機報告：おおむね正常。旧Nパネルの自動同期設定とQtスイッチに優先関係があるように見える。\n'
         '- 点検：Qt側で通信中に同期スイッチを押すと、送信されずチェック表示を戻す分岐を確認。\n'
         '- 対処：Qtの同期意図を通信空きまで保留・最終操作へ集約。Blender ACKまたは失敗時に表示を確定。\n'
         '- 3D View Nパネルは外部AnimRefの起動専用に変更。Reference Editorパネル登録を解除（ファイルは保存）。\n'
         '- 旧Image Editorビュアーは維持。Python契約試験とV-1/V-2/V-3/V-3.1回帰試験を実施予定。\n'
         '- Windows + Blender実機での挙動は未実施。\n'),
    )
    for path, marker, text in additions:
        if path.is_file():
            old = path.read_text(encoding='utf-8')
            if marker not in old:
                dest[path] = old.rstrip() + text + '\n'
    backup = Path(tempfile.gettempdir()) / 'animref_backups' / ('phase_v3_2_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir(parents=True, exist_ok=False)
    for path in dest:
        copied = backup / path.relative_to(ROOT)
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, copied)
    installed = []
    try:
        for path, code in dest.items():
            temp = path.with_name(path.name + '.animref-v3-2-tmp')
            try:
                temp.write_text(code, encoding='utf-8')
                os.replace(temp, path)
                installed.append(path)
            finally:
                temp.unlink(missing_ok=True)
            print('Updated', path.relative_to(ROOT))
    except Exception:
        for path in installed:
            shutil.copy2(backup / path.relative_to(ROOT), path)
        raise
    print('Backup:', backup)
    print('Restart Blender and the external Qt app to reload the 3D N-panel.')


if __name__ == '__main__':
    main()
