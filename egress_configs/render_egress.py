import pathlib
import argparse
import re
import ipaddress
import logging

log = logging.getLogger(__file__)
log.setLevel(logging.DEBUG)

from jinja2 import Environment, FileSystemLoader
import pandas as pd


# https://stackoverflow.com/a/71037719
def _valid_ip_or_cidr(ip):
    try:
        ipaddress.IPv4Address(ip)
        print("valid as address")
        return True
    except:
        try:
            ipaddress.IPv4Network(ip)
            # print('valid as network')
            return True
        except:
            print("invalid as both an address and network")
            return False


# https://codereview.stackexchange.com/a/235484
def _is_fqdn(hostname):
    return re.match(
        r"^(?!.{255}|.{253}[^.])([a-z0-9](?:[-a-z-0-9]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?[.]?$",
        hostname,
        re.IGNORECASE,
    )


def lint_includes(includes_dir: pathlib.Path) -> None:

    include_files = includes_dir.glob("*.conf")

    for include_file in include_files:
        with open(include_file, "r") as f:
            for line in f:
                line = line.strip()

                if line.startswith("@include"):
                    raise Exception(
                        f"Line: '{line}'. Cannot have 'includes' in an includes file."
                    )

                elif line.startswith("@profile"):
                    raise Exception(
                        f"Line: '{line}'. Cannot have 'profile' in an includes file."
                    )

                elif line.startswith("@rate"):
                    raise Exception(
                        f"Line: '{line}'. Cannot have 'rate' in an includes file."
                    )


def prepare_confs(conf_dir: pathlib.Path, includes_dir: pathlib.Path) -> None:

    conf_files = conf_dir.glob("*.conf")

    for conf_file in conf_files:
        prepared_filename = conf_file.with_suffix(".prepared")

        with open(conf_file, "rt") as fin, open(prepared_filename, "wt") as fout:
            for line in fin:
                line = line.strip()

                if line.startswith("@include"):
                    include_filename = line.lstrip("@include").strip()

                    if not include_filename:
                        raise Exception(
                            f"Line: '{line}'. The keyword '@include' must be followed by the name of the include file."
                        )

                    include_file = list(includes_dir.glob(f"{include_filename}.conf"))
                    if not include_file:
                        raise Exception(
                            f"No include files with the name '{include_file}' found."
                        )
                    elif len(include_file) > 1:
                        raise Exception(
                            f"Multiple include files with the same name '{include_file}' found."
                        )

                    with open(include_file[0], "r") as fmid:
                        line = fmid.read()
                        line = (
                            f"\n#>>>>>>>>>>>>>>>>\n# The following is included from '{include_filename}'\n#\n\n"
                            + line
                            + "\n#<<<<<<<<<<<<<<<<<<\n"
                        )

                fout.write(line + "\n")


