"""AnimRef Viewer, Phase V-2: read-only reference browser with zoom/pan.

Only uses snapshot data supplied by ManagerWindow. It does not call bpy, edit
references, or communicate with Blender directly. Continuous Timeline updates
and camera overlay controls belong to later phases.
"""
from pathlib import Path

from PySide6.QtCore import Qt, QSize, Signal, QRectF
from PySide6.QtGui import QPixmap, QIcon, QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QPlainTextEdit,
    QCheckBox, QSlider, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
)

# UI_QT_VIEWER_DISPLAY_V2
CATEGORIES = (
    ("KEYFRAME", "原画", "keyframe"),
    ("LAYOUT", "レイアウト", "layout"),
    ("STORYBOARD", "絵コンテ", "storyboard"),
)
CATEGORY_COLORS = {
    "KEYFRAME": "#ff686c",
    "LAYOUT": "#4c95fa",
    "STORYBOARD": "#54a640",
}


def reference_at_current_frame(state):
    """Return (active_cut, current_ref, image_asset, category_refs)."""
    if not state:
        return None, None, None, []
    cuts = state.get("cuts", [])
    idx = state.get("active_cut_index", -1)
    if not isinstance(idx, int) or not 0 <= idx < len(cuts):
        return None, None, None, []
    cut = cuts[idx]
    refs = cut.get("categories", {}).get(state.get("active_category"), [])
    frame = state.get("frame", -1)
    current = next((r for r in refs if r["start"] <= frame <= r["end"]), None)
    asset = None
    if current:
        asset = next(
            (a for a in state.get("images", []) if a["uid"] == current["image_id"]),
            None,
        )
    return cut, current, asset, refs


def next_zoom_scale(current, wheel_delta, minimum=0.01, maximum=32.0):
    """Calculate clamped image scale. Zero delta leaves the value untouched."""
    if wheel_delta == 0:
        return current
    candidate = current * (1.15 ** (wheel_delta / 120.0))
    return max(minimum, min(maximum, candidate))


def reference_list_signature(cut, category, refs, image_lookup):
    """Identify list changes so a refresh doesn't reset the user's scroll."""
    return (
        cut.get("uid", cut.get("name", "")) if cut else None,
        category,
        tuple(
            (
                ref.get("uid"), ref.get("image_id"), ref.get("start"),
                ref.get("end"), ref.get("duration"),
                image_lookup.get(ref.get("image_id"), {}).get("name", ""),
                image_lookup.get(ref.get("image_id"), {}).get("path", ""),
            )
            for ref in refs
        ),
    )


class ImageCanvas(QGraphicsView):
    """Non-destructive image viewer. Wheel to zoom, left-drag to pan."""
    zoomChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original = QPixmap()
        self._fitted = True
        self._scene = QGraphicsScene(self)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._message = self._scene.addText("Blenderの現在フレームに対応する資料を表示")
        self._message.setDefaultTextColor(QColor("#aab5c8"))
        self.setScene(self._scene)
        self.setSceneRect(QRectF(-320, -200, 640, 400))
        self._center_message()
        self.setRenderHints(self.renderHints())
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setMinimumSize(300, 220)
        self.setBackgroundBrush(QBrush(QColor("#090a14")))
        self.setStyleSheet("border:1px solid #39364b; border-radius:6px;")

    def _center_message(self):
        rect = self._message.boundingRect()
        self._message.setPos(-rect.width() / 2, -rect.height() / 2)

    def _show_placeholder(self, text):
        self._message.setPlainText(text)
        self._message.setVisible(True)
        self._center_message()
        self.setSceneRect(QRectF(-320, -200, 640, 400))
        self.resetTransform()
        self.centerOn(0, 0)
        self.zoomChanged.emit(1.0)

    def show_file(self, filename):
        path = Path(filename) if filename else None
        image = QPixmap(str(path)) if path and path.is_file() else QPixmap()
        self._original = image
        self._pixmap_item.setPixmap(image)
        if image.isNull():
            self._fitted = True
            self._show_placeholder("表示する画像がありません" if not filename else "画像を読み込めません")
            return
        self._message.setVisible(False)
        self.setSceneRect(self._pixmap_item.boundingRect())
        self.fit_image()

    def fit_image(self):
        """Show the entire image while keeping its original aspect ratio."""
        if self._original.isNull():
            return
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._fitted = True
        self.zoomChanged.emit(self.transform().m11())

    def actual_size(self):
        """One source pixel per scene unit (100% at normal display scaling)."""
        if self._original.isNull():
            return
        self.resetTransform()
        self.centerOn(self._pixmap_item)
        self._fitted = False
        self.zoomChanged.emit(1.0)

    def wheelEvent(self, event):
        if self._original.isNull():
            event.ignore()
            return
        delta = event.angleDelta().y()
        if not delta:
            delta = event.pixelDelta().y()
        if not delta:
            event.ignore()
            return
        current = self.transform().m11()
        target = next_zoom_scale(current, delta)
        if abs(target - current) > 1e-8:
            factor = target / current
            self.scale(factor, factor)
            self._fitted = False
            self.zoomChanged.emit(target)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fitted and not self._original.isNull():
            self.fit_image()


