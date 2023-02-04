#!/usr/bin/env python3
"""
Python implementation of the linux kernel merge-config kconfig bash script

Some options are missing
Can process the file with/without make

"""

from ColorLognameFormatter import ColorLognameFormatter
from enum import Enum
import argparse
import logging
import os
import subprocess
import re

DEFAULT_CONFIG_FILE = 'arch/x86/configs/x86_64_defconfig'
DEFAULT_OUT_FILE = '.config'

logger = logging.getLogger(__name__)

stdout_handler = logging.StreamHandler()
stdout_handler.setFormatter(ColorLognameFormatter())

logger.addHandler(stdout_handler)
logger.propagate = False


class ParserWarning(Exception):
    pass


class ParserError(Exception):
    pass


class ConfigLineTypes(Enum):
    DEFINE = 1
    UNDEFINE = 2
    INVALID = 3


class KernelConfigParameter:
    """
    A single kernel configuration parameter
    """
    _CONFIG_REGEX = re.compile(r'(CONFIG)([a-zA-Z0-9_])+')
    _DEFINE_REGEX = r'^([a-zA-Z0-9_])+=(-?([0-9])+|[ynm]+|"([a-zA-Z0-9/_.,-=\(\) ])*")$'
    _UNDEFINE_REGEX = re.compile(r"^(# CONFIG_)([a-zA-Z0-9_]+)( is not set)$")

    name = ''
    value = ''
    define_type = ConfigLineTypes.INVALID

    def __init__(self, raw_config_line):
        self.raw_config_line = raw_config_line
        logger.debug("Set the raw config line to: %s", raw_config_line)

        self.parse_line()

    def clean_line(self):
        """
        Strips unwanted characters from the input config line, sets config_line
        """
        self.config_line = self.raw_config_line.rstrip()
        logger.debug("Clean Line: %s", self.config_line)

    def classify_line(self):
        """
        Classifies a line as a define, undefine or invalid
        """
        # Check that the line contains expected config syntax
        if not re.search(self._CONFIG_REGEX, self.config_line):
            raise ParserWarning(f"The following line does not seem to contain a kernel .config parameter: {self.config_line}")
            self.define_type = ConfigLineTypes.INVALID
        elif re.match(self._DEFINE_REGEX, self.config_line):
            self.define_type = ConfigLineTypes.DEFINE
        elif re.match(self._UNDEFINE_REGEX, self.config_line):
            self.define_type = ConfigLineTypes.UNDEFINE
        else:
            raise ParserWarning(f"Unable to interpret config parameter: {self.config_line}")

    def parse_line(self):
        """
        Attempts to parse self.config_line based on self.define_type
        """
        self.clean_line()
        self.classify_line()
        match self.define_type:
            case ConfigLineTypes.DEFINE:
                return self.parse_define()
            case ConfigLineTypes.UNDEFINE:
                return self.parse_undefine()
            case ConfigLineTypes.INVALID:
                raise ParserWarning("Attempting to call parse line when the define type is invald")

    def parse_define(self):
        """
        Attempts to parse a config definition
        Sets the name and value of the config line
        """
        self.strip_comment()
        if not re.match(self._DEFINE_REGEX, self.config_line):
            raise ParserError(f"The input line failed the definition regex: {self.config_line}")

        eq_loc = self.config_line.find('=')
        self.name = self.config_line[:eq_loc]
        logger.debug("Set name: %s", self.name)
        self.value = self.config_line[eq_loc + 1:]
        logger.debug("Set value: %s", self.value)

    def strip_comment(self):
        """
        Removes comments from the config line
        """
        if '#' in self.config_line:
            logger.debug("Comment detected, removing: %s", self.config_line)
            self.config_line = self.config_line[:self.config_line.find('#')].strip()
            logger.debug("Processed line: %s", self.config_line)

    def parse_undefine(self):
        """
        Attempts to parse a config undefinition
        Sets the name of the config variable
        """
        if not re.match(self._UNDEFINE_REGEX, self.config_line):
            raise ParserError(f"The input line failed the undefinition regex: {self.config_line}")

        logger.debug("Parsing line: %s", self.config_line)
        self.name = "CONFIG_" + re.search(self._UNDEFINE_REGEX, self.config_line).group(2)
        logger.debug("Detected undefine for variable: %s", self.name)
        self.value = False

    def __str__(self):
        """
        Represents the Kernel Config Parameter as a string
        """
        match self.define_type:
            case ConfigLineTypes.DEFINE:
                return f"{self.name}={self.value}"
            case ConfigLineTypes.UNDEFINE:
                return f"# {self.name} is not set"
            case ConfigLineTypes.INVALID:
                return self.config_line


