"""Plain-Python message transport shared by Blender and the Qt manager.

Only JSON files are exchanged. No Blender Python API is invoked by Qt.
"""
import json
import os
from pathlib import Path
from uuid import uuid4

MAX_JSON_BYTES = 2_000_000


def write_json_atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    contents = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    if len(contents.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("JSON message exceeds size limit")
    temp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(contents)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_json(path):
    path = Path(path)
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("JSON message exceeds size limit")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
