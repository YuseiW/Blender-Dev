import bpy


# ============================================================
# Image Pool List
# ============================================================

class ANIMREF_UL_ImagePool(bpy.types.UIList):

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

        layout.label(
            text=item.name,
            icon='IMAGE_DATA'
        )


# ============================================================
# Cut List
# ============================================================

class ANIMREF_UL_CutList(bpy.types.UIList):

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

        layout.prop(
            item,
            "name",
            text="",
            emboss=False,
            icon='SEQUENCE'
        )


# ============================================================
# Main Panel
# ============================================================

class ANIMREF_PT_MainPanel(bpy.types.Panel):

    bl_label = "Animation Reference"
    bl_idname = "ANIMREF_PT_MainPanel"

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AnimRef"

    def draw(self, context):

        layout = self.layout

        project = context.scene.animref_project

        # --------------------------------
        # Project
        # --------------------------------

        layout.label(
            text="Project"
        )

        layout.prop(
            project,
            "project_name",
            text=""
        )

        layout.separator()

        # --------------------------------
        # Image Pool
        # --------------------------------

        layout.label(
            text="Image Pool"
        )

        layout.operator(
            "animref.import_images",
            text="画像をインポート",
            icon='IMPORT'
        )

        layout.template_list(
            "ANIMREF_UL_ImagePool",
            "",
            project,
            "images",
            project,
            "active_image_index",
            rows=6,
        )

        layout.label(
            text=f"画像数: {len(project.images)}"
        )

        layout.separator()

        # --------------------------------
        # Cuts
        # --------------------------------

        layout.label(
            text="Cuts"
        )

        row = layout.row()

        row.template_list(
            "ANIMREF_UL_CutList",
            "",
            project,
            "cuts",
            project,
            "active_cut_index",
            rows=5,
        )

        column = row.column(
            align=True
        )

        column.operator(
            "animref.add_cut",
            text="",
            icon='ADD'
        )

        column.operator(
            "animref.remove_cut",
            text="",
            icon='REMOVE'
        )

        # --------------------------------
        # Active Cut
        # --------------------------------

        if len(project.cuts) > 0:

            index = project.active_cut_index

            if index < len(project.cuts):

                cut = project.cuts[index]

                box = layout.box()

                box.label(
                    text=f"Selected: {cut.name}"
                )

                box.prop(
                    cut,
                    "timeline_start",
                    text="開始フレーム"
                )

                box.label(
                    text=(
                        f"絵コンテ: "
                        f"{len(cut.storyboard_items)}"
                    )
                )

                box.label(
                    text=(
                        f"レイアウト: "
                        f"{len(cut.layout_items)}"
                    )
                )

                box.label(
                    text=(
                        f"原画: "
                        f"{len(cut.keyframe_items)}"
                    )
                )


classes = (
    ANIMREF_UL_ImagePool,
    ANIMREF_UL_CutList,
    ANIMREF_PT_MainPanel,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)