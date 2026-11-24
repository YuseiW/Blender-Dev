"""AnimRef Phase V-5.1: newline-safe V-4 -> V-5 camera overlay upgrade.

Compared sources are decoded UTF-8 and normalized by line endings ONLY.
If local code differs, the installer stops and prints a diff, preserving local edits.
No bpy/PySide6 dependency. Other addon modules and user .blend/.json are untouched.
"""
from __future__ import annotations

import ast
from datetime import datetime
import difflib
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts/addons/anim_reference_tool/camera_overlay_manager.py"
V4 = ROOT / "phase_v5_baseline/camera_overlay_manager_v4.py"
V5 = ROOT / "phase_v5_payload/camera_overlay_manager.py"


def normalized(raw: bytes) -> str:
    # Strip only the optional UTF-8 BOM and normalize Windows/Unix newlines.
    text = raw.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def newline_style(raw: bytes) -> bytes:
    # Keep a uniform CRLF file CRLF on output, otherwise normalize to LF.
    return b"\r\n" if b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"") else b"\n"


def report_difference(actual: str, expected: str) -> None:
    lines = list(difflib.unified_diff(
        expected.splitlines(keepends=True), actual.splitlines(keepends=True),
        fromfile="公式V-4コード", tofile="ローカルのcamera_overlay_manager.py"))
    print("V-4配布版とは改行以外にも差分があります。安全のため変更しません。")
    if lines:
        print("".join(lines[:100]))
        if len(lines) > 100:
            print("... 差分が長いため最初の100行のみ表示しました")
    print("差分を確認してから統合する必要があります。ローカルファイルは保持されています。")


def main():
    for path in (TARGET, V4, V5):
        if not path.is_file():
            raise SystemExit(f"必要なファイルが見つかりません: {path}")

    original = TARGET.read_bytes()
    try:
        local = normalized(original)
        baseline = normalized(V4.read_bytes())
        upgraded = normalized(V5.read_bytes())
    except UnicodeError as exc:
        raise SystemExit(f"UTF-8として読み取れません。変更は行いません: {exc}")

    if local == upgraded:
        print("Phase V-5はすでに適用済みです。変更はありません。")
        return

    if local != baseline:
        report_difference(local, baseline)
        raise SystemExit(1)

    # Validate source before touching existing code.
    ast.parse(upgraded, filename=str(V5))
    eol = newline_style(original)
    content = upgraded.encode("utf-8")
    if eol == b"\r\n":
        content = content.replace(b"\n", b"\r\n")
    if original.startswith(b"\xef\xbb\xbf"):
        content = b"\xef\xbb\xbf" + content

    backup = (Path(tempfile.gettempdir()) / "animref_backups" /
              ("phase_v5_1_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")))
    backup.mkdir(parents=True, exist_ok=False)
    backup_file = backup / TARGET.name
    shutil.copy2(TARGET, backup_file)

    fd, temp_path = tempfile.mkstemp(prefix=".animref-v5-", dir=str(TARGET.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(temp_path, TARGET)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    print("Phase V-5.1適用成功（V-4と同一内容・改行形式は維持）。")
    print("バックアップ:", backup_file)
    print("Blenderを再起動後、実機テストを行ってください。")


if __name__ == "__main__":
    main()
