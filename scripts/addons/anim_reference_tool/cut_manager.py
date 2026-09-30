from .utils import generate_uid


def generate_cut_name(project):
    """
    未使用のカット名を生成する。

    C001
    C002
    C003
    ...
    """

    existing_names = {
        cut.name
        for cut in project.cuts
    }

    number = 1

    while True:

        name = f"C{number:03d}"

        if name not in existing_names:
            return name

        number += 1


def add_cut(project):
    """
    新しいCutを追加する。
    """

    cut = project.cuts.add()

    cut.uid = generate_uid("cut")
    cut.name = generate_cut_name(project)
    cut.timeline_start = 1

    project.active_cut_index = len(project.cuts) - 1

    return cut


def remove_cut(project, index):
    """
    指定されたCutを削除する。
    """

    if index < 0:
        return False

    if index >= len(project.cuts):
        return False

    project.cuts.remove(index)

    # 選択位置を修正
    if len(project.cuts) == 0:

        project.active_cut_index = 0

    else:

        project.active_cut_index = min(
            index,
            len(project.cuts) - 1
        )

    return True