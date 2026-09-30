import bpy

from bpy.props import EnumProperty

from ..reference_manager import (
    add_reference,
    remove_reference,
    move_reference,
    get_reference_collection,
    get_active_index_property,
)


# ============================================================
# Add Reference
# ============================================================

class ANIMREF_OT_AddReference(
    bpy.types.Operator
):

    bl_idname = "animref.add_reference"
    bl_label = "資料を登録"
    bl_description = (
        "画像プールで選択中の画像を"
        "現在の資料として登録します"
    )

    def execute(self, context):

        project = context.scene.animref_project

        # -------------------------------
        # Cut確認
        # -------------------------------

        if len(project.cuts) == 0:

            self.report(
                {'WARNING'},
                "カットがありません"
            )

            return {'CANCELLED'}

        # -------------------------------
        # Image確認
        # -------------------------------

        if len(project.images) == 0:

            self.report(
                {'WARNING'},
                "画像がありません"
            )

            return {'CANCELLED'}

        cut_index = project.active_cut_index

        image_index = project.active_image_index

        if cut_index >= len(project.cuts):
            return {'CANCELLED'}

        if image_index >= len(project.images):
            return {'CANCELLED'}

        cut = project.cuts[
            cut_index
        ]

        image_asset = project.images[
            image_index
        ]

        category = project.active_category

        reference, status = add_reference(
            cut,
            category,
            image_asset.uid
        )

        if status == "DUPLICATE":

            self.report(
                {'WARNING'},
                "この画像は既に登録されています"
            )

            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"{image_asset.name} を登録しました"
        )

        return {'FINISHED'}


# ============================================================
# Remove Reference
# ============================================================

class ANIMREF_OT_RemoveReference(
    bpy.types.Operator
):

    bl_idname = "animref.remove_reference"
    bl_label = "資料を削除"

    def execute(self, context):

        project = context.scene.animref_project

        if len(project.cuts) == 0:
            return {'CANCELLED'}

        cut = project.cuts[
            project.active_cut_index
        ]

        category = project.active_category

        collection = get_reference_collection(
            cut,
            category
        )

        if len(collection) == 0:

            self.report(
                {'WARNING'},
                "削除する資料がありません"
            )

            return {'CANCELLED'}

        active_property = (
            get_active_index_property(
                category
            )
        )

        index = getattr(
            cut,
            active_property
        )

        success = remove_reference(
            cut,
            category,
            index
        )

        if not success:
            return {'CANCELLED'}

        return {'FINISHED'}


# ============================================================
# Move Reference
# ============================================================

class ANIMREF_OT_MoveReference(
    bpy.types.Operator
):

    bl_idname = "animref.move_reference"
    bl_label = "資料を並べ替え"

    direction: EnumProperty(
        items=[
            ('UP', "上", ""),
            ('DOWN', "下", ""),
        ]
    )

    def execute(self, context):

        project = context.scene.animref_project

        if len(project.cuts) == 0:
            return {'CANCELLED'}

        cut = project.cuts[
            project.active_cut_index
        ]

        category = project.active_category

        active_property = (
            get_active_index_property(
                category
            )
        )

        index = getattr(
            cut,
            active_property
        )

        direction_value = (
            -1
            if self.direction == 'UP'
            else 1
        )

        success = move_reference(
            cut,
            category,
            index,
            direction_value
        )

        if not success:
            return {'CANCELLED'}

        return {'FINISHED'}


classes = (
    ANIMREF_OT_AddReference,
    ANIMREF_OT_RemoveReference,
    ANIMREF_OT_MoveReference,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)