"""AnimRef Manager UI-1, independent PySide6 process. No Blender imports.

Start through Blender's '資料管理ツールを開く' button.  --demo permits
checking the layout without a Blender connection.
"""
import argparse
import sys
import time
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QSize, QTimer, Signal, QMimeData, QSignalBlocker
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QDrag, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QComboBox, QSpinBox,
    QPlainTextEdit, QFileDialog, QMessageBox, QFrame, QSplitter,
)
from manager_ipc import read_json, write_json_atomic


COLORS = {
    "STORYBOARD": "#54a640",
    "LAYOUT": "#4c95fa",
    "KEYFRAME": "#ff686c",
}
CATEGORY_NAMES = {"STORYBOARD": "絵コンテ", "LAYOUT": "レイアウト", "KEYFRAME": "原画"}
MIME_TYPE = "application/x-animref-image-uid"

STYLE = """
QWidget { background: #0b0820; color: #f2f0fa; font-size: 13px; }
QMainWindow { background: #0b0820; }
QLabel { background: transparent; }
QFrame#pane { border: 1px solid #33304a; border-radius: 6px; background: #100c2b; }
QFrame#referenceRow { background: #100c2b; border-bottom: 1px solid #55516c; }
QLabel#heading { color: #f4f1fb; font-size: 17px; font-weight: 600; }
QLabel#muted { color: #bbb7ce; }
QLabel#status { color: #aaa5c5; font-size: 11px; }
QPushButton { background: #2b2750; border: 1px solid #4d4974; border-radius: 5px;
              padding: 7px 10px; }
QPushButton:hover { background: #403966; }
QPushButton:pressed { background: #585080; }
QPushButton#primary { background: #2a5b45; border: 1px solid #488b6b; }
QPushButton#primary:hover { background: #327958; }
QPushButton#storyboard { background: #245d22; border: 0px; }
QPushButton#layout { background: #1c4b8c; border: 0px; }
QPushButton#keyframe { background: #83383e; border: 0px; }
QPushButton#storyboard:checked { background: #3e9739; border: 2px solid #c8ffc2; }
QPushButton#layout:checked { background: #357cdc; border: 2px solid #bcdfff; }
QPushButton#keyframe:checked { background: #e05b62; border: 2px solid #ffcbce; }
QComboBox, QSpinBox, QPlainTextEdit { background: #191532; border: 1px solid #48435d;
                                  border-radius: 4px; padding: 5px; }
QListWidget { background: #0f0b29; border: 1px solid #393451; outline: 0px; }
QListWidget::item:selected { background: #302957; border: 1px solid #9188be; }
QListWidget::item:hover { background: #211b43; }
QSplitter::handle { background: #55516a; width: 4px; }
QScrollBar:vertical { background: #121027; width: 12px; }
QScrollBar::handle:vertical { background: #635e83; border-radius: 5px; }
"""


