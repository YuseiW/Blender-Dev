bl_info = {
    "name": "Animation Reference Tool",
    "author": "Yusei Watanabe",
    "version": (0, 1, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar",
    "description": "Animation reference image management tool",
    "category": "Animation",
}


import bpy


class ANIMREF_PT_main_panel(bpy.types.Panel):

    bl_label = "Animation Reference"
    bl_idname = "ANIMREF_PT_main_panel"

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AnimRef"

    def draw(self, context):

        layout = self.layout

        layout.label(
            text="テスト"
        )


classes = (
    ANIMREF_PT_main_panel,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)