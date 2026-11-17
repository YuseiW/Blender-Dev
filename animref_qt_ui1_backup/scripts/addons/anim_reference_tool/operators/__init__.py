
from . import image
from . import cut
from . import reference
from . import timeline
from . import project
from . import manager_workspace
from . import viewer


modules = (
    image,
    cut,
    reference,
    timeline,
    project,
    manager_workspace,
    viewer,
)


def register():
    for module in modules:
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()
