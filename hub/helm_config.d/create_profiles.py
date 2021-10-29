
import os

import yaml
from jinja2 import Template
from jinja2.filters import FILTERS, pass_environment

@pass_environment
def space_to_underscore(enviroment, value):
    return str(value).replace(' ', '_')

FILTERS["space_to_underscore"] = space_to_underscore

#read your yaml file
with open("profiles.yaml", "r") as yam, open("profiles.py.template", "r") as tem, open("profiles.py", 'w') as pro:
    profiles = yaml.safe_load(yam)
    template = Template(tem.read())
    pro.write(template.render(profiles=profiles))
