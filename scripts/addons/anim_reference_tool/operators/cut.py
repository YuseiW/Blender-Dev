import bpy

from ..cut_manager import (
    add_cut,
    remove_cut,
)


# ============================================================
# Add Cut
# ============================================================

class ANIMREF_OT_AddCut(bpy.types.Operator):

    bl_idname = "animref.add_cut"
    bl_label = "カットを追加"
    bl_description = "新しいカットを追加します"

    def execute(self, context):

        project = context.scene.animref_project

        cut = add_cut(project)

        self.report(
            {'INFO'},
            f"{cut.name} を追加しました"
        )

        return {'FINISHED'}


# ============================================================
# Remove Cut
# ============================================================

class ANIMREF_OT_RemoveCut(bpy.types.Operator):

    bl_idname = "animref.remove_cut"
    bl_label = "カットを削除"
    bl_description = "選択中のカットを削除します"

    def execute(self, context):

        project = context.scene.animref_project

        if len(project.cuts) == 0:

            self.report(
                {'WARNING'},
                "削除するカットがありません"
            )

            return {'CANCELLED'}

        index = project.active_cut_index

        cut_name = project.cuts[index].name

        success = remove_cut(
            project,
            index
        )

        if not success:

            self.report(
                {'WARNING'},
                "カットを削除できませんでした"
            )

            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"{cut_name} を削除しました"
        )

        return {'FINISHED'}


classes = (
    ANIMREF_OT_AddCut,
    ANIMREF_OT_RemoveCut,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)