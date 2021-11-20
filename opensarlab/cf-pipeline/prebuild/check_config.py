
import argparse

import yaml

def check_parameters(config):

    params = config['parameters']
    print(params)

    # Check to see if all required fields are present.
    required_fields = [
        'code_commit_repo_name',
        'code_commit_branch_name',
        'cost_tag_key',
        'cost_tag_value',
        'admin_user_name',
        'admin_email_address',
        'admin_email_address_sns_arn',
        'certificate_arn',
        'container_namespace',
        'deployment_url',
        'ical_url',
        'az_suffix'
    ]
    for required in required_fields:
        if required not in params.keys():
            raise Exception(f"Not all required fields found for parameters. Must have '{required}'.")

def check_nodes(config):
    required_fields = [
        'name',
        'instance',
        'min_number',
        'max_number',
        'node_policy'
    ]
    for nodes in config['nodes']:
        # Check to see if all required fields are present.
        for required in required_fields:
            if required not in nodes.keys():
                raise Exception(f"Not all required fields found for profile '{ nodes['name'] }'. Must have '{required}'.")

def check_profiles(config):
    all_node_names = []
    for nodes in config['nodes']:
        all_node_names.append(nodes['name'])

    required_fields = [
        'name',
        'description',
        'image_name',
        'image_tag',
        'node_name',
        'storage_capacity'
    ]
    for profile in config['profiles']:
        # Check to see if all required fields are present.
        for required in required_fields:
            if required not in profile.keys():
                raise Exception(f"Not all required fields found for profile '{ profile['name'] }'. Must have {required}.")

        # Check to see if node_names are valid
        if profile['node_name'] not in all_node_names:
            raise Exception(f"Node name '{profile['node_name']}'' is not valid for profile '{ profile['name'] }'. Must be one of '{all_node_names}'.")

def main(config):
    with open(config, "r") as infile:
        yaml_config = yaml.safe_load(infile)

    check_parameters(yaml_config)
    check_nodes(yaml_config)
    check_profiles(yaml_config)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    args = parser.parse_args()

    main(args.config)
