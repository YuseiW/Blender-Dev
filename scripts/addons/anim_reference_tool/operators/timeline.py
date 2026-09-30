import bpy

from ..timeline_manager import (
    sync_reference_display,
)


class ANIMREF_OT_SyncCurrentFrame(
    bpy.types.Operator
):

    bl_idname = "animref.sync_current_frame"
    bl_label = "現在フレームを同期"
    bl_description = (
        "現在フレームに対応する制作資料を表示します"
    )

    def execute(self, context):

        result = sync_reference_display(
            context.scene
        )

        status = result["status"]

        if status == "OK":

            image_asset = result[
                "image_asset"
            ]

            frame_start = result[
                "frame_start"
            ]

            frame_end = result[
                "frame_end"
            ]

            self.report(
                {'INFO'},
                (
                    f"{image_asset.name} "
                    f"({frame_start}-{frame_end}f)"
                )
            )

            return {'FINISHED'}

        if status == "NO_REFERENCE":

            self.report(
                {'INFO'},
                "現在フレームに対応する資料はありません"
            )

        elif status == "NO_IMAGE_EDITOR":

            self.report(
                {'WARNING'},
                "Image Editorがありません"
            )

        else:

            self.report(
                {'WARNING'},
                f"同期失敗: {status}"
            )

        return {'CANCELLED'}


classes = (
    ANIMREF_OT_SyncCurrentFrame,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)