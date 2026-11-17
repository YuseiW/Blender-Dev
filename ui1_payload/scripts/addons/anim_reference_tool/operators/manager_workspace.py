"""UI-1: create/activate the native Blender AnimRef Manager workspace.

Only a duplicated workspace is modified. Original Layout or Animation
workspaces are not modified. The standard Layout arrangement, containing
a 3D View and a Properties editor on its right, is required to create it.
"""

import bpy

MANAGER_WORKSPACE_NAME = "AnimRef Manager"


def _find_manager_areas(screen):
    """Return a large 3D View and the right-side Properties editor."""
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

    right = max(
        right_candidates, key=lambda area: area.width * area.height
    )
    return left, right


class ANIMREF_OT_OpenManagerWorkspace(bpy.types.Operator):
    bl_idname = "animref.open_manager_workspace"
    bl_label = "AnimRef Managerを開く"
    bl_description = "専用管理ワークスペースを作成または再表示します"

    @classmethod
    def poll(cls, context):
        return not bpy.app.background and context.window is not None

    def execute(self, context):
        window = context.window
        existing = bpy.data.workspaces.get(MANAGER_WORKSPACE_NAME)

        if existing is not None:
            window.workspace = existing
            self.report({'INFO'}, "AnimRef Managerを開きました")
            return {'FINISHED'}

        # Check *before* duplication so a failed setup leaves no extra space.
        left, right = _find_manager_areas(window.screen)
        if left is None or right is None:
            self.report(
                {'ERROR'},
                "Layoutワークスペースから実行してください（3D Viewと右側Propertiesが必要）",
            )
            return {'CANCELLED'}

        original_workspace = window.workspace
        before = {w.as_pointer() for w in bpy.data.workspaces}

        try:
            result = bpy.ops.workspace.duplicate()
        except Exception as error:
            self.report({'ERROR'}, f"Workspace複製失敗: {error}")
            return {'CANCELLED'}

        new_workspaces = [
            w for w in bpy.data.workspaces
            if w.as_pointer() not in before
        ]
        if 'FINISHED' not in result or len(new_workspaces) != 1:
            self.report({'ERROR'}, "Workspaceが一つだけ複製されたことを確認できません")
            return {'CANCELLED'}

        manager_workspace = new_workspaces[0]

        try:
            window.workspace = manager_workspace
            left, right = _find_manager_areas(window.screen)
            if left is None or right is None:
                raise RuntimeError("複製後の編集領域を識別できません")

            # Left: registration editor; Right: image pool.
            left.type = 'PROPERTIES'
            left.spaces.active.context = 'SCENE'
            right.spaces.active.context = 'RENDER'
            right.spaces.active.outliner_sync = 'NEVER'

            manager_workspace.name = MANAGER_WORKSPACE_NAME
            left.tag_redraw()
            right.tag_redraw()
        except Exception as error:
            window.workspace = original_workspace
            self.report(
                {'ERROR'},
                f"管理画面の設定に失敗: {error}（複製Workspaceは手動で削除可能）",
            )
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            "AnimRef Managerを作成しました。左: Scene / 右: Render",
        )
        return {'FINISHED'}


classes = (ANIMREF_OT_OpenManagerWorkspace,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
