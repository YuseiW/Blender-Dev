"""AnimRef Viewer, Phase V-2: read-only reference browser with zoom/pan.

Only uses snapshot data supplied by ManagerWindow. It does not call bpy, edit
references, or communicate with Blender directly. Continuous Timeline updates
and camera overlay controls belong to later phases.
"""
from pathlib import Path

from PySide6.QtCore import Qt, QSize, Signal, QRectF, QSignalBlocker, QTimer
from PySide6.QtGui import QPixmap, QIcon, QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QPlainTextEdit,
    QCheckBox, QSlider, QComboBox, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
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
    syncRequested = Signal(bool)
    cutRequested = Signal(int)
    overlayRequested = Signal(bool)  # UI_V4_CAMERA_OVERLAY
    opacityRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshot = None
        self._preview_path = None
        self._list_signature = None
        self._highlight_uid = None
        self._held_frame = None
        self._held_scope = None
        self._held_uid = None
        self._force_refresh = False
        self._sync_pending = None  # UI_V3_2_PENDING_SYNC_DISPLAY
        self._overlay_pending = None
        self._opacity_pending = None
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
        refresh.clicked.connect(self._manual_refresh)
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
        setting_lay.addWidget(QLabel("表示・同期設定"))
        self.overlay_toggle = QCheckBox("カメラ重畳")
        self.overlay_toggle.setToolTip("Blenderのカメラビューに現在の資料を半透明表示")
        self.overlay_toggle.toggled.connect(self.overlayRequested.emit)
        setting_lay.addWidget(self.overlay_toggle)
        self.sync_toggle = QCheckBox("自動同期")
        self.sync_toggle.setToolTip("OFF: 現在の資料を固定。カテゴリ切替と手動更新は可能")
        self.sync_toggle.toggled.connect(self.syncRequested.emit)
        setting_lay.addWidget(self.sync_toggle)
        opacity_row = QHBoxLayout()
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

        # UI_V3_1_VIEWER_CUT_SELECTOR
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
        self.status = QLabel("V-3：Blenderのフレーム変更に追従。自動同期OFFで表示を固定します。")
        self.status.setObjectName("status")
        layout.addWidget(self.status)

    def _opacity_changed(self, value):
        self.opacity_value.setText(f"{value}%")
        # Coalesce rapid slider movement into the latest requested value.
        self._opacity_timer.start()

    def _submit_opacity(self):
        self.opacityRequested.emit(self.opacity_slider.value())

    def _cut_selected(self, index):
        # Snapshot-driven model: Qt never edits Project state locally.
        if index >= 0:
            self.cutRequested.emit(index)

    def _manual_refresh(self):
        """Even if auto-sync is OFF, a user refresh adopts the current frame."""
        self._force_refresh = True
        self.refreshRequested.emit()

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
        if not state:
            self.frame_label.setText("Blenderに未接続")
        else:
            self.frame_label.setText(
                f"{state.get('scene', '')} / {cut['name'] if cut else 'カットなし'}"
                f" / Frame {state.get('frame', 0)}"
                + (f" / 固定表示 {self._held_frame}f" if not state.get('auto_sync', True) else "")
            )
        # Block selection signals during incoming Blender state updates.
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
            button.setChecked(key == cat)
        # A pending Qt command must not be undone by an older live snapshot.
        sync_value = (self._sync_pending if self._sync_pending is not None
                      else bool(state and state.get("auto_sync")))
        with QSignalBlocker(self.sync_toggle):
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
