
import bpy


# 実行中のBlenderセッションでのみ保持する
_viewer_window_pointer = None


def find_viewer_window(window_manager):
    """
    以前作成したビュアーが
    まだ存在するか確認する。
    """

    global _viewer_window_pointer

    if _viewer_window_pointer is None:
        return None

    for window in window_manager.windows:

        if (
            window.as_pointer()
            == _viewer_window_pointer
        ):
            return window

    # 閉じられていた場合は参照を破棄
    _viewer_window_pointer = None

    return None


def open_viewer_window(context):
    """
    Blenderの別ウィンドウを生成し、
    Image Editorとして使用する。

    Returns:
        (status, window)

    status:
        OPENED
        ALREADY_OPEN
        INVALID_CONTEXT
        CREATE_FAILED
        AREA_NOT_FOUND
    """

    global _viewer_window_pointer

    wm = context.window_manager

    # 既に開いている場合
    existing = find_viewer_window(wm)

    if existing is not None:
        return "ALREADY_OPEN", existing

    source_window = context.window
    source_area = context.area

    if (
        source_window is None
        or source_area is None
        or source_area.type != 'VIEW_3D'
    ):
        return "INVALID_CONTEXT", None

    # 作成前のWindow一覧を記録
    before = {
        window.as_pointer()
        for window in wm.windows
    }

    # 3D Viewの描画領域を取得
    region = next(
        (
            r for r in source_area.regions
            if r.type == 'WINDOW'
        ),
        None
    )

    if region is None:
        return "INVALID_CONTEXT", None

    # 現在の3D Viewを別ウィンドウに複製
    with context.temp_override(
        window=source_window,
        area=source_area,
        region=region,
    ):
        result = bpy.ops.screen.area_dupli()

    if 'FINISHED' not in result:
        return "CREATE_FAILED", None

    # 新しく増えたWindowを特定
    created = [
        window
        for window in wm.windows
        if window.as_pointer() not in before
    ]

    if len(created) != 1:
        return "CREATE_FAILED", None

    new_window = created[0]

    # 複製された3D Viewを取得
    new_area = next(
        (
            area
            for area in new_window.screen.areas
            if area.type == 'VIEW_3D'
        ),
        None
    )

    if new_area is None:
        return "AREA_NOT_FOUND", new_window

    # Image Editorへ変更
    new_area.type = 'IMAGE_EDITOR'

    # ビュアーの識別用に記録
    _viewer_window_pointer = (
        new_window.as_pointer()
    )

    return "OPENED", new_window
