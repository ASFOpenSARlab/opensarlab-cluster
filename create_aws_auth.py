import sys
import pathlib

import yaml
from jinja2 import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader(pathlib.Path().parent),
    autoescape=True
)

# python3 create_aws_auth.py opensarlab.yaml templates/aws-auth-cm.yaml.jinja aws-auth-cm.yaml osl-cluster us-west-2
opensarlab_yaml_path = sys.argv[1]
template_path = sys.argv[2]
output_config_path = sys.argv[3]

cluster_name = sys.argv[4]
region_name = sys.argv[5]

with open(opensarlab_yaml_path, "r") as yaml_file, open(output_config_path, 'w') as output_file:
    yaml_config = yaml.safe_load(yaml_file)

    template = env.get_template(template_path)
    output_file.write(template.render(opensarlab=yaml_config, cluster_name=cluster_name, region_name=region_name))
