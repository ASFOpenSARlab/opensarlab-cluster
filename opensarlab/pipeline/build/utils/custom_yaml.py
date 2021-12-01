
import yaml

#### Custom dumpers
#https://github.com/yaml/pyyaml/issues/234
class IndentDumper(yaml.Dumper):
    def increase_indent(self, flow=False, *args, **kwargs):
        return super().increase_indent(flow=flow, indentless=False)
