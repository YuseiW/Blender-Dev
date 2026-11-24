import uuid


def generate_uid(prefix: str) -> str:
    """
    一意なIDを生成する。IDが被らないような仕組みになっている。

    例:
    img-a83043c9...
    cut-81aa4302...
    ref-50de1234...
    """

    return f"{prefix}-{uuid.uuid4().hex}"

def find_image_by_uid(project, uid):

    for image in project.images:

        if image.uid == uid:
            return image

    return None

def calculate_reference_ranges(
    collection,
    start_frame=1
):

    current_frame = start_frame

    result = []

    for reference in collection:

        frame_start = current_frame

        frame_end = (
            frame_start
            + reference.duration
            - 1
        )

        result.append({
            "reference": reference,
            "start": frame_start,
            "end": frame_end,
        })

        current_frame = frame_end + 1

    return result