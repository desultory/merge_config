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


def line_to_config(file_line):
    """
    Attempts to convert a line in a .config file to a config parameter
    Returns a tuple contaning the name of the parameter and a dict
    containing the value information or if it should be removed from the config
    and the parameter info, which is the line stripped of other information
    """
    # Do a basic string clean
    line = file_line.rstrip()
    # Every kernel parameter should have "CONFIG_ABC_XYZ" present
    # If it does not, raise a SyntaxWarning
    if not regex.search(CONFIG_REGEX, line):
        raise SyntaxWarning(f"`{line}` does not seem to be a kernel .config parameter")
    # Define should be implied, gets unset by undefinitions
    define = True

    # Ensure the entire line starts and ends with these values
    if line.startswith(UNDEFINE_START) and line.endswith(UNDEFINE_END):
        logger.debug("Detected an undefine")
        # Removing all portions of the line other than the parameter name
        parameter = line.replace(UNDEFINE_START, '').replace(UNDEFINE_END, '')
        if regex.match(UNDEFINE_REGEX, parameter):
            # Extract the regex match if it exists
            parameter = regex.search(UNDEFINE_REGEX, parameter).group(1)
            logger.debug("Detected paramter: %s", parameter)
            # Return the parameter name, and instructions to not define
            return parameter, {"define": False}
        else:
            raise ValueError(f"Parameter: {parameter} failed the regex")
    # When a standard definition is detected
    elif line.startswith(DEFINE_START):
        logger.debug("Detected a defintion")
        # Remove the start of the definition for processing
        parameter = line.replace(DEFINE_START, '')
        # Consider line comments
        if "#" in parameter:
            logger.debug("Comment detected, removing")
            # Cut the string to where the comment is found
            parameter = parameter[:parameter.find("#")]
            # Clean the string
            parameter = parameter.strip()
        # Check that the string matches the definition regex
        if regex.match(DEFINE_REGEX, parameter) or regex.match(DEFINE_REGEX, parameter):
            # Find the location of the = character, to split the parameter and value
            eq_loc = parameter.find('=')
            # The value is everything after the equal sign
            value = parameter[eq_loc + 1:]
            logger.debug("Detected value: %s", value)
            # The parameter is everything before, this also strips the = sign
            parameter = parameter[:eq_loc]
            if parameter and value:
                logger.debug("Detected paramter: %s", parameter)
                return parameter, {"define": define,
                                   "value": value}
            raise ValueError(f"Parameter `{parameter}` is defined with no value")
        else:
            raise ValueError(f"Parameter: {parameter} failed the regex")
    else:
        raise SyntaxWarning(f"Unable to parse possible config line: {line}")


def compare_config(config_full, config_diff):
    """
    Compare the key differences between config files
    Config_full should be the most complete one, such as the one make generates
    config_diff should be one with intended configuration
    Both objects should be the dict type used in this script
    """
    for config_name in config_diff:
        logger.debug("Checking config name: %s", config_name)
        if config_name not in config_full:
            logger.warning("Argument `%s` is undefined when it should be", config_name)
            logger.warning("Expected value: %s", config_diff[config_name].get('value'))
        elif config_full[config_name] != config_diff[config_name]:
            logger.warning("Argument value mismatch: %s", config_name)
            logger.warning("Configured value: %s", config_full[config_name].get('value'))
            logger.warning("Expected value: %s", config_diff[config_name].get('value'))


def load_config(config_file_name='.config'):
    """
    Processes a kernel.config file, returns a dict contaning defined parameters
    """
    with open(config_file_name, 'r') as config_file:
        kernel_config = {}
        logger.info("Processing the config file: %s", config_file.name)
        for line in config_file.readlines():
            try:
                name, config = line_to_config(line)
                logger.debug("Detected config name: %s", name)
                # Ignore undefines in the base config
                if not config.get('define'):
                    logger.debug("Line is an undefine in the base config, ignoring parameter: %s", name)
                else:
                    logger.info("Saving parameter: %s=%s", name, config.get('value'))
                kernel_config[name] = config
            # Allow the value errors but throw errors
            except ValueError as e:
                logger.error(e)
            except SyntaxWarning as e:
                logger.debug(e)
        # Throw a value error if the file could not be processed
        if not kernel_config:
            raise ValueError(f"Failed to load base config from {config_file_name}")
    return kernel_config


