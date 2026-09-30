import json
import os

from .utils import generate_uid


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


# ============================================================
# Load Project
# ============================================================

def load_project(project, filepath):

    filepath = os.path.abspath(filepath)

    with open(
        filepath,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    # ----------------------------------------
    # ファイル形式確認
    # ----------------------------------------

    if data.get("format") != PROJECT_FORMAT:

        raise ValueError(
            "Animation Reference Projectではありません"
        )

    project_directory = os.path.dirname(filepath)

    # ----------------------------------------
    # 古いデータを削除
    # ----------------------------------------

    project.images.clear()
    project.cuts.clear()

    # ----------------------------------------
    # Project
    # ----------------------------------------

    project.project_name = data.get(
        "project_name",
        "Untitled Project"
    )

    project.fps = data.get(
        "fps",
        24
    )

    project.project_filepath = filepath

    # ----------------------------------------
    # Images
    # ----------------------------------------

    for image_data in data.get(
        "images",
        []
    ):

        image = project.images.add()

        image.uid = image_data.get(
            "uid",
            generate_uid("img")
        )

        image.name = image_data.get(
            "name",
            "Unnamed Image"
        )

        stored_path = image_data.get(
            "filepath",
            ""
        )

        if stored_path:

            if os.path.isabs(stored_path):
                image.filepath = stored_path

            else:
                image.filepath = os.path.normpath(
                    os.path.join(
                        project_directory,
                        stored_path
                    )
                )

    # ----------------------------------------
    # Cuts
    # ----------------------------------------

    for cut_data in data.get(
        "cuts",
        []
    ):

        cut = project.cuts.add()

        cut.uid = cut_data.get(
            "uid",
            generate_uid("cut")
        )

        cut.name = cut_data.get(
            "name",
            "Cut"
        )

        cut.timeline_start = cut_data.get(
            "timeline_start",
            1
        )

        # 絵コンテ
        for reference_data in cut_data.get(
            "storyboard",
            []
        ):

            load_reference(
                cut.storyboard_items,
                reference_data
            )

        # レイアウト
        for reference_data in cut_data.get(
            "layout",
            []
        ):

            load_reference(
                cut.layout_items,
                reference_data
            )

        # 原画
        for reference_data in cut_data.get(
            "keyframe",
            []
        ):

            load_reference(
                cut.keyframe_items,
                reference_data
            )

    return project