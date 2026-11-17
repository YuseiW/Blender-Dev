"""UI-1: open AnimRef Manager as a separate native Blender main window.

This operator deliberately keeps the legacy bl_idname so existing UI buttons
and keymaps remain compatible.  No workspace is duplicated or activated in
the caller's window.  A Screen ID property identifies the manager window.
"""

import bpy

MANAGER_SCREEN_KEY = "animref_manager_window"


def find_manager_window(window_manager):
    """Return an open manager window, or None (also after it was closed)."""
    if window_manager is None:
        return None
    for window in window_manager.windows:
        screen = window.screen
        if screen is not None and bool(screen.get(MANAGER_SCREEN_KEY, False)):
            return window
    return None


def _find_manager_areas(screen):
    """Find a large left VIEW_3D and a right-hand PROPERTIES area."""
    if screen is None:
        return None, None

    views = [area for area in screen.areas if area.type == 'VIEW_3D']
    if not views:
        return None, None
    left = max(views, key=lambda area: area.width * area.height)

    right_candidates = [
        area for area in screen.areas
        if area.type == 'PROPERTIES'
        and area.x >= left.x + left.width - 4
    ]
    if not right_candidates:
        return None, None
    right = max(right_candidates, key=lambda area: area.width * area.height)
    return left, right


class ANIMREF_OT_OpenManagerWorkspace(bpy.types.Operator):
    # Keep the original identifier to avoid changing existing button wiring.
    bl_idname = "animref.open_manager_workspace"
    bl_label = "AnimRef Manager（別ウィンドウ）"
    bl_description = "資料登録画面を別のBlenderウィンドウで開きます"

    @classmethod
    def poll(cls, context):
        return not bpy.app.background and context.window is not None

    def execute(self, context):
        wm = context.window_manager
        source_window = context.window
        source_screen = source_window.screen
        source_scene = context.scene

        existing = find_manager_window(wm)
        if existing is not None:
            self.report(
                {'INFO'},
                "AnimRef Managerは既に開いています。別ウィンドウを確認してください",
            )
            return {'FINISHED'}

        # Avoid leaving an empty new window on unsupported layouts.
        source_left, source_right = _find_manager_areas(source_screen)
        if source_left is None or source_right is None:
            self.report(
                {'ERROR'},
                "Layoutから実行してください（3D Viewと右側Propertiesが必要）",
            )
            return {'CANCELLED'}

        before = {w.as_pointer() for w in wm.windows}
        try:
            # A NEW top-level OS window, not bpy.ops.workspace.duplicate().
            # This retains a multi-editor screen that can show two columns.
            result = bpy.ops.wm.window_new_main()
        except Exception as error:
            self.report({'ERROR'}, f"新規ウィンドウ作成に失敗: {error}")
            return {'CANCELLED'}

        new_windows = [
            w for w in wm.windows if w.as_pointer() not in before
        ]
        if 'FINISHED' not in result or len(new_windows) != 1:
            self.report({'ERROR'}, "新しいウィンドウを特定できません")
            return {'CANCELLED'}

        new_window = new_windows[0]
        new_screen = new_window.screen

        # Prevent the caller's layout from ever being modified accidentally.
        if new_screen.as_pointer() == source_screen.as_pointer():
            self.report(
                {'ERROR'},
                "新規ウィンドウのScreenが共有されています。画面は変更しません",
            )
            return {'CANCELLED'}

        left, right = _find_manager_areas(new_screen)
        if left is None or right is None:
            self.report(
                {'ERROR'},
                "新規ウィンドウに管理画面用の領域がありません。ウィンドウを閉じてLayoutから再実行してください",
            )
            return {'CANCELLED'}

        try:
            # Set both editors only inside the NEW window.
            left.type = 'PROPERTIES'
            left.spaces.active.context = 'SCENE'
            right.spaces.active.context = 'RENDER'

            new_window.scene = source_scene
            # Mark only after successful setup.
            new_screen[MANAGER_SCREEN_KEY] = True
            left.tag_redraw()
            right.tag_redraw()
        except Exception as error:
            self.report({'ERROR'}, f"管理ウィンドウの初期化に失敗: {error}")
            return {'CANCELLED'}

        self.report({'INFO'}, "別ウィンドウを開きました：左＝資料登録 / 右＝画像プール")
        return {'FINISHED'}


classes = (ANIMREF_OT_OpenManagerWorkspace,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
