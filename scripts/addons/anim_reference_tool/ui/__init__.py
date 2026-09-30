from . import main_panel
from . import reference_editor


modules = (
    main_panel,
    reference_editor,
)


def register():

    for module in modules:
        module.register()


def unregister():

    for module in reversed(modules):
        module.unregister()