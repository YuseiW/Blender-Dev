
from . import main_panel
from . import viewer_panel


modules = (
    main_panel,
    viewer_panel,
)


def register():

    for module in modules:
        module.register()


def unregister():

    for module in reversed(modules):
        module.unregister()
