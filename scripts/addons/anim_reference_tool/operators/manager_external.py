"""Blender-side bridge to the external PySide6 reference manager.

Blender data is touched ONLY in the Blender main-thread timer callback.
The Qt application is a separate Python process with no bpy imports.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import bpy

from ..manager_ipc import read_json, write_json_atomic
from ..managers.image_manager import add_image_asset
from ..managers.reference_manager import (
    add_reference, get_reference_collection, move_reference, remove_reference,
)
from ..managers.cut_manager import add_cut, remove_cut
from ..storage.project_io import save_project, load_project
from ..managers.timeline_manager import sync_reference_display
from ..managers import camera_overlay_manager


_process = None
_session_dir = None
_source_window_pointer = None
_last_live_signature = None
_last_live_error = None


def _python_commands():
    """Never run Qt inside Blender's bundled Python process."""
    override = os.environ.get("ANIMREF_PYTHON", "").strip().strip('"')
    if override:
        return [[override]]
    if os.name == "nt":
        return [["py", "-3"], ["python"]]
    return [["python3"], ["python"]]


def _find_external_python():
    errors = []
    for prefix in _python_commands():
        try:
            result = subprocess.run(
                prefix + ["-c", "from PySide6 import QtWidgets"],
                capture_output=True,
                text=True,
                timeout=12,
            )
            if result.returncode == 0:
                return prefix
            errors.append(prefix[0] + ": PySide6 not installed")
        except (OSError, subprocess.TimeoutExpired):
            errors.append(prefix[0] + ": not executable")
    raise RuntimeError(
        "PySide6を使える外部Pythonが見つかりません。"
        " `py -3 -m pip install PySide6` を実行してください。"
        " ANIMREF_PYTHONでPythonの実行パスを指定できます。"
        " [" + ", ".join(errors) + "]"
    )


def _current_window_and_scene():
    wm = bpy.context.window_manager
    if wm is None or _source_window_pointer is None:
        raise RuntimeError("Blenderの元ウィンドウが見つかりません")
    window = next(
        (w for w in wm.windows if w.as_pointer() == _source_window_pointer),
        None,
    )
    if window is None or window.scene is None:
        raise RuntimeError("管理元ウィンドウまたはSceneが失われました")
    return window, window.scene


def _active_cut(project):
    index = project.active_cut_index
    if not (0 <= index < len(project.cuts)):
        raise ValueError("カットを選択してください")
    return project.cuts[index]


def _snapshot():
    _, scene = _current_window_and_scene()
    project = scene.animref_project
    used = {asset.uid: set() for asset in project.images}
    cuts = []
    labels = {
        "STORYBOARD": "storyboard_items",
        "LAYOUT": "layout_items",
        "KEYFRAME": "keyframe_items",
    }
    for cut in project.cuts:
        categories = {}
        for category, attr in labels.items():
            frame = cut.timeline_start
            items = []
            for item in getattr(cut, attr):
                if item.image_id in used:
                    used[item.image_id].add(category)
                items.append({
                    "uid": item.uid,
                    "image_id": item.image_id,
                    "duration": item.duration,
                    "instruction": item.instruction,
                    "start": frame,
                    "end": frame + item.duration - 1,
                })
                frame += item.duration
            categories[category] = items
        cuts.append({
            "uid": cut.uid,
            "name": cut.name,
            "timeline_start": cut.timeline_start,
            "categories": categories,
        })
    images = []
    for asset in project.images:
        try:
            path = bpy.path.abspath(asset.filepath) if asset.filepath else ""
        except (OSError, ValueError, TypeError):
            path = ""
        images.append({
            "uid": asset.uid,
            "name": asset.name,
            "path": path,
            "categories": sorted(used.get(asset.uid, set())),
        })
    return {
        "scene": scene.name,
        "scene_token": str(scene.as_pointer()) if hasattr(scene, "as_pointer") else scene.name,
        "frame": scene.frame_current,
        "project": project.project_name,
        # UI_BRIDGE_SAVE_REORDER_V1
        "project_filepath": project.project_filepath,
        "auto_sync": project.auto_sync,
        "overlay_enabled": scene.animref_overlay_enabled,  # UI_V4_CAMERA_OVERLAY
        "overlay_opacity": scene.animref_overlay_opacity,
        "active_category": project.active_category,
        "active_cut_index": project.active_cut_index,
        "cuts": cuts,
        "images": images,
    }


def _refresh_display(scene):
    if scene.animref_project.auto_sync:
        try:
            sync_reference_display(scene)
        except Exception as exc:
            print("[AnimRef][Qt Manager] Sync warning:", exc)


