
from . import main_panel
from . import reference_editor
from . import viewer_panel


modules = (
    main_panel,
    reference_editor,
    viewer_panel,
)


def register():

    for module in modules:
        module.register()


def unregister():

    for module in reversed(modules):
        module.unregister()
