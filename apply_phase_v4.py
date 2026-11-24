"""Phase V-4: integrate camera overlay with existing V-3.2 Viewer / Manager.

Run from Blender-Dev repository root: python apply_phase_v4.py
Requires V-3.2 already applied. No Blender/PySide6 imports for installation.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
import os
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
ADDON = ROOT / "scripts" / "addons" / "anim_reference_tool"
VIEWER = ADDON / "qt_viewer_page.py"
QT = ADDON / "qt_manager_app.py"
BRIDGE = ADDON / "operators" / "manager_external.py"
TIMELINE = ADDON / "timeline_manager.py"
OVERLAY = ADDON / "camera_overlay_manager.py"
PAYLOAD = ROOT / "phase_v4_payload" / "camera_overlay_manager.py"
MARK = "UI_V4_CAMERA_OVERLAY"


def one(src, before, after, label):
    matches = src.count(before)
    if matches != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {matches}: {before[:80]!r}")
    return src.replace(before, after, 1)


def patch_viewer(s):
    if "UI_V3_2_PENDING_SYNC_DISPLAY" not in s:
        raise RuntimeError("Viewer Phase V-3.2 is required")
    s = one(s, "from PySide6.QtCore import Qt, QSize, Signal, QRectF, QSignalBlocker",
            "from PySide6.QtCore import Qt, QSize, Signal, QRectF, QSignalBlocker, QTimer",
            "Viewer Qt import")
    s = one(s, "    cutRequested = Signal(int)\n",
            "    cutRequested = Signal(int)\n"
            "    overlayRequested = Signal(bool)  # UI_V4_CAMERA_OVERLAY\n"
            "    opacityRequested = Signal(int)\n",
            "Viewer signals")
    s = one(s, "        self._sync_pending = None  # UI_V3_2_PENDING_SYNC_DISPLAY\n",
            "        self._sync_pending = None  # UI_V3_2_PENDING_SYNC_DISPLAY\n"
            "        self._overlay_pending = None\n"
            "        self._opacity_pending = None\n",
            "Viewer optimistic state")
    s = one(s,
            '''        setting_lay.addWidget(QLabel("表示・同期設定（後続工程で接続）"))
        self.overlay_toggle = QCheckBox("カメラ重畳（Phase V-4）")
        self.overlay_toggle.setEnabled(False)
        setting_lay.addWidget(self.overlay_toggle)
''',
            '''        setting_lay.addWidget(QLabel("表示・同期設定"))
        self.overlay_toggle = QCheckBox("カメラ重畳")
        self.overlay_toggle.setToolTip("Blenderのカメラビューに現在の資料を半透明表示")
        self.overlay_toggle.toggled.connect(self.overlayRequested.emit)
        setting_lay.addWidget(self.overlay_toggle)
''', "enable overlay checkbox")
    s = one(s,
            '''        setting_lay.addWidget(QLabel("重畳の不透明度（Phase V-4）"))
        opacity = QSlider(Qt.Orientation.Horizontal)
        opacity.setRange(0, 100)
        opacity.setValue(50)
        opacity.setEnabled(False)
        setting_lay.addWidget(opacity)
''',
            '''        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("重畳の不透明度"))
        self.opacity_value = QLabel("50%")
        opacity_row.addWidget(self.opacity_value)
        setting_lay.addLayout(opacity_row)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(50)
        self._opacity_timer = QTimer(self)
        self._opacity_timer.setSingleShot(True)
        self._opacity_timer.setInterval(120)
        self._opacity_timer.timeout.connect(self._submit_opacity)
        self.opacity_slider.valueChanged.connect(self._opacity_changed)
        setting_lay.addWidget(self.opacity_slider)
''', "enable opacity slider")
    s = one(s, "    def _cut_selected(self, index):\n",
            '''    def _opacity_changed(self, value):
        self.opacity_value.setText(f"{value}%")
        # Coalesce rapid slider movement into the latest requested value.
        self._opacity_timer.start()

    def _submit_opacity(self):
        self.opacityRequested.emit(self.opacity_slider.value())

    def _cut_selected(self, index):
''', "opacity handlers")
    s = one(s,
            '''        with QSignalBlocker(self.sync_toggle):
            self.sync_toggle.setChecked(sync_value)
        image_lookup = {a["uid"]: a for a in state.get("images", [])} if state else {}
''',
            '''        with QSignalBlocker(self.sync_toggle):
            self.sync_toggle.setChecked(sync_value)
        overlay_enabled = (self._overlay_pending if self._overlay_pending is not None
                           else bool(state and state.get("overlay_enabled", False)))
        with QSignalBlocker(self.overlay_toggle):
            self.overlay_toggle.setChecked(overlay_enabled)
        opacity_percent = (self._opacity_pending if self._opacity_pending is not None
                           else round(100 * float(state.get("overlay_opacity", 0.5) if state else 0.5)))
        # Don't overwrite a slider while the user is dragging it.
        if not self.opacity_slider.isSliderDown() and not self._opacity_timer.isActive():
            with QSignalBlocker(self.opacity_slider):
                self.opacity_slider.setValue(opacity_percent)
            self.opacity_value.setText(f"{opacity_percent}%")
        image_lookup = {a["uid"]: a for a in state.get("images", [])} if state else {}
''', "overlay snapshot rendering")
    return s


def patch_qt(s):
    if "UI_V3_2_SYNC_INTENT_QUEUE" not in s:
        raise RuntimeError("Manager Phase V-3.2 is required")
    s = one(s, "if k not in ('frame', 'auto_sync')",
            "if k not in ('frame', 'auto_sync', 'overlay_enabled', 'overlay_opacity')",
            "do not redraw Manager for overlay settings")
    s = one(s, "        self._sync_request_id = None\n        self._manager_data_key = None\n",
            "        self._sync_request_id = None\n"
            "        self._queued_overlay_enabled = None  # UI_V4_CAMERA_OVERLAY\n"
            "        self._queued_overlay_opacity = None\n"
            "        self._overlay_request_id = None\n"
            "        self._overlay_request_kind = None\n"
            "        self._manager_data_key = None\n",
            "overlay queue fields")
    s = one(s, '''        self._viewer_page.cutRequested.connect(self._request_viewer_cut)
''',
            '''        self._viewer_page.cutRequested.connect(self._request_viewer_cut)
        self._viewer_page.overlayRequested.connect(self._request_overlay_enabled)
        self._viewer_page.opacityRequested.connect(self._request_overlay_opacity)
''', "Viewer signals routing")
    s = one(s, '''        self._viewer_page.refreshRequested.connect(
            lambda: self.command("snapshot")
        )''',
            '''        self._viewer_page.refreshRequested.connect(
            lambda: self.command("refresh_viewer")
        )''', "manual camera refresh")
    s = one(s, "    def _set_status(self, text, error=False):\n",
            '''    def _request_overlay_enabled(self, enabled):
        if self.demo or self.state is None:
            return
        wanted = bool(enabled)
        self._viewer_page._overlay_pending = wanted
        self._queued_overlay_enabled = wanted
        self._set_status('カメラ重畳の切替を予約しました')

    def _request_overlay_opacity(self, percent):
        if self.demo or self.state is None:
            return
        wanted = max(0, min(100, int(percent)))
        self._viewer_page._opacity_pending = wanted
        self._queued_overlay_opacity = wanted

    def _set_status(self, text, error=False):
''', "overlay command handlers")
    s = one(s, '''            if self._queued_viewer_command is not None:
''',
            '''            if getattr(self, '_queued_overlay_enabled', None) is not None:
                wanted = self._queued_overlay_enabled
                self._queued_overlay_enabled = None
                if self.state is not None and bool(self.state.get('overlay_enabled', False)) == wanted:
                    self._viewer_page._overlay_pending = None
                    self._viewer_page.set_snapshot(self.state)
                else:
                    self.command('set_overlay_enabled', enabled=wanted)
                    if self.pending:
                        self._overlay_request_id = self.pending
                        self._overlay_request_kind = 'enabled'
                return
            if getattr(self, '_queued_overlay_opacity', None) is not None:
                wanted = self._queued_overlay_opacity
                self._queued_overlay_opacity = None
                actual = round(100 * float(self.state.get('overlay_opacity', 0.5))) if self.state else None
                if actual == wanted:
                    self._viewer_page._opacity_pending = None
                    self._viewer_page.set_snapshot(self.state)
                else:
                    self.command('set_overlay_opacity', percent=wanted)
                    if self.pending:
                        self._overlay_request_id = self.pending
                        self._overlay_request_kind = 'opacity'
                return
            if self._queued_viewer_command is not None:
''', "overlay queued dispatch")
    s = one(s,
            '''                is_sync_response = self.pending == getattr(self, '_sync_request_id', None)
                self.pending = None
''',
            '''                is_sync_response = self.pending == getattr(self, '_sync_request_id', None)
                is_overlay_response = self.pending == getattr(self, '_overlay_request_id', None)
                overlay_kind = self._overlay_request_kind if is_overlay_response else None
                self.pending = None
''', "overlay response identification")
    s = one(s,
            '''            except (ValueError, OSError) as exc:
                if self.pending == getattr(self, '_sync_request_id', None):
''',
            '''                if is_overlay_response:
                    self._overlay_request_id = None
                    self._overlay_request_kind = None
                    if not data.get('ok'):
                        self._queued_overlay_enabled = None
                        self._queued_overlay_opacity = None
                    if overlay_kind == 'enabled' and self._queued_overlay_enabled is None:
                        self._viewer_page._overlay_pending = None
                    if overlay_kind == 'opacity' and self._queued_overlay_opacity is None:
                        self._viewer_page._opacity_pending = None
                    if self.state is not None:
                        self._viewer_page.set_snapshot(self.state)
            except (ValueError, OSError) as exc:
                if self.pending == getattr(self, '_overlay_request_id', None):
                    self._overlay_request_id = None
                    self._overlay_request_kind = None
                    self._queued_overlay_enabled = None
                    self._queued_overlay_opacity = None
                    self._viewer_page._overlay_pending = None
                    self._viewer_page._opacity_pending = None
                if self.pending == getattr(self, '_sync_request_id', None):
''', "overlay acknowledgement and error cleanup")
    s = one(s,
            '''        elif time.monotonic() - self.pending_since > 30:
            if self.pending == getattr(self, '_sync_request_id', None):
''',
            '''        elif time.monotonic() - self.pending_since > 30:
            if self.pending == getattr(self, '_overlay_request_id', None):
                self._overlay_request_id = None
                self._overlay_request_kind = None
                self._queued_overlay_enabled = None
                self._queued_overlay_opacity = None
                self._viewer_page._overlay_pending = None
                self._viewer_page._opacity_pending = None
                if self.state is not None:
                    self._viewer_page.set_snapshot(self.state)
            if self.pending == getattr(self, '_sync_request_id', None):
''', "overlay timeout cleanup")
    return s


def patch_bridge(s):
    if "UI_V3_TIMELINE_LIVE_PUBLISH" not in s or '"set_auto_sync"' not in s:
        raise RuntimeError("Blender bridge Phase V-3 is required")
    s = one(s, "from ..timeline_manager import sync_reference_display\n",
            "from ..timeline_manager import sync_reference_display\nfrom .. import camera_overlay_manager\n",
            "overlay module import")
    s = one(s,
            '        "auto_sync": project.auto_sync,\n',
            '        "auto_sync": project.auto_sync,\n'
            '        "overlay_enabled": scene.animref_overlay_enabled,  # UI_V4_CAMERA_OVERLAY\n'
            '        "overlay_opacity": scene.animref_overlay_opacity,\n',
            "snapshot overlay state")
    s = one(s, '    elif action == "select_cut":\n',
            '''    elif action == "set_overlay_enabled":
        enabled = args.get('enabled')
        if not isinstance(enabled, bool):
            raise ValueError('カメラ重畳はON/OFFで指定してください')
        status = camera_overlay_manager.set_enabled(scene, enabled)
        message = f'カメラ重畳: {status}'
    elif action == "set_overlay_opacity":
        percent = args.get('percent')
        if type(percent) is not int or not 0 <= percent <= 100:
            raise ValueError('不透明度は0〜100の整数で指定してください')
        camera_overlay_manager.set_opacity(scene, percent / 100.0)
        message = f'重畳不透明度を{percent}%に変更しました'
    elif action == "refresh_viewer":
        camera_overlay_manager.sync_overlay(scene, explicit=True)
        message = '現在フレームの資料を更新しました'
    elif action == "select_cut":
''', "Blender overlay actions")
    s = one(s, '''    return {"ok": True, "message": message, "state": _snapshot()}
''',
            '''    # Explicit changes in Manager/Viewer must also update a held overlay
    # when the Cut/Category has changed (but not on mere Timeline movement).
    if action not in {'snapshot', 'set_overlay_enabled',
                      'set_overlay_opacity', 'refresh_viewer'}:
        camera_overlay_manager.sync_overlay(scene)
    return {"ok": True, "message": message, "state": _snapshot()}
''', "refresh on explicit edits")
    s = one(s, '''def _publish_viewer_state(root):
''',
            '''def _publish_viewer_state(root):
''', "publisher marker")
    s = one(s,
            '''    try:
        state = _snapshot()
        signature = json.dumps(state, sort_keys=True, ensure_ascii=False,
''',
            '''    try:
        # Also update the camera overlay while Qt is running; no bpy on Qt.
        try:
            _, scene = _current_window_and_scene()
            camera_overlay_manager.sync_overlay(scene)
        except Exception as overlay_error:
            # A camera/asset problem must not stop Timeline state publishing.
            print('[AnimRef][Overlay] Warning:', overlay_error)
        state = _snapshot()
        signature = json.dumps(state, sort_keys=True, ensure_ascii=False,
''', "pump overlay refresh")
    s = one(s,
            '''def register():
    bpy.utils.register_class(ANIMREF_OT_OpenExternalManager)
''',
            '''def register():
    camera_overlay_manager.register()
    bpy.utils.register_class(ANIMREF_OT_OpenExternalManager)
''', "camera settings register")
    s = one(s,
            '''def unregister():
    _stop()
    bpy.utils.unregister_class(ANIMREF_OT_OpenExternalManager)
''',
            '''def unregister():
    _stop()
    bpy.utils.unregister_class(ANIMREF_OT_OpenExternalManager)
    camera_overlay_manager.unregister()
''', "camera settings unregister")
    return s


def patch_timeline(s):
    if 'def on_frame_change(scene, depsgraph=None):' not in s:
        raise RuntimeError('Timeline handler not found')
    old = '''        print(
            "[AnimRef] Timeline sync error:",
            error
        )
'''
    after = old + '''
    # V-4: camera overlay follows Timeline even if Qt has been closed.
    # It never touches the user's unrelated camera background images.
    try:
        from .camera_overlay_manager import frame_changed
        frame_changed(scene)
    except Exception as error:
        print("[AnimRef] Camera overlay sync error:", error)
'''
    return one(s, old, after, 'Timeline camera overlay hook')


def patch_old_contracts():
    """Remove historical 'V-4 controls disabled' expectations from V-1/V-2.

    Update V-3's fake Blender namespace to handle the new overlay call.
    This only touches those specific source-test lines, not product code.
    """
    tests = ROOT / 'tests'
    proposals = {}
    p1 = tests / 'test_phase_v1_contract.py'
    if p1.is_file():
        original = p1.read_text(encoding='utf-8')
        before = "    assert 'self.overlay_toggle.setEnabled(False)' in page\n"
        after = ("    assert ('self.overlay_toggle.setEnabled(False)' in page or\n"
                 "            'self.overlay_toggle.toggled.connect' in page)\n")
        if before in original:
            proposals[p1] = original.replace(before, after, 1)
    p2 = tests / 'test_phase_v2_contract.py'
    if p2.is_file():
        original = p2.read_text(encoding='utf-8')
        before = "                'self.overlay_toggle.setEnabled(False)', 'self.sync_toggle.toggled.connect(self.syncRequested.emit)',\n"
        after = "                'self.sync_toggle.toggled.connect(self.syncRequested.emit)',\n"
        if before in original:
            changed = original.replace(before, after, 1)
            signature = "    assert 'import bpy' not in page and 'from bpy' not in page\n"
            if signature in changed:
                changed = changed.replace(signature,
                    "    assert ('self.overlay_toggle.setEnabled(False)' in page or\n"
                    "            'self.overlay_toggle.toggled.connect' in page)\n" + signature, 1)
                proposals[p2] = changed
    p3 = tests / 'test_phase_v3_contract.py'
    if p3.is_file():
        original = p3.read_text(encoding='utf-8')
        before = "        '_refresh_display': lambda s: calls.append('sync'),\n"
        after = ("        '_refresh_display': lambda s: calls.append('sync'),\n"
                 "        'camera_overlay_manager': SimpleNamespace(sync_overlay=lambda *_: None),\n")
        if before in original:
            proposals[p3] = original.replace(before, after, 1)
    if p3.is_file():
        current = proposals.get(p3, p3.read_text(encoding='utf-8'))
        before = "    assert 'self.overlay_toggle.setEnabled(False)' in a\n"
        after = ("    assert ('self.overlay_toggle.setEnabled(False)' in a or\n"
                 "            'self.overlay_toggle.toggled.connect' in a)\n")
        if before in current:
            proposals[p3] = current.replace(before, after, 1)
    for path, code in proposals.items():
        ast.parse(code, filename=str(path))
    return proposals


SPEC_NOTE = """
### Phase V-4：カメラ重畳のQt Viewer統合（2026-11-17）

