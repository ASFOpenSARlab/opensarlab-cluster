import sys
import pathlib
import argparse
import logging

log = logging.getLogger(__file__)
#console_handler = logging.StreamHandler(sys.stdout)
#console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#console_handler.setFormatter(console_formatter)
#log.addHandler(console_handler)
log.setLevel(logging.DEBUG)

from jinja2 import Environment, FileSystemLoader


def parse_includes_files(include_files: []) -> []:

    workloads = []
    for include_file in include_files:

        name = include_file.stem 
        hosts = []
        namespace = None
        lab = None

        log.info(f"Checking configuration of include file '{name}'...")

        with open(include_file, 'r') as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                elif line.startswith('#'):
                    continue

                elif line.startswith('%include'):
                    log.info(f"Cannot include other files like '{line}'. Ignoring....")

                elif line.startswith('%lab'):
                    lab = line.lstrip('%lab').strip()

                elif line.startswith('!'):
                    line = line.lstrip('!').strip()
                    log.info(f"Remove host '{line}'")
                    if line in hosts:
                        hosts.remove(line)

                elif line.startswith('%namespace'):
                    line = line.lstrip('%namespace').strip()
                    namespace = line

                elif '*' in line:
                    log.warning(f"Host '{line}' cannot contain wildcards. Ignoring...")
                    continue

                else:
                    # TODO: Check to see if line is a valid domain
                    log.info(f"Adding host '{line}'")
                    hosts.append(line)
        
        if hosts:
            workloads.append({
                'name': name,
                'namespace': namespace,
                'hosts': list(set(hosts)),
                'lab': lab
            })

        else:
            log.warning(f"No valid hosts found for include file '{name}'.")
    
    log.info("Done checking include files.\n")

    return workloads

def parse_config_files(config_files: [], includes_workloads: []) -> []:

    workloads = []
    for config_file in config_files:

        name = config_file.stem 
        hosts = []
        namespace = None
        lab = None

        log.info(f"Checking configuration '{name}'...")

        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                elif line.startswith('#'):
                    continue

                elif line.startswith('%include'):
                    line = line.lstrip('%include').strip()
                    include_workload = [w for w in includes_workloads if w['name'] == line]

                    if include_workload:
                        log.info(f"Including config '{line}' in line of hosts.")
                        include_workload = include_workload[0]

                        if include_workload.get('lab', None):
                            lab = include_workload['lab']

                        if include_workload.get('%namespace', None):
                            namespace = include_workload['namespace']

                        if include_workload.get('hosts', None):
                            hosts.extend(include_workload['hosts'])

                elif line.startswith('%lab'):
                    lab = line.lstrip('%lab').strip()

                elif line.startswith('!'):
                    line = line.lstrip('!').strip()
                    log.info(f"Remove host '{line}'")
                    if line in hosts:
                        hosts.remove(line)

                elif line.startswith('%namespace'):
                    line = line.lstrip('%namespace').strip()
                    namespace = line

                elif '*' in line:
                    log.warning(f"Host '{line}' cannot contain wildcards. Ignoring...")
                    continue

                else:
                    # TODO: Check to see if line is a valid domain
                    log.info(f"Adding host '{line}'")
                    hosts.append(line)

        if hosts:

            if not name:
                raise Exception("A profile name must be set.")
            
            if not namespace:
                raise Exception("A namespace must be set.")

            if not lab:
                raise Exception("A lab name must be set.")

            # Labels cannot have any spaces so make sure they don't
            name = name.replace(" ", "_")
            lab = lab.replace(" ", "_")

            workloads.append({
                'profile': name,
                'namespace': namespace,
                'lab': lab,
                'hosts': list(set(hosts))
            })

            log.info(
                f"""To apply firewall config '{name}', apply pod labels: 
                    \"se-lab: {lab}\"
                    \"se-profile: {name}\"              
                """    
            )
        
        else:
            log.warning(f"No valid hosts found for '{name}'. No egress configuration will be created.")

    log.info("Done checking host config files.\n")

    return workloads

def main(configs_path: str, template_path: str, output_path: str) -> None:

    configs_path = pathlib.Path(configs_path)
    template_path = pathlib.Path(template_path)
    output_path = pathlib.Path(output_path)

    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        autoescape=True
    )

    includes_files = configs_path.glob("includes/*.conf")
    includes_workloads = parse_includes_files(includes_files)

    config_files = configs_path.glob("*.conf")
    workloads = parse_config_files(config_files, includes_workloads)
    
    template = env.get_template(template_path.name)
    with open(output_path, 'w') as outfile:
        outfile.write(template.render(workloads=workloads))

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--configs_path', default=None)
    parser.add_argument('--template_path', default=None)
    parser.add_argument('--output_file', default=None)
    args = parser.parse_args()

    main(args.configs_path, args.template_path, args.output_file)
