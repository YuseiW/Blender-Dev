
import bpy

from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ..project_io import save_project, load_project


# ==========================================
# Save Project
# ==========================================

class ANIMREF_OT_SaveProject(
    bpy.types.Operator,
    ExportHelper
):
    bl_idname = "animref.save_project"
    bl_label = "プロジェクトを保存"
    bl_description = "現在の資料構成をJSON形式で保存する"

    filename_ext = ".json"

    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'},
    )

    def invoke(self, context, event):
        project = context.scene.animref_project

        if project.project_filepath:
            self.filepath = project.project_filepath
        else:
            name = bpy.path.clean_name(project.project_name)
            self.filepath = name + ".json"

        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        project = context.scene.animref_project

        try:
            save_project(project, self.filepath)

        except Exception as error:
            self.report(
                {'ERROR'},
                f"保存失敗: {error}"
            )
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            "プロジェクトを保存しました"
        )

        return {'FINISHED'}


# ==========================================
# Load Project
# ==========================================

class ANIMREF_OT_LoadProject(
    bpy.types.Operator,
    ImportHelper
):
    bl_idname = "animref.load_project"
    bl_label = "プロジェクトを読み込み"
    bl_description = "保存済みプロジェクトを読み込む"

    filename_ext = ".json"

    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'},
    )

    def execute(self, context):
        project = context.scene.animref_project

        try:
            load_project(project, self.filepath)

            project.active_cut_index = 0
            project.active_image_index = 0

        except Exception as error:
            self.report(
                {'ERROR'},
                f"読み込み失敗: {error}"
            )
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            "プロジェクトを読み込みました"
        )

        return {'FINISHED'}


# ==========================================
# Registration
# ==========================================

classes = (
    ANIMREF_OT_SaveProject,
    ANIMREF_OT_LoadProject,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
