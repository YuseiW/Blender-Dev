from .utils import generate_uid


CATEGORY_COLLECTIONS = {
    'STORYBOARD': 'storyboard_items',
    'LAYOUT': 'layout_items',
    'KEYFRAME': 'keyframe_items',
}


CATEGORY_ACTIVE_INDEX = {
    'STORYBOARD': 'active_storyboard_index',
    'LAYOUT': 'active_layout_index',
    'KEYFRAME': 'active_keyframe_index',
}


def get_reference_collection(cut, category):
    """
    categoryに対応するReferenceItemのCollectionを返す。
    """

    collection_name = CATEGORY_COLLECTIONS.get(category)

    if collection_name is None:
        raise ValueError(
            f"Unknown reference category: {category}"
        )

    return getattr(
        cut,
        collection_name
    )


def get_active_index_property(category):
    """
    categoryに対応するactive indexのプロパティ名を返す。
    """

    property_name = CATEGORY_ACTIVE_INDEX.get(category)

    if property_name is None:
        raise ValueError(
            f"Unknown reference category: {category}"
        )

    return property_name


def find_reference_by_image_id(
    collection,
    image_id
):
    """
    同じ画像が既に登録されているか確認する。
    """

    for reference in collection:

        if reference.image_id == image_id:
            return reference

    return None


def add_reference(
    cut,
    category,
    image_id,
    duration=1
):
    """
    ReferenceItemを追加する。

    同じカテゴリ内への同一画像の重複登録は防止する。
    """

    collection = get_reference_collection(
        cut,
        category
    )

    existing = find_reference_by_image_id(
        collection,
        image_id
    )

    if existing is not None:

        return existing, "DUPLICATE"

    reference = collection.add()

    reference.uid = generate_uid("ref")
    reference.image_id = image_id
    reference.duration = duration
    reference.instruction = ""

    # 追加したReferenceItemを選択状態にする
    active_property = get_active_index_property(
        category
    )

    setattr(
        cut,
        active_property,
        len(collection) - 1
    )

    return reference, "ADDED"


def remove_reference(
    cut,
    category,
    index
):
    """
    ReferenceItemを削除する。
    """

    collection = get_reference_collection(
        cut,
        category
    )

    if index < 0 or index >= len(collection):
        return False

    collection.remove(index)

    active_property = get_active_index_property(
        category
    )

    if len(collection) == 0:

        setattr(
            cut,
            active_property,
            0
        )

    else:

        setattr(
            cut,
            active_property,
            min(
                index,
                len(collection) - 1
            )
        )

    return True


def move_reference(
    cut,
    category,
    index,
    direction
):
    """
    ReferenceItemを上下に並べ替える。

    direction:
        -1 = 上
         1 = 下
    """

    collection = get_reference_collection(
        cut,
        category
    )

    new_index = index + direction

    if index < 0:
        return False

    if index >= len(collection):
        return False

    if new_index < 0:
        return False

    if new_index >= len(collection):
        return False

    collection.move(
        index,
        new_index
    )

    active_property = get_active_index_property(
        category
    )

    setattr(
        cut,
        active_property,
        new_index
    )

    return True