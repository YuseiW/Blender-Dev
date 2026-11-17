"""Apply Explorer -> Image Pool drag-and-drop to the existing Qt Manager.

Run from anywhere:
    python apply_explorer_drop.py

Place this script in the Blender-Dev repository root before running.
Only edits scripts/addons/anim_reference_tool/qt_manager_app.py.
Creates a timestamped backup on the FIRST application; subsequent runs are no-ops.
"""
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts/addons/anim_reference_tool/qt_manager_app.py"
MARKER = "# UI1_EXPLORER_IMAGE_DROP_V1"


def once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one code anchor, found {source.count(old)}. "
            "Source may have changed; no files were modified."
        )
    return source.replace(old, new, 1)


def patch(source: str) -> str:
    if MARKER in source:
        return source

    source = once(
        source,
        "import argparse\nimport sys\n",
        "import argparse\nimport os\nimport sys\n",
        "Add os import",
    )

    source = once(
        source,
        'MIME_TYPE = "application/x-animref-image-uid"\n',
        '''MIME_TYPE = "application/x-animref-image-uid"

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
''',
        "Add file drop helpers",
    )

    source = once(
        source,
        "class AssetGrid(QListWidget):\n    assetDropped = Signal(str)\n",
        "class AssetGrid(QListWidget):\n    assetDropped = Signal(str)\n    filePathsDropped = Signal(list)\n",
        "Add image path signal",
    )

    source = once(
        source,
        "        self.setDragEnabled(True)\n        self.setIconSize(QSize(152, 116))\n",
        """        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setIconSize(QSize(152, 116))
""",
        "Enable inbound drag and drop",
    )

    source = once(
        source,
        "        drag.exec(Qt.DropAction.CopyAction)\n\n\nclass ReferenceList(QListWidget):\n",
        '''        drag.exec(Qt.DropAction.CopyAction)

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
''',
        "Add Explorer file drop event handlers",
    )

    source = once(
        source,
        "        self.assets = AssetGrid()\n        self.assets.itemDoubleClicked.connect",
        "        self.assets = AssetGrid()\n        self.assets.filePathsDropped.connect(self._import_dropped_files)\n        self.assets.itemDoubleClicked.connect",
        "Connect the file drop signal",
    )

    source = once(
        source,
        '        note = QLabel("画像を左側のリストへドラッグしても登録できます。")\n',
        '        note = QLabel("エクスプローラーから画像をここへドロップして追加できます。画像プールから左側へドラッグすると資料登録できます。")\n',
        "Update image pool hint",
    )

    source = once(
        source,
        '''    def _import_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "画像を追加", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.exr)"
        )
        if paths:
            self.command("import_images", paths=paths[:100])

''',
        '''    def _import_dropped_files(self, paths):
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

''',
        "Unify dropped files and import dialog path",
    )
    compile(source, str(TARGET), "exec")
    return source


def main():
    if not TARGET.is_file():
        raise FileNotFoundError(
            f"{TARGET} is missing. First apply the original PySide6 UI-1 patch."
        )
    original = TARGET.read_text(encoding="utf-8")
    updated = patch(original)
    if updated == original:
        print("Already applied; no changes needed.")
        return
    backup = (Path(tempfile.gettempdir()) / "animref_backups" /
              "qt_manager_app.before_explorer_drop.py")
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(TARGET, backup)
    print("Backup:", backup)
    TARGET.write_text(updated, encoding="utf-8")
    try:
        compile(TARGET.read_text(encoding="utf-8"), str(TARGET), "exec")
    except Exception:
        TARGET.write_text(original, encoding="utf-8")
        raise
    print("Patched:", TARGET.relative_to(ROOT))
    print("Restart Blender and reopen AnimRef Manager to load the change.")


if __name__ == "__main__":
    main()
