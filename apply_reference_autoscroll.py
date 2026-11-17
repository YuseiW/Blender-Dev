"""Patch Qt reference list with drag-hover edge autoscroll.

Place this file at the Blender-Dev repository root next to 'scripts/', then:
    python apply_reference_autoscroll.py

Requires the previous Qt UI + Explorer drop + Save/Reorder patches.
Only edits scripts/addons/anim_reference_tool/qt_manager_app.py.
The operation validates anchors, makes a backup and is idempotent.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
QT = ROOT / "scripts" / "addons" / "anim_reference_tool" / "qt_manager_app.py"
MARKER = "# UI_QT_REFERENCE_AUTOSCROLL_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Cannot patch {label}: expected one original block, found {count}. "
            "Check your local changes and do not overwrite them."
        )
    return text.replace(old, new, 1)


def patch(source: str) -> str:
    if MARKER in source:
        return source
    if "MIME_REFERENCE_TYPE" not in source or "reorderRequested" not in source:
        raise RuntimeError("Save/Reorder patch not found in qt_manager_app.py.")
    if "UI1_EXPLORER_IMAGE_DROP_V1" not in source:
        raise RuntimeError("Explorer-to-Image-Pool D&D patch not found.")

    source = replace_once(
        source,
        '''MIME_REFERENCE_TYPE = "application/x-animref-reference-uid"\n''',
        '''MIME_REFERENCE_TYPE = "application/x-animref-reference-uid"\n
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
''',
        "pure scroll-speed helper",
    )

    source = replace_once(
        source,
        '''        self.setDropIndicatorShown(True)
        self.setSpacing(4)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

    def startDrag(self, supported_actions):
''',
        '''        self.setDropIndicatorShown(True)
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
''',
        "autoscroll timer and pixel-scroll initialization",
    )
    source = replace_once(
        source,
        '''        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def _insertion_index_at(self, position):
''',
        '''        drag = QDrag(self)
        drag.setMimeData(mime)
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            # Also stop when a drag is cancelled with Escape or released outside.
            self._stop_drag_autoscroll()

    def _insertion_index_at(self, position):
''',
        "cancelled drag cleanup",
    )
    source = replace_once(
        source,
        '''    def dragMoveEvent(self, event):
        if (event.mimeData().hasFormat(MIME_TYPE)
                or event.mimeData().hasFormat(MIME_REFERENCE_TYPE)):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
''',
        '''    def dragMoveEvent(self, event):
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
''',
        "drag events and timeout cleanup",
    )

    compile(source, str(QT), "exec")
    return source


def main():
    if not QT.is_file():
        raise FileNotFoundError(
            "qt_manager_app.py not found; run from the Blender-Dev repository root."
        )
    original = QT.read_text(encoding="utf-8")
    updated = patch(original)  # Check every anchor before changing any file.
    if updated == original:
        print("Already applied; no file changed.")
        return
    backup_dir = Path(tempfile.gettempdir()) / "animref_backups" / (
        "reference_autoscroll_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / "qt_manager_app.py"
    shutil.copy2(QT, backup)
    try:
        QT.write_text(updated, encoding="utf-8")
        compile(QT.read_text(encoding="utf-8"), str(QT), "exec")
    except Exception:
        QT.write_text(original, encoding="utf-8")
        raise
    print("Updated:", QT.relative_to(ROOT))
    print("Backup:", backup)
    print("Restart AnimRef Manager (Blender bridge changes are not needed).")


if __name__ == "__main__":
    main()
