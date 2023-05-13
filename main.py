#!/usr/bin/env python3

from kernel_config import LinuxKernelConfig

import argparse
import logging

logging.root.setLevel(5)

if __name__ == '__main__':

    argparser = argparse.ArgumentParser(prog='Linux Kconfig generator',
                                        description='Generates linux kernel .config files using yaml dafinitions')

    argparser.add_argument('config',
                           action='store',
                           help='Configurator config file')

    argparser.add_argument('kernel_configs',
                           nargs="*",
                           action='store',
                           help='Kernel config definition file(s)')

    args = argparser.parse_args()

    kconfig = LinuxKernelConfig(args.config, kernel_config_files=args.kernel_configs)

