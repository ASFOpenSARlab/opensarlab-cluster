
import pathlib
import argparse

import yaml
from jinja2 import Environment, FileSystemLoader

from utils.custom_filters import regex_replace

def main(config, work_dir):

    work_dir = pathlib.Path(work_dir).absolute().resolve()

    env = Environment(
        loader=FileSystemLoader(work_dir),
        autoescape=True
    )
    env.filters['regex_replace'] = regex_replace

    with open(config, "r") as infile:
        yaml_config = yaml.safe_load(infile)

    # 1_service_creds.py
    template_file = work_dir / '1_service_creds.py.jinja'
    output_file = work_dir / '1_service_creds.py'
    print(f"Rendering {template_file} as {output_file}")

    with open(output_file, 'w') as outfile:
        template = env.get_template(template_file.name)
        outfile.write(template.render(yaml_config=yaml_config))

    # 3_profiles.py
    template_file = work_dir / '3_profiles.py.jinja'
    output_file = work_dir / '3_profiles.py'
    print(f"Rendering {template_file} as {output_file}")

    with open(output_file, 'w') as outfile:
        template = env.get_template(template_file.name)
        outfile.write(template.render(yaml_config=yaml_config))

    # Any other files in config.d that need to be rendered

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    parser.add_argument('--work_dir', default=None)
    args = parser.parse_args()

    main(args.config, args.work_dir)
