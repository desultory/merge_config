#!/usr/bin/env python3
"""
Python implementation of the linux kernel merge-config kconfig bash script

Some options are missing
Can process the file with/without make

"""

from ColorLognameFormatter import ColorLognameFormatter
import argparse
import logging
import os
import re

DEFAULT_CONFIG_FILE = 'arch/x86/configs/x86_64_defconfig'
DEFAULT_OUT_FILE = '.config'


class ConfigMerger:
    _CONFIG_REGEX = re.compile(r'(CONFIG)([a-zA-Z0-9_])+')
    _DEFAULT_OUT_FILE = DEFAULT_OUT_FILE
    # Ensure slightly different rules for captures in quotes/not
    _DEFINE_REGEX = r'^([a-zA-Z0-9_])+=(-?([0-9])+|[yn]+|"([a-zA-Z0-9/_.,-=\(\) ])*")$'
    _UNDEFINE_REGEX = re.compile(r"^(# CONFIG_)([a-zA-Z0-9_]+)( is not set)$")
    _strict_fail = False

    def __init__(self, base_file, merge_files, out_file_name=_DEFAULT_OUT_FILE, custom_parameters=[], allnoconfig=False, strict_mode=False, log_level=logging.WARNING, no_make=False):
        self.log_level = log_level
        self.logger = logging.getLogger("ConfigMerger")
        self.logger.setLevel(self.log_level)
        self._stdout_handler = logging.StreamHandler()
        self._stdout_handler.setLevel(self.log_level)
        self._stdout_handler.setFormatter(ColorLognameFormatter())
        self.logger.addHandler(self._stdout_handler)
        self.logger.propagate = False
        self.logger.debug("Initialized logging")

        self.base_file = base_file
        self.logger.debug("Set the base file name to: %s", self.base_file)
        self.merge_files = merge_files
        self.logger.debug("Set the merge files to: %s", self.merge_files)
        self.custom_parameters = custom_parameters
        self.logger.debug("Set the custom parameters to: %s", self.custom_parameters)
        self.out_file_name = out_file_name
        self.logger.debug("Set the output file name to: %s", self.out_file_name)
        self.allnoconfig = allnoconfig
        self.logger.debug("Set allnoconfig to: %s", self.allnoconfig)
        self.strict_mode = strict_mode
        self.logger.debug("Set strict mode to: %s", self.strict_mode)
        self.no_make = no_make
        self.logger.debug("Set no make to: %s", self.no_make)

        self.process()

    def process(self):
        """
        Processes the config based on the supplied parameters
        """
        # Load the base config
        self.load()

        # Merge config files
        if self.merge_files:
            self.process_merge_files()
        elif not self.custom_parameters:
            self.logger.error("No merge files or custom parameters specified")

        if self.custom_parameters:
            self.process_custom_parameters()

        self.write_config()

        if not self.no_make:
            self.make_config()
            make_processed_config = self._load_config(self.out_file_name)
            self.compare_config(make_processed_config)

    def classify_line(self, line):
        """
        Classifies a line as a define, undefine or unknown
        Returns true for a define, false for an undefine
        """
        # Check that the line contains expected config syntax
        if not re.search(self._CONFIG_REGEX, line):
            raise SyntaxWarning(f"The following line does not seem to contain a kernel .config parameter: {line}")

        if re.match(self._DEFINE_REGEX, line):
            return True

        if re.match(self._UNDEFINE_REGEX, line):
            return False

        raise SyntaxWarning(f"Unable to interpret config parameter: {line}")

    def parse_line(self, input_line):
        """
        Attempts to parse an input line, returns a tuple and dict containing the config information
        """
        line = input_line.rstrip()
        if self.classify_line(line):
            return self.parse_define(line)
        else:
            return self.parse_undefine(line)

    def parse_define(self, input_line):
        """
        Attempts to parse a config definition, returns the name and a dict containing the values and whether it should be defined
        Returns the name and value of the config line
        """
        line = self.strip_comment(input_line)
        if not re.match(self._DEFINE_REGEX, line):
            raise SyntaxError(f"The input line failed the definition regex: {line}")

        return self.split_parameter(input_line)

    def strip_comment(self, input_line):
        """
        Removes comments from a string
        """
        if '#' in input_line:
            self.logger.debug("Comment detected, removing: %s", input_line)
            input_line = input_line[:input_line.find('#')].strip()
            self.logger.debug("Processed line: %s", input_line)
        return input_line

    def split_parameter(self, input_config):
        """
        Splits a config line into a config variable and value
        """
        eq_loc = input_config.find('=')

        name = input_config[:eq_loc]
        self.logger.debug("Detected name: %s", name)

        value = input_config[eq_loc + 1:]
        self.logger.debug("Detected value: %s", value)

        return name, value

    def parse_undefine(self, input_line):
        """
        Attempts to parse a config undefinition
        Returns the name of the config variable
        """
        if not re.match(self._UNDEFINE_REGEX, input_line):
            raise SyntaxError(f"The input line failed the undefinition regex: {input_line}")

        self.logger.debug("Parsing line: %s", input_line)
        name = "CONFIG_" + re.search(self._UNDEFINE_REGEX, input_line).group(2)
        self.logger.debug("Detected undefine for variable: %s", name)

        return name, False

    def compare_config(self, other_config):
        """
        Compare the key differences between then loaded config and old config
        Both objects should be the dict type used in this script
        """
        for config_name in self.base_config:
            self.logger.debug("Checking config name: %s", config_name)
            if config_name not in other_config:
                self.logger.warning("Argument is undefined when it should be set to: %s=%s",
                                    config_name,
                                    self.base_config[config_name])
            elif other_config[config_name] != self.base_config[config_name]:
                self.logger.warning("Argument value mismatch for: %s  | Found: %s | Expected: %s",
                                    config_name,
                                    other_config[config_name],
                                    self.base_config[config_name])
            else:
                self.logger.debug("Config check passed")

    def load(self, config_file_name=None):
        """
        Loads a config file, self.base_file by default, into self.base_config
        """
        if not config_file_name:
            config_file_name = self.base_file
        self.base_config = self._load_config(config_file_name)

    def _load_config(self, config_file_name=None):
        """
        Processes and returns a config file as a dict
        """
        self.logger.debug("Loading the config file: %s", config_file_name)
        with open(config_file_name, 'r') as config_file:
            kernel_config = {}
            self.logger.info("Processing the config file: %s", config_file.name)
            for line in config_file.readlines():
                try:
                    name, value = self.parse_line(line)
                    kernel_config[name] = value
                # Allow the value errors but throw errors
                except SyntaxError as e:
                    self.logger.error(e)
                except SyntaxWarning as e:
                    self.logger.debug(e)
            # Throw a value error if the file could not be processed
            if not kernel_config:
                raise RuntimeWarning(f"Failed to load base config from {self.base_file}")
        return kernel_config

    def merge_config(self, merge_config):
        """
        Merges the supplied config wile with the base config
        If strict mode is enabled, errors will be emitted when parameters are redefined
        The script should process them all, but will eventually fail
        """
        changed = False
        for name, value in merge_config.items():
            if name in self.base_config:
                self.logger.info("Config var aleady detected in the base config: %s=%s", name, self.base_config.get(name))
                if self.strict_mode:
                    self.logger.error("Attempting to redefine in strict mode: %s=%s", name, value)
                    self._strict_fail = True
                elif value == self.base_config[name]:
                    self.logger.debug("Merge value equals base value: %s=%s", name, value)
                elif value:
                    self.logger.info("Updated value: %s=%s", name, value)
                    self.base_config[name] = value
                    changed = True
                else:
                    self.logger.info("Marking config var for deletion: %s", name)
                    self.base_config[name] = value
                    changed = True
            else:
                if value:
                    self.logger.info("New config parameter: %s=%s", name, value)
                    self.base_config[name] = value
                    changed = True
                else:
                    self.logger.warning("Attempting to undefine a parameter which is not defined: %s", name)
                    self.base_config[name] = value
                    changed = True
        if not changed:
            raise RuntimeWarning("No changes detected after processing config")

    def make_config(self):
        """
        Runs the output .config file through make
        outputs a working .config file for the current kernel version
        Uses allnoconfig if allnoconfig is True, otherwise uses alldefconfig
        Substitutes the generated config into KCONFIG_ALLCONFIG
        """
        make_args = f"make KCONFIG_ALLCONFIG={self.out_file_name} "
        make_args += "allnoconfig" if self.allnoconfig else "alldefconfig"
        self.logger.info("Running the following make command: %s", make_args)
        output = os.system(make_args)
        if output != 0:
            raise RuntimeError(f"Unable to run make command, args: {make_args}")

    def process_merge_files(self):
        """
        Iterates through the merge files and attempts to apply them over the base config
        """
        # Sections are applied over the base config as they are processed
        for merge_file in self.merge_files:
            try:
                self.logger.info("Attempting to merge file: %s", merge_file)
                self.merge_config(self._load_config(merge_file))
            except RuntimeWarning as e:
                self.logger.warning("%s file: %s", e, merge_file)

        self.logger.info("Merging has completed")

        if self._strict_fail:
            raise RuntimeError("Strict mode is enabled and has detected a failure")

    def process_custom_parameters(self):
        """
        Iterates through the custom parameters and attempts to apply them over the base config
        """
        params = {}
        for parameter in self.custom_parameters:
            self.logger.debug("Attempting to parse passed config parameter: %s", parameter)
            try:
                name, value = self.parse_line(parameter)
                self.logger.info("Loaded parameter from the command line: %s=%s", name, value)
                params[name] = value
            except SyntaxWarning as e:
                self.logger.warning(e)
        try:
            self.merge_config(params)
        except RuntimeWarning as e:
            self.logger.warning("%s: passed parameters", e)

    def __str__(self):
        """
        Returns self.base_config as a string, as it should be represented in a config file
        """
        out_str = ''
        for name, value in self.base_config.items():
            if value:
                out_str += f"{name}={value}\n"
            else:
                out_str += f"# {name} is not set\n"
        return out_str

    def write_config(self):
        """
        Takes a dictionary where the name is the config variable name, and the value is the... value
        writes as CONFIG_{name}={value}
        Writes to self.out_file_name
        """
        self.logger.info("Writing config file: %s", self.out_file_name)
        with open(self.out_file_name, 'w') as out_file:
            out_file.write(self.__str__())
        self.logger.info("Wrote config file: %s", self.out_file_name)


