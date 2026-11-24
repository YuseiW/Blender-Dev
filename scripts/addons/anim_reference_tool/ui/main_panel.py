"""3D View N-panel: only the entry point to the external AnimRef application.

All editing and display controls live in PySide6 Viewer / Manager.
The old Blender Image Editor Viewer remains registered separately until V-5.
"""
import bpy

# UI_V3_2_LAUNCHER_ONLY
class ANIMREF_PT_MainPanel(bpy.types.Panel):
    bl_label = "AnimRef"
    bl_idname = "ANIMREF_PT_MainPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AnimRef"

    def draw(self, context):
        self.layout.operator(
            "animref.open_external_manager",
            text="AnimRefを開く",
            icon='IMAGE_DATA',
        )


classes = (ANIMREF_PT_MainPanel,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
