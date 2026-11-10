import os
import bpy

from .utils import generate_uid
from .viewer_manager import find_viewer_window

SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".exr",
}


def normalize_filepath(filepath: str) -> str:
    """
    比較用にファイルパスを正規化する。
    """

    return os.path.normcase(
        os.path.abspath(
            os.path.normpath(filepath)
        )
    )


def is_supported_image(filepath: str) -> bool:
    """
    対応している画像形式か確認する。
    """

    extension = os.path.splitext(filepath)[1].lower()

    return extension in SUPPORTED_EXTENSIONS


def find_image_by_filepath(project, filepath):
    """
    同じファイルパスのImageAssetを検索する。
    """

    target_path = normalize_filepath(filepath)

    for image_asset in project.images:

        current_path = normalize_filepath(
            image_asset.filepath
        )

        if current_path == target_path:
            return image_asset

    return None


def add_image_asset(project, filepath):
    """
    画像をImage Poolへ登録する。

    Returns:
        (ImageAsset | None, status)

    status:
        "ADDED"
        "DUPLICATE"
        "NOT_FOUND"
        "UNSUPPORTED"
        "LOAD_ERROR"
    """

    filepath = os.path.abspath(filepath)

    # --------------------------------
    # ファイル存在確認
    # --------------------------------

    if not os.path.isfile(filepath):
        return None, "NOT_FOUND"

    # --------------------------------
    # 拡張子確認
    # --------------------------------

    if not is_supported_image(filepath):
        return None, "UNSUPPORTED"

    # --------------------------------
    # 重複確認
    # --------------------------------

    existing = find_image_by_filepath(
        project,
        filepath
    )

    if existing is not None:
        return existing, "DUPLICATE"

    # --------------------------------
    # Blenderへ画像ロード
    # --------------------------------

    try:

        bpy.data.images.load(
            filepath,
            check_existing=True
        )

    except RuntimeError:

        return None, "LOAD_ERROR"

    # --------------------------------
    # ImageAsset生成
    # --------------------------------

    image_asset = project.images.add()

    image_asset.uid = generate_uid("img")

    image_asset.name = os.path.basename(
        filepath
    )

    image_asset.filepath = filepath

    return image_asset, "ADDED"

def load_blender_image(image_asset):
    """
    ImageAssetからBlenderのImageを取得する。

    未ロードなら読み込む。
    """

    filepath = os.path.abspath(
        image_asset.filepath
    )

    if not os.path.isfile(filepath):

        return None, "NOT_FOUND"

    try:

        image = bpy.data.images.load(
            filepath,
            check_existing=True
        )

    except RuntimeError:

        return None, "LOAD_ERROR"

    return image, "OK"


def iter_target_image_areas():
    """
    画像を同期するImage Editorを取得する。

    専用ビュアーがある場合:
        ビュアー内だけを対象にする。

    専用ビュアーがない場合:
        Phase 1と同じく全Image Editorを対象にする。
    """

    wm = bpy.context.window_manager

    if wm is None:
        return

    viewer = find_viewer_window(wm)

    # 専用ビュアーがある場合
    if viewer is not None:

        screen = viewer.screen

        if screen is not None:
            for area in screen.areas:

                if area.type == 'IMAGE_EDITOR':
                    yield area

        # ビュアーが存在する場合は、
        # 他のウィンドウへフォールバックしない
        return

    # ビュアーがない場合は従来の方式
    for window in wm.windows:

        screen = window.screen

        if screen is None:
            continue

        for area in screen.areas:

            if area.type == 'IMAGE_EDITOR':
                yield area


def show_image_in_editors(image):
    """
    同期対象のImage Editorへ画像を表示する。

    Returns:
        更新したImage Editorの数
    """

    displayed_count = 0

    for area in iter_target_image_areas():

        space = area.spaces.active

        space.image = image

        area.tag_redraw()

        displayed_count += 1

    return displayed_count


def clear_reference_images_in_editors(project):
    """
    同期対象のImage Editorにある
    現在のプロジェクトの画像だけを解除する。

    他の画像は変更しない。
    """
    
    # ----------------------------------
    # 専用ビュアーがある場合
    # ----------------------------------

    wm = bpy.context.window_manager

    viewer = (
        find_viewer_window(wm)
        if wm is not None
        else None
    )

    if viewer is not None:

        cleared_count = 0

        for area in viewer.screen.areas:

            if area.type != 'IMAGE_EDITOR':
                continue

            space = area.spaces.active

            if space.image is not None:

                space.image = None
                area.tag_redraw()

                cleared_count += 1

        return cleared_count

    # 以下は既存のproject_pathsによる
    # 画像解除処理をそのまま残す


    project_paths = set()

    # プロジェクトに登録された画像パスを取得
    for asset in project.images:

        if not asset.filepath:
            continue

        filepath = bpy.path.abspath(
            asset.filepath
        )

        project_paths.add(
            normalize_filepath(filepath)
        )

    cleared_count = 0

    for area in iter_target_image_areas():

        space = area.spaces.active

        image = space.image

        if image is None:
            continue

        if not image.filepath:
            continue

        image_path = normalize_filepath(
            bpy.path.abspath(image.filepath)
        )

        # 現在のプロジェクトの画像だけ解除
        if image_path in project_paths:

            space.image = None

            area.tag_redraw()

            cleared_count += 1

    return cleared_count
