import bpy

from bpy.props import (
    StringProperty,
    IntProperty,
    BoolProperty,
    CollectionProperty,
    PointerProperty,
    EnumProperty,
)


# ============================================================
# Image Asset
# 画像プールに存在する「画像そのもの」
# ============================================================

class ANIMREF_PG_ImageAsset(bpy.types.PropertyGroup):

    uid: StringProperty(
        name="ID",
        description="画像を識別する一意のID",
    )

    name: StringProperty(
        name="Name",
        description="画像の表示名",
    )

    filepath: StringProperty(
        name="File Path",
        description="画像ファイルへのパス",
        subtype='FILE_PATH',
    )


# ============================================================
# Reference Item
# カットのタイムライン上に配置された資料
# ============================================================

class ANIMREF_PG_ReferenceItem(bpy.types.PropertyGroup):

    uid: StringProperty(
        name="ID",
        description="登録項目を識別する一意のID",
    )

    image_id: StringProperty(
        name="Image ID",
        description="ImageAssetのID",
    )

    duration: IntProperty(
        name="Duration",
        description="この画像を表示するフレーム数",
        default=1,
        min=1,
    )

    instruction: StringProperty(
        name="Instruction",
        description="作画・演出などの指示",
        default="",
    )


# ============================================================
# Cut
# 1つのカット
# ============================================================

class ANIMREF_PG_Cut(bpy.types.PropertyGroup):

    uid: StringProperty(
        name="ID",
        description="カットを識別する一意のID",
    )

    name: StringProperty(
        name="Cut Name",
        description="カット名",
        default="Cut",
    )

    timeline_start: IntProperty(
        name="Timeline Start",
        description="このカットの開始フレーム",
        default=1,
        min=0,
    )

    storyboard_items: CollectionProperty(
        type=ANIMREF_PG_ReferenceItem,
    )

    layout_items: CollectionProperty(
        type=ANIMREF_PG_ReferenceItem,
    )

    keyframe_items: CollectionProperty(
        type=ANIMREF_PG_ReferenceItem,
    )

    active_storyboard_index: IntProperty(
        default=0,
        min=0,
    )

    active_layout_index: IntProperty(
        default=0,
        min=0,
    )

    active_keyframe_index: IntProperty(
        default=0,
        min=0,
    )


# ============================================================
# Project
# プロジェクト全体
# ============================================================

class ANIMREF_PG_Project(bpy.types.PropertyGroup):

    project_name: StringProperty(
        name="Project Name",
        default="Untitled Project",
    )

    project_filepath: StringProperty(
        name="Project File",
        subtype='FILE_PATH',
        default="",
    )

    fps: IntProperty(
        name="FPS",
        default=24,
        min=1,
    )

    images: CollectionProperty(
        type=ANIMREF_PG_ImageAsset,
    )

    cuts: CollectionProperty(
        type=ANIMREF_PG_Cut,
    )

    active_image_index: IntProperty(
        default=0,
        min=0,
    )

    active_cut_index: IntProperty(
        default=0,
        min=0,
    )

    active_category: EnumProperty(
        name="Reference Type",
        items=[
            ('STORYBOARD', "絵コンテ", ""),
            ('LAYOUT', "レイアウト", ""),
            ('KEYFRAME', "原画", ""),
        ],
        default='STORYBOARD',
    )

    auto_sync: BoolProperty(
      name="Auto Sync",
      description="Timelineの変更に合わせて資料を自動表示する",
      default=False,
    )

# ============================================================
# Registration
# ============================================================

classes = (
    ANIMREF_PG_ImageAsset,
    ANIMREF_PG_ReferenceItem,
    ANIMREF_PG_Cut,
    ANIMREF_PG_Project,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.animref_project = PointerProperty(
        type=ANIMREF_PG_Project
    )


def unregister():

    del bpy.types.Scene.animref_project

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)