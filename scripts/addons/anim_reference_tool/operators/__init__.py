
from . import image
from . import cut
from . import reference
from . import timeline
from . import project
from . import viewer


modules = (
    image,
    cut,
    reference,
    timeline,
    project,
    viewer,
)


def register():
    for module in modules:
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()
