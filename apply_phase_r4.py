"""AnimRef R-4: move shared IPC into an import-safe package."""
import argparse
import ast
import re
import subprocess
from pathlib import Path

BASE = Path('scripts/addons/anim_reference_tool')
OLD = BASE / 'manager_ipc.py'
NEW = BASE / 'ipc/manager_ipc.py'
INIT = BASE / 'ipc/__init__.py'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    def fail(msg):
        raise SystemExit(msg)
    for rel in ('core/properties.py', 'storage/project_io.py', 'managers/timeline_manager.py', 'qt_manager_app.py', 'operators/manager_external.py', 'manager_ipc.py'):
        if not (BASE / rel).is_file():
            fail('Missing R-3 baseline: ' + rel)
    if INIT.parent.exists():
        fail('IPC directory already exists; no changes made.')
    dirty = subprocess.check_output(['git','status','--porcelain','--untracked-files=no','--',BASE.as_posix(),'tests','tools'], text=True)
    dirty = [x for x in dirty.splitlines() if '__pycache__' not in x and not x.endswith(('.pyc','.pyo'))]
    if dirty:
        fail('Commit or stash tracked source/test changes first:\n'+'\n'.join(dirty))
    originals = {OLD: OLD.read_bytes()}
    writes = {NEW: originals[OLD], INIT: b'"""Shared JSON IPC; no Blender or Qt dependencies."""\n'}
    seen = set()
    for folder in (BASE, Path('tests'), Path('tools')):
        for p in folder.rglob('*.py'):
            if p == OLD or '__pycache__' in p.parts:
                continue
            raw = p.read_bytes()
            new = raw
            if p == BASE/'operators/manager_external.py':
                old = b'from ..manager_ipc import'
                if new.count(old) != 1: fail('Unexpected bridge IPC import: '+str(p))
                new = new.replace(old,b'from ..ipc.manager_ipc import'); seen.add('bridge')
            if p == BASE/'qt_manager_app.py':
                old = b'from manager_ipc import'
                if new.count(old) != 1: fail('Unexpected Qt IPC import: '+str(p))
                new = new.replace(old,b'from ipc.manager_ipc import'); seen.add('qt')
            if p.name == 'test_bridge_mock.py':
                new = new.replace(b'anim_reference_tool.manager_ipc',b'anim_reference_tool.ipc.manager_ipc')
                new = new.replace(b"ROOT/'manager_ipc.py'",b"ROOT/'ipc/manager_ipc.py'")
                new = new.replace(b'ROOT/"manager_ipc.py"',b'ROOT/"ipc/manager_ipc.py"')
            # Fail closed on remaining old imports or explicit old file paths.
            tree = ast.parse(new, filename=str(p))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or '') in ('manager_ipc','anim_reference_tool.manager_ipc'):
                    fail(f'Unmigrated import: {p}:{node.lineno}')
                if isinstance(node, ast.Import) and any(a.name in ('manager_ipc','anim_reference_tool.manager_ipc') for a in node.names):
                    fail(f'Unmigrated import: {p}:{node.lineno}')
                if isinstance(node, ast.Constant) and isinstance(node.value,str):
                    s=node.value.replace('\\','/')
                    if 'anim_reference_tool.manager_ipc' in s or re.search(r'(?<![\w/])manager_ipc\.py$',s) or s.endswith('anim_reference_tool/manager_ipc.py'):
                        fail(f'Unmigrated IPC path: {p}:{node.lineno}')
            if new != raw:
                originals[p]=raw; writes[p]=new
    if seen != {'bridge','qt'}: fail('Missing expected IPC consumers')
    for p,data in writes.items(): ast.parse(data,filename=str(p))
    for p in originals:
        subprocess.run(['git','ls-files','--error-unmatch','--',p.as_posix()],check=True,stdout=subprocess.DEVNULL)
    print('R-4 planned writes:')
    for p in sorted(writes): print('  '+str(p))
    print('Old path removed: '+str(OLD))
    if args.check:
        print('PASS: preflight and Python syntax; no files modified.'); return
    created=[]; touched=[]
    try:
        INIT.parent.mkdir()
        for p,data in writes.items():
            (touched if p in originals else created).append(p)
            p.write_bytes(data)
        touched.append(OLD); OLD.unlink()
    except Exception:
        for p in touched: p.write_bytes(originals[p])
        for p in created: p.unlink(missing_ok=True)
        INIT.parent.rmdir(); raise
    print('PASS: R-4 applied. Run regression tests before committing.')

if __name__ == '__main__': main()
