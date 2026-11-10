
import bpy


# BlenderのScreenに保存する識別キー
VIEWER_SCREEN_KEY = "animref_reference_viewer"


def find_viewer_window(window_manager):
    """
    Screenに付けられた識別情報から
    専用ビュアーのWindowを探す。

    Returns:
        Window | None
    """

    if window_manager is None:
        return None

    for window in window_manager.windows:

        screen = window.screen

        if screen is None:
            continue

        if screen.get(
            VIEWER_SCREEN_KEY,
            False
        ):
            return window

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


    wm = context.window_manager


    
    existing = find_viewer_window(wm)

    if existing is not None:

        has_image_editor = any(
            area.type == 'IMAGE_EDITOR'
            for area in existing.screen.areas
        )

        if not has_image_editor:
            return "VIEWER_AREA_MISSING", existing

        # 今回ボタンを押したSceneを表示対象にする
        target_scene = context.scene

        if (
            existing.scene.as_pointer()
            != target_scene.as_pointer()
        ):

            try:
                existing.scene = target_scene

            except Exception:
                return "SCENE_BIND_FAILED", existing

            # 切替前の画像を表示し続けない
            for area in existing.screen.areas:

                if area.type == 'IMAGE_EDITOR':

                    area.spaces.active.image = None
                    area.tag_redraw()

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
   
        result = bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
    

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

    space = new_area.spaces.active

    # 画像のピン留め
    space.use_image_pin = True

    # 右側のNパネルを表示
    space.show_region_ui = True

    # 描画更新
    new_area.tag_redraw()


    # 新しいScreenを専用ビュアーとして識別
    new_window.screen[VIEWER_SCREEN_KEY] = True

    new_area.tag_redraw()

    return "OPENED", new_window




