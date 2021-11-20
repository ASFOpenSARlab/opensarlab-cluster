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

def main(config):
    with open(config, "r") as infile:
        yaml_config = yaml.safe_load(infile)

    template = env.get_template('templates/cf-cognito.yaml.jinja')

    with open('lambda_handler.py', 'w') as outfile:
        outfile.write(template.render(opensarlab=yaml_config))

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    args = parser.parse_args()

    main(args.config)
