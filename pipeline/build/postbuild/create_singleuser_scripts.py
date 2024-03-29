"""
Only shell scripts (.sh) will be found and scaffolded up.

singleuser file names MUST not have spaces in them.

python3 create_singleuser_scripts.py \
    --origin_singleuser_scripts_dir=$OSL_HOME/singleuser_singleusers/ \
    --dest_hook_scripts_dir=$OSL_HOME/jupyterhub/singleuser/singleusers/ \
    --helm_config_template=$OSL_HOME/jupyterhub/helm_config.yaml.j2 \
    --helm_config_template=$OSL_HOME/jupyterhub/helm_config.yaml \
    --jupyterhub_codebuild_template=$OSL_HOME/pipeline/build/jupyterhub/codebuild.sh.j2 \
    --jupyterhub_codebuild=$OSL_HOME/pipeline/build/jupyterhub/codebuild.sh
"""

import glob
import shutil
import pathlib
import argparse

from jinja2 import Environment, FileSystemLoader


def main(
    origin_singleuser_scripts_dir: str,
    dest_hook_scripts_dir: str,
    dest_extension_override_dir: str,
    helm_config_template: str,
    helm_config: str,
    jupyterhub_codebuild_template: str,
    jupyterhub_codebuild: str,
) -> None:
    # Convert file paths to pathlib
    origin_singleuser_scripts_dir = pathlib.Path(origin_singleuser_scripts_dir)
    dest_hook_scripts_dir = pathlib.Path(dest_hook_scripts_dir)
    dest_extension_override_dir = pathlib.Path(dest_extension_override_dir)
    helm_config_template = pathlib.Path(helm_config_template)
    helm_config = pathlib.Path(helm_config)
    jupyterhub_codebuild_template = pathlib.Path(jupyterhub_codebuild_template)
    jupyterhub_codebuild = pathlib.Path(jupyterhub_codebuild)

    ### Hooks
    # Get .sh hook script names and move them to dest
    hook_names = [
        pathlib.Path(filename).name
        for filename in glob.glob(str(origin_singleuser_scripts_dir / "hooks" / "*.sh"))
    ]

    # Move scripts to new location
    for hook_name in hook_names:
        try:
            shutil.copy2(
                origin_singleuser_scripts_dir / "hooks" / hook_name,
                dest_hook_scripts_dir / hook_name,
            )
        except shutil.SameFileError:
            print(f"Could not copy file due to SameFileError for {hook_name}.")

    ### Overrides
    extension_overrides_names = [
        pathlib.Path(filename).name
        for filename in glob.glob(
            str(origin_singleuser_scripts_dir / "overrides" / "*.json")
        )
    ]

    # Move scripts to new location
    for extension_overrides_name in extension_overrides_names:
        try:
            shutil.copy2(
                origin_singleuser_scripts_dir / "overrides" / extension_overrides_name,
                dest_extension_override_dir / extension_overrides_name,
            )
        except shutil.SameFileError:
            print(
                f"Could not copy file due to SameFileError for {extension_overrides_name}."
            )

    # Render helm_config templates
    environment = Environment(loader=FileSystemLoader(helm_config_template.parent))
    template = environment.get_template(helm_config_template.name)
    content = template.render(
        hook_script_filenames=hook_names,
        extension_override_filenames=extension_overrides_names,
    )

    with open(helm_config, "w") as outfile:
        outfile.write(content)

    # Render jupyterhub codebuild config templates
    environment = Environment(
        loader=FileSystemLoader(jupyterhub_codebuild_template.parent)
    )
    template = environment.get_template(jupyterhub_codebuild_template.name)
    content = template.render(
        hook_script_filenames=hook_names,
        extension_override_filenames=extension_overrides_names,
    )

    with open(jupyterhub_codebuild, "w") as outfile:
        outfile.write(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin_singleuser_scripts_dir", default=None)
    parser.add_argument("--dest_hook_scripts_dir", default=None)
    parser.add_argument("--dest_extension_override_dir", default=None)
    parser.add_argument("--helm_config_template", default=None)
    parser.add_argument("--helm_config", default=None)
    parser.add_argument("--jupyterhub_codebuild_template", default=None)
    parser.add_argument("--jupyterhub_codebuild", default=None)
    args = parser.parse_args()

    main(
        args.origin_singleuser_scripts_dir,
        args.dest_hook_scripts_dir,
        args.dest_extension_override_dir,
        args.helm_config_template,
        args.helm_config,
        args.jupyterhub_codebuild_template,
        args.jupyterhub_codebuild,
    )
