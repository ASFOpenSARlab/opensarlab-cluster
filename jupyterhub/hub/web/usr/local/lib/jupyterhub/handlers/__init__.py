from . import base
from . import metrics
from . import pages
from . import alive
from . import possible_profiles
from .base import *

# Importing groups above and adding to the handler is customized. 
# This will need to be watched closely on JupyterHub upgrades.
default_handlers = []
for mod in (base, pages, metrics, alive, possible_profiles):
    default_handlers.extend(mod.default_handlers)
