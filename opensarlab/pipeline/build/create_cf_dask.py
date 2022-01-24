import pathlib
import argparse

import yaml
from jinja2 import Environment, FileSystemLoader

from utils.custom_filters import regex_replace

def main(config, output_file, template_path):

    template_path = pathlib.Path(template_path)

    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        autoescape=True
    )
    env.filters['regex_replace'] = regex_replace

    with open(config, "r") as infile, open(output_file, 'w') as outfile:
        yaml_config = yaml.safe_load(infile)

        template = env.get_template(template_path.name)
        outfile.write(template.render(opensarlab=yaml_config))

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    parser.add_argument('--output_file', default=None)
    parser.add_argument('--template_path', default=None)
    args = parser.parse_args()

    main(args.config, args.output_file, args.template_path)
