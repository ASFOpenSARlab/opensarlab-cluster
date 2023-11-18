import re
import pathlib
import argparse
import logging

log = logging.getLogger(__file__)
log.setLevel(logging.DEBUG)

from jinja2 import Environment, FileSystemLoader

# https://codereview.stackexchange.com/a/235484
def _is_fqdn(hostname):
    return re.match(r'^(?!.{255}|.{253}[^.])([a-z0-9](?:[-a-z-0-9]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?[.]?$', hostname, re.IGNORECASE)

def parse_includes_files(include_files: []) -> []:

    workloads = []
    for include_file in include_files:

        filename = include_file.stem

        #included_profile = None
        included_namespace = None
        included_lab = None

        hosts = []

        log.info(f"Checking configuration of include file '{filename}'...")

        with open(include_file, 'r') as f:
            for line in f:

                line_host = None
                line_port = None

                line = line.strip()

                if not line:
                    continue

                elif line.startswith('#'):
                    continue

                elif line.startswith('%include'):
                    log.warning(f"Cannot include other files like '{line}'. Ignoring....")
                    continue

                elif line.startswith('%profile'):
                    log.warning(f"Cannot include %profile in includes file. Ignoring....")
                    continue
                #    line = line.lstrip('%profile').strip()
                #    if not line:
                #        raise Exception(f"Line: '{line}'. Keyword '%profile' does not have any required following arguments: profile_name")
                #    included_profile = line

                elif line.startswith('%lab'):
                    line = line.lstrip('%lab').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '%lab' does not have any required following arguments: lab_short_name")
                    included_lab = line

                elif line.startswith('!'):
                    line = line.lstrip('!').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '!' does not have any required following arguments: host")                
                    log.info(f"Remove host '{line}' from list of hosts")
                    for element in hosts:
                        if element['host'] == line:
                            hosts.remove(element)

                elif line.startswith('%namespace'):
                    line = line.lstrip('%namespace').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '%namespace' does not have any required following arguments: namespace")
                    included_namespace = line.strip()

                elif '*' in line:
                    log.warning(f"Host '{line}' cannot contain wildcards. Ignoring...")
                    continue

                elif line.startswith('@port'):
                    line = line.lstrip('@port').strip()
                    parts = line.split(' ')
                    if len(parts) == 0:
                        raise Exception(f"Line: '{line}'. Keyword '@port' does not have any required following arguments: port, host")
                    line_port = parts[0]
                    if len(parts) == 1:
                        raise Exception(f"Line: '{line}'. Keyword '@port' does not have any required following arguments: host")
                    line_host = parts[1]

                else:
                    # TODO: Check to see if line is a valid domain
                    log.info(f"Adding host '{line}'")
                    line_host = line.strip()
                    if not _is_fqdn(line_host):
                        raise Exception(f"Line: '{line}'. Hostname is not a fqdn.")

                if line_host:

                    missing_parts = []
                    if not included_namespace:
                        missing_parts.append("Namespace must be defined for host. Did you forget to put a %namespace at the beginning?")
                    
                    if not included_lab:
                        missing_parts.append("Lab Short Name must be defined for host. Did you forget to put a %lab at the beginning?")

                    #if not included_profile:
                    #    missing_parts.append("Server Profile must be defined for host. Did you forget to put a %profile at the beginning?")
                    
                    if missing_parts:
                        raise Exception("Missing some required config values: ", '\n'.join(missing_parts))

                    hosts.append({
                        'includes': filename,
                        'host': line_host,
                        'port': line_port or 'default',
                        'namespace': included_namespace,
                        'lab': included_lab,
                        #'profile': included_profile
                    })
        
        if hosts:
            workloads.extend(hosts)
        else:
            log.warning(f"No valid hosts found in include file '{filename}'.")
    
    log.info("Done checking include files.\n")

    return workloads

def parse_config_files(config_files: [], includes_workloads: []) -> []:

    workloads = []
    for config_file in config_files:

        filename = config_file.stem

        config_profile = None
        config_namespace = None
        config_lab = None

        hosts = []

        log.info(f"Checking configuration of config file '{filename}'...")

        with open(config_file, 'r') as f:
            for line in f:

                line_host = None
                line_port = None

                line = line.strip()

                if not line:
                    continue

                elif line.startswith('#'):
                    continue

                elif line.startswith('%include'):
                    line = line.lstrip('%include').strip()
                    include_workload = [w for w in includes_workloads if w['includes'] == line]

                    if include_workload:
                        for work in include_workload:
                            log.info(f"Including config '{work}' in line of hosts.")

                            if work.get('lab', None):
                                config_lab = work['lab']
                            else:
                                work['lab'] = config_lab

                            if work.get('namespace', None):
                                config_namespace = work['namespace']
                            else:
                                work['namespace'] = config_namespace

                            work['profile'] = config_profile

                            hosts.extend(work)

                elif line.startswith('%profile'):
                    line = line.lstrip('%profile').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '%profile' does not have any required following arguments: profile_name")
                    config_profile = line

                elif line.startswith('%lab'):
                    line = line.lstrip('%lab').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '%lab' does not have any required following arguments: lab_short_name")
                    config_lab = line

                elif line.startswith('!'):
                    line = line.lstrip('!').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '!' does not have any required following arguments: host")                
                    log.info(f"Remove host '{line}' from list of hosts")
                    #for element in hosts:
                    #    if element['host'] == line:
                    #        hosts.remove(element)

                elif line.startswith('%namespace'):
                    line = line.lstrip('%namespace').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '%namespace' does not have any required following arguments: namespace")
                    config_namespace = line.strip()

                elif '*' in line:
                    log.warning(f"Host '{line}' cannot contain wildcards. Ignoring...")
                    continue

                elif line.startswith('@port'):
                    line = line.lstrip('@port').strip()
                    parts = line.split(' ')
                    if len(parts) == 0:
                        raise Exception(f"Line: '{line}'. Keyword '@port' does not have any required following arguments: port, host")
                    line_port = parts[0]
                    if len(parts) == 1:
                        raise Exception(f"Line: '{line}'. Keyword '@port' does not have any required following arguments: host")
                    line_host = parts[1]

                else:
                    # TODO: Check to see if line is a valid domain
                    log.info(f"Adding host '{line}'")
                    line_host = line.strip()
                    if not _is_fqdn(line_host):
                        raise Exception(f"Line: '{line}'. Hostname is not a fqdn.")

                if line_host:

                    missing_parts = []
                    if not config_namespace:
                        missing_parts.append("Namespace must be defined for host. Did you forget to put a %namespace at the beginning?")
                    
                    if not config_lab:
                        missing_parts.append("Lab Short Name must be defined for host. Did you forget to put a %lab at the beginning?")

                    if not config_profile:
                        missing_parts.append("Server Profile must be defined for host. Did you forget to put a %profile at the beginning?")
                    
                    if missing_parts:
                        raise Exception("Missing some required config values: ", '\n'.join(missing_parts))

                    hosts.append({
                        'includes': None,
                        'host': line_host,
                        'port': line_port or 'default',
                        'namespace': config_namespace,
                        'lab_short_name': config_lab,
                        'profile': config_profile
                    })
        
        if hosts:
            workloads.extend(hosts)
        else:
            log.warning(f"No valid hosts found in include file '{filename}'.")
    
    log.info("Done checking include files.\n")

    return workloads

def reduce_workloads(workloads: []) -> []:
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
    
    workloads = reduce_workloads(workloads)

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
