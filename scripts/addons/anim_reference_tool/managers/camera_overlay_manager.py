"""AnimRef V-4: camera-background reference overlay, owned by AnimRef only.

Blender/main-thread module. No Qt imports. The user's existing background-image
slots and images are never edited or deleted. The selected camera must be in
Camera View for its background to be visible (Numpad 0).
"""
from pathlib import Path
from uuid import uuid4

import bpy
from bpy.props import BoolProperty, FloatProperty

OWNER_KEY = "_animref_v4_overlay_owner"
TOKEN_KEY = "_animref_v4_scene_token"
OLD_VISIBILITY_KEY = "_animref_v4_previous_background_visibility"

# Runtime cache is not serialized; all owned layers can be rediscovered by token.
_RUNTIME = {}


def _token(scene, create=False):
    """Return a unique Scene ownership token.

    Blender copies custom ID properties when a Scene is duplicated. The older
    Scene (first in bpy.data.scenes) retains the original token; a copied Scene
    must not acquire its reference overlay or remove the original's layer.
    """
    token = scene.get(TOKEN_KEY)
    if token:
        first_owner = next(
            (other for other in bpy.data.scenes if other.get(TOKEN_KEY) == token),
            None,
        )
        if first_owner is not None and first_owner.as_pointer() != scene.as_pointer():
            token = None
    if not token and create:
        used = {other.get(TOKEN_KEY) for other in bpy.data.scenes}
        token = uuid4().hex
        while token in used:
            token = uuid4().hex
        scene[TOKEN_KEY] = token
    return token


def _owned(slot, token):
    image = getattr(slot, "image", None)
    return bool(token and image is not None and image.get(OWNER_KEY) == token)


def _camera(scene):
    obj = getattr(scene, "camera", None)
    return obj.data if obj is not None and obj.type == 'CAMERA' else None


def _scope(scene):
    project = scene.animref_project
    index = project.active_cut_index
    cut_id = project.cuts[index].uid if 0 <= index < len(project.cuts) else None
    cam = _camera(scene)
    return (cut_id, project.active_category,
            cam.as_pointer() if cam is not None else None)


def _redraw():
    for wm in bpy.data.window_managers:
        for win in wm.windows:
            for area in win.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()


def _any_owned(camera, token):
    return any(_owned(slot, token) for slot in camera.background_images)


def _any_animref_slot(camera):
    """Identify only image blocks tagged with an AnimRef V-4 UUID owner."""
    for slot in camera.background_images:
        image = getattr(slot, 'image', None)
        owner = image.get(OWNER_KEY) if image is not None else None
        if (isinstance(owner, str) and len(owner) == 32
                and all(char in '0123456789abcdef' for char in owner)):
            return True
    return False


def _remove_animref_slot(camera, slot):
    image = slot.image
    camera.background_images.remove(slot)
    if image is not None and image.users == 0:
        bpy.data.images.remove(image)


def _restore_visibility_if_empty(camera):
    if not _any_animref_slot(camera) and OLD_VISIBILITY_KEY in camera:
        camera.show_background_images = bool(camera[OLD_VISIBILITY_KEY])
        del camera[OLD_VISIBILITY_KEY]


def _retire_foreign_slots(camera, current_token):
    """A Camera datablock is shared by Scenes: only the active Scene owns it.

    Retire other AnimRef layers, *never* user background layers. Switching back
    to a Scene rebuilds its own layer from its own current frame and category.
    Two windows sharing one Camera datablock cannot show distinct overlays at
    the same instant; this is a Blender Camera-data limitation.
    """
    stale_tokens = set()
    removed = 0
    for slot in list(camera.background_images):
        image = getattr(slot, 'image', None)
        owner = image.get(OWNER_KEY) if image is not None else None
        if (isinstance(owner, str) and len(owner) == 32
                and all(char in '0123456789abcdef' for char in owner)
                and owner != current_token):
            stale_tokens.add(owner)
            _remove_animref_slot(camera, slot)
            removed += 1
    if stale_tokens:
        for other in bpy.data.scenes:
            if other.get(TOKEN_KEY) in stale_tokens:
                _RUNTIME.pop(other.as_pointer(), None)
    _restore_visibility_if_empty(camera)
    if removed:
        _redraw()
    return removed


def clear_overlay(scene, keep=None):
    """Remove *only* this Scene's AnimRef V-4 slots, keep other backgrounds."""
    token = _token(scene)
    if not token:
        _RUNTIME.pop(scene.as_pointer(), None)
        return 0
    keep_ptr = keep.as_pointer() if keep is not None else None
    count = 0
    for camera in bpy.data.cameras:
        for slot in list(camera.background_images):
            if not _owned(slot, token):
                continue
            if keep_ptr is not None and slot.as_pointer() == keep_ptr:
                continue
            _remove_animref_slot(camera, slot)
            count += 1
        # Other Scenes may still have an AnimRef layer on this shared Camera.
        _restore_visibility_if_empty(camera)
    if keep is None:
        _RUNTIME.pop(scene.as_pointer(), None)
    if count:
        _redraw()
    return count


def set_opacity(scene, fraction):
    """Opacity can change without re-reading or changing a held reference."""
    value = float(fraction)
    if not 0.0 <= value <= 1.0:
        raise ValueError("不透明度は0〜100%で指定してください")
    if abs(scene.animref_overlay_opacity - value) > 1e-6:
        scene.animref_overlay_opacity = value
    token = _token(scene)
    changed = False
    if token:
        for camera in bpy.data.cameras:
            for slot in camera.background_images:
                if _owned(slot, token) and abs(slot.alpha - value) > 1e-6:
                    slot.alpha = value
                    changed = True
    if changed:
        _redraw()
    return value


