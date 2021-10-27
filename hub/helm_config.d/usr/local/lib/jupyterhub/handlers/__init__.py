from . import base
from . import login
from . import metrics
from . import pages
from . import groups
from .base import *
from .login import *

# Importing groups above and adding to the handler is customized. 
# This will need to be watched closely on JupyterHub upgrades.
default_handlers = []
for mod in (base, pages, login, metrics, groups):
    default_handlers.extend(mod.default_handlers)
