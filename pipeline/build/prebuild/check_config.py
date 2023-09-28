
import argparse
import re

import yaml

def check_parameters(config):

    params = config['parameters']
    print(params)

    # Check to see if all required fields are present.
    required_fields = [
        'code_commit_repo_name',
        'code_commit_branch_name',
        'lab_short_name',
        'cost_tag_key',
        'cost_tag_value',
        'admin_user_name',
        'certificate_arn',
        'container_namespace',
        'lab_domain',
        'portal_domain',
        'az_suffix',
        'days_till_volume_deletion',
        'days_till_snapshot_deletion',
        'days_after_server_stop_till_warning_email',
        'days_after_server_stop_till_deletion_email',
        'utc_hour_of_day_snapshot_cron_runs',
        'utc_hour_of_day_volume_cron_runs'
    ]

    optional_fields = []

    for required in required_fields:
        if required not in params.keys():
            raise Exception(f"Not all required fields found for parameters. Must have '{required}'.")

        if required == 'days_till_volume_deletion':
            value = params['days_till_volume_deletion']
            if type(value) != int:
                    raise Exception(f"Value for 'days_till_volume_deletion' is '{ params['days_till_volume_deletion'] }' and must be an integer.")
            value = int(value)
            if value < 0:
                raise Exception(f"Value for 'days_till_volume_deletion' is '{ params['days_till_volume_deletion'] }' and must be greater than zero.")

        elif required == 'days_till_snapshot_deletion':
            value = params['days_till_snapshot_deletion']
            if type(value) != int:
                raise Exception(f"Value for 'days_till_snapshot_deletion' is '{ params['days_till_snapshot_deletion'] }' and must be an integer.")
            value = int(value)
            if value < 0:
                raise Exception(f"Value for 'days_till_snapshot_deletion' is '{ params['days_till_snapshot_deletion'] }' and must be greater than zero.")

        elif required == 'days_after_server_stop_till_warning_email':
            value = params['days_after_server_stop_till_warning_email']
            if value is None:
                raise Exception(f"Value for 'days_after_server_stop_till_warning_email' is '{ params['days_after_server_stop_till_warning_email'] }' and must be an integer or comma-seperated list of integers.")
            value = str(value)
            for i in value.split(','):
                try:
                    _  = int(i)
                except Exception:
                    raise Exception(f"Value for 'days_after_server_stop_till_warning_email' is '{ params['days_after_server_stop_till_warning_email'] }' and must be an integer or comma-seperated list of integers.")

        elif required == 'days_after_server_stop_till_deletion_email':
            value = params['days_after_server_stop_till_deletion_email']
            if type(value) != int:
                raise Exception(f"Value for 'days_after_server_stop_till_deletion_email' is '{ params['days_after_server_stop_till_deletion_email'] }' and must be an integer.")
            value = int(value)
            if value < 0:
                raise Exception(f"Value for 'days_after_server_stop_till_deletion_email' is '{ params['days_after_server_stop_till_deletion_email'] }' and must be greater than zero.")

        if required == 'portal_domain':
            value = params['portal_domain']

            pattern = r"^http://|https://"
            results = re.search(pattern, value)
            if not results:
                raise Exception(f"Missing http:// or https:// in url '{value}'")

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

def check_service_accounts(config):
    for sa in config.get('service_accounts', ''):
        try:
            name = sa['name']
            _ = sa['namespace']
            _ = sa['permissions']
        except Exception as e:
            raise Exception(f"Service Account '{sa}' is malformed.")

        # The name of the Service Account needs to satisfy some requirements.
        # a lowercase RFC 1123 subdomain must consist of lower case alphanumeric characters, '-' or '.', and must start and end with an alphanumeric character
        regex = '^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$'
        pattern = re.compile(regex)
        if not pattern.match(name):
            raise Exception(f"Service Account {name} is not subdomain url compatible.")

def check_profiles(config):
    all_node_names = []
    for nodes in config['nodes']:
        all_node_names.append(nodes['name'])

    all_service_accounts = []
    for sa in config.get('service_accounts', ''):
        all_service_accounts.append(sa['name'])

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
        'classic',
        'default',
        'service_account'
    ]

    for profile in config['profiles']:
        # Check to see if all required fields are present.
        for required in required_fields:
            if required not in profile.keys():
                raise Exception(f"Not all required fields found for profile '{ profile['name'] }'. Must have {required}.")

        # Check to see if node_names are valid
        if profile['node_name'] not in all_node_names:
            raise Exception(f"Node name '{profile['node_name']}'' is not valid for profile '{ profile['name'] }'. Must be one of '{all_node_names}'.")

        # Check to see if service_account names are valid
        service_account_name = profile.get('service_account', '')
        if service_account_name and service_account_name not in all_service_accounts:
            raise Exception(f"Service account name '{profile['service_account']}' is not valid for profile '{ profile['name'] }'. Must be one of '{all_service_accounts}'.")

def main(config):
    with open(config, "r") as infile:
        yaml_config = yaml.safe_load(infile)

    check_parameters(yaml_config)
    check_nodes(yaml_config)
    check_service_accounts(yaml_config)
    check_profiles(yaml_config)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    args = parser.parse_args()

    main(args.config)
