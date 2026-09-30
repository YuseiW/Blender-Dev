import os
import bpy

from bpy.props import (
    StringProperty,
    CollectionProperty,
)

from ..image_manager import add_image_asset


class ANIMREF_OT_ImportImages(bpy.types.Operator):

    bl_idname = "animref.import_images"
    bl_label = "画像をインポート"
    bl_description = "複数の画像を画像プールへ追加します"

    # ファイル選択画面で選択されたファイル
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={
            'HIDDEN',
            'SKIP_SAVE',
        },
    )

    # 選択されたディレクトリ
    directory: StringProperty(
        subtype='DIR_PATH',
        options={
            'HIDDEN',
            'SKIP_SAVE',
        },
    )

    # ファイルブラウザに表示する画像形式
    filter_glob: StringProperty(
        default=(
            "*.png;"
            "*.jpg;"
            "*.jpeg;"
            "*.bmp;"
            "*.tif;"
            "*.tiff;"
            "*.webp;"
            "*.exr"
        ),
        options={'HIDDEN'},
    )

    def invoke(self, context, event):

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):

        project = context.scene.animref_project

        if not self.files:

            self.report(
                {'WARNING'},
                "画像が選択されていません"
            )

            return {'CANCELLED'}

        added_count = 0
        duplicate_count = 0
        failed_count = 0

        # 順序を安定させるため名前順
        selected_files = sorted(
            self.files,
            key=lambda file: file.name.lower()
        )

        for selected_file in selected_files:

            filepath = os.path.join(
                self.directory,
                selected_file.name
            )

            image_asset, status = add_image_asset(
                project,
                filepath
            )

            if status == "ADDED":

                added_count += 1

            elif status == "DUPLICATE":

                duplicate_count += 1

            else:

                failed_count += 1

                print(
                    "[AnimRef]",
                    status,
                    filepath
                )

        message = (
            f"{added_count}枚追加"
        )

        if duplicate_count > 0:

            message += (
                f" / {duplicate_count}枚重複"
            )

        if failed_count > 0:

            message += (
                f" / {failed_count}枚失敗"
            )

        self.report(
            {'INFO'},
            message
        )

        return {'FINISHED'}


classes = (
    ANIMREF_OT_ImportImages,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)