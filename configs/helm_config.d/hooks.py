
import os

# Before mounting the home directory, check to see if a volume exists.
# If it doesn't, check for any EBS snapshots.
# If a snapshot exists, create a volume from the snapshot.
# Otherwise, JupyterHub will do the mounting and other volume handling.
def my_pre_hook(spawner):
    try:
        from volume_from_snapshot import volume_from_snapshot

        meta = {
            'username': spawner.user.name,
            'pvc_name': spawner.pvc_name,
            'namespace': 'jupyter',
            'cluster_name': os.environ.get('OSL_CLUSTER_NAME'),
            'cost_tag_key': os.environ.get('OSL_COST_TAG_KEY'),
            'cost_tag_value': os.environ.get('OSL_COST_TAG_VALUE'),
            'az_name': os.environ.get('OSL_AZ_NAME'),
            'vol_size': spawner.storage_capacity,
            'spawn_pvc': spawner.get_pvc_manifest()
        }

        volume_from_snapshot(meta)

    except Exception as e:
        print(e)
        raise

c.Spawner.pre_spawn_hook = my_pre_hook


# After stopping the notebook server, tag the volume with the current "stopping" time. This will help determine which volumes are active.
def my_post_hook(spawner):
    try:
        from volume_stopping_tags import volume_stopping_tags

        meta = {
            'pvc_name': spawner.pvc_name,
            'cluster_name': os.environ.get('OSL_CLUSTER_NAME'),
            'az_name': os.environ.get('OSL_AZ_NAME')
        }

        volume_stopping_tags(meta)

    except Exception as e:
        print("Something went wrong with the volume stopping tag post hook...")
        print(e)
        raise

c.Spawner.post_stop_hook = my_post_hook