def _process_request(request):
    if not isinstance(request, dict):
        raise ValueError("Invalid request")
    action = request.get("action")
    args = request.get("args", {})
    if not isinstance(args, dict):
        raise ValueError("Invalid request args")
    _, scene = _current_window_and_scene()
    project = scene.animref_project
    expect_scene = request.get("expect_scene")
    if action != "snapshot" and expect_scene != scene.name:
        raise ValueError("Blender側のSceneが変わりました。画面を更新してください")

    message = "更新しました"
    if action == "snapshot":
        message = "Blenderに接続しました"
    elif action == "set_auto_sync":
        enabled = args.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("自動同期はON/OFFで指定してください")
        project.auto_sync = enabled
        if enabled:
            _refresh_display(scene)
        message = "自動同期をONにしました" if enabled else "自動同期をOFFにしました"
    elif action == "set_overlay_enabled":
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
        index = int(args.get("index", -1))
        if not 0 <= index < len(project.cuts):
            raise ValueError("カットの番号が不正です")
        project.active_cut_index = index
        _refresh_display(scene)
    elif action == "select_category":
        category = args.get("category")
        if category not in {"STORYBOARD", "LAYOUT", "KEYFRAME"}:
            raise ValueError("資料種別が不正です")
        project.active_category = category
        _refresh_display(scene)
    elif action == "add_cut":
        cut = add_cut(project)
        message = f"{cut.name}を追加しました"
    elif action == "remove_cut":
        index = project.active_cut_index
        if not remove_cut(project, index):
            raise ValueError("カットを削除できませんでした")
        _refresh_display(scene)
    elif action == "update_cut":
        cut = _active_cut(project)
        name = str(args.get("name", "")).strip()
        frame = int(args.get("timeline_start", -1))
        if not name or len(name) > 128 or frame < 0:
            raise ValueError("カット名または開始フレームが不正です")
        cut.name = name
        cut.timeline_start = frame
        _refresh_display(scene)
    elif action == "import_images":
        paths = args.get("paths")
        if not isinstance(paths, list) or not 1 <= len(paths) <= 100:
            raise ValueError("1〜100枚の画像を指定してください")
        counts = {"ADDED": 0, "DUPLICATE": 0, "FAILED": 0}
        for filepath in paths:
            if not isinstance(filepath, str) or not filepath:
                counts["FAILED"] += 1
                continue
            _, status = add_image_asset(project, filepath)
            counts[status if status in counts else "FAILED"] += 1
        message = (
            f"画像追加 {counts['ADDED']}枚 / 重複 {counts['DUPLICATE']}枚"
            f" / 失敗 {counts['FAILED']}枚"
        )
    elif action == "add_reference":
        cut = _active_cut(project)
        uid = args.get("image_id", "")
        if not any(a.uid == uid for a in project.images):
            raise ValueError("画像プールにその画像が見つかりません")
        _, status = add_reference(cut, project.active_category, uid)
        if status == "DUPLICATE":
            message = "この画像は現在のカテゴリに登録済みです"
        else:
            message = "資料を末尾に登録しました"
        _refresh_display(scene)
    elif action in {"remove_reference", "move_reference", "update_reference", "reorder_reference"}:
        cut = _active_cut(project)
        coll = get_reference_collection(cut, project.active_category)
        index = int(args.get("index", -1))
        expected_uid = args.get("uid", "")
        if not (0 <= index < len(coll)) or coll[index].uid != expected_uid:
            raise ValueError("資料の選択が変わりました。画面を更新してください")
        if action == "remove_reference":
            if not remove_reference(cut, project.active_category, index):
                raise ValueError("資料を削除できませんでした")
        elif action == "move_reference":
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
            instruction = args.get("instruction", "")
            if not 1 <= duration <= 1_000_000:
                raise ValueError("表示尺は1以上にしてください")
            if not isinstance(instruction, str) or len(instruction) > 20000:
                raise ValueError("指示文が長すぎます")
            coll[index].duration = duration
            coll[index].instruction = instruction
        _refresh_display(scene)
    elif action == "save_project":
        path = args.get("path", "")
        if not isinstance(path, str) or not path.lower().endswith(".json"):
            raise ValueError("保存先には.jsonを指定してください")
        ref_update = args.get("ref_update")
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
    elif action == "load_project":
        path = args.get("path", "")
        if not isinstance(path, str) or not path.lower().endswith(".json"):
            raise ValueError(".jsonを指定してください")
        load_project(project, path)
        _refresh_display(scene)
        message = "JSONプロジェクトを読み込みました"
    else:
        raise ValueError("Unsupported action: " + str(action))

    # Explicit changes in Manager/Viewer must also update a held overlay
    # when the Cut/Category has changed (but not on mere Timeline movement).
    if action not in {'snapshot', 'set_overlay_enabled',
                      'set_overlay_opacity', 'refresh_viewer'}:
        camera_overlay_manager.sync_overlay(scene)
    return {"ok": True, "message": message, "state": _snapshot()}