- カメラ背景画像のFRONT表示（Blender 5.2でPoC実機成功）を利用。
- Viewerからカメラ重畳ON/OFF、不透明度0〜100%を操作する。初期設定はOFF・50%。
- QtからBlenderへのJSON要求／応答を再利用する。設定値はSceneのBlenderプロパティに保持し、AnimRef ProjectのJSON保存形式は変更しない。
- 自動同期ON: カメラ重畳もフレーム・カット・カテゴリに追従。OFF: 同じカット・カテゴリ・カメラで最後の画像を維持。明示更新や選択変更では更新。
- 既存カメラ背景画像は削除・変更しない。AnimRefの所有タグを付けたレイヤーだけを解除し、元の背景表示設定を復元する。
- カメラビューでの位置合わせはFIT（縦横比維持）、最終レンダリングへは含めない。
- 旧3D Nパネルは起動ボタンのみ。旧Blender Image EditorビュアーはV-5まで残す。
- 状態: ソース契約／Blender模擬試験／IPC模擬試験済み。Windows/Blender 5.2実機は未検証。
"""
LOG_NOTE = """
## 2026-11-17 Phase V-4（実機確認待ち）

- ユーザーからV-3.2の6項目すべて成功を確認。
- Blender背景画像方式のPoC（V-0実機成功）をaddonのcamera_overlay_manager.pyへ統合。
- Qt Viewerのカメラ重畳ON/OFFと不透明度スライダーを有効化、送信の連打を抑制。
- Blender側IPCのset_overlay_enabled / set_overlay_opacity / refresh_viewerを追加。
- Timelineフレーム変更Handlerから重畳も更新。Qt起動中はtimerでも状態を整合。
- ユーザー既存のカメラ背景画像の保護、画像解放、フレーム追従・固定表示の模擬試験PASS。
- Qt操作保留／最終意図優先／設定ACKの模擬試験PASS。
- V-1〜V-3.2契約テストの旧仕様チェックはV-4対応へ更新。
- Blender 5.2 + Qt実機動作は**未実施**。試験成功後にPASSを追記する。
"""


def patch_docs():
    changes = {}
    for name, marker, note in (
        ('CURRENT_SPEC.md', '### Phase V-4：カメラ重畳のQt Viewer統合', SPEC_NOTE),
        ('DEVELOPMENT_LOG.md', '## 2026-11-17 Phase V-4（実機確認待ち）', LOG_NOTE),
    ):
        path = ROOT / 'docs' / name
        if path.is_file():
            existing = path.read_text(encoding='utf-8')
            if marker not in existing:
                changes[path] = existing.rstrip() + '\n' + note
    return changes


def main():
    files = (QT, VIEWER, BRIDGE, TIMELINE)
    for f in files:
        if not f.is_file():
            raise FileNotFoundError(f)
    if not PAYLOAD.is_file():
        raise FileNotFoundError(PAYLOAD)
    originals = {f: f.read_text(encoding='utf-8') for f in files}
    if all(MARK in originals[f] for f in (QT, VIEWER, BRIDGE)) and OVERLAY.is_file():
        print('Phase V-4 already applied; no changes.')
        return
    if any(MARK in originals[f] for f in (QT, VIEWER, BRIDGE)) or OVERLAY.exists():
        raise RuntimeError('Partial V-4 installation detected. Restore the backup before retrying.')
    patched = {
        QT: patch_qt(originals[QT]),
        VIEWER: patch_viewer(originals[VIEWER]),
        BRIDGE: patch_bridge(originals[BRIDGE]),
        TIMELINE: patch_timeline(originals[TIMELINE]),
        OVERLAY: PAYLOAD.read_text(encoding='utf-8'),
    }
    patched.update(patch_old_contracts())
    patched.update(patch_docs())
    for f, code in patched.items():
        if f.suffix == '.py':
            ast.parse(code, filename=str(f))
    backup = Path(tempfile.gettempdir()) / 'animref_backups' / ('phase_v4_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir(parents=True)
    for f in patched:
        if f not in originals and f.is_file():
            originals[f] = f.read_text(encoding='utf-8')
    for f in originals:
        dest = backup / f.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
    changed = []
    try:
        for f, code in patched.items():
            f.parent.mkdir(parents=True, exist_ok=True)
            temp = f.with_suffix(f.suffix + '.v4tmp')
            temp.write_text(code, encoding='utf-8')
            os.replace(temp, f)
            changed.append(f)
    except Exception:
        for f in reversed(changed):
            if f in originals:
                shutil.copy2(backup / f.relative_to(ROOT), f)
            elif f.exists():
                f.unlink()
        raise
    print('Phase V-4 applied. Backup:', backup)
    print('Restart Blender and the external Qt application before testing.')


if __name__ == '__main__':
    main()
