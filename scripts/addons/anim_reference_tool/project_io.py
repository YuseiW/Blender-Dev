import json
import os

from .utils import generate_uid
from .validation import validate_project_data

PROJECT_FORMAT = "AnimationReferenceProject"
PROJECT_VERSION = 1


# ============================================================
# ReferenceItem -> dict
# ============================================================

def reference_to_dict(reference):

    return {
        "uid": reference.uid,
        "image_id": reference.image_id,
        "duration": reference.duration,
        "instruction": reference.instruction,
    }


# ============================================================
# ImageAsset -> dict
# ============================================================

def image_to_dict(image, project_directory):

    filepath = image.filepath

    # 相対パスへ変換を試みる
    if filepath:

        absolute_path = os.path.abspath(filepath)

        try:

            filepath = os.path.relpath(
                absolute_path,
                project_directory
            )

        except ValueError:
            # Windowsで別ドライブの場合など
            filepath = absolute_path

    return {
        "uid": image.uid,
        "name": image.name,
        "filepath": filepath,
    }


# ============================================================
# Cut -> dict
# ============================================================

def cut_to_dict(cut):

    return {
        "uid": cut.uid,
        "name": cut.name,
        "timeline_start": cut.timeline_start,

        "storyboard": [
            reference_to_dict(item)
            for item in cut.storyboard_items
        ],

        "layout": [
            reference_to_dict(item)
            for item in cut.layout_items
        ],

        "keyframe": [
            reference_to_dict(item)
            for item in cut.keyframe_items
        ],
    }


# ============================================================
# Project -> dict
# ============================================================

def project_to_dict(project, project_filepath):

    project_directory = os.path.dirname(
        os.path.abspath(project_filepath)
    )

    return {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,

        "project_name": project.project_name,
        "fps": project.fps,

        "images": [
            image_to_dict(
                image,
                project_directory
            )
            for image in project.images
        ],

        "cuts": [
            cut_to_dict(cut)
            for cut in project.cuts
        ],
    }


# ============================================================
# Save
# ============================================================

def save_project(project, filepath):

    filepath = os.path.abspath(filepath)

    # 保存先フォルダを取得
    project_directory = os.path.dirname(filepath)

    # フォルダが存在しなければ作成
    if project_directory:
        os.makedirs(
            project_directory,
            exist_ok=True
        )

    data = project_to_dict(
        project,
        filepath
    )

    with open(
        filepath,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4
        )

    project.project_filepath = filepath


# ============================================================
# dict -> ReferenceItem
# ============================================================

def load_reference(collection, data):

    reference = collection.add()

    reference.uid = data.get(
        "uid",
        generate_uid("ref")
    )

    reference.image_id = data.get(
        "image_id",
        ""
    )

    reference.duration = data.get(
        "duration",
        1
    )

    reference.instruction = data.get(
        "instruction",
        ""
    )

    return reference



# ==========================================
# Load Project with Rollback
# ==========================================

