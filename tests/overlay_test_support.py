import importlib.util
from pathlib import Path
import sys
import types

ADDON = Path(__file__).resolve().parents[1] / "scripts/addons/anim_reference_tool/managers"

class FakeImage(dict):
    def __init__(self, path):
        super().__init__()
        self.filepath = path
        self.name = ''
        self.users = 0

class FakeImageStore(list):
    def __init__(self):
        super().__init__()
        self.load_count = 0
    def load(self, path, check_existing=False):
        assert check_existing is False
        self.load_count += 1
        result = FakeImage(path)
        self.append(result)
        return result
    def remove(self, item):
        assert item.users == 0
        super().remove(item)

class FakeSlot:
    def __init__(self):
        self._image = None
        self.alpha = 1.0
    def as_pointer(self):
        return id(self)
    @property
    def image(self):
        return self._image
    @image.setter
    def image(self, value):
        if self._image is not None:
            self._image.users -= 1
        self._image = value
        if value is not None:
            value.users += 1

class FakeSlots(list):
    def new(self):
        slot = FakeSlot()
        self.append(slot)
        return slot
    def remove(self, slot):
        slot.image = None
        super().remove(slot)

class FakeCamera(dict):
    def __init__(self):
        super().__init__()
        self.background_images = FakeSlots()
        self.show_background_images = False
    def as_pointer(self):
        return id(self)

class FakeScene(dict):
    def __init__(self, cam, project):
        super().__init__()
        self.camera = types.SimpleNamespace(type='CAMERA', data=cam)
        self.animref_project = project
        self.animref_overlay_enabled = False
        self.animref_overlay_opacity = 0.5
        self.frame_current = 1
    def as_pointer(self):
        return id(self)

def mock_blender():
    bpy = types.ModuleType('bpy')
    bpy.path = types.SimpleNamespace(abspath=lambda path: path)
    bpy.data = types.SimpleNamespace(images=FakeImageStore(), cameras=[], window_managers=[], scenes=[])
    bpy.types = types.SimpleNamespace(Scene=type('BlenderScene', (), {}))
    props = types.ModuleType('bpy.props')
    props.BoolProperty = lambda **kw: kw
    props.FloatProperty = lambda **kw: kw
    bpy.props = props
    sys.modules['bpy'] = bpy
    sys.modules['bpy.props'] = props
    pkg = types.ModuleType('phase_v4_fake_pkg')
    pkg.__path__ = [str(ADDON)]
    sys.modules[pkg.__name__] = pkg
    timeline = types.ModuleType('phase_v4_fake_pkg.timeline_manager')
    def resolve(project, cut, category, frame):
        items = cut.categories.get(category, [])
        ref = next((r for r in items if r.start <= frame <= r.end), None)
        asset = next((a for a in project.images if ref and a.uid == ref.image_id), None)
        return (ref, asset, ref.start if ref else None, ref.end if ref else None)
    timeline.resolve_reference_at_frame = resolve
    sys.modules[timeline.__name__] = timeline
    spec = importlib.util.spec_from_file_location('phase_v4_fake_pkg.camera_overlay_manager', ADDON/'camera_overlay_manager.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return bpy, mod
