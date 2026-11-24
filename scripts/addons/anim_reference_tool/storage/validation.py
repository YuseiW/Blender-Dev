
"""Animation Reference ProjectのJSON検証処理"""

import os

MAX_INT = 2**31 - 1

CATEGORIES = (
    "storyboard",
    "layout",
    "keyframe",
)


class ProjectValidationError(ValueError):
    """プロジェクトデータが不正な場合の例外"""
    pass


def _valid_int(value, minimum):
    """指定した範囲内の整数か確認する"""
    return (
        type(value) is int
        and minimum <= value <= MAX_INT
    )


def validate_project_data(
    data,
    project_directory,
    expected_format,
    expected_version,
):
    """
    JSONの内容を検証する。

    Returns:
        warnings: 警告メッセージのリスト

    Raises:
        ProjectValidationError:
            不正なデータが見つかった場合
    """

    errors = []
    warnings = []

    # =====================================
    # 基本構造の確認
    # =====================================

    if not isinstance(data, dict):
        raise ProjectValidationError(
            "JSONの最上位はオブジェクトである必要があります"
        )

    if data.get("format") != expected_format:
        errors.append(
            "formatが対象プロジェクト形式ではありません"
        )

    if (
        type(data.get("version")) is not int
        or data["version"] != expected_version
    ):
        errors.append(
            f"未対応のversionです（対応版: {expected_version}）"
        )

    if not isinstance(
        data.get("project_name"), str
    ):
        errors.append(
            "project_nameは文字列である必要があります"
        )

    if not _valid_int(data.get("fps"), 1):
        errors.append(
            "fpsは1以上の整数である必要があります"
        )

    # =====================================
    # 配列の確認
    # =====================================

    images = data.get("images")
    cuts = data.get("cuts")

    if not isinstance(images, list):
        errors.append(
            "imagesは配列である必要があります"
        )
        images = []

    if not isinstance(cuts, list):
        errors.append(
            "cutsは配列である必要があります"
        )
        cuts = []

    image_ids = set()
    cut_ids = set()
    reference_ids = set()

    # =====================================
    # ImageAssetの検証
    # =====================================

    for i, image in enumerate(images):

        place = f"images[{i}]"

        if not isinstance(image, dict):
            errors.append(
                f"{place}はオブジェクトである必要があります"
            )
            continue

        # UID
        uid = image.get("uid")

        if not isinstance(uid, str) or not uid.strip():
            errors.append(
                f"{place}.uidが不正です"
            )

        elif uid in image_ids:
            errors.append(
                f"{place}.uidが重複しています: {uid}"
            )

        else:
            image_ids.add(uid)

        # 名前
        if not isinstance(image.get("name"), str):
            errors.append(
                f"{place}.nameは文字列である必要があります"
            )

        # ファイルパス
        path = image.get("filepath")

        if not isinstance(path, str):
            errors.append(
                f"{place}.filepathは文字列である必要があります"
            )
            continue

        if not path:
            warnings.append(
                f"{place}: 画像パスが空です"
            )
            continue

        # 画像ファイルの存在確認
        if project_directory is not None:

            if os.path.isabs(path):
                resolved = path
            else:
                resolved = os.path.join(
                    project_directory,
                    path
                )

            try:
                exists = os.path.isfile(resolved)

            except (OSError, ValueError):
                errors.append(
                    f"{place}.filepathが不正です"
                )
                continue

            if not exists:
                warnings.append(
                    f"{place}: 画像ファイルが見つかりません: {path}"
                )

    # =====================================
    # Cutの検証
    # =====================================

    for i, cut in enumerate(cuts):

        place = f"cuts[{i}]"

        if not isinstance(cut, dict):
            errors.append(
                f"{place}はオブジェクトである必要があります"
            )
            continue

        # UID
        uid = cut.get("uid")

        if not isinstance(uid, str) or not uid.strip():
            errors.append(
                f"{place}.uidが不正です"
            )

        elif uid in cut_ids:
            errors.append(
                f"{place}.uidが重複しています: {uid}"
            )

        else:
            cut_ids.add(uid)

        # カット名
        if not isinstance(cut.get("name"), str):
            errors.append(
                f"{place}.nameは文字列である必要があります"
            )

        # 開始フレーム
        start = cut.get("timeline_start")

        if not _valid_int(start, 0):
            errors.append(
                f"{place}.timeline_startは0以上の整数である必要があります"
            )

        # =================================
        # 資料カテゴリごとの検証
        # =================================

        for category in CATEGORIES:

            refs = cut.get(category)

            location = f"{place}.{category}"

            if not isinstance(refs, list):
                errors.append(
                    f"{location}は配列である必要があります"
                )
                continue

            duration_sum = 0

            for j, ref in enumerate(refs):

                rp = f"{location}[{j}]"

                if not isinstance(ref, dict):
                    errors.append(
                        f"{rp}はオブジェクトである必要があります"
                    )
                    continue

                # Reference UID
                rid = ref.get("uid")

                if (
                    not isinstance(rid, str)
                    or not rid.strip()
                ):
                    errors.append(
                        f"{rp}.uidが不正です"
                    )

                elif rid in reference_ids:
                    errors.append(
                        f"{rp}.uidが重複しています: {rid}"
                    )

                else:
                    reference_ids.add(rid)

                # 参照画像ID
                image_id = ref.get("image_id")

                if (
                    not isinstance(image_id, str)
                    or not image_id.strip()
                ):
                    errors.append(
                        f"{rp}.image_idが不正です"
                    )

                elif image_id not in image_ids:
                    errors.append(
                        f"{rp}.image_idに対応する画像が存在しません: {image_id}"
                    )

                # 表示フレーム数
                duration = ref.get("duration")

                if not _valid_int(duration, 1):
                    errors.append(
                        f"{rp}.durationは1以上の整数である必要があります"
                    )

                else:
                    duration_sum += duration

                # 指示文
                if not isinstance(
                    ref.get("instruction"), str
                ):
                    errors.append(
                        f"{rp}.instructionは文字列である必要があります"
                    )

            # フレーム範囲が上限を超えないか
            if (
                _valid_int(start, 0)
                and duration_sum
                and start + duration_sum - 1 > MAX_INT
            ):
                errors.append(
                    f"{location}の終了フレームが上限を超えています"
                )

    # =====================================
    # 最終判定
    # =====================================

    if errors:

        message = (
            "プロジェクトデータが不正です: "
            + errors[0]
        )

        if len(errors) > 1:

            message += (
                f"（ほか{len(errors) - 1}件）"
            )

            message += "\n" + "\n".join(
                f"- {e}"
                for e in errors[1:12]
            )

        raise ProjectValidationError(message)

    return warnings