class KernelConfig:
    """
    A collection of kernel config parameters
    """
    def __init__(self, config_file=None, config_parameters=[]):
        if not config_file and not config_parameters:
            raise ValueError("Either a config file or parameters should be defined")

        self.config_file = config_file
        logger.debug("Set the config file to: %s", self.config_file)

        self.config_parameters = config_parameters
        logger.debug("Set the config parameters to: %s", self.config_parameters)

        self.config = {}
        self.process()

    def process(self):
        """
        Loads a config file, self.config_file into self.config
        """
        if self.config_file:
            self.config = self._load_config(self.config_file)
            logger.info("Loaded kernel config file: %s", self.config_file)
        if self.config_parameters:
            self.process_list_parameters()

    def _load_config(self, config_file_name):
        """
        Processes and returns a config file as a dict
        """
        logger.debug("Loading the config file: %s", config_file_name)
        with open(config_file_name, 'r') as config_file:
            kernel_config = {}
            logger.info("Processing the config file: %s", config_file.name)
            for line in config_file.readlines():
                try:
                    config_parameter = KernelConfigParameter(line)
                    kernel_config[config_parameter.name] = config_parameter
                # Allow the value errors but throw errors
                except ParserError as e:
                    logger.error(e)
                except ParserWarning as e:
                    logger.debug(e)
            # Throw a value error if the file could not be processed
            if not kernel_config:
                raise RuntimeWarning(f"Failed to load kernel config from {config_file_name}")
        return kernel_config

    def process_list_parameters(self):
        """
        Iterates through the custom parameters and attempts to apply them over the base config
        """
        for parameter in self.config_parameters:
            logger.debug("Attempting to parse passed config parameter: %s", parameter)
            try:
                config_parameter = KernelConfigParameter(parameter)
                self.config[config_parameter.name] = config_parameter
                logger.debug("Loaded config parameter from list: %s", config_parameter)
            except ParserWarning as e:
                logger.warning(e)

    def __str__(self):
        """
        Iterates through all kernel config parameters and outputs them as a large string
        """
        out_str = ''
        for name, parameter in self.config.items():
            out_str += str(parameter) + "\n"

        return out_str