def _current_reference(scene):
    project = scene.animref_project
    index = project.active_cut_index
    if not 0 <= index < len(project.cuts):
        return None, None
    cut = project.cuts[index]
    # Reuse the same resolution method as Timeline/Qt Viewer.
    from .timeline_manager import resolve_reference_at_frame
    reference, asset, _, _ = resolve_reference_at_frame(
        project, cut, project.active_category, scene.frame_current
    )
    return reference, asset


def sync_overlay(scene, explicit=False):
    """Reconcile camera image to Viewer state.

    - auto_sync=True: follow current Timeline frame.
    - auto_sync=False: hold last slot unless Cut/Category/Camera changed.
    - explicit=True: force current frame (user refresh or changed selection).
    """
    key = scene.as_pointer()
    camera = _camera(scene)
    if not getattr(scene, 'animref_overlay_enabled', False):
        if camera is not None:
            _retire_foreign_slots(camera, None)
        clear_overlay(scene)
        return 'DISABLED'
    if camera is None:
        clear_overlay(scene)
        return 'NO_CAMERA'
    scope = _scope(scene)
    old = _RUNTIME.get(key)
    token = _token(scene, create=True)
    # In a shared-camera setup, a previous Scene's overlay must not leak into
    # the currently displayed Scene, even if that Scene has no valid reference.
    _retire_foreign_slots(camera, token)
    if (not explicit and not scene.animref_project.auto_sync and old
            and old.get('scope') == scope and _any_owned(camera, token)):
        set_opacity(scene, scene.animref_overlay_opacity)
        return 'HELD'

    ref, asset = _current_reference(scene)
    if ref is None:
        clear_overlay(scene)
        return 'NO_REFERENCE'
    if asset is None or not asset.filepath:
        clear_overlay(scene)
        return 'NO_ASSET'
    path = Path(bpy.path.abspath(asset.filepath)).expanduser()
    if not path.is_file():
        clear_overlay(scene)
        return 'MISSING_FILE'

    # Avoid loading a new Blender Image datablock for every Timeline tick.
    if (old and old.get('scope') == scope and old.get('ref_uid') == ref.uid
            and old.get('path') == str(path) and _any_owned(camera, token)):
        set_opacity(scene, scene.animref_overlay_opacity)
        return 'OK'

    image = None
    slot = None
    saved_visibility = False
    try:
        # A separate Image datablock is vital: never tag/delete a user image.
        image = bpy.data.images.load(str(path), check_existing=False)
        if image is None:
            raise RuntimeError("画像を読み込めません")
        # Do not inspect image.has_data; Blender loads pixel buffers lazily.
        image[OWNER_KEY] = token
        image.name = f"AnimRef Overlay | {path.name}"
        if OLD_VISIBILITY_KEY not in camera and not _any_owned(camera, token):
            camera[OLD_VISIBILITY_KEY] = bool(camera.show_background_images)
            saved_visibility = True
        slot = camera.background_images.new()
        slot.image = image
        slot.display_depth = 'FRONT'
        slot.show_on_foreground = True
        slot.frame_method = 'FIT'
        slot.alpha = float(scene.animref_overlay_opacity)
        slot.show_background_image = True
        camera.show_background_images = True
        # Old slot is removed only after new one is fully prepared.
        clear_overlay(scene, keep=slot)
        _RUNTIME[key] = {'scope': scope, 'ref_uid': ref.uid, 'path': str(path)}
        _redraw()
        return 'OK'
    except Exception:
        if slot is not None:
            camera.background_images.remove(slot)
        if image is not None and image.users == 0:
            bpy.data.images.remove(image)
        if saved_visibility and OLD_VISIBILITY_KEY in camera:
            camera.show_background_images = bool(camera[OLD_VISIBILITY_KEY])
            del camera[OLD_VISIBILITY_KEY]
        raise


def frame_changed(scene):
    """Called by Blender frame_change_post, including when Qt is closed."""
    if getattr(scene, 'animref_overlay_enabled', False) and scene.animref_project.auto_sync:
        return sync_overlay(scene, explicit=True)
    return 'NO_CHANGE'


def set_enabled(scene, enabled):
    if not isinstance(enabled, bool):
        raise ValueError("カメラ重畳はON/OFFで指定してください")
    previous = scene.animref_overlay_enabled
    scene.animref_overlay_enabled = enabled
    if not enabled:
        return sync_overlay(scene)
    try:
        return sync_overlay(scene, explicit=True)
    except Exception:
        scene.animref_overlay_enabled = previous
        raise


def register():
    bpy.types.Scene.animref_overlay_enabled = BoolProperty(
        name="AnimRef Camera Overlay", default=False,
        description="カメラビューにAnimRefの現在資料を重ねる",
    )
    bpy.types.Scene.animref_overlay_opacity = FloatProperty(
        name="AnimRef Overlay Opacity", default=0.5,
        min=0.0, max=1.0, subtype='FACTOR',
    )


def end_session():
    """Disable overlay for all Scenes and retire only AnimRef-owned slots."""
    for scene in bpy.data.scenes:
        if getattr(scene, 'animref_overlay_enabled', False):
            scene.animref_overlay_enabled = False
    for camera in bpy.data.cameras:
        _retire_foreign_slots(camera, None)
        _restore_visibility_if_empty(camera)
    _RUNTIME.clear()


def unregister():
    for scene in bpy.data.scenes:
        clear_overlay(scene)
    # Scenes may have been removed after their overlays were created. Sweep
    # only tagged AnimRef-owned layers; never delete user camera backgrounds.
    for camera in bpy.data.cameras:
        _retire_foreign_slots(camera, None)
        _restore_visibility_if_empty(camera)
    _RUNTIME.clear()
    del bpy.types.Scene.animref_overlay_enabled
    del bpy.types.Scene.animref_overlay_opacity
