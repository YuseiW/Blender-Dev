
import bpy

from ..viewer_manager import open_viewer_window

from ..timeline_manager import (
    sync_reference_display,
)


class ANIMREF_OT_OpenViewer(bpy.types.Operator):

    bl_idname = "animref.open_viewer"
    bl_label = "リファレンスビュアーを開く"
    bl_description = (
        "制作資料用の別ウィンドウを開きます"
    )

    @classmethod
    def poll(cls, context):
        return (
            not bpy.app.background
            and context.window is not None
            and context.area is not None
            and context.area.type == 'VIEW_3D'
        )

    def execute(self, context):

        try:
            status, window = open_viewer_window(
                context
            )

        except Exception as error:

            self.report(
                {'ERROR'},
                f"Viewer error: {error}"
            )

            return {'CANCELLED'}

        if status not in {
            "OPENED",
            "ALREADY_OPEN",
        }:

            self.report(
                {'ERROR'},
                f"Viewer creation failed: {status}"
            )

            return {'CANCELLED'}

        # 開いた直後に現在フレームを同期
        try:

            sync_result = sync_reference_display(
                context.scene
            )

        except Exception as error:

            self.report(
                {'WARNING'},
                f"Viewer sync error: {error}"
            )

            return {'FINISHED'}

        sync_status = sync_result["status"]

        # 同期の結果を確認
        if sync_status not in {
            "OK",
            "NO_REFERENCE",
            "NO_CUT",
        }:

            self.report(
                {'WARNING'},
                f"Viewer sync status: {sync_status}"
            )

        else:

            self.report(
                {'INFO'},
                "Reference viewer ready"
            )

        return {'FINISHED'}


classes = (
    ANIMREF_OT_OpenViewer,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