def merge_config(merge_file_name, base_config):
    """
    Merges a file into the supplied config
    """

    merged_config = base_config
    with open(merge_file_name, 'r') as merge_file:
        for line in merge_file.readlines():
            try:
                name, new_config = line_to_config(line)
                if name in base_config:
                    logger.info("Parameter: %s already detected in base config", name)
                    logger.info("Current value: %s", base_config.get(name).get('value'))
                    if new_config.get('define'):
                        logger.info("New value: %s", new_config.get('value'))
                        merged_config[name] = new_config
                    else:
                        logger.info("Deleting config entry for parameter: %s", name)
                        del merged_config[name]
                else:
                    logger.info("Parameter: %s does not exist in the base config", name)
                    if new_config.get('define'):
                        logger.info("New value: %s", new_config.get('value'))
                        merged_config[name] = new_config
                    else:
                        logger.warning("Attempting to undefine a parameter which is not defined: %s", name)
            except ValueError as e:
                logger.error(e)
            except SyntaxWarning as e:
                logger.debug(e)

    if merged_config == base_config:
        logger.warning("No changes detected after merging: %s", merge_file_name)

    return merged_config


def make_config(alldefconfig=True, base_file='.config'):
    """
    Runs a kernel.config file through make
    outputs a working .config file for the current kernel version
    Uses allnoconfig if alldefconfig is False, otherwise uses alldefconfig
    Substitutes the generated config into KCONFIG_ALLCONFIG
    """
    make_args = f"make KCONFIG_ALLCONFIG={base_file}"
    make_args += "alldefconfig" if alldefconfig else "allnoconfig"
    logger.debug("Args: %s", make_args)
    output = os.system(make_args)
    if output != 0:
        raise RuntimeError(f"Unable to run make command, args: {make_args}")


def process_config(base_file_name, merge_files, processed_config={}):
    """
    Processes the base file into base config
    Iterates through the merge files and attempts to apply them over the base file
    returns the merged base file once complete
    """
    # Load the base config from the passed base config file if it's not defined
    if not processed_config:
        processed_config = load_config(base_file_name)

    # Keep processing merge files while the list is populated
    # Item entries are popped from the list when processing has started
    # This should not run endlessly but may fail to process each merge section
    # Sections are applied over the base config as they are processed
    if merge_files:
        merge_file = merge_files.pop(0)
        processed_config = merge_config(merge_file, processed_config)
        process_config(base_file_name, merge_files, processed_config)
    else:
        logger.info("Merging has completed")
    return processed_config


def write_config(config_dict, out_file_name):
    """
    Takes a dictionary where the name is the parameter name, and the value is the parameter value
    writes as CONFIG_{name}={value}
    """
    logger.info("Writing config file: %s", out_file_name)
    with open(out_file_name, 'w') as out_file:
        out_file.write("## Starting config\n")
        for name, items in config_dict.items():
            value = items.get('value')
            out_file.write(f"CONFIG_{name}={value}\n")
        out_file.write("## Ending config\n")
    logger.info("Wrote config file: %s", out_file_name)


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
                        action='store_true',
                        help="Enables debugging, set your DEBUG environment variable to 1 for earlier debugging")
    # Add the output file arg
    parser.add_argument('-o',
                        action='store',
                        help=f"The output file location, the default is {DEFAULT_OUT_FILE}")
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
    log_level = logging.DEBUG if debug or args.v else logging.INFO
    logger.setLevel(log_level)
    stdout_handler.setLevel(log_level)
    logger.debug("Parsed the arguments")
    merge_files = []
    # If no merge files are passed, assume the base file is actually a merge file
    # If the default flag is enabled, move the passed base file to the merge files
    if not args.merge_files:
        logger.info("Using %s as the base config file", DEFAULT_CONFIG)
        base_file_name = DEFAULT_CONFIG
        merge_files.append(args.base_file)
        # if -d is passed, and there are still merge files, add them
        if args.merge_files:
            merge_files += args.merge_files
    else:
        logger.info("Using %s as the base config file", args.base_file_name)
        base_file_name = args.base_file
        merge_files = args.merge_files

    for file in merge_files:
        logger.info("Considering file %s for merge", file)

    out_file_name = args.o if args.o else DEFAULT_OUT_FILE
    logger.debug("Set the output file to: %s", out_file_name)
    processed_config = process_config(base_file_name, merge_files)

    write_config(processed_config, out_file_name)

    if not args.m:
        logger.info("Running make on: %s", out_file_name)
        # first load the config before running through make
        script_processed_config = load_config(out_file_name)
        make_config(alldefconfig=args.n, base_file=out_file_name)
        # Load the config after it has been processed through make
        processed_config = load_config(out_file_name)
        compare_config(processed_config, script_processed_config)


