
import bpy
import sys
import os
import json
import copy
import tempfile
import importlib
from pathlib import Path


# ==========================================
# アドオンモジュール取得
# ==========================================

project_io = next(
    (
        module
        for name, module in sys.modules.items()
        if name.endswith(
            "anim_reference_tool.project_io"
        )
    ),
    None
)

if project_io is None:
    raise RuntimeError(
        "Animation Reference Toolを有効にしてから"
        "テストを実行してください"
    )

timeline_manager = importlib.import_module(
    project_io.__package__ + ".timeline_manager"
)


def create_reference(
    collection,
    uid,
    image_id,
    duration,
    instruction=""
):
    ref = collection.add()
    ref.uid = uid
    ref.image_id = image_id
    ref.duration = duration
    ref.instruction = instruction
    return ref


# ==========================================
# テスト実行
# ==========================================

def run_tests():

    scene = bpy.data.scenes.new(
        "__ANIMREF_TEST_SCENE__"
    )

    test_images = []

    try:
        with tempfile.TemporaryDirectory() as temp:

            project = scene.animref_project
            project.auto_sync = False
            project.project_name = "Integration Test"
            project.fps = 24

            # --------------------------
            # テスト画像を2枚作成
            # --------------------------

            for i in range(2):

                image = bpy.data.images.new(
                    f"__ANIMREF_TEST_{i}__",
                    width=2,
                    height=2
                )

                test_images.append(image)

                filepath = os.path.join(
                    temp,
                    f"image_{i}.png"
                )

                image.filepath_raw = filepath
                image.file_format = 'PNG'
                image.save()

                asset = project.images.add()
                asset.uid = f"img-test-{i}"
                asset.name = f"image_{i}.png"
                asset.filepath = filepath

            # --------------------------
            # カットC001
            # --------------------------

            cut = project.cuts.add()
            cut.uid = "cut-test-1"
            cut.name = "C001"
            cut.timeline_start = 1

            create_reference(
                cut.storyboard_items,
                "ref-1",
                "img-test-0",
                8,
                "最初の絵コンテ"
            )

            create_reference(
                cut.storyboard_items,
                "ref-2",
                "img-test-1",
                12,
                "次の絵コンテ"
            )

            create_reference(
                cut.keyframe_items,
                "ref-3",
                "img-test-1",
                10,
                "原画"
            )

            # --------------------------
            # カットC002
            # --------------------------

            cut2 = project.cuts.add()
            cut2.uid = "cut-test-2"
            cut2.name = "C002"
            cut2.timeline_start = 41

            create_reference(
                cut2.storyboard_items,
                "ref-4",
                "img-test-0",
                5
            )

            print("[PASS] テストデータ作成")

            # --------------------------
            # JSON保存
            # --------------------------

            filepath = os.path.join(
                temp,
                "test_project.json"
            )

            project_io.save_project(
                project,
                filepath
            )

            assert os.path.isfile(filepath)

            with open(
                filepath,
                encoding="utf-8"
            ) as file:
                data = json.load(file)

            assert data["version"] == 1
            assert len(data["images"]) == 2
            assert len(data["cuts"]) == 2

            print("[PASS] JSON保存")

            # --------------------------
            # JSON読み込み
            # --------------------------

            project.project_name = "Changed"

            project_io.load_project(
                project,
                filepath
            )

            assert project.project_name == (
                "Integration Test"
            )
            assert len(project.images) == 2
            assert len(project.cuts) == 2

            assert (
                project.cuts[0]
                .storyboard_items[0]
                .instruction
                == "最初の絵コンテ"
            )

            print("[PASS] JSON読み込み・復元")

            # --------------------------
            # フレーム検索
            # --------------------------

            cut = project.cuts[0]

            cases = [
                (1, "img-test-0", 1, 8),
                (8, "img-test-0", 1, 8),
                (9, "img-test-1", 9, 20),
                (20, "img-test-1", 9, 20),
            ]

            for frame, uid, start, end in cases:

                ref, asset, s, e = (
                    timeline_manager.resolve_reference_at_frame(
                        project,
                        cut,
                        "STORYBOARD",
                        frame
                    )
                )

                assert ref is not None
                assert asset.uid == uid
                assert (s, e) == (start, end)

            ref, asset, s, e = (
                timeline_manager.resolve_reference_at_frame(
                    project,
                    cut,
                    "STORYBOARD",
                    21
                )
            )

            assert ref is None
            assert asset is None

            print("[PASS] フレーム範囲検索")

            # --------------------------
            # 不正JSONの拒否
            # --------------------------

            bad_data = copy.deepcopy(data)

            bad_data["cuts"][0]["storyboard"][0][
                "duration"
            ] = 0

            bad_path = os.path.join(
                temp,
                "invalid.json"
            )

            with open(
                bad_path,
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(bad_data, file)

            before_name = project.project_name
            before_cuts = len(project.cuts)

            rejected = False

            try:
                project_io.load_project(
                    project,
                    bad_path
                )

            except ValueError:
                rejected = True

            assert rejected, (
                "不正JSONが拒否されませんでした"
            )

            assert project.project_name == before_name
            assert len(project.cuts) == before_cuts

            print("[PASS] 不正JSONの拒否・状態保持")

            # --------------------------
            # 欠損画像の扱い
            # --------------------------

            missing_data = copy.deepcopy(data)

            missing_data["images"][0][
                "filepath"
            ] = "missing_image.png"

            missing_path = os.path.join(
                temp,
                "missing_project.json"
            )

            with open(
                missing_path,
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(missing_data, file)

            project_io.load_project(
                project,
                missing_path
            )

            assert len(project.images) == 2
            assert len(project.cuts) == 2

            print("[PASS] 欠損画像を含むJSONの読込")

            print()
            print("=== ALL TESTS PASSED ===")

    finally:

        for image in test_images:
            if image.name in bpy.data.images:
                bpy.data.images.remove(image)

        bpy.data.scenes.remove(scene)


run_tests()
