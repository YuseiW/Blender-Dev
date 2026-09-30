import bpy

from ..utils import find_image_by_uid

from ..reference_manager import (
    get_reference_collection,
    get_active_index_property,
    CATEGORY_COLLECTIONS,
)


# ============================================================
# Reference List
# ============================================================

class ANIMREF_UL_ReferenceList(bpy.types.UIList):

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index
    ):

        project = context.scene.animref_project

        image_asset = find_image_by_uid(
            project,
            item.image_id
        )

        if image_asset is None:

            image_name = "Missing Image"
            icon_name = 'ERROR'

        else:

            image_name = image_asset.name
            icon_name = 'IMAGE_DATA'

        # -----------------------------
        # フレーム範囲を計算
        # -----------------------------

        project = context.scene.animref_project

        cut = data

        category = project.active_category

        collection = get_reference_collection(
           cut,
         category
        )

        frame_start = cut.timeline_start

        for i in range(index):
          frame_start += collection[i].duration

        frame_end = (
             frame_start
                + item.duration
                 - 1
            )

        # -----------------------------
        # 表示
        # -----------------------------

        row = layout.row()

        row.label(
            text=image_name,
            icon=icon_name
        )

        row.label(
            text=f"{frame_start}-{frame_end}f"
        )


# ============================================================
# Reference Editor Panel
# ============================================================

class ANIMREF_PT_ReferenceEditor(bpy.types.Panel):

    bl_label = "Reference Editor"
    bl_idname = "ANIMREF_PT_ReferenceEditor"

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AnimRef"

    def draw(self, context):

        layout = self.layout

        project = context.scene.animref_project

        # --------------------------------
        # Cutが存在しない場合
        # --------------------------------

        if len(project.cuts) == 0:

            layout.label(
                text="カットを作成してください",
                icon='INFO'
            )

            return

        # --------------------------------
        # Active Cut
        # --------------------------------

        if project.active_cut_index >= len(project.cuts):
            return

        cut = project.cuts[
            project.active_cut_index
        ]

        layout.label(
            text=f"Cut: {cut.name}"
        )

        # --------------------------------
        # Current Frame
        # --------------------------------

        row = layout.row()

        row.label(
            text=f"現在フレーム: {context.scene.frame_current}"
        )

        row.operator(
            "animref.sync_current_frame",
            text="同期",
            icon='FILE_REFRESH'
        )

        layout.separator()

        # --------------------------------
        # Category
        # --------------------------------

        layout.prop(
            project,
            "active_category",
            expand=True
        )

        category = project.active_category

        collection_name = CATEGORY_COLLECTIONS[
            category
        ]

        active_property = get_active_index_property(
            category
        )

        collection = get_reference_collection(
            cut,
            category
        )

        # --------------------------------
        # Reference List
        # --------------------------------

        row = layout.row()

        row.template_list(
            "ANIMREF_UL_ReferenceList",
            "",
            cut,
            collection_name,
            cut,
            active_property,
            rows=6,
        )

        buttons = row.column(
            align=True
        )

        buttons.operator(
            "animref.add_reference",
            text="",
            icon='ADD'
        )

        buttons.operator(
            "animref.remove_reference",
            text="",
            icon='REMOVE'
        )

        buttons.separator()

        op = buttons.operator(
            "animref.move_reference",
            text="",
            icon='TRIA_UP'
        )

        op.direction = 'UP'

        op = buttons.operator(
            "animref.move_reference",
            text="",
            icon='TRIA_DOWN'
        )

        op.direction = 'DOWN'

        # --------------------------------
        # Selected Reference
        # --------------------------------

        if len(collection) == 0:

            layout.label(
                text="資料が登録されていません"
            )

            return

        index = getattr(
            cut,
            active_property
        )

        if index >= len(collection):
            return

        reference = collection[index]

        image_asset = find_image_by_uid(
            project,
            reference.image_id
        )

        box = layout.box()

        if image_asset is not None:

            box.label(
                text=image_asset.name,
                icon='IMAGE_DATA'
            )

        else:

            box.label(
                text="画像が見つかりません",
                icon='ERROR'
            )

        box.prop(
            reference,
            "duration",
            text="表示フレーム数"
        )

        box.prop(
            reference,
            "instruction",
            text="指示"
        )


# ============================================================
# Registration
# ============================================================

classes = (
    ANIMREF_UL_ReferenceList,
    ANIMREF_PT_ReferenceEditor,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)