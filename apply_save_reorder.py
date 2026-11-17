"""Apply Qt Manager JSON overwrite-save + reference list drag-to-reorder.

Place this file in the root of the Blender-Dev repository and run:
    python apply_save_reorder.py

Changes ONLY the current Qt manager and its Blender bridge. Validates anchors,
backs up both files before writing, and is safe to run repeatedly.
"""
from pathlib import Path
from datetime import datetime
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
ADDON = ROOT / "scripts" / "addons" / "anim_reference_tool"
QT = ADDON / "qt_manager_app.py"
BRIDGE = ADDON / "operators" / "manager_external.py"
MARKER_QT = "# UI_QT_SAVE_REORDER_V1"
MARKER_BRIDGE = "# UI_BRIDGE_SAVE_REORDER_V1"


def replace_one(source, before, after, label):
    count = source.count(before)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one matching source anchor, found {count}. "
            "The source may be different from the distributed Qt UI-1 version. "
            "Nothing was changed."
        )
    return source.replace(before, after, 1)


def patch_qt(source):
    if MARKER_QT in source:
        return source
    # The Explorer -> Pool drag-and-drop patch is a prerequisite for this
    # version, which preserves that feature without touching its event code.
    if "UI1_EXPLORER_IMAGE_DROP_V1" not in source:
        raise RuntimeError(
            "The Explorer -> Image Pool drag-and-drop patch was not detected "
            "in qt_manager_app.py. Apply it first."
        )
    source = replace_one(
        source,
        'MIME_TYPE = "application/x-animref-image-uid"\n',
        '''MIME_TYPE = "application/x-animref-image-uid"
# UI_QT_SAVE_REORDER_V1
MIME_REFERENCE_TYPE = "application/x-animref-reference-uid"
''',
        "Reference MIME type",
    )
    source = replace_one(
        source,
        '''class ReferenceList(QListWidget):
    imageDropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.setSpacing(4)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE):
            uid = bytes(event.mimeData().data(MIME_TYPE)).decode("utf-8")
            self.imageDropped.emit(uid)
            event.acceptProposedAction()
        else:
            event.ignore()
''',
        '''class ReferenceList(QListWidget):
    imageDropped = Signal(str)
    reorderRequested = Signal(str, int)  # reference UID, destination insertion slot

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDropIndicatorShown(True)
        self.setSpacing(4)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

    def startDrag(self, supported_actions):
        # Internal drag carries the ReferenceItem's stable UID, NOT the image ID.
        item = self.currentItem()
        if item is None:
            return
        uid = item.data(Qt.ItemDataRole.UserRole)
        if not uid:
            return
        mime = QMimeData()
        mime.setData(MIME_REFERENCE_TYPE, str(uid).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def _insertion_index_at(self, position):
        """Find a slot [0..count], using the upper/lower half of each row."""
        item = self.itemAt(position)
        if item is None:
            if self.count() and position.y() < self.visualItemRect(self.item(0)).top():
                return 0
            return self.count()
        row = self.row(item)
        rect = self.visualItemRect(item)
        return row + (1 if position.y() >= rect.center().y() else 0)

    def dragEnterEvent(self, event):
        if (event.mimeData().hasFormat(MIME_TYPE)
                or event.mimeData().hasFormat(MIME_REFERENCE_TYPE)):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if (event.mimeData().hasFormat(MIME_TYPE)
                or event.mimeData().hasFormat(MIME_REFERENCE_TYPE)):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        # Existing image-pool drag remains "add this image to references".
        if event.mimeData().hasFormat(MIME_TYPE):
            uid = bytes(event.mimeData().data(MIME_TYPE)).decode("utf-8")
            self.imageDropped.emit(uid)
            event.acceptProposedAction()
            return

        # Dragging a reference within this list asks Blender to reorder data.
        if event.source() is self and event.mimeData().hasFormat(MIME_REFERENCE_TYPE):
            uid = bytes(event.mimeData().data(MIME_REFERENCE_TYPE)).decode("utf-8")
            insertion_index = self._insertion_index_at(event.position().toPoint())
            self.reorderRequested.emit(uid, insertion_index)
            event.acceptProposedAction()
            return
        event.ignore()
''',
        "ReferenceList DnD implementation",
    )
    source = replace_one(
        source,
        '''        save = QPushButton("JSON保存")
        save.clicked.connect(self._save_project)
        header.addWidget(save)
        load = QPushButton("JSON読込")
''',
        '''        save = QPushButton("上書き保存")
        save.setToolTip("既存のAnimRef JSONへ保存（未保存の場合は名前を付けて保存）")
        save.clicked.connect(self._save_project)
        header.addWidget(save)
        save_as = QPushButton("名前を付けて保存…")
        save_as.clicked.connect(self._save_project_as)
        header.addWidget(save_as)
        load = QPushButton("JSON読込")
''',
        "Save buttons",
    )
    source = replace_one(
        source,
        '''        self.ref_list.currentRowChanged.connect(self._ref_changed)
        self.ref_list.imageDropped.connect(self._add_reference)
        ll.addWidget(self.ref_list, 1)
''',
        '''        self.ref_list.currentRowChanged.connect(self._ref_changed)
        self.ref_list.imageDropped.connect(self._add_reference)
        self.ref_list.reorderRequested.connect(self._reorder_ref)
        ll.addWidget(self.ref_list, 1)
''',
        "Connect reference reorder signal",
    )
    source = replace_one(
        source,
        '''    def _move_ref(self, direction):
        args = self._selected_ref_args()
        if args:
            self.command("move_reference", **args, direction=direction)

    def _delete_ref(self):
''',
        '''    def _move_ref(self, direction):
        args = self._selected_ref_args()
        if args:
            self.command("move_reference", **args, direction=direction)

    def _reorder_ref(self, uid, insertion_index):
        """Convert the drop insertion slot into the final Blender collection index.

        The list is not locally modified: Blender is the single source of truth.
        Example: move index 1 into slot 4 -> final index 3.
        """
        refs = self._current_refs()
        src = next((i for i, ref in enumerate(refs) if ref["uid"] == uid), None)
        if src is None:
            self._set_status("移動する資料が見つかりません。更新してください", True)
            return
        if not (0 <= insertion_index <= len(refs)):
            self._set_status("移動先の位置が不正です", True)
            return
        dest = insertion_index - 1 if insertion_index > src else insertion_index
        if dest == src:  # dropped in the original position
            return
        if self.pending:
            self._set_status("前の操作を処理中です。完了後に移動してください", True)
            return
        # Preserve selection by UID when Blender's snapshot is rendered.
        self.selected_uid = uid
        self.command("reorder_reference", index=src, uid=uid, to_index=dest)

    def _delete_ref(self):
''',
        "Reorder handler",
    )
    source = replace_one(
        source,
        '''    def _save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "プロジェクト保存", "", "AnimRef JSON (*.json)")
        if path:
            self.command("save_project", path=path if path.lower().endswith(".json") else path + ".json")

    def _load_project(self):
''',
        '''    def _editor_update_for_save(self):
        """Include edits still in the duration/instruction widgets with Save.

        Existing explicit '表示尺・指示文を保存' remains available.
        """
        refs = self._current_refs()
        if not 0 <= self.ref_index < len(refs):
            return None
        ref = refs[self.ref_index]
        duration = self.duration.value()
        instruction = self.instruction.toPlainText()
        if duration == ref["duration"] and instruction == ref["instruction"]:
            return None
        return {
            "index": self.ref_index,
            "uid": ref["uid"],
            "expected_duration": ref["duration"],
            "expected_instruction": ref["instruction"],
            "duration": duration,
            "instruction": instruction,
        }

    def _submit_project_save(self, path):
        args = {"path": path}
        update = self._editor_update_for_save()
        if update is not None:
            args["ref_update"] = update
        self.command("save_project", **args)

    def _save_project(self):
        """Save to current JSON, including the active reference editor's edits."""
        if not self.state:
            self._set_status("Blenderとの接続が完了していません", True)
            return
        path = self.state.get("project_filepath", "")
        if not path:
            self._save_project_as()
            return
        self._submit_project_save(path)

    def _save_project_as(self):
        """Save to a chosen filename, including pending reference editor edits."""
        if not self.state:
            self._set_status("Blenderとの接続が完了していません", True)
            return
        current_path = self.state.get("project_filepath", "")
        path, _ = QFileDialog.getSaveFileName(
            self, "プロジェクトを名前を付けて保存", current_path, "AnimRef JSON (*.json)"
        )
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            self._submit_project_save(path)

    def _load_project(self):
''',
        "Save vs Save As handlers",
    )
    source = replace_one(
        source,
        '''        "scene": "Scene", "frame": 1, "project": "Animation Reference", "auto_sync": True,
''',
        '''        "scene": "Scene", "frame": 1, "project": "Animation Reference",
        "project_filepath": "", "auto_sync": True,
''',
        "Demo data: project_filepath",
    )
    compile(source, str(QT), "exec")
    return source


