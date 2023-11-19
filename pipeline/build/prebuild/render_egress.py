import pathlib
import argparse
import re
import logging

log = logging.getLogger(__file__)
log.setLevel(logging.DEBUG)

from jinja2 import Environment, FileSystemLoader
import pandas as pd

# https://codereview.stackexchange.com/a/235484
def _is_fqdn(hostname):
    return re.match(r'^(?!.{255}|.{253}[^.])([a-z0-9](?:[-a-z-0-9]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?[.]?$', hostname, re.IGNORECASE)

def lint_includes(includes_dir: pathlib.Path) -> None:

    include_files = includes_dir.glob("*.conf")
    
    for include_file in include_files:
        with open(include_file, 'r') as f:
            for line in f:
                line = line.strip()

                if line.startswith('@include'):
                    raise Exception(f"Line: '{line}'. Cannot have 'includes' in an includes file.")

def prepare_confs(conf_dir: pathlib.Path, includes_dir: pathlib.Path) -> None:

    conf_files = conf_dir.glob("*.conf")

    for conf_file in conf_files:
        prepared_filename = conf_file.with_suffix('.prepared')

        with open(conf_file, 'rt') as fin, open(prepared_filename, 'wt') as fout:
            for line in fin:
                line = line.strip()

                if line.startswith('@include'):
                    include_filename = line.lstrip('@include').strip()
    
                    if not include_filename:
                        raise Exception(f"Line: '{line}'. The keyword '@include' must be followed by the name of the include file.")
                    
                    include_file = list(includes_dir.glob(f"{include_filename}.conf"))
                    if not include_file:
                        raise Exception(f"No include files with the name '{include_file}' found.")
                    elif len(include_file) > 1:
                        raise Exception(f"Multiple include files with the same name '{include_file}' found.")
                    
                    with open(include_file[0], 'r') as fmid:
                        line = fmid.read()
                        line = f"\n#>>>>>>>>>>>>>>>>\n# The following is included from '{include_filename}'\n#\n\n" + line + "\n#<<<<<<<<<<<<<<<<<<\n"
            
                fout.write(line + '\n')

def evaluate_confs(conf_dir: pathlib.Path) -> pd.DataFrame:

    conf_files = conf_dir.glob("*.prepared")

    workloads = []
    for conf_file in conf_files:

        filename = conf_file.stem

        config_profile = None
        config_namespace = None
        config_lab = None
        config_ports = None
        config_rate_limit = None

        hosts = []

        log.info(f"Checking configuration of config file '{filename}'...")

        with open(conf_file, 'r') as f:
            for line in f:

                line_host = None

                line = line.strip()

                if not line:
                    continue

                elif line.startswith('#'):
                    continue

                elif line.startswith('@profile'):
                    line = line.lstrip('@profile').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '@profile' does not have any required following arguments: profile_name")
                    config_profile = line

                elif line.startswith('@lab'):
                    line = line.lstrip('@lab').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '@lab' does not have any required following arguments: lab_short_name")
                    config_lab = line

                elif line.startswith('!'):
                    line = line.lstrip('!').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '!' does not have any required following arguments: host")                
                    log.info(f"Remove host '{line}' from list of hosts")
                    for element in hosts:
                        if element['host'] == line:
                            hosts.remove(element)

                elif line.startswith('@namespace'):
                    line = line.lstrip('@namespace').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '@namespace' does not have any required following arguments: namespace")
                    config_namespace = line.strip()

                elif line.startswith('@port'):
                    line = line.lstrip('@port').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '@port' does not have any required following arguments: port_number(s)")
                    config_ports = line

                elif line.startswith('@rate'):
                    line = line.lstrip('@rate').strip()
                    if not line:
                        raise Exception(f"Line: '{line}'. Keyword '@rate' does not have any required following arguments: rate_limit")
                    config_rate_limit = line

                elif '*' in line:
                    log.warning(f"Host '{line}' cannot contain wildcards. Ignoring...")
                    continue

                else:
                    log.info(f"Adding host '{line}'")
                    line_host = line.strip()
                    if not _is_fqdn(line_host):
                        raise Exception(f"Line: '{line}'. Hostname is not a fqdn.")

                if line_host:

                    missing_parts = []
                    if not config_namespace:
                        missing_parts.append("Namespace must be defined for host. Did you forget to put a @namespace at the beginning?")
                    
                    if not config_lab:
                        missing_parts.append("Lab Short Name must be defined for host. Did you forget to put a @lab at the beginning?")

                    if not config_profile:
                        missing_parts.append("Server Profile must be defined for host. Did you forget to put a @profile at the beginning?")

                    if not config_ports:
                        missing_parts.append("Host Port must be defined for host. Did you forget to put a @port at the beginning?")

                    if not config_rate_limit:
                        missing_parts.append("Rate limit (requests/min) must be defined for host. To turn off, set to None. Did you forget to put a @rate at the beginning?")
                    
                    if missing_parts:
                        raise Exception("Missing some required config values: ", '\n'.join(missing_parts))

                    entries = []

                    # If more than one port given, split into seperate entries
                    for port in config_ports.split(','):
                        entries.append(
                            {
                                'host': line_host,
                                'port': port,
                                'namespace': config_namespace,
                                'lab': config_lab,
                                'profile': config_profile,
                                'rate': config_rate_limit
                            }
                        )

                    hosts.extend(entries)
        
        if hosts:
            workloads.extend(hosts)
        else:
            log.warning(f"No valid hosts found in file '{filename}'.")
    
    log.info("Done checking conf files.")
    
    return workloads