def evaluate_confs(conf_dir: pathlib.Path) -> pd.DataFrame:

    conf_files = conf_dir.glob("*.prepared")

    workloads = []
    for conf_file in conf_files:

        filename = conf_file.stem

        config_profile = None
        config_rate_limit = None
        config_list_type = None

        line_ports = None
        line_timeout = None

        hosts = []

        log.info(f"Checking configuration of config file '{filename}'...")

        with open(conf_file, "r") as f:
            for line in f:

                line = line.strip()

                line_host = None
                line_ip = None

                if not line:
                    continue

                elif line.startswith("#"):
                    continue

                elif line.startswith("@profile"):
                    line = line.lstrip("@profile").strip().lower()
                    if not line:
                        raise Exception(
                            f"Line: '{line}'. Keyword '@profile' does not have any required following arguments: profile_name"
                        )
                    if not _is_fqdn(line):
                        raise Exception(
                            f"Line: '{line}'. Profile is not in fqdn format. This is needed since the profile is part of the name for some K8s resources."
                        )
                    if line == "none":
                        raise Exception(
                            f"Line: '{line}'. Profile cannot have the value 'none'. This is a special value defined in code."
                        )
                    # Any profiles later found after the first will be ignored
                    if config_profile == None:
                        config_profile = line

                elif line.startswith("@rate"):
                    line = line.lstrip("@rate").strip()
                    if not line:
                        raise Exception(
                            f"Line: '{line}'. Keyword '@rate' does not have any required following arguments: rate_limit"
                        )
                    # Any rates later found after the first will be ignored
                    if config_rate_limit == None:
                        config_rate_limit = line

                elif line.startswith("@list"):
                    line = line.lstrip("@list").strip()
                    if not line:
                        raise Exception(
                            f"Line: '{line}'. Keyword '@list' does not have any required following arguments: white/black list type"
                        )
                    # Any list types later found after the first will be ignored
                    if config_list_type == None:
                        config_list_type = line

                elif line.startswith("^"):
                    line = line.lstrip("^").strip()
                    if not line:
                        raise Exception(
                            f"Line: '{line}'. Keyword '^' does not have any required following arguments: host"
                        )
                    log.info(f"Remove host '{line}' from list of hosts")
                    for element in hosts:
                        if element["host"] == line:
                            hosts.remove(element)

                elif line.startswith("%port"):
                    line = line.lstrip("%port").strip()
                    if not line:
                        raise Exception(
                            f"Line: '{line}'. Keyword '%port' does not have any required following arguments: port_number(s)"
                        )
                    line_ports = line

                elif line.startswith("%timeout"):
                    line = line.lstrip("%timeout").strip()
                    if not line:
                        raise Exception(
                            f"Line: '{line}'. Keyword '%timeout' does not have any required following arguments: timeout"
                        )
                    line_timeout = line

                elif "*" in line:
                    log.warning(f"Host '{line}' cannot contain wildcards. Ignoring...")
                    continue

                elif line.startswith("+ip"):
                    line = line.lstrip("+ip").strip()
                    if not line:
                        raise Exception(
                            f"Line: '{line}'. Keyword '+ip' does not have any required following arguments: ip_address"
                        )
                    line_ip = line
                    if not _valid_ip_or_cidr(line_ip):
                        raise Exception(f"Line: '{line}'. IP is not valid.")

                else:
                    log.info(f"Adding host '{line}'")
                    line_host = line.strip()
                    if not _is_fqdn(line_host):
                        raise Exception(f"Line: '{line}'. Hostname is not a fqdn.")

                if line_host or line_ip:

                    missing_parts = []

                    if not config_profile:
                        missing_parts.append(
                            "Server Profile must be defined for host. Did you forget to put a @profile at the beginning?"
                        )

                    if not line_ports:
                        missing_parts.append(
                            "Host Port must be defined for host. Did you forget to put a %port at the beginning?"
                        )

                    if not config_rate_limit:
                        missing_parts.append(
                            "Rate limit (requests/min) must be defined for host. To turn off, set to None. Did you forget to put a @rate at the beginning?"
                        )

                    if not config_list_type:
                        missing_parts.append(
                            "List type: white or black must be defined. Did you forget to put a @list at the beginning?"
                        )

                    if missing_parts:
                        raise Exception(
                            "Missing some required config values: ",
                            "\n".join(missing_parts),
                        )

                    if not line_timeout:
                        line_timeout = "10s"

                    entries = []

                    # If more than one port given, split into seperate entries
                    for line_port in line_ports.split(","):
                        line_port_redirect = None
                        if "=>" in line_port:
                            line_port, line_port_redirect = line_port.split("=>")

                        if int(line_port) < 1 or int(line_port) > 65535:
                            raise Exception(
                                f"'line_port' must have a value between 1 and 65535"
                            )

                        if line_port_redirect is not None and (
                            int(line_port_redirect) < 1
                            or int(line_port_redirect) > 65535
                        ):
                            raise Exception(
                                f"'line_port_redirect' must have a value between 1 and 65535"
                            )

                        entries.append(
                            {
                                "host": line_host,
                                "ip": line_ip,
                                "port": line_port,
                                "port_redirect": line_port_redirect,
                                "profile": config_profile,
                                "rate": config_rate_limit,
                                "timeout": line_timeout,
                                "list_type": config_list_type,
                            }
                        )

                        if line_port_redirect is not None:
                            entries.append(
                                {
                                    "host": line_host,
                                    "ip": line_ip,
                                    "port": line_port_redirect,
                                    "port_redirect": None,
                                    "profile": config_profile,
                                    "rate": config_rate_limit,
                                    "timeout": line_timeout,
                                    "list_type": config_list_type,
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

    # Get all profiles
    profiles = df.get("profile").unique()

    # For service entry, group [host] by [port,port_redirect,profile,rate,list_type] independent of [ip,timeout]
    service_entry_hosts = (
        df.query("host == host")
        .get(["port", "port_redirect", "profile", "rate", "host", "list_type"])
        .groupby(
            ["port", "port_redirect", "profile", "rate", "list_type"], dropna=False
        )["host"]
        .apply(lambda row: list(set(row)))
        .reset_index()
        .to_dict("records")
    )

    # For service entry, group [ip] by [port,port_redirect,profile,rate,list_type] independent of [host,timeout]
    service_entry_ips = (
        df.query("ip == ip")
        .get(["port", "port_redirect", "profile", "rate", "list_type", "ip"])
        .groupby(
            ["port", "port_redirect", "profile", "rate", "list_type"], dropna=False
        )["ip"]
        .apply(lambda row: list(set(row)))
        .reset_index()
        .to_dict("records")
    )

    # For desination rule, group [host] by [port,port_redirect,profile,rate,timeout,list_type] independent of [ip]
    destination_rule = (
        df.query("host == host")
        .get(
            ["port", "port_redirect", "profile", "rate", "timeout", "list_type", "host"]
        )
        .groupby(
            ["port", "port_redirect", "profile", "rate", "timeout", "list_type"],
            dropna=False,
        )["host"]
        .apply(lambda row: list(set(row)))
        .reset_index()
        .to_dict("records")
    )

    # For virtual services, group [host] by [port,port_redirect,profile,rate,timeout] independent of [ip]
    virtual_services = (
        df.query("host == host")
        .get(
            ["port", "port_redirect", "profile", "rate", "timeout", "list_type", "host"]
        )
        .groupby(
            ["port", "port_redirect", "profile", "rate", "timeout", "list_type"],
            dropna=False,
        )["host"]
        .apply(lambda row: list(set(row)))
        .reset_index()
        .to_dict("records")
    )

    # For sidecar, group [host] by [profile,list_type] independent of [port,port_redirect,rate,timeout,ip]
    sidecar = (
        df.query("host == host")
        .get(["profile", "list_type", "host"])
        .groupby(["profile", "list_type"], dropna=False)["host"]
        .apply(lambda row: list(set(row)))
        .reset_index()
        .to_dict("records")
    )

    # For Envoy Filter, group [rate] by [profile,list_type] independent of [host,ip,port,port_redirect,timeout]
    # If more than one rate is found per profile/list_type, the last one takes precedence
    envoy_filter = (
        df.get(["profile", "list_type", "rate"])
        .groupby(["profile", "list_type"], dropna=False)["rate"]
        .apply(lambda row: list(row)[-1] if len(list(row)) > 0 else None)
        .reset_index()
        .to_dict("records")
    )

    return {
        "profiles": profiles,
        "service_entry_hosts": service_entry_hosts,
        "service_entry_ips": service_entry_ips,
        "destination_rule": destination_rule,
        "virtual_services": virtual_services,
        "sidecar": sidecar,
        "envoy_filter": envoy_filter,
    }


def create_egress_yamls(
    reduced_workloads: {},
    egress_template: pathlib.Path,
    egress_output_file: pathlib.Path,
) -> None:

    env = Environment(loader=FileSystemLoader(egress_template.parent), autoescape=True)

    template = env.get_template(egress_template.name)
    with open(egress_output_file, "w") as outfile:
        outfile.write(template.render(workloads=reduced_workloads))


def main(
    conf_dir: str, includes_dir: str, egress_template: str, egress_output_file: str
):

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
    parser.add_argument("--configs-dir", dest="conf_dir", default=None)
    parser.add_argument("--includes-dir", dest="includes_dir", default=None)
    parser.add_argument("--egress-template", dest="egress_template", default=None)
    parser.add_argument("--egress-output-file", dest="egress_output_file", default=None)
    args = parser.parse_args()

    main(
        args.conf_dir, args.includes_dir, args.egress_template, args.egress_output_file
    )
