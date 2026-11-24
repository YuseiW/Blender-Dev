"""Phase V-1: read-only Viewer page sharing the existing Qt Manager state.

Does not communicate with Blender on its own. ManagerWindow remains the only
IPC client and supplies snapshots through set_snapshot(). This page deliberately
has no reference-editing operations or camera overlay implementation yet.
"""
from pathlib import Path

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QIcon, QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QPlainTextEdit,
    QCheckBox, QSlider,
)


CATEGORIES = (
    ("KEYFRAME", "原画", "keyframe"),
    ("LAYOUT", "レイアウト", "layout"),
    ("STORYBOARD", "絵コンテ", "storyboard"),
)


def reference_at_current_frame(state):
    """Pure snapshot selector: (cut, reference, asset, refs), or None entries.

    Cuts and category definitions are from the bridge snapshot. It is deliberately
    tolerant of a missing cut, a frame with no reference, or a missing image file.
    """
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
        asset = next((a for a in state.get("images", []) if a["uid"] == current["image_id"]), None)
    return cut, current, asset, refs


class ImageCanvas(QLabel):
    """Keep the original pixel aspect ratio on resize; never edit the image."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._original = QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(300, 220)
        self.setText("Blenderの現在フレームに対応する資料を表示")
        self.setStyleSheet("background:#090a14; border:1px solid #39364b; border-radius:6px;")

    def show_file(self, filename):
        path = Path(filename) if filename else None
        self._original = QPixmap(str(path)) if path and path.is_file() else QPixmap()
        if self._original.isNull():
            self.clear()
            self.setText("表示する画像がありません" if not filename else "画像を読み込めません")
        else:
            self._redraw()

    def _redraw(self):
        if self._original.isNull():
            return
        target = self.size() - QSize(18, 18)
        if target.width() <= 0 or target.height() <= 0:
            return
        scaled = self._original.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._redraw()


class ViewerPage(QWidget):
    """Read-only page. Only category changes and explicit refresh are requested."""
    categoryRequested = Signal(str)
    refreshRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshot = None
        self._preview_path = None
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
        btn = QPushButton("現在フレームを更新")
        btn.clicked.connect(lambda checked=False: self.refreshRequested.emit())
        header.addWidget(btn)
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

        self.preview = ImageCanvas()
        left_lay.addWidget(self.preview, 3)
        self.preview_info = QLabel("資料未選択")
        self.preview_info.setObjectName("muted")
        left_lay.addWidget(self.preview_info)

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
        self.status = QLabel("V-1：画面統合試験。Timelineの自動追従は次工程で追加します。")
        self.status.setObjectName("status")
        layout.addWidget(self.status)

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
        self.references.clear()
        image_lookup = {a["uid"]: a for a in state.get("images", [])} if state else {}
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
            if current is ref:
                entry.setBackground(QBrush(QColor("#264b47")))
                entry.setForeground(QBrush(QColor("#d6fff1")))
            self.references.addItem(entry)
            if current is ref:
                current_item = entry
        if current:
            self.references.scrollToItem(current_item)
            self.instruction.setPlainText(current.get("instruction", ""))
            self.preview_info.setText(
                f"{asset['name'] if asset else '画像データ未取得'}"
                f"  /  {current['start']}–{current['end']}f"
            )
        else:
            self.instruction.clear()
            self.preview_info.setText("現在フレームに登録資料はありません")
        filename = asset.get("path", "") if asset else ""
        if filename != self._preview_path or self.preview._original.isNull():
            self._preview_path = filename
            self.preview.show_file(filename)
