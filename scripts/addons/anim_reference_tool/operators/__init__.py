
from . import image
from . import cut
from . import reference
from . import timeline
from . import project
from . import viewer
from . import manager_external


modules = (
    image,
    cut,
    reference,
    timeline,
    project,
    viewer,
    manager_external,
)


def register():
    for module in modules:
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()
