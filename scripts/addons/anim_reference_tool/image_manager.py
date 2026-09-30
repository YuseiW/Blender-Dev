import os
import bpy

from .utils import generate_uid


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


def show_image_in_editors(image):
    """
    現在開いているすべてのWindowを調べ、
    Image Editorに画像を表示する。

    Returns:
        表示できたImage Editorの数
    """

    displayed_count = 0

    window_manager = bpy.context.window_manager

    if window_manager is None:
        return 0

    for window in window_manager.windows:

        screen = window.screen

        if screen is None:
            continue

        for area in screen.areas:

            if area.type != 'IMAGE_EDITOR':
                continue

            area.spaces.active.image = image

            displayed_count += 1

    return displayed_count