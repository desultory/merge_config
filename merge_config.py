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
import regex


CONFIG_REGEX = regex.compile(r'(CONFIG)([a-zA-Z0-9_])+')
DEFAULT_CONFIG = 'arch/x86/configs/x86_64_defconfig'
DEFAULT_OUT_FILE = '.config'
DEFINE_START = "CONFIG_"
# Ensure slightly different rules for captures in quotes/not
DEFINE_REGEX = r'^([a-zA-Z0-9_])+=(-?([a-zA-Z0-9])+|"([a-zA-Z0-9/_.,-=\(\) ])*")$'
UNDEFINE_START = "# CONFIG_"
UNDEFINE_END = " is not set"
UNDEFINE_REGEX = regex.compile(r"^([a-zA-Z0-9_]+)$")

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


class ConfigMerger:
    _strict_fail = False
    def __init__(self, base_file, merge_files, out_file_name=DEFAULT_OUT_FILE, allnoconfig=False, strict_mode=False, log_level=logging.WARNING, no_make=False):
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
        self.out_file_name = out_file_name
        self.logger.debug("Set the output file name to: %s", self.out_file_name)
        self.allnoconfig = allnoconfig
        self.logger.debug("Set allnoconfig to: %b", self.allnoconfig)
        self.strict_mode = strict_mode
        self.logger.debug("Set strict mode to: %b", self.strict_mode)
        self.no_make = no_make
        self.logger.debug("Set no make to : %b", self.no_make)

        self.load_config()
        self.process_config()
        self.write_config()

        if not no_make:
            self.old_config = self.base_config.copy()
            self.make_config()
            self.base_file = out_file_name
            self.logger.info("Changing the base file to: %s", self.base_file)
            self.load_config()
            self.compare_config()

    def line_to_config(self, file_line):
        """
        Attempts to convert a line in a .config file to a config parameter
        Returns a tuple contaning the name of the parameter and a dict
        containing the value information or if it should be removed from the config
        and the parameter info, which is the line stripped of other information
        """
        # Do a basic string clean
        line = file_line.rstrip()
        # Check that the line contains expected config syntax
        if not regex.search(CONFIG_REGEX, line):
            raise SyntaxWarning(f"`{line}` does not seem to be a kernel .config parameter")
        # Define should be implied, gets unset by undefinitions
        define = True

        # Ensure the entire line starts and ends with these values
        if line.startswith(UNDEFINE_START) and line.endswith(UNDEFINE_END):
            self.logger.debug("Detected an undefine")
            # Removing all portions of the line other than the config variable name
            config_var = line.replace(UNDEFINE_START, '').replace(UNDEFINE_END, '')
            if regex.match(UNDEFINE_REGEX, config_var):
                # Extract the regex match if it exists
                config_var = regex.search(UNDEFINE_REGEX, config_var).group(1)
                self.logger.debug("Detected config variable: %s", config_var)
                # Return the config variable name, and instructions to not define
                return config_var, {"define": False}
            else:
                raise ValueError(f"Configuration variable: {config_var} failed the regex")
        # When a standard definition is detected
        elif line.startswith(DEFINE_START):
            self.logger.debug("Detected a defintion")
            # Remove the start of the definition for processing
            config_var = line.replace(DEFINE_START, '')
            # Consider line comments
            if "#" in config_var:
                self.logger.debug("Comment detected, removing")
                # Cut the string to where the comment is found
                config_var = config_var[:config_var.find("#")]
                # Clean the string
                config_var = config_var.strip()
            # Check that the string matches the definition regex
            if regex.match(DEFINE_REGEX, config_var) or regex.match(DEFINE_REGEX, config_var):
                # Find the location of the = character, to split the config_var and value
                eq_loc = config_var.find('=')
                # The value is everything after the equal sign
                value = config_var[eq_loc + 1:]
                self.logger.debug("Detected value: %s", value)
                # The config_var is everything before, this also strips the = sign
                config_var = config_var[:eq_loc]
                if config_var and value:
                    self.logger.debug("Detected config variable: %s", config_var)
                    return config_var, {"define": define,
                                        "value": value}
                raise ValueError(f"Configuration variable is defined with no value: {config_var}")
            else:
                raise ValueError(f"Configuration variable faliled the regex: {config_var}")
        else:
            raise SyntaxWarning(f"Unable to parse possible config line: {line}")

    def compare_config(self):
        """
        Compare the key differences between then loaded config and old config
        Both objects should be the dict type used in this script
        """
        for config_name in self.old_config:
            logger.debug("Checking config name: %s", config_name)
            if config_name not in self.base_config:
                logger.warning("Argument `%s` is undefined when it should be set to: %s",
                               config_name,
                               self.old_config[config_name].get('value'))
            elif self.base_config[config_name] != self.old_config[config_name]:
                logger.warning("Argument value mismatch for: %s  | Found: %s | Expected: %s",
                               config_name,
                               self.base_config[config_name].get('value'),
                               self.old_config[config_name].get('value'))

    def load_config(self):
        """
        Loads self.base_file into self.base_config
        """
        self.logger.debug("Loading the base config")
        with open(self.base_file, 'r') as config_file:
            kernel_config = {}
            self.logger.info("Processing the config file: %s", config_file.name)
            for line in config_file.readlines():
                try:
                    name, config = self.line_to_config(line)
                    self.logger.debug("Detected config name: %s", name)
                    # Ignore undefines in the base config
                    if not config.get('define'):
                        self.logger.debug("Line is an undefine in the base config, ignoring parameter: %s", name)
                    else:
                        self.logger.debug("Saving parameter: %s=%s", name, config.get('value'))
                        kernel_config[name] = config
                # Allow the value errors but throw errors
                except ValueError as e:
                    self.logger.error(e)
                except SyntaxWarning as e:
                    self.logger.debug(e)
            # Throw a value error if the file could not be processed
            if not kernel_config:
                raise ValueError(f"Failed to load base config from {self.base_file}")
        self.base_config = kernel_config

    def merge_config(self, merge_file_name):
        """
        Merges the supplied config wile with the base config
        If strict mode is enabled, errors will be emitted when parameters are redefined
        The script should process them all, but will eventually fail
        """

        # Copy the dict
        merged_config = self.base_config.copy()
        self.logger.info("Opening config file for merge: %s", merge_file_name)
        with open(merge_file_name, 'r') as merge_file:
            for line in merge_file.readlines():
                try:
                    name, new_config = self.line_to_config(line)
                    if name in self.base_config:
                        self.logger.info("Config var aleady detected in the base config: %s", name)
                        self.logger.info("Current value: %s", self.base_config.get(name).get('value'))
                        if self.strict_mode:
                            self.logger.error("Attempting to redefine in strict mode: %s=%s", name, new_config.get('value'))
                            self._strict_fail = True
                        elif new_config.get('define'):
                            self.logger.info("New value: %s", new_config.get('value'))
                            merged_config[name] = new_config
                        else:
                            self.logger.info("Deleting config entry for config var: %s", name)
                            del merged_config[name]
                    else:
                        self.logger.info("Config var does not exist in the base config: %s", name)
                        if new_config.get('define'):
                            self.logger.info("New value: %s", new_config.get('value'))
                            merged_config[name] = new_config
                        else:
                            self.logger.warning("Attempting to undefine a parameter which is not defined: %s", name)
                except ValueError as e:
                    self.logger.error(e)
                except SyntaxWarning as e:
                    self.logger.debug(e)

        if merged_config == self.base_config:
            logger.warning("No changes detected after merging: %s", merge_file_name)

        self.base_config = merged_config

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
        output = os.system(make_args)
        if output != 0:
            raise RuntimeError(f"Unable to run make command, args: {make_args}")

    def process_config(self):
        """
        Merges
        Processes the base file into base config
        Iterates through the merge files and attempts to apply them over the base file
        returns the merged base file once complete
        """
        # Load the base config from the passed base config file if it's not defined
        if not self.base_config:
            self.load_config

        # Keep processing merge files while the list is populated
        # Item entries are popped from the list when processing has started
        # This should not run endlessly but may fail to process each merge section
        # Sections are applied over the base config as they are processed
        for merge_file in self.merge_files:
            self.merge_config(merge_file)
        logger.info("Merging has completed")
    
        if self._strict_fail:
            raise RuntimeError("Strict mode is enabled and has detected a failure")

    def write_config(self):
        """
        Takes a dictionary where the name is the config variable name, and the value is the... value
        writes as CONFIG_{name}={value}
        Writes to self.out_file_name
        """
        self.logger.info("Writing config file: %s", self.out_file_name)
        with open(self.out_file_name, 'w') as out_file:
            out_file.write("## Starting config\n")
            for name, items in self.base_config.items():
                value = items.get('value')
                out_file.write(f"CONFIG_{name}={value}\n")
            out_file.write("## Ending config\n")
        self.logger.info("Wrote config file: %s", self.out_file_name)


if __name__ == '__main__':
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
                        help=f"Use {DEFAULT_CONFIG} as the base file")
    # Add the strict mode arg
    parser.add_argument('-s',
                        action='store_true',
                        help="Enable strict mode, the script will fail if any value is redefined")
    # First take the base argument
    # If this is the only argument, use it as the merge file using the DEFAULT_CONFIG as the base file
    parser.add_argument('base_file',
                        type=str,
                        help=f"The base kernel file, defaults to {DEFAULT_CONFIG}")
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
    # If no merge files are passed, assume the base file is actually a merge file
    # If the default flag is enabled, move the passed base file to the merge files
    if args.d or not args.merge_files:
        logger.info("Using %s as the base config file", DEFAULT_CONFIG)
        base_file = DEFAULT_CONFIG
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

    config_merger = ConfigMerger(base_file, merge_files, out_file_name=args.o, allnoconfig=args.m, strict_mode=args.s, log_level=log_level, no_make=args.m)

