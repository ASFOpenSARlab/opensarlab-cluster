
import yaml
from jinja2 import Template
from jinja2.filters import FILTERS, pass_environment

@pass_environment
def space_to_underscore(enviroment, value):
    return str(value).replace(' ', '_')

FILTERS["space_to_underscore"] = space_to_underscore

#read your yaml file
with open("profiles.yaml", "r") as yam, open("profiles.py.template", "r") as tem, open("./hub/helm_config.d/profiles.py", 'w') as pro:
    profiles = yaml.safe_load(yam)

    all_node_names = []
    for nodes in profiles['nodes']:
        all_node_names.append(nodes['node_name'])

    required_fields = ['name', 'description', 'image_name', 'image_tag', 'node_name', 'storage_capacity']
    for profile in profiles['profiles']:
        # Check to see if all required fields are present.
        for required in required_fields:
            if required not in profile.keys():
                raise Exception(f"Not all required fields found for profile '{ profile['name'] }'. Must have {required_fields}.")

        # Check to see if node_names are valid
        if profile['node_name'] not in all_node_names:
            raise Exception(f"Node name '{profile['node_name']}'' is not valid for profile '{ profile['name'] }'. Must be one of '{all_node_names}'.")


    template = Template(tem.read())
    pro.write(template.render(profiles=profiles))
