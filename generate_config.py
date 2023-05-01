#!/usr/bin/env python3
"""
Used to create kernel configuration files for specific hardware configurations
"""

__version__ = "0.0.3"

from CustomLogging import class_logger

from jinja2 import Environment, PackageLoader, select_autoescape
import logging
import re
import yaml

logging.root.setLevel(10)


@class_logger
class LinuxKernelConfigParameter:
    """
    Abstraction of a linux kernel .config parameter
    """

    def __init__(self, name, value, defined=True):
        self.set_name(name)
        self.set_value(value)
        self.defined = defined

    def set_name(self, name):
        """
        Sets the name, normalizes to a config paramter name, checks the name
        """
        if not self._validate_name(name):
            raise ValueError("Invalid name: %s" % name)

        name = name.upper()

        if not name.startswith('CONFIG_'):
            self.logger.info("Config name '%s' does not start with 'CONFIG_', appending" % name)
            name = 'CONFIG_' + name

        self.name = name

    def set_value(self, value):
        """
        Sets the value of the config parameter
        """
        if not self._validate_value(value):
            raise ValueError("Invalid value: %s" % value)

        self.value = value
        if self.value is None:
            self.logger.warning("Value for '%s' is not set, setting defined to False" % self.name)
            self.defined = False

    @staticmethod
    def parse_file(file):
        """ Parses a yaml file, returns a list of LinuxKernelConfigParameters"""
        import yaml
        yaml_dict = yaml.safe_load(file)

        config_items = list()
        for name, value in yaml_dict.items():
            config_items.append(LinuxKernelConfigParameter(name, value))

        return config_items

    @staticmethod
    def _validate_name(name):
        """Validates the characters in a kernel config parameter name"""
        invalid_name_chars = r'[^a-zA0-Z_0-9]'

        return not re.search(invalid_name_chars, name)

    @staticmethod
    def _validate_value(value):
        """Validates the characters in a kernel config parameter value"""
        valid_value_match = r'(-?([0-9])+|[ynm]+|"([a-zA-Z0-9/_.,-=\(\) ])*")$'
        search_result = re.search(valid_value_match, value)

        return True if search_result else False

    def __str__(self):
        return f"{self.name}={self.value}" if self.defined else f"# {self.name} is not set"


if __name__ == '__main__':
    with open('config.yaml', 'r') as f:
        base_config = yaml.safe_load(f)

    templates = base_config.pop('templates')

    jinja_env = Environment(loader=PackageLoader("generate_config"), autoescape=select_autoescape())

    for template in templates:
        jinja_template = jinja_env.get_template(template)
        print(jinja_template.render(**base_config))

