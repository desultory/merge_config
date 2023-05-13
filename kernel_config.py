"""
A collection of classes and other code to define linux kernel .config

"""

__author__ = "desultory"
__version__ = "0.2.1"

from custom_logging import class_logger

from collections import OrderedDict
from re import search
from yaml import safe_load


@class_logger
class LinuxKernelConfigParameter:
    """
    Abstraction of a linux kernel .config parameter

    defined with:
        name={parameter name}
        value={paramete value}
    optional:
        defined=bool

    defined is assumed to be true if it's not specified.

    This object can be printed for a representation of how it would be defined in a .config file
    """
    _invalid_name_chars = r'[^a-zA0-Z_0-9]'
    _valid_value_chars = r'(-?([0-9])+|[ynm]+|"([a-zA-Z0-9/_.,-=\(\) ])*")$'

    components = OrderedDict({'name': {'required': True},
                              'defined': {'required': True, 'default': True},
                              'value': {'required': True},
                              'description': {'required': False}})

    def __init__(self, *args, **kwargs):
        for component_name, specification in self.components.items():
            self.logger.debug("Checking kwargs for component: %s" % component_name)
            if specification.get('required'):
                setattr(self, component_name, kwargs.pop(component_name, specification.get('default')))
            else:
                passed_parameter = kwargs.pop(component_name, specification.get('default'))
                if passed_parameter is not None:
                    setattr(self, component_name, kwargs.pop(component_name, specification.get('default')))

        while kwargs:
            self.logger.warning("Unable to process kwarg: %s=%s" % kwargs.popitem())

    def __setattr__(self, name, value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            self.logger.debug("Making value a string: %s" % value)
            value = str(value)
        if hasattr(self, f"_validate_{name}") and not getattr(self, f"_validate_{name}")(value):
            raise ValueError(f"Invalid {name}: {value}")
        if hasattr(self, f"_set_{name}"):
            getattr(self, f"_set_{name}")(value)
        else:
            super().__setattr__(name, value)

    def _set_name(self, name: str):
        """
        Used for setting the name, should be called after validation

        Automatically converts the name to CONFIG_NAME format
        """
        name = name.upper()
        name = f"CONFIG_{name}" if not name.startswith("CONFIG_") else name
        super().__setattr__('name', name)

    @staticmethod
    def _validate_name(name):
        """ Validates the characters in a kernel config parameter name """
        return not search(LinuxKernelConfigParameter._invalid_name_chars, name)

    def _validate_value(self, value):
        """
        Validates the characters in a kernel config parameter value
        all values should be interpreted as strings

        If the parameter is an undefine, allow the value to be None
        """
        if self.defined is False:
            return True
        return True if search(LinuxKernelConfigParameter._valid_value_chars, value) else False

    def __str__(self):
        """ Returns a string representation of how this kernel config should be specified in a kernel .config """
        return f"{self.name}={self.value}" if self.defined else f"# {self.name} is not set"


@class_logger
class KConfig:
    """
    Parses and represents KConfig information
    """
    _KCONFIG_FILE_REGEX = r'/(Kconfig)(\.|-)?([a-zA-Z0-9])*$'
    excluded_search_dirs = ['Documentation']

    def __init__(self, index_dir='/usr/src/linux/', *args, **kwargs):
        self.index_dir = index_dir
        self.kconfig_files = list()

        self.index_files()
        print(self.kconfig_files)

    def index_files(self):
        from os import scandir
        subdirs = [subdir.path for subdir in scandir(self.index_dir) if subdir.path.replace(self.index_dir, '') not in self.excluded_search_dirs and subdir.is_dir()]
        self.logger.debug("Detected KConfig subdirectories: %s" % subdirs)
        for subdir in subdirs:
            self.logger.debug("Scanning directory for Kconfig files: %s", subdir)
            found_kconfigs = [subdir + search(self._KCONFIG_FILE_REGEX, file.path).group() for file in scandir(subdir) if search(self._KCONFIG_FILE_REGEX, file.path)]
            if not found_kconfigs:
                self.logger.debug("Did not find any Kconfig files in: %s", subdir)
            else:
                self.logger.info("Discovered KConfigs: %s", found_kconfigs)
                self.kconfig_files.append(found_kconfigs)


@class_logger
class KernelDict(dict):
    """
    Special dictionary for linux kernel config
    Meant to be used by LinuxKernelConfig

    Automatically tries to make a LinuxKernelConfigParameter defined by the name with the passed value when defined

    Exist to merge items as they are added, according to the mode
    Mostly just an updated __setitem__

    """
    def __init__(self, config_values, *args, **kwargs):
        self._config_values = config_values

    def __setitem__(self, key, value):
        if key in self:
            self.logger.warning("Key is already defined: %s" % key)
        self.update_value(key, value)

    def update_value(self, key, value):
        kwargs = dict()
        kwargs['logger'] = self.logger
        kwargs['name'] = key
        if value is None:
            kwargs['defined'] = False

        if isinstance(value, dict):
            self.logger.info("Advanced config detected for config: %s" % key)
            self.logger.debug("Config: %s" % value)
            kwargs['value'] = value['value']
            if 'description' in value:
                kwargs['description'] = value['description']
            if 'if' in value:
                if True not in [self.check_expression(expression) for expression in value['if']]:
                    self.logger.warning("All tests failed for: %s" % value)
                    return
        else:
            kwargs['value'] = value
        super().__setitem__(key, LinuxKernelConfigParameter(**kwargs))

    def check_expression(self, expression):
        self.logger.debug("Checking expression: %s" % expression)
        if 'in' in expression:
            value = expression['value']
            config = self._config_values[expression['in']]
            self.logger.debug("Checking that '%s' is in list: %s" % (value, config))
            return True if value in config else False
        return False

    def __str__(self):
        return "".join([f"{str(parameter)}\n" for parameter in self.values()])


@class_logger
class LinuxKernelConfig:
    """
    Abstraction of a collection of 'LinuxKernelConfigParameter's
    """
    def __init__(self, config_file, *args, **kwargs):
        self.kconfig = KConfig()
        self.load_config(config_file)
        self.config_parameters = KernelDict(self.config)

        if kernel_config_files := kwargs.get('kernel_config_files'):
            self.from_config_files(kernel_config_files)
        elif kernel_config_file := kwargs.get('kernel_config_file'):
            self.from_config_file(kernel_config_file)

        self.logger.info("Parsed config parameters:\n%s" % self.config_parameters)

    def load_config(self, file_name: str):
        """ Loads the config from a file """
        with open(file_name, 'r') as config_file:
            self.logger.info("Loading config from file: %s" % config_file.name)
            self.config = safe_load(config_file)

    def from_config_files(self, file_names: list):
        """ Parses each file name, in the order it's defined in the list """
        for file_name in file_names:
            self.from_config_file(file_name)

    def from_config_file(self, file_name: str):
        """ Parses a yaml file into the current loaded kernel config """
        with open(file_name, 'r') as config_file:
            file_contents = safe_load(config_file)
            for name, value in file_contents.items():
                self.logger.debug("Processing parameter '%s' with value: %s" % (name, value))
                self.config_parameters[name] = value