# UI_V3_TIMELINE_LIVE_PUBLISH

def _publish_viewer_state(root):
    """Publish only changed state. The main-thread Blender timer owns bpy.

    This independent, atomic file doesn't occupy Qt's command slot and does
    not trigger redraws of the Manager editor while a Viewer is visible.
    """
    global _last_live_signature, _last_live_error
    try:
        # Also update the camera overlay while Qt is running; no bpy on Qt.
        try:
            _, scene = _current_window_and_scene()
            camera_overlay_manager.sync_overlay(scene)
        except Exception as overlay_error:
            # A camera/asset problem must not stop Timeline state publishing.
            print('[AnimRef][Overlay] Warning:', overlay_error)
        state = _snapshot()
        signature = json.dumps(state, sort_keys=True, ensure_ascii=False,
                               separators=(',', ':'))
        if signature != _last_live_signature:
            write_json_atomic(Path(root) / 'state' / 'latest.json',
                              {'schema': 1, 'state': state})
            _last_live_signature = signature
        _last_live_error = None
    except Exception as exc:
        error = str(exc)
        if error != _last_live_error:
            print('[AnimRef][Qt Viewer] Live state warning:', error)
            _last_live_error = error


def _pump():
    global _process, _session_dir, _source_window_pointer
    if _process is None or _session_dir is None or _process.poll() is not None:
        _cleanup()
        return None
    root = Path(_session_dir)
    for req_file in sorted((root / "requests").glob("*.json"))[:16]:
        request_id = req_file.stem
        try:
            request = read_json(req_file)
            if request.get("id") != request_id:
                raise ValueError("Request ID mismatch")
            response = _process_request(request)
        except Exception as exc:
            response = {"ok": False, "message": str(exc)}
            print("[AnimRef][Qt Manager]", exc)
        try:
            write_json_atomic(root / "responses" / (request_id + ".json"), response)
        finally:
            req_file.unlink(missing_ok=True)
    _publish_viewer_state(root)
    return 0.25


def _cleanup():
    global _process, _session_dir, _source_window_pointer
    global _last_live_signature, _last_live_error
    _last_live_signature = None
    _last_live_error = None
    _process = None
    _source_window_pointer = None
    if _session_dir is not None:
        shutil.rmtree(_session_dir, ignore_errors=True)
        _session_dir = None


def _stop():
    if bpy.app.timers.is_registered(_pump):
        bpy.app.timers.unregister(_pump)
    if _process is not None and _process.poll() is None:
        _process.terminate()
    _cleanup()


class ANIMREF_OT_OpenExternalManager(bpy.types.Operator):
    bl_idname = "animref.open_external_manager"
    bl_label = "資料管理ツールを開く"
    bl_description = "PySide6による独立した資料管理ウィンドウを開きます"

    @classmethod
    def poll(cls, context):
        return not bpy.app.background and context.window is not None and context.scene is not None

    def execute(self, context):
        global _process, _session_dir, _source_window_pointer
        if _process is not None and _process.poll() is None:
            self.report({'INFO'}, "AnimRef Managerは既に開いています")
            return {'FINISHED'}
        try:
            _stop()
            interpreter = _find_external_python()
            addon_dir = Path(__file__).resolve().parent.parent
            app_path = addon_dir / "qt_manager_app.py"
            if not app_path.is_file():
                raise RuntimeError("qt_manager_app.py が見つかりません")
            _session_dir = tempfile.mkdtemp(prefix="animref_qt_")
            root = Path(_session_dir)
            (root / "requests").mkdir()
            (root / "responses").mkdir()
            _source_window_pointer = context.window.as_pointer()
            cmd = interpreter + [str(app_path), "--bridge-dir", str(root)]
            with (root / "manager.log").open("w", encoding="utf-8") as log:
                _process = subprocess.Popen(
                    cmd,
                    cwd=str(addon_dir),
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            bpy.app.timers.register(_pump, first_interval=0.2)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            _stop()
            return {'CANCELLED'}
        self.report({'INFO'}, "AnimRef Managerを起動しました")
        return {'FINISHED'}


def register():
    camera_overlay_manager.register()
    bpy.utils.register_class(ANIMREF_OT_OpenExternalManager)


def unregister():
    _stop()
    bpy.utils.unregister_class(ANIMREF_OT_OpenExternalManager)
    camera_overlay_manager.unregister()
