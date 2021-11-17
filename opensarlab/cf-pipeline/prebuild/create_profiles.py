
import pathlib
import argparse

import yaml
from jinja2 import Environment, FileSystemLoader

from opensarlab.utils.custom_filters import regex_replace

env = Environment(
    loader=FileSystemLoader(pathlib.Path(__file__).parent),
    autoescape=True
)

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

def main(config, output_file):
    with open(config, "r") as infile, open(output_file, 'w') as outfile:
        yaml_config = yaml.safe_load(infile)

        checks(yaml_config)

        template = env.get_template('templates/profiles.py.jinja')
        outfile.write(template.render(profiles=yaml_config['profiles']))

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    parser.add_argument('--output_file', default=None)
    args = parser.parse_args()

    main(args.config, args.output_file)
