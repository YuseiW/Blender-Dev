"""Legacy Image Editor retirement: no Blender or Qt required."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import sys
import types

ADDON = Path(__file__).resolve().parents[1] / 'scripts/addons/anim_reference_tool'

def main():
    tree = ast.parse((ADDON/'managers/timeline_manager.py').read_text(encoding='utf-8-sig'))
    names = {'calculate_reference_ranges','find_reference_at_frame','resolve_reference_at_frame','sync_reference_display','on_frame_change'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names
    for n in nodes:
        n.decorator_list = []
    forbidden = {'find_viewer_window','load_blender_image','show_image_in_editors','clear_reference_images_in_editors','iter_target_image_areas'}
    assert not any(isinstance(n, ast.Name) and n.id in forbidden for n in ast.walk(tree))
    assert not any(isinstance(n, ast.ImportFrom) and n.module in {'viewer_manager','image_manager'} for n in ast.walk(tree))
    calls = []
    overlay = types.ModuleType('fake.camera_overlay_manager')
    overlay.frame_changed = lambda scene: calls.append(scene)
    pkg = types.ModuleType('fake'); pkg.__path__ = []
    scope = {'__package__':'fake', 'get_reference_collection':lambda c,k:c.refs, 'find_image_by_uid':lambda p,u:next((a for a in p.images if a.uid==u),None)}
    with patch.dict(sys.modules, {'fake':pkg,'fake.camera_overlay_manager':overlay}):
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])), '<timeline>', 'exec'),scope)
        ref = NS(uid='r', image_id='a', duration=8)
        asset = NS(uid='a')
        cut = NS(timeline_start=10,refs=[ref])
        project = NS(cuts=[cut],active_cut_index=0,active_category='STORYBOARD',images=[asset],auto_sync=True)
        scene = NS(animref_project=project,frame_current=10)
        sync = scope['sync_reference_display']
        assert sync(scene)==dict(status='OK',reference=ref,image_asset=asset,frame_start=10,frame_end=17)
        scene.frame_current=17; assert sync(scene)['status']=='OK'
        scene.frame_current=18; assert sync(scene)['status']=='NO_REFERENCE'
        scene.frame_current=10; project.images=[]; assert sync(scene)['status']=='MISSING_IMAGE_ASSET'
        project.images=[asset]; project.active_cut_index=-1; assert sync(scene)['status']=='INVALID_CUT'
        project.active_cut_index=0; project.cuts=[]; assert sync(scene)['status']=='NO_CUT'
        project.cuts=[cut]
        scope['on_frame_change'](scene); assert calls==[scene]
        project.auto_sync=False; scope['on_frame_change'](scene); assert calls==[scene]
        scope['on_frame_change'](NS()); assert calls==[scene]
    for rel, retired in [('operators/__init__.py','viewer'),('ui/__init__.py','viewer_panel')]:
        t=ast.parse((ADDON/rel).read_text(encoding='utf-8-sig'))
        assert not any(isinstance(n,ast.ImportFrom) and any(a.name==retired for a in n.names) for n in ast.walk(t))
        assert not any(isinstance(n,ast.Name) and n.id==retired for n in ast.walk(t))
    print('PASS: legacy sync retired; frame resolution, overlay handler and registration contracts')

if __name__=='__main__': main()
