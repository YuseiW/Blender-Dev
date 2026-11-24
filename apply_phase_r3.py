"""AnimRef R-3: relocate manager modules, preserving behavior. Run at repo root."""
import argparse
import ast
import re
import subprocess
from pathlib import Path

BASE = Path('scripts/addons/anim_reference_tool')
NAMES = ('cut_manager','image_manager','reference_manager','timeline_manager','camera_overlay_manager','viewer_manager')
ALT = '|'.join(NAMES)

def fail(msg):
    raise SystemExit(msg)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--check',action='store_true'); group.add_argument('--apply',action='store_true')
    args = ap.parse_args()
    for p in ('core/properties.py','core/utils.py','storage/project_io.py','storage/validation.py',*(n+'.py' for n in NAMES)):
        if not (BASE/p).is_file(): fail('Missing R-2 baseline: '+p)
    if (BASE/'managers').exists(): fail('managers already exists; no changes made.')
    original = {}; writes = {}; removes = set()
    def put(p,data):
        ast.parse(data,filename=str(p)); writes[p]=data
    for p in BASE.rglob('*.py'):
        if '__pycache__' in p.parts: continue
        raw=p.read_bytes(); original[p]=raw
        rel=p.relative_to(BASE); moved=rel.parent==Path('.') and p.stem in NAMES
        depth=len(rel.parts)-1
        text=raw.decode('utf-8-sig'); bom=raw.startswith(b'\xef\xbb\xbf')
        # All old relative imports addressing the add-on root; internal manager imports remain siblings.
        if not moved:
            dots='.'*(depth+1)
            text=re.sub(r'(?m)^(\s*from )'+re.escape(dots)+r'('+ALT+r')(\s+import\b)',lambda m:m[1]+dots+'managers.'+m[2]+m[3],text)
            text=re.sub(r'(?m)^(\s*from )'+re.escape(dots)+r'(\s+import\s+)('+ALT+r')\b',lambda m:m[1]+dots+'managers'+m[2]+m[3],text)
        else:
            text=re.sub(r'(?m)^(\s*from )\.(core|storage)(\.)',r'\1..\2\3',text)
        new=text.encode('utf-8'); new=(b'\xef\xbb\xbf'+new) if bom else new
        target=BASE/'managers'/p.name if moved else p
        tree=ast.parse(new,filename=str(target))
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                mod=node.module or ''; names={a.name for a in node.names}
                if mod in NAMES or (not mod and names.intersection(NAMES)):
                    if not (moved and node.level==1): fail(f'Unmigrated import {target}:{node.lineno}')
                if mod.startswith('anim_reference_tool.') and mod.split('.')[-1] in NAMES and '.managers.' not in mod: fail(f'Unmigrated absolute import {target}:{node.lineno}')
            if isinstance(node,ast.Import) and any(a.name in NAMES or a.name in ['anim_reference_tool.'+n for n in NAMES] for a in node.names): fail(f'Unmigrated import {target}:{node.lineno}')
        if moved: removes.add(p)
        if moved or new!=raw: put(target,new)
    put(BASE/'managers/__init__.py',b'"""AnimRef management and synchronization modules."""\n')
    for folder in ('tests','tools'):
        for p in Path(folder).rglob('*.py'):
            if '__pycache__' in p.parts: continue
            raw=p.read_bytes(); original[p]=raw; new=raw
            for n in NAMES:
                # Explicit paths and qualified mock module names.
                new=re.sub(rb'(?<![\w/])'+n.encode()+rb'\.py(?=[\'\"])',b'managers/'+n.encode()+b'.py',new)
                new=new.replace(('anim_reference_tool.'+n).encode(),('anim_reference_tool.managers.'+n).encode())
            if p.name=='integration_smoke.py':
                old=b'project_io.__package__.rsplit(".", 1)[0] + ".timeline_manager"'
                if new.count(old)!=1: fail('Unexpected integration smoke timeline lookup')
                new=new.replace(old,b'project_io.__package__.rsplit(".", 1)[0] + ".managers.timeline_manager"')
            if p.name=='test_bridge_mock.py':
                for n in NAMES:
                    new=new.replace(("('"+n+"',").encode(),("('managers."+n+"',").encode())
                anchor=b"sys.modules['anim_reference_tool.operators']=ops_pkg"
                if new.count(anchor)!=1: fail('Unexpected bridge mock package setup')
                eol=b'\r\n' if b'\r\n' in new else b'\n'
                new=new.replace(anchor,anchor+eol+eol.join((b"managers_pkg=ModuleType('anim_reference_tool.managers')",b"managers_pkg.__path__=[str(ROOT/'managers')]",b"sys.modules['anim_reference_tool.managers']=managers_pkg")))
            if new!=raw: put(p,new)
    # Restrict dirty-file checks to source and test/tool paths, ignoring cache.
    dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no','--',str(BASE),'tests','tools'],text=True)
    dirty=[x for x in dirty.splitlines() if '__pycache__' not in x and not x.endswith(('.pyc','.pyo'))]
    if dirty: fail('Commit or stash tracked source/test changes first:\n'+'\n'.join(dirty))
    for p in removes | (set(writes)&set(original)):
        subprocess.run(['git','ls-files','--error-unmatch','--',p.as_posix()],check=True,stdout=subprocess.DEVNULL)
    for p in writes:
        if p not in original and p.exists(): fail('Destination exists: '+str(p))
    print('R-3 planned writes:'); print('\n'.join('  '+str(p) for p in sorted(writes)))
    print('Old paths removed:'); print('\n'.join('  '+str(p) for p in sorted(removes)))
    if args.check:
        print('PASS: preflight and Python syntax; no files modified.'); return
    created=[]; touched=[]
    try:
        (BASE/'managers').mkdir()
        for p,data in writes.items():
            (touched if p in original else created).append(p); p.write_bytes(data)
        for p in removes:
            touched.append(p); p.unlink()
    except Exception:
        for p in touched: p.write_bytes(original[p])
        for p in created: p.unlink(missing_ok=True)
        (BASE/'managers').rmdir(); raise
    print('PASS: R-3 applied. Run regression tests before committing.')

if __name__=='__main__': main()
