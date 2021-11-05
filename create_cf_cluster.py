import sys
import pathlib
import re

import yaml
from jinja2 import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader(pathlib.Path(__file__).parent),
    autoescape=True
)

# python3 create_infrastructure.py opensarlab.yaml templates/cf-cluster.yaml.jinja cf-cluster.yaml
opensarlab_yaml_path = sys.argv[1]
template_path = sys.argv[2]
output_config_path = sys.argv[3]

# Custom filter method
def regex_replace(s, find, replace):
    """A non-optimal implementation of a regex filter"""
    return re.sub(find, replace, s)

env.filters['regex_replace'] = regex_replace

with open(opensarlab_yaml_path, "r") as yaml_file, open(output_config_path, 'w') as output_file:
    yaml_config = yaml.safe_load(yaml_file)

    template = env.get_template(template_path)
    output_file.write(template.render(opensarlab=yaml_config))
