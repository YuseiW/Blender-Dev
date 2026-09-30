import bpy

from bpy.app.handlers import persistent

from .reference_manager import get_reference_collection
from .utils import find_image_by_uid

from .image_manager import (
    load_blender_image,
    show_image_in_editors,
)

def calculate_reference_ranges(
    collection,
    start_frame=1
):
    """
    ReferenceItemのdurationから、
    各ReferenceItemの開始・終了フレームを計算する。

    例:
        A = 8f
        B = 12f
        C = 6f

    start_frame=1 の場合:

        A = 1～8
        B = 9～20
        C = 21～26
    """

    current_frame = start_frame

    result = []

    for reference in collection:

        frame_start = current_frame

        frame_end = (
            frame_start
            + reference.duration
            - 1
        )

        result.append({
            "reference": reference,
            "start": frame_start,
            "end": frame_end,
        })

        current_frame = frame_end + 1

    return result


def find_reference_at_frame(
    collection,
    frame,
    start_frame=1
):
    """
    指定フレームに対応するReferenceItemを探す。

    Returns:
        (reference, frame_start, frame_end)

    見つからない場合:
        (None, None, None)
    """

    current_frame = start_frame

    for reference in collection:

        frame_start = current_frame

        frame_end = (
            frame_start
            + reference.duration
            - 1
        )

        if frame_start <= frame <= frame_end:

            return (
                reference,
                frame_start,
                frame_end,
            )

        current_frame = frame_end + 1

    return None, None, None


def resolve_reference_at_frame(
    project,
    cut,
    category,
    frame
):
    """
    指定Cut・Category・Frameから、

    ReferenceItem
    ImageAsset
    開始フレーム
    終了フレーム

    を解決する。
    """

    collection = get_reference_collection(
        cut,
        category
    )

    reference, frame_start, frame_end = (
        find_reference_at_frame(
            collection,
            frame,
            cut.timeline_start
        )
    )

    if reference is None:

        return (
            None,
            None,
            None,
            None,
        )

    image_asset = find_image_by_uid(
        project,
        reference.image_id
    )

    return (
        reference,
        image_asset,
        frame_start,
        frame_end,
    )

def sync_reference_display(scene):
    """
    Sceneの現在フレームに対応する資料を検索し、
    Image Editorへ表示する。

    Returns:
        {
            "status": str,
            "reference": ReferenceItem | None,
            "image_asset": ImageAsset | None,
            "frame_start": int | None,
            "frame_end": int | None,
        }
    """

    project = scene.animref_project

    # --------------------------------
    # Cut確認
    # --------------------------------

    if len(project.cuts) == 0:

        return {
            "status": "NO_CUT",
            "reference": None,
            "image_asset": None,
            "frame_start": None,
            "frame_end": None,
        }

    if project.active_cut_index >= len(project.cuts):

        return {
            "status": "INVALID_CUT",
            "reference": None,
            "image_asset": None,
            "frame_start": None,
            "frame_end": None,
        }

    cut = project.cuts[
        project.active_cut_index
    ]

    # --------------------------------
    # 現在フレームから資料検索
    # --------------------------------

    (
        reference,
        image_asset,
        frame_start,
        frame_end,
    ) = resolve_reference_at_frame(
        project,
        cut,
        project.active_category,
        scene.frame_current,
    )

    if reference is None:

        return {
            "status": "NO_REFERENCE",
            "reference": None,
            "image_asset": None,
            "frame_start": None,
            "frame_end": None,
        }

    if image_asset is None:

        return {
            "status": "MISSING_IMAGE_ASSET",
            "reference": reference,
            "image_asset": None,
            "frame_start": frame_start,
            "frame_end": frame_end,
        }

    # --------------------------------
    # Blender Image取得
    # --------------------------------

    image, status = load_blender_image(
        image_asset
    )

    if status != "OK":

        return {
            "status": status,
            "reference": reference,
            "image_asset": image_asset,
            "frame_start": frame_start,
            "frame_end": frame_end,
        }

    # --------------------------------
    # Image Editorへ表示
    # --------------------------------

    displayed_count = show_image_in_editors(
        image
    )

    if displayed_count == 0:

        return {
            "status": "NO_IMAGE_EDITOR",
            "reference": reference,
            "image_asset": image_asset,
            "frame_start": frame_start,
            "frame_end": frame_end,
        }

    return {
        "status": "OK",
        "reference": reference,
        "image_asset": image_asset,
        "frame_start": frame_start,
        "frame_end": frame_end,
    }


# ============================================================
# Timeline Handler
# ============================================================

@persistent
def on_frame_change(scene, depsgraph=None):
    """
    Blenderの現在フレームが変更されたときに実行する。
    """

    # animref_projectが存在しないSceneでは何もしない
    if not hasattr(scene, "animref_project"):
        return

    project = scene.animref_project

    # 自動同期がOFFなら何もしない
    if not project.auto_sync:
        return

    try:

        sync_reference_display(
            scene
        )

    except Exception as error:

        print(
            "[AnimRef] Timeline sync error:",
            error
        )


# ============================================================
# Handler Registration
# ============================================================

def register_handlers():
    """
    Timeline変更Handlerを登録する。
    """

    handlers = bpy.app.handlers.frame_change_post

    if on_frame_change not in handlers:

        handlers.append(
            on_frame_change
        )


def unregister_handlers():
    """
    Timeline変更Handlerを解除する。
    """

    handlers = bpy.app.handlers.frame_change_post

    if on_frame_change in handlers:

        handlers.remove(
            on_frame_change
        )