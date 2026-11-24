"""Minimal fake-bpy integration test; not a substitute for Blender 5.2 testing."""
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
import importlib.util

ROOT = Path(__file__).resolve().parents[1]/'scripts/addons/anim_reference_tool'

class FakePtr:
    def __init__(self, value): self.ptr=value
    def as_pointer(self): return self.ptr

class FakeRef:
    def __init__(self,uid,img, duration=8,instruction=''):
        self.uid=uid;self.image_id=img;self.duration=duration;self.instruction=instruction

class FakeCut:
    def __init__(self):
        self.uid='cut1';self.name='C001';self.timeline_start=1
        self.storyboard_items=[FakeRef('ref1','img1')]
        self.layout_items=[];self.keyframe_items=[]

class FakeProject:
    def __init__(self):
        self.project_name='Test';self.active_category='STORYBOARD';self.auto_sync=False
        self.active_cut_index=0
        self.cuts=[FakeCut()]
        self.images=[SimpleNamespace(uid='img1',name='one.png',filepath='/tmp/one.png')]

project=FakeProject()
scene=SimpleNamespace(name='Scene', frame_current=1,animref_project=project)
window=FakePtr(321);window.scene=scene
wm=SimpleNamespace(windows=[window])
class FakeTimers:
    def is_registered(self, f): return False
bpy=ModuleType('bpy');bpy.context=SimpleNamespace(window_manager=wm)
bpy.types=SimpleNamespace(Operator=type('Operator',(),{}))
bpy.app=SimpleNamespace(timers=FakeTimers(), background=False)
bpy.path=SimpleNamespace(abspath=lambda s:s)
sys.modules['bpy']=bpy

pkg=ModuleType('anim_reference_tool');pkg.__path__=[str(ROOT)]
ops_pkg=ModuleType('anim_reference_tool.operators');ops_pkg.__path__=[str(ROOT/'operators')]
sys.modules['anim_reference_tool']=pkg
sys.modules['anim_reference_tool.operators']=ops_pkg
managers_pkg=ModuleType('anim_reference_tool.managers')
managers_pkg.__path__=[str(ROOT/'managers')]
sys.modules['anim_reference_tool.managers']=managers_pkg
storage_pkg=ModuleType('anim_reference_tool.storage')
storage_pkg.__path__=[str(ROOT/'storage')]
sys.modules['anim_reference_tool.storage']=storage_pkg

# Stub dependencies that are irrelevant to snapshot/JSON dispatch
image=ModuleType('anim_reference_tool.managers.image_manager');image.add_image_asset=lambda p,path:(None,'NOT_FOUND')
reference=ModuleType('anim_reference_tool.managers.reference_manager')
reference.get_reference_collection=lambda cut,cat:getattr(cut,{'STORYBOARD':'storyboard_items','LAYOUT':'layout_items','KEYFRAME':'keyframe_items'}[cat])
def add_reference(cut,cat,img):
    coll=reference.get_reference_collection(cut,cat)
    r=FakeRef('ref'+str(len(coll)+1),img)
    coll.append(r);return r,'ADDED'
reference.add_reference=add_reference
reference.remove_reference=lambda cut,cat,i: (reference.get_reference_collection(cut,cat).pop(i) is not None)
def move_reference(cut,cat,i,delta):
    coll=reference.get_reference_collection(cut,cat)
    if not (0<=i+delta<len(coll)):return False
    coll[i],coll[i+delta]=coll[i+delta],coll[i];return True
reference.move_reference=move_reference
cutmod=ModuleType('anim_reference_tool.managers.cut_manager')
cutmod.add_cut=lambda p:p.cuts.append(FakeCut()) or p.cuts[-1]
cutmod.remove_cut=lambda p,i:False
io=ModuleType('anim_reference_tool.storage.project_io');io.save_project=lambda p,path:None;io.load_project=lambda p,path:None
timeline=ModuleType('anim_reference_tool.managers.timeline_manager');timeline.sync_reference_display=lambda s:None
for name,mod in [('managers.image_manager',image),('managers.reference_manager',reference),('managers.cut_manager',cutmod),('storage.project_io',io),('managers.timeline_manager',timeline)]:
    sys.modules['anim_reference_tool.'+name]=mod

# Import pure IPC and operator module with package-qualified name
for name,path in [('anim_reference_tool.manager_ipc', ROOT/'manager_ipc.py'),('anim_reference_tool.operators.manager_external',ROOT/'operators/manager_external.py')]:
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
bridge=sys.modules['anim_reference_tool.operators.manager_external']
bridge._source_window_pointer=321

def req(action,**args):
    return bridge._process_request({'action':action,'args':args,'expect_scene':'Scene'})

s=bridge._process_request({'action':'snapshot','args':{}})['state']
assert s['project']=='Test' and s['cuts'][0]['categories']['STORYBOARD'][0]['start']==1
assert s['images'][0]['categories']==['STORYBOARD']
req('add_reference',image_id='img1')
assert len(project.cuts[0].storyboard_items)==2
req('update_reference',index=1,uid='ref2',duration=12,instruction='二枚目')
s=req('snapshot')['state']
assert s['cuts'][0]['categories']['STORYBOARD'][1]['start']==9
assert s['cuts'][0]['categories']['STORYBOARD'][1]['end']==20
assert s['cuts'][0]['categories']['STORYBOARD'][1]['instruction']=='二枚目'
req('move_reference',index=1,uid='ref2',direction=-1)
assert project.cuts[0].storyboard_items[0].uid=='ref2'
req('remove_reference',index=0,uid='ref2')
assert len(project.cuts[0].storyboard_items)==1
req('select_category',category='LAYOUT')
assert req('snapshot')['state']['active_category']=='LAYOUT'
try:
    bridge._process_request({'action':'add_cut','args':{},'expect_scene':'Other'})
except ValueError:
    pass
else:
    raise AssertionError('Cross-scene mutation must fail')
print('=== MOCK BLENDER BRIDGE TESTS PASSED ===')
