#!/usr/bin/env python3


from CustomFormatter import CustomFormatter
import argparse
import logging
import os
import regex


DEFAULT_CONFIG = 'arch/x86/configs/x86_64_defconfig'
DEFAULT_OUT_FILE = '.config'
DEFINE_START = "CONFIG_"
DEFINE_REGEXR = regex.compile(r'^([a-zA-Z0-9_])+=-?([a-zA-Z0-9"])+$')
UNDEFINE_START = "# CONFIG_"
UNDEFINE_END = " is not set"
UNDEFINE_REGEXR = regex.compile(r"^([a-zA-Z0-9_]+)$")

debug = int(os.environ.get('DEBUG', 0))
log_level = logging.DEBUG if debug else logging.INFO
log_fmt = '%(asctime)s | %(levelname)8s '

logger = logging.getLogger(__name__)
logger.setLevel(log_level)

stdout_handler = logging.StreamHandler()

stdout_handler.setLevel(log_level)
stdout_handler.setFormatter(CustomFormatter(log_fmt))

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
    # Every kernel parameter should have "CONFIG" present
    # If it does not, raise a value error
    if "CONFIG" not in line:
        raise ValueError(f"`{line}` does not seem to be a kernel .config parameter")
    # Define should be implied, gets unset by undefinitions
    define = True

    # Ensure the entire line starts and ends with these values
    if line.startswith(UNDEFINE_START) and line.endswith(UNDEFINE_END):
        logger.debug("Detected an undefine")
        # Removing all portions of the line other than the parameter name
        parameter = line.replace(UNDEFINE_START, '').replace(UNDEFINE_END, '')
        if regex.match(UNDEFINE_REGEXR, parameter):
            # Extract the regex match if it exists
            parameter = regex.search(UNDEFINE_REGEXR, parameter).group(1)
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
        if regex.match(DEFINE_REGEXR, parameter):
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
        raise ValueError(f"Unable to parse line: {line}")


def process_config(base_file, merge_files, base_configs={}):
    """
    Processes the base file into base config
    Iterates through the merge files and attempts to apply them over the base file
    returns the merged base file once complete
    """
    # Only run this the first time the script runs
    if not base_configs:
        logger.info("Processing the base file: %s", base_file.name)
        for line in base_file.readlines():
            try:
                name, config = line_to_config(line)
                logger.debug("Using config name: %s", name)
                # Ignore undefines in the base config
                if not config.get('define'):
                    logger.error("Line is undefine, ignoring parameter: %s", name)
                else:
                    logger.info("Saving parameter: %s=%s", name, config.get('value'))
                    base_configs[name] = config
            # Allow the value errors but throw errors
            except ValueError as e:
                logger.error(e)
        # Throw a value error if the file could not be processed
        if not base_file:
            raise ValueError(f"Failed to load base config from {base_file.name}")
    else:
        logger.debug("Not processing the base file as base config is already loaded")

    # Keep processing merge files while the list is populated
    # Item entries are popped from the list when processing has started
    # This should not run endlessly but may fail to process each merge section
    # Sections are applied over the base config as they are processed
    if merge_files:
        merge_file = merge_files.pop(0)
        for line in merge_file.readlines():
            try:
                name, new_config = line_to_config(line)
                if name in base_configs:
                    logger.info("Parameter: %s already detected in base config", name)
                    logger.info("Current value: %s", base_configs.get(name).get('value'))
                    logger.info("Current status: %s", base_configs.get(name).get('define'))
                    if new_config.get('define'):
                        logger.info("New value: %s", new_config.get('value'))
                        base_configs[name] = new_config
                    else:
                        logger.info("Deleting config entry for parameter: %s", name)
                        del base_configs[name]
                else:
                    logger.info("Parameter: %s is new", name)
                    if new_config.get('define'):
                        logger.info("New value: %s", new_config.get('value'))
                        base_configs[name] = new_config
                    else:
                        logger.info("Attempting to undefine a parameter which is not defined")
            except ValueError as e:
                logger.error(e)
        process_config(base_file, merge_files, base_configs)
    else:
        logger.info("Merging has completed")
    return base_configs


def write_config(config_dict, out_file):
    """
    Takes a dictionary where the name is the parameter name, and the value is the parameter value
    writes as CONFIG_{name}={value}
    """
    logger.debug("Got config dict: %s", config_dict)
    logger.info("Writing config file: %s", out_file)
    with open(out_file, 'w') as file:
        file.write("## Starting config\n")
        for name, items in config_dict.items():
            value = items.get('value')
            logger.debug("Parameter name: %s", name)
            logger.debug("Parameter value: %s", value)
            file.write(f"CONFIG_{name}={value}\n")
            logger.debug("Wrote line: %s", f"CONFIG_{name}={value}")
        file.write("## Ending config\n")
    logger.info("Wrote config file: %s", out_file)


if __name__ == '__main__':
    # Initialise the arg parser
    parser = argparse.ArgumentParser(prog='merge-config',
                                     description='Merges kernel.config files')
    logger.debug("Initialized the argparser")
    # Add a debugging arg
    parser.add_argument('-v',
                        action='store_true',
                        help="Enables debugging, set your DEBUG environment variable to 1 for earlier debugging")
    logger.debug("Added the debug argument")
    # Add the default config arg
    # If enabled, the default config will be used
    parser.add_argument('-d',
                        action='store_true',
                        help="Use the default configuration")
    logger.debug("Added the default configuration argument")
    # Add the output file arg
    parser.add_argument('-o',
                        action='store',
                        help=f"The output file location, the default is {DEFAULT_OUT_FILE}")
    logger.debug("Added the output file location argument")
    # First take the base argument
    # If this is the only argument, use it as the merge file,
    # using the DEFAULT_CONFIG as the base file
    parser.add_argument('base_file',
                        type=argparse.FileType('r'),
                        help=f"The base kernel file, defaults to {DEFAULT_CONFIG}")
    logger.debug("Added the base_file argparser argument")
    # Then take the rest of the arguments as files to open
    parser.add_argument('merge_files',
                        type=argparse.FileType('r'),
                        nargs='*',
                        help="Files to be merged")
    logger.debug("Added the merge_files argparser argument")
    args = parser.parse_args()
    log_level = logging.DEBUG if debug or args.v else logging.INFO
    logger.setLevel(log_level)
    stdout_handler.setLevel(log_level)
    logger.debug("Parsed the arguments")
    merge_files = []
    # If no merge files are passed,
    # assume the base file is actually a merge file
    # If the default flag is enabled,
    # move the passed base file to the merge files
    if not args.merge_files or args.d:
        logger.info("Using %s as the base config file", DEFAULT_CONFIG)
        base_file = open(DEFAULT_CONFIG, 'r', encoding='utf-8')
        merge_files.append(args.base_file)
        # if -d is passed, and there are still merge files, add them
        if args.merge_files:
            merge_files += args.merge_files
    else:
        logger.info("Using %s as the base config file", args.base_file.name)
        base_file = args.base_file
        merge_files = args.merge_files

    for file in merge_files:
        logger.info("Considering file %s for merge", file.name)

    out_file = args.o if args.o else DEFAULT_OUT_FILE
    logger.debug("Set the output file to: %s", out_file)
    processed_config = process_config(base_file, merge_files)
    write_config(processed_config, out_file)