def reduce_workloads(workloads: []) -> {}:

    df = pd.DataFrame(workloads)

    # For service entry, group hosts by [port,lab,profile,namespace]
    service_entry_df = df.groupby(['port', 'lab', 'profile', 'namespace'])['host'].apply(list).reset_index()

     # For sidecar, group hosts by [lab,profile,namespace] independent of port
    sidecar_df = df.groupby(['lab', 'profile', 'namespace'])['host'].apply(list).reset_index()

    return {
        'service_entry': service_entry_df.to_dict('records'),
        'sidecar': sidecar_df.to_dict('records')
    }

def create_egress_yamls(reduced_workloads: {}, egress_template: pathlib.Path, egress_output_file: pathlib.Path) -> None:

    env = Environment(
        loader=FileSystemLoader(egress_template.parent),
        autoescape=True
    )

    template = env.get_template(egress_template.name)
    with open(egress_output_file, 'w') as outfile:
        outfile.write(template.render(workloads=reduced_workloads))

def main(conf_dir: str, includes_dir: str, egress_template: str, egress_output_file: str):

    conf_dir = pathlib.Path(conf_dir)
    includes_dir = pathlib.Path(includes_dir)
    egress_template = pathlib.Path(egress_template)
    egress_output_file = pathlib.Path(egress_output_file)

    # Pre-lint 'includes' files. They cannot contain "include <file>".
    lint_includes(includes_dir)

    # Run through all the confs and subsitute text of "include <file>" as needed
    prepare_confs(conf_dir, includes_dir)

    # Process/lint conf
    workloads = evaluate_confs(conf_dir)

    # Take processed conf data and reduce it to the right format for yamls
    reduced_workloads = reduce_workloads(workloads)

    # Create egress yamls
    create_egress_yamls(reduced_workloads, egress_template, egress_output_file)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--configs-dir', dest='conf_dir', default=None)
    parser.add_argument('--includes-dir', dest='includes_dir', default=None)
    parser.add_argument('--egress-template', dest='egress_template', default=None)
    parser.add_argument('--egress-output-file', dest='egress_output_file', default=None)
    args = parser.parse_args()

    main(args.conf_dir, args.includes_dir, args.egress_template, args.egress_output_file)
