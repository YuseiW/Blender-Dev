
from . import image
from . import cut
from . import reference
from . import timeline
from . import project


modules = (
    image,
    cut,
    reference,
    timeline,
    project,
)


def register():
    for module in modules:
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()
