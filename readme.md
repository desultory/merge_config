# Merge-config

Based on https://github.com/torvalds/linux/blob/master/scripts/kconfig/merge_config.sh

## Description

Merges .config files.  


## Parameters

| Name	        | Default			                | Description												                                                    |
| ------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| base_config	| arch/x86/configs/x86_64_defconfig | The base config file, merges are applied over it								                                |
| merge_config	|				                    | The files to be merged over the base config.  Uses the base_config argument if it is the only conf specified  |
| -v		    |				                    | Increases verbosity, can also be enabled by exporting `DEBUG=1`						                        |
| -m		    | 				                    | Only merge fragments, don't pass through make								                                    |
| -n            |                                   | Use allnoconfig instead of alldefconfig                                                                       |
| -s            |                                   | Strict mode: Fails if there is a parameter redefinition                                                       |
| -o		    | .config			                | The output file, defaults to `.config`									                                    |
| -p            |                                   | Custom paramater, ex: `-p 'CONFIG_TEST=1'` `-p '# CONFIG_TEST is not set'`                                    |

## Example usage

` /usr/src/linux # merge-config.py 99-custom.config `