if __name__ == '__main__':
    debug = int(os.environ.get('DEBUG', 0))
    log_level = logging.DEBUG if debug else logging.INFO

    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)

    stdout_handler = logging.StreamHandler()

    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(ColorLognameFormatter())

    logger.addHandler(stdout_handler)

    logger.propagate = False
    logging.debug("Initialized logging")

    # Initialise the arg parser
    parser = argparse.ArgumentParser(prog='merge-config',
                                     description='Merges kernel.config files')
    # Add the make arg
    parser.add_argument('-m',
                        action='store_true',
                        help="Only merge fragments, disables using make to compile the final config")
    # Add the noconfig arg
    parser.add_argument('-n',
                        action='store_true',
                        help="Use allnoconfig instead of alldefconfig")
    # Add a debugging arg
    parser.add_argument('-v',
                        action='count',
                        default=0,
                        help="Enables debugging, set your DEBUG environment variable to 1 for earlier debugging, set to -vv for even more debug info")
    # Add the output file arg
    parser.add_argument('-o',
                        type=str,
                        default=DEFAULT_OUT_FILE,
                        help=f"The output file location, the default is {DEFAULT_OUT_FILE}")
    # Add the default config arg
    parser.add_argument('-d',
                        action='store_true',
                        help=f"Use {DEFAULT_CONFIG_FILE} as the base file")
    # Add the strict mode arg
    parser.add_argument('-s',
                        action='store_true',
                        help="Enable strict mode, the script will fail if any value is redefined")
    # Add the parameter argument
    parser.add_argument('-p',
                        action='append',
                        help="Specify parameters by command line")
    # First take the base argument
    # If this is the only argument, use it as the merge file using the DEFAULT_CONFIG_FILE as the base file
    parser.add_argument('base_file',
                        type=str,
                        help=f"The base kernel file, defaults to {DEFAULT_CONFIG_FILE}")
    # Then take the rest of the arguments as files to open
    parser.add_argument('merge_files',
                        type=str,
                        nargs='*',
                        help="Files to be merged")
    args = parser.parse_args()

    if debug or args.v == 2:
        log_level = logging.DEBUG
    elif args.v == 1:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING
    logger.setLevel(log_level)
    stdout_handler.setLevel(log_level)
    logger.debug("Parsed the arguments")

    merge_files = []
    # If the default flag is enabled, move the passed base file to the merge files
    if args.d:
        logger.info("Using %s as the base config file", DEFAULT_CONFIG_FILE)
        base_file = DEFAULT_CONFIG_FILE
        merge_files.append(args.base_file)
        # if -d is passed, and there are still merge files, add them
        if args.merge_files:
            merge_files += args.merge_files
    else:
        logger.info("Using %s as the base config file", args.base_file)
        base_file = args.base_file
        merge_files = args.merge_files

    for file in merge_files:
        logger.info("Considering file %s for merge", file)

    config_merger = ConfigMerger(base_file,
                                 merge_files,
                                 custom_parameters=args.p,
                                 out_file_name=args.o,
                                 allnoconfig=args.m,
                                 strict_mode=args.s,
                                 log_level=log_level,
                                 no_make=args.m)