def _thumbnail(path, size=QSize(152, 116), categories=()):
    canvas = QPixmap(size)
    canvas.fill(QColor("#211d37"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    img = QPixmap(str(path)) if path and Path(path).is_file() else QPixmap()
    if not img.isNull():
        scaled = img.scaled(
            size.width() - 10, size.height() - 14,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (size.width() - scaled.width()) // 2
        y = (size.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
    else:
        painter.setPen(QColor("#c3bfd2"))
        painter.drawText(canvas.rect(), Qt.AlignmentFlag.AlignCenter, "IMAGE\n未取得")
    painter.setPen(QPen(QColor("#56516e"), 2))
    painter.drawRect(1, 1, size.width()-3, size.height()-3)
    cats = [c for c in COLORS if c in categories]
    if cats:
        width = (size.width()-8) // len(cats)
        for i, cat in enumerate(cats):
            painter.fillRect(4 + i*width, size.height()-9, width, 5, QColor(COLORS[cat]))
    painter.end()
    return canvas


class AssetGrid(QListWidget):
    assetDropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setWrapping(True)
        self.setDragEnabled(True)
        self.setIconSize(QSize(152, 116))
        self.setGridSize(QSize(180, 163))
        self.setSpacing(7)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None:
            return
        uid = item.data(Qt.ItemDataRole.UserRole)
        if not uid:
            return
        data = QMimeData()
        data.setData(MIME_TYPE, str(uid).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(data)
        drag.setPixmap(item.icon().pixmap(110, 86))
        drag.exec(Qt.DropAction.CopyAction)


class ReferenceList(QListWidget):
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


class RefRow(QFrame):
    def __init__(self, number, ref, asset, parent=None):
        super().__init__(parent)
        self.setObjectName("referenceRow")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 8, 10, 8)
        thumb = QLabel()
        thumb.setFixedSize(126, 91)
        thumb.setPixmap(_thumbnail(asset.get("path", ""), QSize(126, 91)))
        h.addWidget(thumb)
        data = QVBoxLayout()
        name = asset.get("name", "画像が見つかりません")
        for txt, bold in (
            (f"{number:02d}  {name}", True),
            (f"{ref['start']}–{ref['end']}f   ({ref['duration']}f)", False),
            (ref.get("instruction", "")[:65] or "指示なし", False),
        ):
            label = QLabel(txt)
            label.setWordWrap(True)
            if bold:
                label.setStyleSheet("font-weight: 600")
            else:
                label.setObjectName("muted")
            data.addWidget(label)
        h.addLayout(data, 1)


class ManagerWindow(QMainWindow):
    def __init__(self, session_dir=None, demo=False):
        super().__init__()
        self.session_dir = Path(session_dir) if session_dir else None
        self.demo = demo
        self.state = None
        self.pending = None
        self.pending_since = 0.0
        self.last_response = time.monotonic()
        self.selected_uid = None
        self.ref_index = -1
        self.setWindowTitle("AnimRef Manager — 資料登録")
        self.resize(1280, 770)
        self.setMinimumSize(900, 560)
        self.setStyleSheet(STYLE)
        self._setup_ui()
        self.poller = QTimer(self)
        self.poller.timeout.connect(self._poll)
        self.poller.start(180)
        if self.demo:
            self.state = demo_data()
            self._render()
            self._set_status("デモモード：Blenderには接続していません")
        else:
            QTimer.singleShot(50, lambda: self.command("snapshot"))

    def _setup_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        full = QVBoxLayout(root)
        full.setContentsMargins(14, 12, 14, 10)
        header = QHBoxLayout()
        title = QLabel("AnimRef Manager")
        title.setObjectName("heading")
        header.addWidget(title)
        self.project_label = QLabel("Blenderに接続中…")
        self.project_label.setObjectName("muted")
        header.addWidget(self.project_label, 1)
        refresh = QPushButton("更新")
        refresh.clicked.connect(lambda: self.command("snapshot"))
        header.addWidget(refresh)
        save = QPushButton("JSON保存")
        save.clicked.connect(self._save_project)
        header.addWidget(save)
        load = QPushButton("JSON読込")
        load.clicked.connect(self._load_project)
        header.addWidget(load)
        full.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        full.addWidget(splitter, 1)
        left = QFrame()
        left.setObjectName("pane")
        right = QFrame()
        right.setObjectName("pane")
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([810, 440])

        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 14, 14, 14)
        row = QHBoxLayout()
        self.category_buttons = {}
        for key, name, obj in [
            ("STORYBOARD", "絵コンテ", "storyboard"),
            ("LAYOUT", "レイアウト", "layout"),
            ("KEYFRAME", "原画", "keyframe"),
        ]:
            button = QPushButton(name)
            button.setObjectName(obj)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, c=key: self.command("select_category", category=c))
            row.addWidget(button)
            self.category_buttons[key] = button
        ll.addLayout(row)
        cut_bar = QHBoxLayout()
        cut_bar.addWidget(QLabel("Cut"))
        self.cut_combo = QComboBox()
        self.cut_combo.currentIndexChanged.connect(self._cut_changed)
        cut_bar.addWidget(self.cut_combo, 1)
        add_cut = QPushButton("＋ カット")
        add_cut.clicked.connect(lambda: self.command("add_cut"))
        cut_bar.addWidget(add_cut)
        del_cut = QPushButton("カット削除")
        del_cut.clicked.connect(self._delete_cut)
        cut_bar.addWidget(del_cut)
        ll.addLayout(cut_bar)
        self.cut_name = QLabel("登録資料")
        self.cut_name.setObjectName("heading")
        ll.addWidget(self.cut_name)
        self.ref_list = ReferenceList()
        self.ref_list.currentRowChanged.connect(self._ref_changed)
        self.ref_list.imageDropped.connect(self._add_reference)
        ll.addWidget(self.ref_list, 1)
        ref_commands = QHBoxLayout()
        for label, callback in [
            ("上へ", lambda: self._move_ref(-1)),
            ("下へ", lambda: self._move_ref(1)),
            ("削除", self._delete_ref),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(callback)
            ref_commands.addWidget(btn)
        ref_commands.addStretch(1)
        ll.addLayout(ref_commands)
        editor = QFrame()
        editor.setObjectName("pane")
        detail = QVBoxLayout(editor)
        dtitle = QLabel("選択資料の編集")
        dtitle.setObjectName("heading")
        detail.addWidget(dtitle)
        duration_bar = QHBoxLayout()
        duration_bar.addWidget(QLabel("表示フレーム数"))
        self.duration = QSpinBox()
        self.duration.setRange(1, 1_000_000)
        duration_bar.addWidget(self.duration)
        duration_bar.addStretch(1)
        detail.addLayout(duration_bar)
        self.instruction = QPlainTextEdit()
        self.instruction.setPlaceholderText("作画・演出の指示を入力")
        self.instruction.setMaximumHeight(90)
        detail.addWidget(self.instruction)
        apply = QPushButton("表示尺・指示文を保存")
        apply.setObjectName("primary")
        apply.clicked.connect(self._apply_ref)
        detail.addWidget(apply)
        ll.addWidget(editor)

        rr = QVBoxLayout(right)
        rr.setContentsMargins(14, 14, 14, 14)
        right_head = QHBoxLayout()
        heading = QLabel("画像プール")
        heading.setObjectName("heading")
        right_head.addWidget(heading)
        self.image_count = QLabel("0枚")
        self.image_count.setObjectName("muted")
        right_head.addWidget(self.image_count)
        right_head.addStretch(1)
        rr.addLayout(right_head)
        self.assets = AssetGrid()
        self.assets.itemDoubleClicked.connect(lambda _: self._add_selected_image())
        rr.addWidget(self.assets, 1)
        import_row = QHBoxLayout()
        import_images = QPushButton("画像を追加…")
        import_images.clicked.connect(self._import_images)
        import_row.addWidget(import_images)
        register = QPushButton("← 選択画像を登録")
        register.setObjectName("primary")
        register.clicked.connect(self._add_selected_image)
        import_row.addWidget(register)
        rr.addLayout(import_row)
        note = QLabel("画像を左側のリストへドラッグしても登録できます。")
        note.setObjectName("muted")
        note.setWordWrap(True)
        rr.addWidget(note)
        self.status = QLabel("起動中…")
        self.status.setObjectName("status")
        full.addWidget(self.status)

    def _set_status(self, text, error=False):
        self.status.setText(text)
        self.status.setStyleSheet("color: #ff9999" if error else "color: #b6b3ce")

    def command(self, action, **args):
        if self.demo:
            self._set_status("デモモードは読み取り専用です")
            return
        if self.pending:
            self._set_status("前の操作を処理中です")
            return
        ident = uuid4().hex
        request = {"id": ident, "action": action, "args": args}
        if self.state is not None:
            request["expect_scene"] = self.state["scene"]
        try:
            write_json_atomic(self.session_dir / "requests" / (ident + ".json"), request)
        except OSError as exc:
            self._set_status(f"接続エラー: {exc}", True)
            return
        self.pending = ident
        self.pending_since = time.monotonic()
        self._set_status("Blenderで処理中…")

    def _poll(self):
        if self.demo or not self.pending:
            return
        path = self.session_dir / "responses" / (self.pending + ".json")
        if path.exists():
            try:
                data = read_json(path)
                path.unlink(missing_ok=True)
                self.pending = None
                self.last_response = time.monotonic()
                if data.get("ok") and isinstance(data.get("state"), dict):
                    self.state = data["state"]
                    self._render()
                    self._set_status(data.get("message", "更新しました"))
                else:
                    self._set_status(data.get("message", "処理に失敗しました"), True)
                    if self.state and "Scene" in data.get("message", ""):
                        QTimer.singleShot(100, lambda: self.command("snapshot"))
            except (ValueError, OSError) as exc:
                self.pending = None
                self._set_status(f"応答の読み取り失敗: {exc}", True)
        elif time.monotonic() - self.pending_since > 30:
            self.pending = None
            self._set_status("Blenderから応答がありません。Blenderが起動中か確認してください。", True)

    def _current_cut(self):
        if not self.state:
            return None
        idx = self.state["active_cut_index"]
        cuts = self.state["cuts"]
        return cuts[idx] if 0 <= idx < len(cuts) else None

    def _current_refs(self):
        cut = self._current_cut()
        if cut is None:
            return []
        return cut["categories"].get(self.state["active_category"], [])

    def _render(self):
        s = self.state
        self.project_label.setText(f"{s['project']}  /  Scene: {s['scene']}  /  {s['frame']}f")
        with QSignalBlocker(self.cut_combo):
            self.cut_combo.clear()
            for cut in s["cuts"]:
                self.cut_combo.addItem(cut["name"])
            self.cut_combo.setCurrentIndex(s["active_cut_index"] if s["cuts"] else -1)
        for key, button in self.category_buttons.items():
            button.setChecked(key == s["active_category"])
        cut = self._current_cut()
        self.cut_name.setText(
            f"{cut['name']}  —  {CATEGORY_NAMES[s['active_category']]}  /  登録順" if cut else "カットを作成してください"
        )
        image_lookup = {a["uid"]: a for a in s["images"]}
        self.assets.clear()
        for asset in s["images"]:
            item = QListWidgetItem(QIcon(_thumbnail(asset["path"], categories=asset["categories"])), asset["name"])
            item.setToolTip(asset["path"] or "画像ファイルなし")
            item.setData(Qt.ItemDataRole.UserRole, asset["uid"])
            self.assets.addItem(item)
        self.image_count.setText(f"{len(s['images'])}枚")
        current_uid = self.selected_uid
        self.ref_list.blockSignals(True)
        try:
            self.ref_list.clear()
            for i, ref in enumerate(self._current_refs()):
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, ref["uid"])
                item.setSizeHint(QSize(220, 112))
                self.ref_list.addItem(item)
                row = RefRow(i+1, ref, image_lookup.get(ref["image_id"], {}))
                self.ref_list.setItemWidget(item, row)
            for index in range(self.ref_list.count()):
                if self.ref_list.item(index).data(Qt.ItemDataRole.UserRole) == current_uid:
                    self.ref_list.setCurrentRow(index)
                    break
            else:
                self.ref_list.setCurrentRow(0 if self.ref_list.count() else -1)
        finally:
            self.ref_list.blockSignals(False)
        self._ref_changed(self.ref_list.currentRow())

    def _cut_changed(self, index):
        if index >= 0:
            self.selected_uid = None
            self.command("select_cut", index=index)

    def _ref_changed(self, row):
        refs = self._current_refs()
        self.ref_index = row if 0 <= row < len(refs) else -1
        if self.ref_index < 0:
            self.selected_uid = None
            self.duration.setValue(1)
            self.instruction.clear()
            return
        ref = refs[row]
        self.selected_uid = ref["uid"]
        with QSignalBlocker(self.duration):
            self.duration.setValue(ref["duration"])
        self.instruction.setPlainText(ref["instruction"])

    def _selected_ref_args(self):
        refs = self._current_refs()
        if not 0 <= self.ref_index < len(refs):
            self._set_status("資料を選択してください", True)
            return None
        return {"index": self.ref_index, "uid": refs[self.ref_index]["uid"]}

    def _apply_ref(self):
        args = self._selected_ref_args()
        if args:
            self.command("update_reference", **args,
                         duration=self.duration.value(), instruction=self.instruction.toPlainText())

    def _move_ref(self, direction):
        args = self._selected_ref_args()
        if args:
            self.command("move_reference", **args, direction=direction)

    def _delete_ref(self):
        args = self._selected_ref_args()
        if args and QMessageBox.question(self, "資料の削除", "選択資料を削除しますか？") == QMessageBox.StandardButton.Yes:
            self.selected_uid = None
            self.command("remove_reference", **args)

    def _add_selected_image(self):
        item = self.assets.currentItem()
        if item:
            self._add_reference(item.data(Qt.ItemDataRole.UserRole))
        else:
            self._set_status("右側の画像を選択してください", True)

    def _add_reference(self, uid):
        if not self._current_cut():
            self._set_status("先にカットを作成してください", True)
            return
        self.command("add_reference", image_id=uid)

    def _delete_cut(self):
        if self._current_cut() and QMessageBox.question(
            self, "カットの削除", "選択したカットと登録資料を削除しますか？"
        ) == QMessageBox.StandardButton.Yes:
            self.selected_uid = None
            self.command("remove_cut")

    def _import_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "画像を追加", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.exr)"
        )
        if paths:
            self.command("import_images", paths=paths[:100])

    def _save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "プロジェクト保存", "", "AnimRef JSON (*.json)")
        if path:
            self.command("save_project", path=path if path.lower().endswith(".json") else path + ".json")

    def _load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "プロジェクト読込", "", "AnimRef JSON (*.json)")
        if path and QMessageBox.question(
            self, "プロジェクト読込", "現在のBlender Sceneの資料データを置き換えます。続けますか？"
        ) == QMessageBox.StandardButton.Yes:
            self.selected_uid = None
            self.command("load_project", path=path)


