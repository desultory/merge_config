# Merge-config

Based on https://github.com/torvalds/linux/blob/master/scripts/kconfig/merge_config.sh

## Description

Merges .config files.  


## Parameters

| Name		| Default			    | Description												    |
| ------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| base_config	| arch/x86/configs/x86_64_defconfig | The base config file, merges are applied over it								    |
| merge_config	|				    | The files to be merged over the base config.  Uses the base_config argument if it is the only conf specified  |
| -v		|				    | Increases verbosity, can also be enabled by exporting `DEBUG=1`						    |
| -o		| .config			    | The output file, defaults to `.config`									    |

## Example usage

` /usr/src/linux # merge-config.py 99-custom.config `

