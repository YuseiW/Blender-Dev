bl_info = {
    "name": "Animation Reference Tool",
    "author": "Yusei Watanabe",
    "version": (0, 1, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > AnimRef",
    "description": "Animation reference image management tool",
    "category": "Animation",
}


from . import properties
from . import operators
from . import ui
from . import timeline_manager


def register():

    properties.register()

    operators.register()

    ui.register()

    timeline_manager.register_handlers()


def unregister():

    timeline_manager.unregister_handlers()

    ui.unregister()

    operators.unregister()

    properties.unregister()