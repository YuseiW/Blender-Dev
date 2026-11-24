"""Move AnimRef storage modules after Phase R-1. Run from repository root."""
import argparse
import ast
from pathlib import Path
import subprocess

BASE = Path('scripts/addons/anim_reference_tool')
MOVES = ('project_io.py', 'validation.py')
RULES = {
    'project_io.py': [(b'from .core.utils import', b'from ..core.utils import')],
    'operators/project.py': [(b'from ..project_io import', b'from ..storage.project_io import')],
    'operators/manager_external.py': [(b'from ..project_io import', b'from ..storage.project_io import')],
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not BASE.is_dir():
        raise SystemExit('Run from Blender-Dev root.')
    if not all((BASE / p).is_file() for p in ('core/__init__.py','core/properties.py','core/utils.py')) or any((BASE / p).exists() for p in ('properties.py','utils.py')):
        raise SystemExit('Phase R-1 must be applied first.')
    if (BASE/'storage').exists():
        raise SystemExit('storage already exists; no changes made.')
    original = {p.relative_to(BASE).as_posix():p.read_bytes() for p in BASE.rglob('*.py') if '__pycache__' not in p.parts}
    if not (set(MOVES)|RULES.keys()) <= original.keys():
        raise SystemExit('Expected source files missing.')
    if original['project_io.py'].count(b'from .validation import') != 1:
        raise SystemExit('Unexpected validation import in project_io.py')
    edits = {}
    for name, raw in original.items():
        new = raw
        for old, replacement in RULES.get(name, []):
            if new.count(old) != 1:
                raise SystemExit(f'Unexpected import in {name}: {old!r}')
            new = new.replace(old, replacement)
        target = 'storage/'+name if name in MOVES else name
        tree = ast.parse(new, filename=target)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ''
                if mod in ('project_io','validation','anim_reference_tool.project_io','anim_reference_tool.validation') or (not mod and any(a.name in ('project_io','validation') for a in node.names)):
                    if not (target == 'storage/project_io.py' and node.level == 1 and mod == 'validation'):
                        raise SystemExit(f'Unexpected storage reference: {target}:{node.lineno}')
            elif isinstance(node, ast.Import) and any(a.name in ('project_io','validation','anim_reference_tool.project_io','anim_reference_tool.validation') for a in node.names):
                raise SystemExit(f'Unexpected storage import: {target}:{node.lineno}')
        if target != name or new != raw:
            edits[target] = new
    edits['storage/__init__.py'] = b'"""AnimRef project persistence and data validation."""\n'
    # Detect old paths in test/tool sources (including dynamic path literals).
    for folder in ('tests','tools'):
        for p in Path(folder).rglob('*.py'):
            if '__pycache__' in p.parts: continue
            tree = ast.parse(p.read_bytes(), filename=str(p))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value,str) and (node.value in ('project_io.py','validation.py','anim_reference_tool.project_io','anim_reference_tool.validation') or any(node.value.endswith('/'+n) and not node.value.endswith('/storage/'+n) for n in MOVES)):
                    raise SystemExit(f'Review old test/tool path first: {p}:{node.lineno}')
                if isinstance(node, ast.ImportFrom) and (node.module or '').split('.')[-1] in ('project_io','validation'):
                    if '.storage.' not in (node.module or ''):
                        raise SystemExit(f'Review test/tool import first: {p}:{node.lineno}')
    status = subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True)
    dirty = [line for line in status.splitlines() if '__pycache__/' not in line and not line.endswith(('.pyc','.pyo'))]
    if dirty: raise SystemExit('Commit or stash tracked non-cache changes first:\n'+'\n'.join(dirty))
    for name in set(MOVES)|RULES.keys():
        subprocess.run(['git','ls-files','--error-unmatch',str(BASE/name)],check=True,stdout=subprocess.DEVNULL)
    for name in ('core/__init__.py','core/properties.py','core/utils.py'):
        subprocess.run(['git','ls-files','--error-unmatch',str(BASE/name)],check=True,stdout=subprocess.DEVNULL)
    print('Phase R-2 planned changes:')
    for name in edits: print('  ',name)
    print('  remove old paths: project_io.py, validation.py')
    if args.check:
        print('PASS: preflight and Python syntax; no files modified.')
        return
    try:
        (BASE/'storage').mkdir()
        for name,data in edits.items(): (BASE/name).write_bytes(data)
        for name in MOVES: (BASE/name).unlink()
    except Exception:
        for name in set(MOVES)|RULES.keys(): (BASE/name).write_bytes(original[name])
        for name in edits:
            if name.startswith('storage/') and (BASE/name).exists(): (BASE/name).unlink()
        if (BASE/'storage').exists(): (BASE/'storage').rmdir()
        raise
    print('PASS: files moved. Run regression tests before committing.')

if __name__ == '__main__': main()
