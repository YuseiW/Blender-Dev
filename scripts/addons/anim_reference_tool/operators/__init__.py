from . import image
from . import cut
from . import reference
from . import timeline


modules = (
    image,
    cut,
    reference,
    timeline,
)


def register():

    for module in modules:
        module.register()


def unregister():

    for module in reversed(modules):
        module.unregister()