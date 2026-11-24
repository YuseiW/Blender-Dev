"""AnimRef V-5: read-only diagnostic snapshot for Blender 5.2.

Run with Blender Text Editor > Run Script. No Blender datablocks are modified.
Paths are reduced to basenames; the script does not write a report to disk.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path


def _active_camera_data(scene):
    obj = getattr(scene, 'camera', None)
    if obj is None or getattr(obj, 'type', None) != 'CAMERA':
        return None
    return obj.data


def _image_state(scene, bpy):
    project = getattr(scene, 'animref_project', None)
    if project is None:
        return {'error': 'AnimRef properties not registered'}
    images = {}
    missing = []
    for image in project.images:
        try:
            path = bpy.path.abspath(image.filepath) if image.filepath else ''
            exists = bool(path and Path(path).is_file())
        except (OSError, TypeError, ValueError):
            exists = False
            path = ''
        images[image.uid] = exists
        if not exists:
            missing.append({'image_uid': image.uid[:8], 'filename':Path(path).name})
    cut = None
    index = project.active_cut_index
    if 0 <= index < len(project.cuts):
        cut = project.cuts[index]
    return {
        'project': project.project_name,
        'frame': scene.frame_current,
        'active_cut': cut.name if cut else None,
        'category': project.active_category,
        'auto_sync': bool(project.auto_sync),
        'overlay_enabled': bool(getattr(scene, 'animref_overlay_enabled', False)),
        'overlay_opacity': round(float(getattr(scene, 'animref_overlay_opacity', 0.5)), 3),
        'cut_count': len(project.cuts),
        'image_count': len(project.images),
        'missing_images': missing[:30],
        'missing_images_total': len(missing),
    }


def collect():
    import bpy
    scenes = list(bpy.data.scenes)
    key = '_animref_v4_scene_token'
    owner_key = '_animref_v4_overlay_owner'
    tokens = [sc.get(key) for sc in scenes if sc.get(key)]
    token_duplicates = sorted(t for t,n in Counter(tokens).items() if n>1)
    scene_out = []
    camera_usage = {}
    for sc in scenes:
        cam = _active_camera_data(sc)
        if cam is not None:
            camera_usage.setdefault(cam.as_pointer(), []).append(sc.name)
        item = {'scene': sc.name, 'camera':cam.name if cam else None,
                'token_present':bool(sc.get(key))}
        item.update(_image_state(sc,bpy))
        scene_out.append(item)
    camera_out = []
    all_tokens = set(tokens)
    orphan_count = 0
    for cam in bpy.data.cameras:
        owners = []
        user_count = 0
        for slot in cam.background_images:
            image = getattr(slot, 'image', None)
            owner = image.get(owner_key) if image is not None else None
            if isinstance(owner, str) and len(owner) == 32:
                owners.append(owner)
                if owner not in all_tokens:
                    orphan_count += 1
            else:
                user_count += 1
        if owners or user_count or cam.as_pointer() in camera_usage:
            camera_out.append({
                'camera':cam.name,
                'scene_users':camera_usage.get(cam.as_pointer(),[]),
                'animref_slots':len(owners),
                'user_background_slots':user_count,
                'orphan_animref_slots':sum(x not in all_tokens for x in owners),
                'background_visible':bool(cam.show_background_images),
            })
    bridge = next((m for n,m in sys.modules.items() if n.endswith('.operators.manager_external')),None)
    if bridge is not None:
        process = getattr(bridge, '_process', None)
        bridge_status = {'loaded':True,'qt_running':bool(process is not None and process.poll() is None),
                         'bridge_session':bool(getattr(bridge, '_session_dir', None))}
    else:
        bridge_status = {'loaded':False}
    return {
        'blender_version':'.'.join(map(str,bpy.app.version[:3])),
        'scene_count':len(scenes),
        'scenes':scene_out,
        'cameras':camera_out,
        'duplicate_scene_owner_tokens':len(token_duplicates),
        'shared_camera_count':sum(len(v)>1 for v in camera_usage.values()),
        'orphan_animref_slots':orphan_count,
        'bridge':bridge_status,
        'notes':['This script never edits Blender data',
                 'Camera data is shared if two Scenes have the same Camera datablock',
                 'Files are reported by basename, not by absolute path'],
    }


if __name__ == '__main__':
    print('===== AnimRef V-5 diagnostic (READ ONLY) =====')
    try:
        report=collect()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print('===== End AnimRef V-5 diagnostic =====')
    except Exception as exc:
        print('V-5 diagnostic FAILED:', type(exc).__name__, str(exc))
        raise
