"""AnimRef R-5: move external Qt UI without changing its behavior."""
import argparse
import ast
import re
import subprocess
from pathlib import Path

BASE = Path('scripts/addons/anim_reference_tool')
NAMES = ('qt_manager_app.py', 'qt_viewer_page.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    def fail(message):
        raise SystemExit(message)
    for rel in ('core/properties.py', 'storage/project_io.py', 'managers/timeline_manager.py', 'ipc/manager_ipc.py', 'operators/manager_external.py', *NAMES):
        if not (BASE / rel).is_file():
            fail('Missing R-4 baseline: ' + rel)
    dest = BASE / 'qt'
    if dest.exists():
        fail('Qt directory already exists; no changes made.')
    dirty = subprocess.check_output(['git','status','--porcelain','--untracked-files=no','--',BASE.as_posix(),'tests','tools'], text=True)
    dirty = [x for x in dirty.splitlines() if '__pycache__' not in x and not x.endswith(('.pyc','.pyo'))]
    if dirty:
        fail('Commit or stash tracked source/test changes first:\n'+'\n'.join(dirty))
    originals = {}
    writes = {dest/'__init__.py': b'"""External PySide6 UI; no Blender imports."""\n'}
    seen = set()
    for folder in (BASE, Path('tests'), Path('tools')):
        for p in sorted(folder.rglob('*.py')):
            if '__pycache__' in p.parts: continue
            raw = p.read_bytes()
            new = raw
            target = p
            if p == BASE/'qt_manager_app.py':
                old = b'from ipc.manager_ipc import read_json, write_json_atomic'
                if new.count(old) != 1: fail('Unexpected Qt IPC import: '+str(p))
                nl = b'\r\n' if b'\r\n' in raw else b'\n'
                # Direct script launch puts qt/ on sys.path. Add addon root only
                # for the shared IPC package, without importing addon __init__.
                new = new.replace(old, nl.join([
                    b'# Shared IPC lives alongside qt/; do not import the Blender addon.',
                    b'_addon_root = str(Path(__file__).resolve().parents[1])',
                    b'if _addon_root not in sys.path:',
                    b'    sys.path.insert(1, _addon_root)', old]))
                if b'from qt_viewer_page import ViewerPage' not in new: fail('Unexpected Viewer import: '+str(p))
                target = dest/p.name; seen.add('qt')
            elif p == BASE/'qt_viewer_page.py':
                target = dest/p.name; seen.add('viewer')
            elif p == BASE/'operators/manager_external.py':
                old = b'addon_dir / "qt_manager_app.py"'
                if new.count(old) != 1: fail('Unexpected launcher path: '+str(p))
                new = new.replace(old,b'addon_dir / "qt" / "qt_manager_app.py"')
                seen.add('bridge')
            elif folder != BASE:
                for name in NAMES:
                    bname = name.encode()
                    new = new.replace(b'anim_reference_tool/'+bname,b'anim_reference_tool/qt/'+bname)
                    new = new.replace(b'anim_reference_tool\\\\'+bname,b'anim_reference_tool\\\\qt\\\\'+bname)
                    # Contract tests use bare filename relative to ADDON.
                    for q in (b"'",b'"'):
                        new = new.replace(q+bname+q,q+b'qt/'+bname+q)
            tree = ast.parse(new, filename=str(target))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value,str):
                    s=node.value.replace('\\','/')
                    if any(s.endswith('anim_reference_tool/'+n) for n in NAMES):
                        fail(f'Unmigrated Qt path: {p}:{node.lineno}')
                    if folder != BASE and s in NAMES:
                        fail(f'Unmigrated Qt path: {p}:{node.lineno}')
                if isinstance(node, ast.ImportFrom) and node.level and node.module in ('qt_manager_app','qt_viewer_page'):
                    fail(f'Review relative Qt import: {p}:{node.lineno}')
            if new != raw or target != p:
                originals[p]=raw; writes[target]=new
    if seen != {'qt','viewer','bridge'}: fail('Missing expected Qt files')
    for p,data in writes.items(): ast.parse(data,filename=str(p))
    for p in originals:
        subprocess.run(['git','ls-files','--error-unmatch','--',p.as_posix()],check=True,stdout=subprocess.DEVNULL)
    print('R-5 planned writes:')
    for p in sorted(writes): print('  '+str(p))
    for name in NAMES: print('Old path removed: '+str(BASE/name))
    if args.check:
        print('PASS: preflight and Python syntax; no files modified.'); return
    created=[]; touched=[]
    try:
        dest.mkdir()
        for p,data in writes.items():
            (touched if p in originals else created).append(p)
            p.write_bytes(data)
        for name in NAMES:
            p=BASE/name; touched.append(p); p.unlink()
    except Exception:
        for p in touched: p.write_bytes(originals[p])
        for p in created: p.unlink(missing_ok=True)
        dest.rmdir(); raise
    print('PASS: R-5 applied. Run regression tests before committing.')

if __name__ == '__main__': main()
