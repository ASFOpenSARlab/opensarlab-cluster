
import sys
import pathlib
import argparse

import yaml
from jinja2 import Environment, FileSystemLoader

from opensarlab.utils.custom_filters import regex_replace

env = Environment(
    loader=FileSystemLoader(pathlib.Path().parent),
    autoescape=True
)

env.filters['regex_replace'] = regex_replace

def main(config, output_file, region_name, account_id):
    with open(config, "r") as infile, open(output_file, 'w') as outfile:
        yaml_config = yaml.safe_load(infile)

        template = env.get_template("templates/aws-auth-cm.yaml.jinja")
        outfile.write(template.render(opensarlab=yaml_config, region_name=region_name, account_id=account_id ))

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    parser.add_argument('--output_file', default=None)
    parser.add_argument('--region_name', default=None)
    parser.add_argument('--account_id', default=None)
    args = parser.parse_args()

    main(args.config, args.output_file, args.region_name, args.account_id)
