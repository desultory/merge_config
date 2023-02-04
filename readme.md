# Merge_config

Based on https://github.com/torvalds/linux/blob/master/scripts/kconfig/merge_config.sh

## Description

Merges .config files.  


## Parameters

| Name	        | Default			                | Description												                                    |
| ------------- | --------------------------------- | --------------------------------------------------------------------------------------------- |
| base_config	| arch/x86/configs/x86_64_defconfig | The base config file, merges are applied over it. Assumes -d if this is the only file passed  |
| merge_config	|				                    | The files to be merged over the base config.                                                  |
| -v		    |				                    | Increases verbosity, can also be enabled by exporting `DEBUG=1`						        |
| -m		    | 				                    | Only merge fragments, don't pass through make								                    |
| -n            |                                   | Use allnoconfig instead of alldefconfig                                                       |
| -s            |                                   | Strict mode: Fails if there is a parameter redefinition                                       |
| -o		    | .config			                | The output file, defaults to `.config`									                    |
| -p            |                                   | Custom paramater, ex: `-p 'CONFIG_TEST=1'`                                                    |

## Example usage

Merge a file named 99-custom.config over the default kernel config

`/usr/src/linux # merge_config.py 99-custom.config `


Write changes but do not run make

`/usr/src/linux # merge_config.py 99-custom.config -m`


Pass an undefine for the kexec config option last

`/usr/src/linux # merge_config.py 99-custom.config -p '# CONFIG_KEXEC is not set'`

Merge serveral files over the default

`/usr/src/linux # merge_config.py -d 99-custom*`

