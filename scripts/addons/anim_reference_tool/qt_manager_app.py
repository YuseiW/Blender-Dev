"""AnimRef Manager UI-1, independent PySide6 process. No Blender imports.

Start through Blender's '資料管理ツールを開く' button.  --demo permits
checking the layout without a Blender connection.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QSize, QTimer, Signal, QMimeData, QSignalBlocker
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QDrag, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QStackedWidget,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QComboBox, QSpinBox,
    QPlainTextEdit, QFileDialog, QMessageBox, QFrame, QSplitter,
)
from manager_ipc import read_json, write_json_atomic
from qt_viewer_page import ViewerPage


COLORS = {
    "STORYBOARD": "#54a640",
    "LAYOUT": "#4c95fa",
    "KEYFRAME": "#ff686c",
}
CATEGORY_NAMES = {"STORYBOARD": "絵コンテ", "LAYOUT": "レイアウト", "KEYFRAME": "原画"}
MIME_TYPE = "application/x-animref-image-uid"
# UI_QT_SAVE_REORDER_V1
MIME_REFERENCE_TYPE = "application/x-animref-reference-uid"

# UI_QT_REFERENCE_AUTOSCROLL_V1
# Called while the reference list is receiving an internal drag.
def _reference_edge_scroll_step(y, viewport_height):
    """Signed pixel movement per timer tick: negative=up, positive=down.

    Uses viewport coordinates, so it works even after the list has scrolled.
    The 64 px outer band scrolls; closer to an edge means faster scrolling.
    """
    if viewport_height <= 0 or y < 0 or y >= viewport_height:
        return 0
    margin = min(64, max(20, int(viewport_height * 0.15)), max(1, viewport_height // 3))
    if y < margin:
        return -max(4, int(4 + 22 * (margin - y) / margin))
    if y >= viewport_height - margin:
        distance = viewport_height - 1 - y
        return max(4, int(4 + 22 * (margin - distance) / margin))
    return 0

# UI1_EXPLORER_IMAGE_DROP_V1
# Keep supported suffixes aligned with Blender's image_manager.py.
SUPPORTED_IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".exr"
})


def _has_local_image_urls(mime_data):
    """Check Explorer file drag MIME without doing disk IO on each mouse move."""
    if not mime_data.hasUrls():
        return False
    return any(
        url.isLocalFile()
        and Path(url.toLocalFile()).suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        for url in mime_data.urls()
    )


def _dropped_image_paths(mime_data):
    """Return supported existing local image paths, removing duplicate URLs.

    Return at most 101 entries so caller can reject >100 files explicitly.
    Directories, web URLs and unsupported file types are ignored.
    """
    if not mime_data.hasUrls():
        return []
    result = []
    seen = set()
    for url in mime_data.urls():
        if not url.isLocalFile():
            continue
        filename = url.toLocalFile()
        if not filename:
            continue
        path = Path(filename)
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            continue
        try:
            if not path.is_file():
                continue
        except (OSError, ValueError):
            continue
        key = os.path.normcase(os.path.normpath(filename))
        if key in seen:
            continue
        seen.add(key)
        result.append(filename)
        if len(result) > 100:
            break
    return result

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
    filePathsDropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setWrapping(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
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

    def dragEnterEvent(self, event):
        if _has_local_image_urls(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if _has_local_image_urls(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not _has_local_image_urls(event.mimeData()):
            event.ignore()
            return
        paths = _dropped_image_paths(event.mimeData())
        if not paths:
            event.ignore()
            return
        self.filePathsDropped.emit(paths)
        event.acceptProposedAction()


class ReferenceList(QListWidget):
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

        # dragMoveEvent is overridden below, so Qt's default autoscroll
        # doesn't run. Use our own timer for smooth, stationary hover.
        self.setAutoScroll(False)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._drag_hover_y = None
        self._drag_autoscroll = QTimer(self)
        self._drag_autoscroll.setInterval(35)
        self._drag_autoscroll.timeout.connect(self._scroll_while_dragging)

    def _stop_drag_autoscroll(self):
        self._drag_autoscroll.stop()
        self._drag_hover_y = None

    def _set_drag_autoscroll(self, y):
        step = _reference_edge_scroll_step(y, self.viewport().height())
        if step == 0:
            self._stop_drag_autoscroll()
            return
        self._drag_hover_y = y
        if not self._drag_autoscroll.isActive():
            self._drag_autoscroll.start()

    def _scroll_while_dragging(self):
        if self._drag_hover_y is None:
            self._stop_drag_autoscroll()
            return
        step = _reference_edge_scroll_step(
            self._drag_hover_y, self.viewport().height()
        )
        bar = self.verticalScrollBar()
        new_value = max(bar.minimum(), min(bar.maximum(), bar.value() + step))
        if step == 0 or new_value == bar.value():
            self._stop_drag_autoscroll()
            return
        bar.setValue(new_value)

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
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            # Also stop when a drag is cancelled with Escape or released outside.
            self._stop_drag_autoscroll()

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
        is_internal_reorder = (
            event.source() is self
            and event.mimeData().hasFormat(MIME_REFERENCE_TYPE)
        )
        if is_internal_reorder:
            self._set_drag_autoscroll(event.position().toPoint().y())
        else:
            # Image Pool -> references is a separate CopyAction, unchanged.
            self._stop_drag_autoscroll()

        if (event.mimeData().hasFormat(MIME_TYPE)
                or event.mimeData().hasFormat(MIME_REFERENCE_TYPE)):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._stop_drag_autoscroll()
        event.accept()

    def dropEvent(self, event):
        self._stop_drag_autoscroll()
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


# UI_V3_TIMELINE_LIVE_CLIENT

def manager_data_key(state):
    """Ignore playback-only changes when deciding to redraw Manager widgets."""
    if not state:
        return None
    return json.dumps({k: v for k, v in state.items()
                       if k not in ('frame', 'auto_sync', 'overlay_enabled', 'overlay_opacity')},
                      ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class ManagerWindow(QMainWindow):
    def __init__(self, session_dir=None, demo=False):
        super().__init__()
        self.session_dir = Path(session_dir) if session_dir else None
        self.demo = demo
        self.state = None
        self._live_mtime_ns = None
        self._last_live_state_at = 0.0
        self._last_viewer_probe_at = 0.0
        self._viewer_probe_pending = False
        self._queued_viewer_command = None
        self._queued_sync_enabled = None  # UI_V3_2_SYNC_INTENT_QUEUE
        self._sync_request_id = None
        self._queued_overlay_enabled = None  # UI_V4_CAMERA_OVERLAY
        self._queued_overlay_opacity = None
        self._overlay_request_id = None
        self._overlay_request_kind = None
        self._manager_data_key = None
        self._manager_needs_render = False
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
        self._setup_page_switcher()
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
        save = QPushButton("上書き保存")
        save.setToolTip("既存のAnimRef JSONへ保存（未保存の場合は名前を付けて保存）")
        save.clicked.connect(self._save_project)
        header.addWidget(save)
        save_as = QPushButton("名前を付けて保存…")
        save_as.clicked.connect(self._save_project_as)
        header.addWidget(save_as)
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
        self.ref_list.reorderRequested.connect(self._reorder_ref)
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
        self.assets.filePathsDropped.connect(self._import_dropped_files)
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
        note = QLabel("エクスプローラーから画像をここへドロップして追加できます。画像プールから左側へドラッグすると資料登録できます。")
        note.setObjectName("muted")
        note.setWordWrap(True)
        rr.addWidget(note)
        self.status = QLabel("起動中…")
        self.status.setObjectName("status")
        full.addWidget(self.status)

    # UI_QT_VIEWER_STACK_V1
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
            lambda: self.command("refresh_viewer")
        )
        self._viewer_page.syncRequested.connect(self._request_auto_sync)
        self._viewer_page.cutRequested.connect(self._request_viewer_cut)
        self._viewer_page.overlayRequested.connect(self._request_overlay_enabled)
        self._viewer_page.opacityRequested.connect(self._request_overlay_opacity)
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
            if self.state is not None and getattr(self, '_manager_needs_render', False):
                # Restore new Blender-side changes only when data changed;
                # Timeline ticks alone must not reset Manager scrolling.
                self._render()

    def _request_viewer_cut(self, index):
        if not self.state:
            return
        cuts = self.state.get('cuts', [])
        if not isinstance(index, int) or not 0 <= index < len(cuts):
            self._set_status('カットを選択できませんでした', True)
            return
        if index != self.state.get('active_cut_index'):
            self.command('select_cut', index=index)

    def _request_auto_sync(self, enabled):
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

    def _request_overlay_enabled(self, enabled):
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
        self.status.setText(text)
        self.status.setStyleSheet("color: #ff9999" if error else "color: #b6b3ce")

    def command(self, action, **args):
        if self.demo:
            self._set_status("デモモードは読み取り専用です")
            return
        if self.pending:
            if self._viewer_probe_pending and self._queued_viewer_command is None:
                # User commands take priority over the background snapshot probe.
                # Run them after its response without dropping the user's click.
                self._queued_viewer_command = (action, args)
                return
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
        if self.demo:
            return
        if not self.pending:
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
            if getattr(self, '_queued_overlay_enabled', None) is not None:
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
                action, args = self._queued_viewer_command
                self._queued_viewer_command = None
                self.command(action, **args)
                return
            self._poll_live_state()
            self._poll_viewer_snapshot_fallback()
            return
        path = self.session_dir / "responses" / (self.pending + ".json")
        if path.exists():
            try:
                data = read_json(path)
                path.unlink(missing_ok=True)
                is_sync_response = self.pending == getattr(self, '_sync_request_id', None)
                is_overlay_response = self.pending == getattr(self, '_overlay_request_id', None)
                overlay_kind = self._overlay_request_kind if is_overlay_response else None
                self.pending = None
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
                if is_overlay_response:
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
                    self._sync_request_id = None
                    self._queued_sync_enabled = None
                    self._viewer_page._sync_pending = None
                    if self.state is not None:
                        self._viewer_page.set_snapshot(self.state)
                self.pending = None
                self._viewer_probe_pending = False
                self._set_status(f"応答の読み取り失敗: {exc}", True)
        elif time.monotonic() - self.pending_since > 30:
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
                self._sync_request_id = None
                self._queued_sync_enabled = None
                self._viewer_page._sync_pending = None
                if self.state is not None:
                    self._viewer_page.set_snapshot(self.state)
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
        self._last_live_state_at = time.monotonic()
        self.state = new_state
        self._manager_needs_render = manager_data_key(new_state) != self._manager_data_key
        self._viewer_page.set_snapshot(new_state)
        status_label = getattr(self._viewer_page, 'status', None)
        if status_label is not None:
            status_label.setText('同期経路：ライブ通知（V-3.1）')

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
        if hasattr(self, "_viewer_page"):
            self._viewer_page.set_snapshot(s)
        self._manager_data_key = manager_data_key(s)
        self._manager_needs_render = False

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

    def _import_dropped_files(self, paths):
        """Explorer file drop and file dialog share one Blender import route."""
        self._submit_import_paths(paths)

    def _submit_import_paths(self, paths):
        if not paths:
            return
        if len(paths) > 100:
            self._set_status("一度に追加できる画像は100枚までです。分けてドロップしてください。", True)
            return
        self.command("import_images", paths=list(paths))

    def _import_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "画像を追加", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.exr)"
        )
        self._submit_import_paths(paths)

    def _editor_update_for_save(self):
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
        "scene": "Scene", "frame": 1, "project": "Animation Reference",
        "project_filepath": "", "auto_sync": True,
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
