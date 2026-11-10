
import os
import unicodedata
import bpy

from ..timeline_manager import (
    resolve_reference_at_frame,
)

from ..viewer_manager import (
    find_viewer_window,
)


# ==========================================
# 長い指示文を表示幅に合わせて分割
# ==========================================

def wrap_visual_text(text, max_columns=32):
    lines = []

    for paragraph in text.splitlines() or [""]:

        if not paragraph:
            lines.append(" ")
            continue

        current = ""
        width = 0

        for char in paragraph:

            char_width = (
                2 if unicodedata.east_asian_width(char)
                in {"F", "W", "A"} else 1
            )

            if (
                current
                and width + char_width > max_columns
            ):
                lines.append(current)
                current = ""
                width = 0

            current += char
            width += char_width

        if current:
            lines.append(current)

    return lines


# ==========================================
# Reference Viewer 情報パネル
# ==========================================

class ANIMREF_PT_ViewerInfo(bpy.types.Panel):

    bl_label = "Reference Info"
    bl_idname = "ANIMREF_PT_ViewerInfo"

    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AnimRef"

    @classmethod
    def poll(cls, context):
        """
        専用ビュアー内だけに表示する。
        """

        window = context.window
        wm = context.window_manager

        if window is None or wm is None:
            return False

        viewer = find_viewer_window(wm)

        return (
            viewer is not None
            and viewer.as_pointer()
            == window.as_pointer()
        )

    def draw(self, context):

        layout = self.layout
        scene = context.scene

        if (
            scene is None
            or not hasattr(scene, "animref_project")
        ):
            layout.label(
                text="Project not available",
                icon='ERROR'
            )
            return

        project = scene.animref_project

        
        layout.label(
            text=f"Scene: {scene.name}",
            icon='SCENE_DATA'
        )

        layout.separator()


        # ----------------------------------
        # 現在フレーム・資料種別
        # ----------------------------------

        layout.label(
            text=f"現在フレーム: {scene.frame_current}"
        )

        layout.prop(
            project,
            "active_category",
            text="資料種別"
        )

        if not project.auto_sync:

            layout.label(
                text="自動同期OFF",
                icon='INFO'
            )

            layout.label(
                text="画像と情報が不一致の可能性"
            )

            layout.operator(
                "animref.sync_current_frame",
                text="現在フレームを同期",
                icon='FILE_REFRESH'
            )

        # ----------------------------------
        # カット確認
        # ----------------------------------

        if not project.cuts:

            layout.label(
                text="カットがありません",
                icon='INFO'
            )
            return

        index = project.active_cut_index

        if index < 0 or index >= len(project.cuts):

            layout.label(
                text="カット選択が不正です",
                icon='ERROR'
            )
            return

        cut = project.cuts[index]

        layout.label(
            text=f"Cut: {cut.name}"
        )

        # ----------------------------------
        # フレームに対応する資料を検索
        # ----------------------------------

        (
            reference,
            asset,
            frame_start,
            frame_end,
        ) = resolve_reference_at_frame(
            project,
            cut,
            project.active_category,
            scene.frame_current
        )

        if reference is None:

            layout.label(
                text="このフレームに資料はありません",
                icon='INFO'
            )
            return

        # ----------------------------------
        # 資料情報
        # ----------------------------------

        box = layout.box()

        box.label(
            text=f"範囲: {frame_start} - {frame_end}f"
        )

        if asset is None:

            box.label(
                text="画像データが見つかりません",
                icon='ERROR'
            )

        else:

            box.label(
                text=f"画像: {asset.name}",
                icon='IMAGE_DATA'
            )

            filepath = bpy.path.abspath(
                asset.filepath
            ) if asset.filepath else ""

            if (
                not filepath
                or not os.path.isfile(filepath)
            ):

                box.label(
                    text="画像ファイルがありません",
                    icon='ERROR'
                )

        # ----------------------------------
        # 作画・演出指示
        # ----------------------------------

        box = layout.box()

        box.label(
            text="作画・演出指示",
            icon='TEXT'
        )

        instruction = (
            reference.instruction or ""
        ).strip()

        if not instruction:

            box.label(
                text="指示なし",
                icon='INFO'
            )

        else:

            # サイドパネルの幅に応じた概算
            max_columns = max(
                16,
                min(
                    52,
                    int(context.region.width / 8)
                )
            )

            for line in wrap_visual_text(
                instruction,
                max_columns
            ):

                box.label(text=line)


# ==========================================
# Registration
# ==========================================

classes = (
    ANIMREF_PT_ViewerInfo,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