def patch_bridge(source):
    if MARKER_BRIDGE in source:
        return source
    source = replace_one(
        source,
        '''    return {
        "scene": scene.name,
        "frame": scene.frame_current,
        "project": project.project_name,
''',
        '''    return {
        "scene": scene.name,
        "frame": scene.frame_current,
        "project": project.project_name,
        # UI_BRIDGE_SAVE_REORDER_V1
        "project_filepath": project.project_filepath,
''',
        "Snapshot project path",
    )
    source = replace_one(
        source,
        '''    elif action in {"remove_reference", "move_reference", "update_reference"}:
''',
        '''    elif action in {"remove_reference", "move_reference", "update_reference", "reorder_reference"}:
''',
        "Allow reorder command",
    )
    source = replace_one(
        source,
        '''        elif action == "move_reference":
            direction = int(args.get("direction", 0))
            if direction not in (-1, 1):
                raise ValueError("並べ替え方向が不正です")
            if not move_reference(cut, project.active_category, index, direction):
                raise ValueError("先頭または末尾を超えて移動できません")
        else:
            duration = int(args.get("duration", 0))
''',
        '''        elif action == "move_reference":
            direction = int(args.get("direction", 0))
            if direction not in (-1, 1):
                raise ValueError("並べ替え方向が不正です")
            if not move_reference(cut, project.active_category, index, direction):
                raise ValueError("先頭または末尾を超えて移動できません")
        elif action == "reorder_reference":
            # The UID + index check above prevents stale Qt lists from
            # silently changing a different reference.
            dest = int(args.get("to_index", -1))
            if not 0 <= dest < len(coll):
                raise ValueError("移動先の資料番号が不正です")
            if dest != index:
                coll.move(index, dest)
            message = f"資料を{dest + 1}番目へ移動しました"
        else:
            duration = int(args.get("duration", 0))
''',
        "Blender collection.move handler",
    )
    source = replace_one(
        source,
        '''        save_project(project, path)
        message = "プロジェクトをJSONに保存しました"
''',
        '''        ref_update = args.get("ref_update")
        if ref_update is not None:
            if not isinstance(ref_update, dict):
                raise ValueError("編集中の資料が不正です")
            cut = _active_cut(project)
            coll = get_reference_collection(cut, project.active_category)
            index = int(ref_update.get("index", -1))
            uid = ref_update.get("uid", "")
            if not 0 <= index < len(coll) or coll[index].uid != uid:
                raise ValueError("編集中の資料が変わりました。画面を更新してください")
            if (coll[index].duration != ref_update.get("expected_duration")
                    or coll[index].instruction != ref_update.get("expected_instruction")):
                raise ValueError("資料がBlender側で更新されています。画面を更新してください")
            duration = int(ref_update.get("duration", 0))
            instruction = ref_update.get("instruction", "")
            if not 1 <= duration <= 1_000_000:
                raise ValueError("表示尺は1以上にしてください")
            if not isinstance(instruction, str) or len(instruction) > 20000:
                raise ValueError("指示文が長すぎます")
            old_duration, old_instruction = coll[index].duration, coll[index].instruction
            coll[index].duration = duration
            coll[index].instruction = instruction
            try:
                save_project(project, path)
            except Exception:
                # Saving failed: do not leave partially applied editor changes.
                coll[index].duration = old_duration
                coll[index].instruction = old_instruction
                raise
            _refresh_display(scene)
        else:
            save_project(project, path)
        message = "プロジェクトをJSONに保存しました"
''',
        "Include unsaved reference editor values in JSON save",
    )
    compile(source, str(BRIDGE), "exec")
    return source


