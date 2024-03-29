
import sys
import pathlib
import argparse

import yaml
from jinja2 import Environment, FileSystemLoader

from utils.custom_filters import regex_replace

def main(config, output_file, template_path, region_name, cluster_name):

    template_path = pathlib.Path(template_path)

    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        autoescape=True
    )
    env.filters['regex_replace'] = regex_replace

    with open(config, "r") as infile, open(output_file, 'w') as outfile:
        yaml_config = yaml.safe_load(infile)

        template = env.get_template(template_path.name)
        outfile.write(template.render(parameters=yaml_config['parameters'], region_name=region_name, cluster_name=cluster_name ))

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    parser.add_argument('--output_file', default=None)
    parser.add_argument('--template_path', default=None)
    parser.add_argument('--region_name', default=None)
    parser.add_argument('--cluster_name', default=None)

    args = parser.parse_args()

    main(args.config, args.output_file, args.template_path, args.region_name, args.cluster_name)
