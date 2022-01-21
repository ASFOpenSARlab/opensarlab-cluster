
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
        'az_suffix'
    ]
    optional_fields = [
        'ical_url',
        'user_whitelist_bucket',
        'user_whitelist_csv'
    ]

    for required in required_fields:
        if required not in params.keys():
            raise Exception(f"Not all required fields found for parameters. Must have '{required}'.")

    for optional in optional_fields:
        if optional in params.keys():
            print(f"Optional field '{optional}' found.")

def check_nodes(config):
    required_fields = [
        'name',
        'instance',
        'min_number',
        'max_number',
        'node_policy'
    ]
    optional_fields = [
        'root_volume_size'
    ]
    for nodes in config['nodes']:
        # Check to see if all required fields are present.
        for required in required_fields:
            if required not in nodes.keys():
                raise Exception(f"Not all required fields found for profile '{ nodes['name'] }'. Must have '{required}'.")

        if not nodes['name'].isalnum():
            raise Exception(f"{nodes['name']} is not pure alphanumeric (no spaces, underscores, special characters).")

        for optional in optional_fields:
            if optional in nodes.keys():
                print(f"Optional field '{optional}' found.")
                if optional == 'root_volume_size':
                    value = int(nodes['root_volume_size'])
                    if value < 1:
                        raise Exception("root_volume_size has value of {value} and is less than 1 GiB")
                    elif value > 16345:
                        raise Exception("root_volume_size has value of {value} and is greater than 16345 GiB")

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
    optional_fields = [
        'hook_script',
        'memory_guarantee',
        'memory_limit',
        'cpu_guarantee',
        'cpu_limit',
        'delete_user_volumes',
        'classic'
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
