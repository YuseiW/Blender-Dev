
import bpy

from ..viewer_manager import open_viewer_window


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

        if status == "OPENED":

            self.report(
                {'INFO'},
                "Reference viewer opened"
            )

            return {'FINISHED'}

        if status == "ALREADY_OPEN":

            self.report(
                {'INFO'},
                "Reference viewer already open"
            )

            return {'FINISHED'}

        self.report(
            {'ERROR'},
            f"Viewer creation failed: {status}"
        )

        return {'CANCELLED'}


classes = (
    ANIMREF_OT_OpenViewer,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
