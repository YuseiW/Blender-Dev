"""UI-1: AnimRef Manager workspace panels.

The left panel is shown under Scene properties; the right panel under
Render properties. Both panels are visible only in the AnimRef Manager
workspace. Image thumbnails and drag-and-drop belong to later phases.
"""

import bpy

from ..reference_manager import (
    CATEGORY_COLLECTIONS,
    get_active_index_property,
    get_reference_collection,
)
from ..utils import find_image_by_uid

MANAGER_WORKSPACE_NAME = "AnimRef Manager"


def _is_manager_workspace(context):
    window = getattr(context, "window", None)
    return bool(
        window is not None
        and window.workspace is not None
        and window.workspace.name == MANAGER_WORKSPACE_NAME
        and getattr(context, "scene", None) is not None
        and hasattr(context.scene, "animref_project")
    )


class ANIMREF_PT_ManagerRegistration(bpy.types.Panel):
    """Left: registration order, category, duration and instructions."""

    bl_idname = "ANIMREF_PT_ManagerRegistration"
    bl_label = "AnimRef | 資料登録"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return _is_manager_workspace(context)

    def draw(self, context):
        layout = self.layout
        project = context.scene.animref_project

        layout.label(text="プロジェクト", icon='FILE_BLEND')
        layout.prop(project, "project_name", text="名前")
        row = layout.row(align=True)
        row.operator("animref.save_project", text="保存", icon='EXPORT')
        row.operator("animref.load_project", text="読み込み", icon='IMPORT')

        layout.separator()
        layout.label(text="カット管理", icon='SEQUENCE')
        row = layout.row()
        row.template_list(
            "ANIMREF_UL_CutList", "UI1Cuts", project, "cuts",
            project, "active_cut_index", rows=4,
        )
        buttons = row.column(align=True)
        buttons.operator("animref.add_cut", text="", icon='ADD')
        buttons.operator("animref.remove_cut", text="", icon='REMOVE')

        if not project.cuts:
            layout.label(text="先にカットを作成してください", icon='INFO')
            return

        cut_index = project.active_cut_index
        if not 0 <= cut_index < len(project.cuts):
            layout.label(text="カット選択が不正です", icon='ERROR')
            return

        cut = project.cuts[cut_index]
        box = layout.box()
        box.label(text=f"選択中: {cut.name}")
        box.prop(cut, "timeline_start", text="開始フレーム")

        layout.separator()
        layout.label(text="登録する資料カテゴリ")
        layout.prop(project, "active_category", text="", expand=True)

        category = project.active_category
        collection_name = CATEGORY_COLLECTIONS[category]
        index_property = get_active_index_property(category)
        collection = get_reference_collection(cut, category)

        layout.label(text="登録順 / 表示フレーム範囲")
        row = layout.row()
        row.template_list(
            "ANIMREF_UL_ReferenceList", "UI1References",
            cut, collection_name, cut, index_property, rows=9,
        )
        buttons = row.column(align=True)
        buttons.operator("animref.add_reference", text="", icon='ADD')
        buttons.operator("animref.remove_reference", text="", icon='REMOVE')
        buttons.separator()
        op = buttons.operator("animref.move_reference", text="", icon='TRIA_UP')
        op.direction = 'UP'
        op = buttons.operator("animref.move_reference", text="", icon='TRIA_DOWN')
        op.direction = 'DOWN'

        if not collection:
            layout.label(text="右の画像プールから選んで + で登録", icon='INFO')
            return

        selected_index = getattr(cut, index_property)
        if not 0 <= selected_index < len(collection):
            return

        reference = collection[selected_index]
        asset = find_image_by_uid(project, reference.image_id)
        box = layout.box()
        box.label(text="選択中の資料", icon='IMAGE_DATA')
        box.label(text=asset.name if asset is not None else "画像が見つかりません")
        box.prop(reference, "duration", text="表示フレーム数")
        box.prop(reference, "instruction", text="作画・演出指示")
        box.label(text="※ サムネイル・D&Dは次の工程で追加", icon='INFO')


class ANIMREF_PT_ManagerImagePool(bpy.types.Panel):
    """Right: project image pool. List view is the UI-1 placeholder."""

    bl_idname = "ANIMREF_PT_ManagerImagePool"
    bl_label = "AnimRef | 画像プール"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'render'
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return _is_manager_workspace(context)

    def draw(self, context):
        layout = self.layout
        project = context.scene.animref_project

        layout.operator(
            "animref.import_images", text="画像をインポート", icon='IMPORT'
        )
        layout.label(text=f"登録済み: {len(project.images)} 枚")
        layout.template_list(
            "ANIMREF_UL_ImagePool", "UI1ImagePool",
            project, "images", project, "active_image_index", rows=12,
        )

        if not project.images:
            layout.label(text="画像を追加してください", icon='INFO')
            return

        image_index = project.active_image_index
        if not 0 <= image_index < len(project.images):
            return

        asset = project.images[image_index]
        box = layout.box()
        box.label(text="選択画像", icon='IMAGE_DATA')
        box.label(text=asset.name)
        # Read-only in this phase to avoid accidentally breaking an asset path.
        box.label(text="画像プール内の画像を選択してください")

        if project.cuts:
            layout.operator(
                "animref.add_reference", text="左の登録順へ追加", icon='ADD'
            )
        else:
            layout.label(text="登録するには先にカットを作成", icon='INFO')

        layout.label(text="※ 2列サムネイルはUI-2で実装", icon='INFO')


classes = (
    ANIMREF_PT_ManagerRegistration,
    ANIMREF_PT_ManagerImagePool,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