def load_project(project, filepath):

    filepath = os.path.abspath(filepath)

    # ----------------------------------
    # 1. JSON読み込み
    # ----------------------------------

    with open(
        filepath,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    # ----------------------------------
    # 2. データ検証
    # ----------------------------------

    project_directory = os.path.dirname(filepath)

    warnings = validate_project_data(
        data,
        project_directory,
        PROJECT_FORMAT,
        PROJECT_VERSION,
    )

    # ----------------------------------
    # 3. 変更前の状態を退避
    # ----------------------------------

    backup = _capture_project_state(project)

    previous_auto_sync = project.auto_sync

    # 中途半端な状態で同期されないよう停止
    project.auto_sync = False

    recovery_ok = True

    # ----------------------------------
    # 4. 新しいProjectを適用
    # ----------------------------------

    try:

        _apply_project_data(
            project,
            data,
            filepath,
            resolve_paths=True,
            restore_selection=False,
        )

    # ----------------------------------
    # 5. エラー時は復元する
    # ----------------------------------

    except Exception as load_error:

        print(
            "[AnimRef] Load failed:",
            load_error
        )

        try:

            _apply_project_data(
                project,
                backup,
                backup["project_filepath"],
                resolve_paths=False,
                restore_selection=True,
            )

            print(
                "[AnimRef] Previous project restored"
            )

        except Exception as rollback_error:

            recovery_ok = False

            raise RuntimeError(
                "読み込みと復元の両方に失敗しました。"
                f" 読み込みエラー: {load_error}"
                f" 復元エラー: {rollback_error}"
            ) from rollback_error

        raise

    # ----------------------------------
    # 6. 同期状態を戻す
    # ----------------------------------

    finally:

        if recovery_ok:
            project.auto_sync = previous_auto_sync
        else:
            project.auto_sync = False

    # ----------------------------------
    # 7. 警告を出力
    # ----------------------------------

    for warning in warnings:

        print(
            "[AnimRef][Warning]",
            warning
        )

    return project


# ==========================================
# Backup Current Project
# ==========================================

def _capture_project_state(project):
    """
    現在のProjectをメモリ上の辞書に退避する。
    画像パスは変換せず、そのまま保持する。
    """

    cuts = []

    for cut in project.cuts:
        cut_data = cut_to_dict(cut)

        for prop in (
            "active_storyboard_index",
            "active_layout_index",
            "active_keyframe_index",
        ):
            cut_data[prop] = getattr(cut, prop)

        cuts.append(cut_data)

    return {
        "project_name": project.project_name,
        "project_filepath": project.project_filepath,
        "fps": project.fps,
        "active_image_index": project.active_image_index,
        "active_cut_index": project.active_cut_index,
        "active_category": project.active_category,

        "images": [
            {
                "uid": img.uid,
                "name": img.name,
                "filepath": img.filepath,
            }
            for img in project.images
        ],

        "cuts": cuts,
    }


# ==========================================
# Apply Project Data
# ==========================================

def _apply_project_data(
    project,
    data,
    filepath,
    *,
    resolve_paths=True,
    restore_selection=False,
):
    """
    辞書データをBlenderのProjectに反映する。

    resolve_paths:
        True: JSONの相対パスを解決する
        False: 退避時のパスをそのまま復元する

    restore_selection:
        True: 選択位置も復元する
    """

    project.images.clear()
    project.cuts.clear()

    project.project_name = data["project_name"]
    project.fps = data["fps"]
    project.project_filepath = filepath

    # ----------------------------------
    # Images
    # ----------------------------------

    for image_data in data["images"]:

        image = project.images.add()

        image.uid = image_data["uid"]
        image.name = image_data["name"]

        path = image_data["filepath"]

        if resolve_paths and path:

            if not os.path.isabs(path):
                path = os.path.normpath(
                    os.path.join(
                        os.path.dirname(filepath),
                        path,
                    )
                )

        image.filepath = path

    # ----------------------------------
    # Cuts
    # ----------------------------------

    for cut_data in data["cuts"]:

        cut = project.cuts.add()

        cut.uid = cut_data["uid"]
        cut.name = cut_data["name"]
        cut.timeline_start = cut_data["timeline_start"]

        categories = (
            ("storyboard", cut.storyboard_items),
            ("layout", cut.layout_items),
            ("keyframe", cut.keyframe_items),
        )

        for key, collection in categories:
            for ref_data in cut_data[key]:
                load_reference(collection, ref_data)

        if restore_selection:

            for prop in (
                "active_storyboard_index",
                "active_layout_index",
                "active_keyframe_index",
            ):
                setattr(
                    cut,
                    prop,
                    cut_data[prop],
                )

    # ----------------------------------
    # Active Selection
    # ----------------------------------

    if restore_selection:

        project.active_image_index = (
            data["active_image_index"]
        )

        project.active_cut_index = (
            data["active_cut_index"]
        )

        project.active_category = (
            data["active_category"]
        )

    else:

        project.active_image_index = 0
        project.active_cut_index = 0