class ViewerPage(QWidget):
    """Viewer only; editing remains in the original Manager page."""
    categoryRequested = Signal(str)
    refreshRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshot = None
        self._preview_path = None
        self._list_signature = None
        self._highlight_uid = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        header = QHBoxLayout()
        name = QLabel("Reference Viewer")
        name.setObjectName("heading")
        header.addWidget(name)
        self.frame_label = QLabel("Blenderからの状態を取得中…")
        self.frame_label.setObjectName("muted")
        header.addWidget(self.frame_label, 1)
        refresh = QPushButton("現在フレームを更新")
        refresh.clicked.connect(self.refreshRequested.emit)
        header.addWidget(refresh)
        layout.addLayout(header)

        split = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(split, 1)
        left = QFrame()
        right = QFrame()
        left.setObjectName("pane")
        right.setObjectName("pane")
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([810, 440])
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 1)
        left_lay = QVBoxLayout(left)
        right_lay = QVBoxLayout(right)
        left_lay.setContentsMargins(12, 12, 12, 12)
        right_lay.setContentsMargins(10, 12, 10, 12)

        tools = QHBoxLayout()
        tools.addWidget(QLabel("メインリファレンス"))
        tools.addStretch(1)
        fit_button = QPushButton("全体表示")
        fit_button.setToolTip("画像全体を表示領域に収める")
        tools.addWidget(fit_button)
        actual_button = QPushButton("100%")
        actual_button.setToolTip("画像を元のピクセルサイズで表示する")
        tools.addWidget(actual_button)
        self.zoom_label = QLabel("—")
        self.zoom_label.setObjectName("muted")
        tools.addWidget(self.zoom_label)
        left_lay.addLayout(tools)

        self.preview = ImageCanvas()
        self.preview.zoomChanged.connect(self._zoom_changed)
        fit_button.clicked.connect(self.preview.fit_image)
        actual_button.clicked.connect(self.preview.actual_size)
        left_lay.addWidget(self.preview, 3)
        self.preview_info = QLabel("資料未選択")
        self.preview_info.setObjectName("muted")
        left_lay.addWidget(self.preview_info)
        help_label = QLabel("ホイール：拡大・縮小    画像上をドラッグ：移動")
        help_label.setObjectName("muted")
        left_lay.addWidget(help_label)

        lower = QHBoxLayout()
        settings = QFrame()
        settings.setObjectName("pane")
        setting_lay = QVBoxLayout(settings)
        setting_lay.addWidget(QLabel("表示・同期設定（後続工程で接続）"))
        self.overlay_toggle = QCheckBox("カメラ重畳（Phase V-4）")
        self.overlay_toggle.setEnabled(False)
        setting_lay.addWidget(self.overlay_toggle)
        self.sync_toggle = QCheckBox("自動同期（Phase V-3）")
        self.sync_toggle.setEnabled(False)
        setting_lay.addWidget(self.sync_toggle)
        setting_lay.addWidget(QLabel("重畳の不透明度（Phase V-4）"))
        opacity = QSlider(Qt.Orientation.Horizontal)
        opacity.setRange(0, 100)
        opacity.setValue(50)
        opacity.setEnabled(False)
        setting_lay.addWidget(opacity)
        setting_lay.addStretch(1)
        lower.addWidget(settings, 1)

        note_card = QFrame()
        note_card.setObjectName("pane")
        note_lay = QVBoxLayout(note_card)
        note_lay.addWidget(QLabel("作画・演出指示"))
        self.instruction = QPlainTextEdit()
        self.instruction.setReadOnly(True)
        self.instruction.setPlaceholderText("表示中の資料に指示はありません")
        note_lay.addWidget(self.instruction)
        lower.addWidget(note_card, 1)
        left_lay.addLayout(lower, 2)

        right_lay.addWidget(QLabel("登録資料一覧"))
        catbar = QHBoxLayout()
        self.category_buttons = {}
        for key, title, object_name in CATEGORIES:
            button = QPushButton(title)
            button.setCheckable(True)
            button.setObjectName(object_name)
            button.clicked.connect(lambda checked=False, c=key: self.categoryRequested.emit(c))
            catbar.addWidget(button)
            self.category_buttons[key] = button
        right_lay.addLayout(catbar)
        self.references = QListWidget()
        self.references.setIconSize(QSize(94, 70))
        self.references.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.references.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        right_lay.addWidget(self.references, 1)
        notice = QLabel("閲覧専用。登録・編集は上部の画面切替から行います。")
        notice.setObjectName("muted")
        notice.setWordWrap(True)
        right_lay.addWidget(notice)
        self.status = QLabel("V-2：ホイールズーム・パン・全体表示。常時同期は次工程。")
        self.status.setObjectName("status")
        layout.addWidget(self.status)

    def _zoom_changed(self, scale):
        self.zoom_label.setText(f"{scale*100:.0f}%")

    def _rebuild_list(self, refs, image_lookup):
        self.references.clear()
        for i, ref in enumerate(refs):
            info = image_lookup.get(ref["image_id"], {})
            entry = QListWidgetItem(
                f"{i+1:02d}  {info.get('name', '画像未取得')}\n"
                f"{ref['start']}–{ref['end']}f  ({ref['duration']}f)"
            )
            thumb_path = info.get("path", "")
            if thumb_path and Path(thumb_path).is_file():
                entry.setIcon(QIcon(thumb_path))
            entry.setSizeHint(QSize(170, 82))
            self.references.addItem(entry)

    def _highlight_current(self, refs, current_uid, category, scroll=False):
        active_color = CATEGORY_COLORS.get(category, "#4c95fa")
        for i, ref in enumerate(refs):
            item = self.references.item(i)
            if item is None:
                continue
            active = ref.get("uid") == current_uid and current_uid is not None
            item.setBackground(QBrush(QColor(active_color if active else "#222432")))
            item.setForeground(QBrush(QColor("#11131a" if active else "#ccd1db")))
            if active and scroll:
                self.references.scrollToItem(item)
        self._highlight_uid = current_uid

    def set_snapshot(self, state):
        self._snapshot = state
        cut, current, asset, refs = reference_at_current_frame(state)
        if not state:
            self.frame_label.setText("Blenderに未接続")
        else:
            self.frame_label.setText(
                f"{state.get('scene', '')} / {cut['name'] if cut else 'カットなし'}"
                f" / Frame {state.get('frame', 0)}"
            )
        cat = state.get("active_category") if state else None
        for key, button in self.category_buttons.items():
            button.setChecked(key == cat)
        self.sync_toggle.setChecked(bool(state and state.get("auto_sync")))
        image_lookup = {a["uid"]: a for a in state.get("images", [])} if state else {}
        signature = reference_list_signature(cut, cat, refs, image_lookup)
        rebuilt = signature != self._list_signature
        if rebuilt:
            self._rebuild_list(refs, image_lookup)
            self._list_signature = signature
        current_uid = current.get("uid") if current else None
        self._highlight_current(
            refs, current_uid, cat,
            scroll=rebuilt or current_uid != self._highlight_uid,
        )

        if current:
            note = current.get("instruction", "")
            if self.instruction.toPlainText() != note:
                self.instruction.setPlainText(note)
            self.preview_info.setText(
                f"{asset['name'] if asset else '画像データ未取得'}"
                f"  /  {current['start']}–{current['end']}f"
            )
        else:
            self.instruction.clear()
            self.preview_info.setText("現在フレームに登録資料はありません")
        filename = asset.get("path", "") if asset else ""
        # Keep zoom/pan on snapshot updates of the same image. Retry a missing
        # image in case the file was restored since the last refresh.
        if filename != self._preview_path or self.preview._original.isNull():
            self._preview_path = filename
            self.preview.show_file(filename)
