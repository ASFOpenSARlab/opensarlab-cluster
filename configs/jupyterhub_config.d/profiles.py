from typing import List, Dict

import os

# Profile list programmatically
# Ideally, if/else statements based on permissions would determine the final choices.
# https://jupyterhub-kubespawner.readthedocs.io/en/latest/spawner.html#kubespawner.KubeSpawner
# Other singleuser server params can be taken from above to below as needed.

"""
To manually add some Groups and names to Groups, `kubectl` into the hub, python3 and

from jupyterhub import groups

g = groups.Groups()
g.add_group('general_cpu')
g.get_users_in_group('general_cpu')
g.add_user_to_group('emlundell_test1', 'general_cpu')
g.get_users_in_group('general_cpu')


The `server_type` found in the profiles (e.g. general_cpu_large) are defined in the cloudformation template.
"""

class NoProfileException(Exception):
    """No Profiles found"""

def profile_list_hook(spawner: c.Spawner) -> List[Dict]:

    try:
        from jupyterhub import groups as groups_py

        user_name = spawner.user.name

        groups = groups_py.Groups()
        group_list = groups.get_all_enabled_group_names_for_user(user_name=user_name)
        group_list.extend(groups.get_all_enabled_group_names_set_to_all_users())
        
        if not group_list:
            raise NoProfileException()

        print(f"Group list: {group_list}")

        profile_list = []

        # m5a.2xlarge: 8 cpus, 32 GiB RAM
        if 'SAR_1_-_Test' in group_list:
            image_url = f"{os.environ.get('OSL_IMAGE_REPO_URL')}/sar:e914cd7"
            profile = {
                'display_name': 'SAR 1 - Test',
                'description': 'Formerly the General CPU option. Contains basic SAR processing packages: ARIA, ISCE, MintPy, MapReady, TRAIN. CPU limit: 8. RAM limit: 16G. Storage: 500G.',
                'default': True,
                'kubespawner_override': {
                    'extra_labels': {
                        'server_type': 'sar_1'
                    },
                    'node_selector': {
                        'server_type': 'sar_1'
                    },
                    'image': image_url,
                    'lifecycle_hooks': {
                        "postStart": {
                            "exec": {
                                "command": ["/bin/sh", "-c", "/etc/jupyter-hooks/sar_test.sh"]
                            }
                        }
                    },
                    'args': [
                        "--NotebookApp.jinja_template_vars={'PROFILE_NAME':'SAR 1 - Test'}"
                    ],
                    'mem_limit': '16G', 
                    'mem_guarantee': '6G',
                    'storage_capacity': '500Gi', 
                    'delete_pvc': False
                }
            }
            profile_list.append(profile)

        # m5a.2xlarge: 8 cpus, 32 GiB RAM
        if 'SAR_1' in group_list:
            image_url = f"{os.environ.get('OSL_IMAGE_REPO_URL')}/sar:e914cd7"
            profile = {
                'display_name': 'SAR 1',
                'description': 'Formerly the General CPU option. Contains basic SAR processing packages: ARIA, ISCE, MintPy, MapReady, TRAIN. CPU limit: 8. RAM limit: 16G. Storage: 500G.',
                'default': True,
                'kubespawner_override': {
                    'extra_labels': {
                        'server_type': 'sar_1'
                    },
                    'node_selector': {
                        'server_type': 'sar_1'
                    },
                    'image': image_url,
                    'lifecycle_hooks': {
                        "postStart": {
                            "exec": {
                                "command": ["/bin/sh", "-c", "/etc/jupyter-hooks/sar.sh"]
                            }
                        }
                    },
                    'args': [
                        "--NotebookApp.jinja_template_vars={'PROFILE_NAME':'SAR 1'}"
                    ],
                    'mem_limit': '16G', 
                    'mem_guarantee': '6G',
                    'storage_capacity': '500Gi', 
                    'delete_pvc': False
                }
            }
            profile_list.append(profile)

        # m5a.2xlarge: 8 cpus, 32 GiB RAM
        if 'SAR_1_-_Dev' in group_list:
            image_url = f"{os.environ.get('OSL_IMAGE_REPO_URL')}/sar:e914cd7"
            profile = {
                'display_name': 'SAR 1 - Dev',
                'description': 'Development profile. CPU limit: 8. RAM limit: 16G. Storage: 500G.',
                'default': False,
                'kubespawner_override': {
                    'extra_labels': {
                        'server_type': 'sar_1'
                    },
                    'node_selector': {
                        'server_type': 'sar_1'
                    },
                    'image': image_url,
                    'lifecycle_hooks': {
                        "postStart": {
                            "exec": {
                                "command": ["/bin/sh", "-c", "/etc/jupyter-hooks/sar_dev.sh"]
                            }
                        }
                    },
                    'args': [
                        "--NotebookApp.jinja_template_vars={'PROFILE_NAME':'SAR 1 - Dev'}"
                    ],
                    'mem_limit': '16G', 
                    'mem_guarantee': '6G',
                    'storage_capacity': '500Gi', 
                    'delete_pvc': False
                }
            }
            profile_list.append(profile)
        
        # m5a.8xlarge: 32 cpu, 128 GiB RAM
        if 'SAR_2' in group_list:
            image_url = f"{os.environ.get('OSL_IMAGE_REPO_URL')}/sar:e914cd7"
            profile = {
                'display_name': 'SAR 2',
                'description': 'Formally UNAVCO. Contains basic SAR processing packages on a bigger machine. RAM limit: 96G. CPU limit: 8 cpus. Storage: 500 GiB.',
                'default': False,
                'kubespawner_override': {
                    'extra_labels': {
                        'server_type': 'sar_2'
                    },
                    'node_selector': {
                        'server_type': 'sar_2'
                    },
                    'image': image_url,
                    'lifecycle_hooks': {
                        "postStart": {
                            "exec": {
                                "command": ["/bin/sh", "-c", "/etc/jupyter-hooks/sar.sh"]
                            }
                        }
                    },
                    'args': [
                        "--NotebookApp.jinja_template_vars={'PROFILE_NAME':'SAR 2'}"
                    ],
                    'mem_limit': '96G', 
                    'mem_guarantee': '32G', 
                    'cpu_limit': 8,
                    'storage_capacity': '500Gi', 
                    'delete_pvc': False
                }
            }
            profile_list.append(profile)

        # m5a.8xlarge: 32 cpu, 128 GiB RAM
        if 'SAR_2_-_Max' in group_list:
            image_url = f"{os.environ.get('OSL_IMAGE_REPO_URL')}/sar:e914cd7"
            profile = {
                'display_name': 'SAR 2 - Max',
                'description': 'Similar to SAR 2 but one person per machine. RAM limit: ~128GB. CPU limit: ~30 cpus. Storage: 500 GiB.',
                'default': False,
                'kubespawner_override': {
                    'extra_labels': {
                        'server_type': 'sar_2'
                    },
                    'node_selector': {
                        'server_type': 'sar_2'
                    },
                    'image': image_url,
                    'lifecycle_hooks': {
                        "postStart": {
                            "exec": {
                                "command": ["/bin/sh", "-c", "/etc/jupyter-hooks/sar.sh"]
                            }
                        }
                    },
                    'args': [
                        "--NotebookApp.jinja_template_vars={'PROFILE_NAME':'SAR 2 - Max'}"
                    ],
                    'cpu_guarantee': 30,
                    'storage_capacity': '500Gi', 
                    'delete_pvc': False
                }
            }
            profile_list.append(profile)

        if 'SAR_1_-_No_Gitpuller' in group_list:
            image_url = f"{os.environ.get('OSL_IMAGE_REPO_URL')}/sar:e914cd7"
            profile = {
                'display_name': 'SAR 1 - No Gitpuller',
                'description': 'Useful for debugging some server timeouts. This does not pull in the latest notebooks.',
                'default': False,
                'kubespawner_override': {
                    'extra_labels': {
                        'server_type': 'sar_1',
                        'extra_configs': 'no_smart_git'
                    },
                    'node_selector': {
                        'server_type': 'sar_1'
                    },
                    'image': image_url,
                    'lifecycle_hooks': {
                        "postStart": {
                            "exec": {
                                "command": ["/bin/sh", "-c", "/etc/jupyter-hooks/no_smart_git.sh"]
                            }
                        }
                    },
                    'args': [
                        "--NotebookApp.jinja_template_vars={'PROFILE_NAME':'SAR 1 - No Gitpuller'}"
                    ],
                    'mem_limit': '16G', 
                    'mem_guarantee': '6G', 
                    'cpu_guarantee': 1.25,
                    'storage_capacity': '500Gi', 
                    'delete_pvc': False
                }
            }
            profile_list.append(profile)

        if 'SAR_1_-_No_Hook' in group_list:
            image_url = f"{os.environ.get('OSL_IMAGE_REPO_URL')}/sar:e914cd7"
            profile = {
                'display_name': 'SAR 1 - No Hook',
                'description': 'Useful for debugging some server timeouts. This does not run the post-hook.',
                'default': False,
                'kubespawner_override': {
                    'extra_labels': {
                        'server_type': 'sar_1',
                        'extra_configs': 'no_hook'
                    },
                    'node_selector': {
                        'server_type': 'sar_1'
                    },
                    'image': image_url,
                    'args': [
                        "--NotebookApp.jinja_template_vars={'PROFILE_NAME':'SAR 1 - No Hook'}"
                    ],
                    'mem_limit': '16G',
                    'mem_guarantee': '6G',
                    'cpu_guarantee': 1.25,
                    'storage_capacity': '500Gi', 
                    'delete_pvc': False
                }
            }
            profile_list.append(profile)

        # This clause for sudo should always be last
        if 'sudo' in group_list:
            print("Adding sudo privs...")
            spawner.args.append('--allow-root')
            spawner.environment["GRANT_SUDO"] = "yes"
            spawner.gid = 599

            # Users should know that sudo is enabled in profile before entering
            for profile in profile_list:
                profile['display_name'] += " (Sudo Enabled)"
        else:
            print("Sudo privs not given.")

        return profile_list 

    except NoProfileException as e:
        print(f"No profiles found for user {spawner.user.name}.")
        print(e)

        return []

    except Exception as e:            
        print("Something went wrong with the profiles list...")
        print(e)

        return []

c.KubeSpawner.profile_list = profile_list_hook