def demo_data():
    image_list = [
        {"uid": f"img{i}", "name": f"Frame{i:02d}.png", "path": "",
         "categories": (["STORYBOARD"] if i % 3 == 0 else ["LAYOUT"] if i % 3 == 1 else ["KEYFRAME"])}
        for i in range(1, 11)
    ]
    refs = [
        {"uid": f"ref{i}", "image_id": f"img{i}", "duration": 8,
         "instruction": f"作画指示 — {i}番目の資料", "start": 1+(i-1)*8, "end": i*8}
        for i in range(1, 5)
    ]
    return {
        "scene": "Scene", "frame": 1, "project": "Animation Reference", "auto_sync": True,
        "active_category": "STORYBOARD", "active_cut_index": 0,
        "images": image_list, "cuts": [{"uid": "cut1", "name": "C001", "timeline_start": 1,
            "categories": {"STORYBOARD": refs, "LAYOUT": [], "KEYFRAME": []}}],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge-dir", help="Temporary file mailbox directory")
    parser.add_argument("--demo", action="store_true", help="Layout preview without Blender")
    args = parser.parse_args()
    if not args.demo and not args.bridge_dir:
        parser.error("Use --bridge-dir or --demo")
    app = QApplication(sys.argv[:1])
    app.setFont(QFont("Yu Gothic UI", 10))
    window = ManagerWindow(args.bridge_dir, demo=args.demo)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
