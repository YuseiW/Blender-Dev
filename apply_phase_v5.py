"""Apply AnimRef Phase V-5 camera/Scene stabilization safely on top of V-4.

No dependency on bpy or PySide6. Does not modify User project JSON or .blend.
"""
from pathlib import Path
from datetime import datetime
import hashlib
import os
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'phase_v5_payload/camera_overlay_manager.py'
TARGET = ROOT / 'scripts/addons/anim_reference_tool/camera_overlay_manager.py'
EXPECTED_V4_SHA256 = 'bf4a762443560bd819a84e5bee560d190a5a1431f4143c7317d2d44a572d0265'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_atomic(src, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.animref-v5-', dir=str(target.parent))
    os.close(fd)
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    if not SRC.exists() or not TARGET.exists():
        raise SystemExit('V-4 camera_overlay_manager.py が見つかりません。Blender-DevのルートにZIPを展開してください。')
    old = digest(TARGET)
    new = digest(SRC)
    if old == new:
        print('Phase V-5は既に適用されています。変更はありません。')
    elif old != EXPECTED_V4_SHA256:
        raise SystemExit('現在のcamera_overlay_manager.pyが既知のV-4版と一致しません。安全のため上書きを中止しました。手作業で差分を確認してください。')
    else:
        backup = Path(tempfile.gettempdir())/'animref_backups'/('phase_v5_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TARGET,backup/TARGET.name)
        copy_atomic(SRC,TARGET)
        print('Phase V-5安定化コードを適用しました。')
        print('バックアップ:',backup/TARGET.name)
    # These are additive: no existing source, tests, or documentation is deleted.
    for rel in ('tests/test_phase_v5_contract.py', 'tools/phase_v5_diagnostics.py', 'README_PHASE_V5.md', 'PHASE_V5_TEST_MATRIX.md'):
        src = ROOT/rel
        dest = ROOT/rel
        if not src.is_file():
            raise SystemExit(f'配布ファイルが見つかりません: {rel}')
    print('テスト: python .\\tests\\test_phase_v5_contract.py')

if __name__=='__main__':
    main()