class ConfigMerger:
    def __init__(self,
                 base_file,
                 merge_files,
                 out_file_name,
                 custom_parameters=[],
                 allnoconfig=False,
                 no_make=False,
                 strict_mode=False):

        self.base_file = base_file
        logger.debug("Set the base file name to: %s", self.base_file)
        self.merge_files = merge_files
        logger.debug("Set the merge files to: %s", self.merge_files)
        self.custom_parameters = custom_parameters
        logger.debug("Set the custom parameters to: %s", self.custom_parameters)
        self.out_file_name = out_file_name
        logger.debug("Set the output file name to: %s", self.out_file_name)
        self.allnoconfig = allnoconfig
        logger.debug("Set allnoconfig to: %s", self.allnoconfig)
        self.strict_mode = strict_mode
        self._strict_fail = False
        logger.debug("Set strict mode to: %s", self.strict_mode)
        self.no_make = no_make
        logger.debug("Set no make to: %s", self.no_make)

    def process(self):
        """
        Processes the config based on the supplied parameters
        """
        # Load the base config
        self.base_config = KernelConfig(config_file=self.base_file)
        # Merge config files
        if self.merge_files or self.custom_parameters:
            self.process_merge()
        else:
            logger.error("No merge files or custom parameters specified")

        if not self.no_make:
            self.make_config()
            make_processed_config = KernelConfig(self.out_file_name)
            self._compare_config(make_processed_config)

    def _compare_config(self, other_config):
        """
        Compare the key differences between then loaded config and old config
        Both objects should be the dict type used in this script
        """
        for name, config in self.base_config.config.items():
            logger.debug("Checking config name: %s", name)
            if name not in other_config.config:
                logger.warning("Argument is undefined when it should be set: %s=%s",
                               name,
                               config.name)
            elif other_config.config[name] != self.base_config.config[name]:
                logger.warning("Argument value mismatch for: %s :: Found: %s | Expected: %s",
                               name,
                               other_config.config[name].value,
                               config.value)
            else:
                logger.debug("Config check passed")

    def _merge_config(self, merge_config):
        """
        Merges the supplied config wile with the base config
        If strict mode is enabled, errors will be emitted when parameters are redefined
        The script should process them all, but will eventually fail
        """
        changed = False
        for name, value in merge_config.config.items():
            if name in self.base_config.config:
                if self.strict_mode:
                    logger.error("Attempting to redefine in strict mode: %s", value)
                    self._strict_fail = True
                elif value == self.base_config.config[name]:
                    logger.debug("Merge value equals base value: %s", value)
                elif value:
                    logger.info("Updated value: %s", value)
                    self.base_config.config[name] = value
                    changed = True
                elif not value and not self.base_config[name]:
                    logger.debug("Value already marked for delection: %s", value)
                else:
                    logger.info("Marking config var for deletion: %s", name)
                    self.base_config.config[name] = value
                    changed = True
            else:
                if value:
                    logger.info("New config parameter: %s", value)
                    self.base_config.config[name] = value
                    changed = True
                else:
                    logger.warning("Undefining a parameter which is not currently defined: %s", name)
                    self.base_config.config[name] = value
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
        logger.info("Running the following make command: %s", make_args)
        try:
            subprocess.check_output(make_args.split(), stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Unable to run make command, args: {make_args}  |  error: {e}")

    def process_merge(self):
        """
        Iterates through the merge files and attempts to apply them over the base config
        """
        # Sections are applied over the base config as they are processed
        logger.info("Attempting to merge passed files")
        for merge_file in self.merge_files:
            logger.info("Attempting to merge file: %s", merge_file)
            merge_config = KernelConfig(merge_file)
            try:
                self._merge_config(merge_config)
            except RuntimeWarning as e:
                logger.warning("%s file: %s", e, merge_file)

        if self.custom_parameters:
            logger.info("Attempting to merge passed parameters")
            merge_config = KernelConfig(config_parameters=self.custom_parameters)
            try:
                self._merge_config(merge_config)
            except RuntimeWarning as e:
                logger.warning("%s parameter: %s", e, self.custom_parameters)

        logger.info("Merging has completed")

        if self._strict_fail:
            raise RuntimeError("Strict mode is enabled and has detected a failure")

    def write_config(self):
        """
        writes the base config to the output file
        """
        logger.info("Writing config file: %s", self.out_file_name)
        with open(self.out_file_name, 'w') as out_file:
            out_file.write(str(self.base_config))
        logger.info("Wrote config file: %s", self.out_file_name)


if __name__ == '__main__':
    debug = int(os.environ.get('DEBUG', 0))
    log_level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(log_level)
    stdout_handler.setLevel(log_level)
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
    if args.d or args.base_file and not args.merge_files:
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
                                 no_make=args.m)

    config_merger.process()
    config_merger.write_config()