def main():
    if not QT.is_file() or not BRIDGE.is_file():
        raise FileNotFoundError(
            "PySide6 UI-1 files were not found. Expected: "
            "scripts/addons/anim_reference_tool/qt_manager_app.py and "
            "scripts/addons/anim_reference_tool/operators/manager_external.py"
        )
    before_qt = QT.read_text(encoding="utf-8")
    before_bridge = BRIDGE.read_text(encoding="utf-8")
    # Both patches are prepared fully before any file is modified.
    after_qt = patch_qt(before_qt)
    after_bridge = patch_bridge(before_bridge)
    if after_qt == before_qt and after_bridge == before_bridge:
        print("Already applied. No changes needed.")
        return
    backup_dir = Path(tempfile.gettempdir()) / "animref_backups" / (
        "save_reorder_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(QT, backup_dir / "qt_manager_app.py")
    shutil.copy2(BRIDGE, backup_dir / "manager_external.py")
    print("Backups:", backup_dir)
    try:
        QT.write_text(after_qt, encoding="utf-8")
        BRIDGE.write_text(after_bridge, encoding="utf-8")
        # Syntax verification after the writes.
        compile(QT.read_text(encoding="utf-8"), str(QT), "exec")
        compile(BRIDGE.read_text(encoding="utf-8"), str(BRIDGE), "exec")
    except Exception:
        QT.write_text(before_qt, encoding="utf-8")
        BRIDGE.write_text(before_bridge, encoding="utf-8")
        raise
    print("Patched:", QT.relative_to(ROOT))
    print("Patched:", BRIDGE.relative_to(ROOT))
    print("Restart Blender and reopen AnimRef Manager to test.")


if __name__ == "__main__":
    main()
