
import sys
import pathlib
import re

import yaml
from jinja2 import Environment, FileSystemLoader, Template

env = Environment(
    loader=FileSystemLoader(pathlib.Path().parent),
    autoescape=True
)

opensarlab_yaml_path = sys.argv[1]
template_path = sys.argv[2]
output_config_path = sys.argv[3]

# Custom filter method
def regex_replace(s, find, replace):
    """A non-optimal implementation of a regex filter"""
    return re.sub(find, replace, s)

env.filters['regex_replace'] = regex_replace

def checks(yaml_config):
    all_node_names = []
    for nodes in yaml_config['nodes']:
        all_node_names.append(nodes['name'])

    required_fields = ['name', 'description', 'image_name', 'image_tag', 'node_name', 'storage_capacity']
    for profile in yaml_config['profiles']:
        # Check to see if all required fields are present.
        for required in required_fields:
            if required not in profile.keys():
                raise Exception(f"Not all required fields found for profile '{ profile['name'] }'. Must have {required_fields}.")

        # Check to see if node_names are valid
        if profile['node_name'] not in all_node_names:
            raise Exception(f"Node name '{profile['node_name']}'' is not valid for profile '{ profile['name'] }'. Must be one of '{all_node_names}'.")

with open(opensarlab_yaml_path, "r") as yaml_file, open(template_path, "r") as template_file, open(output_config_path, 'w') as output_file:
    yaml_config = yaml.safe_load(yaml_file)

    checks(yaml_config)

    template = Template(template_file.read())
    output_file.write(template.render(profiles=yaml_config['profiles']))
