# Copyright (C) 2021-2022 Giovix92

import argparse
import getopt, re
import os, sys, shutil
import subprocess, time
# SubModules
from modules import downloader, logparser, mkssdt

version = 'v1.2'
rootdir = os.getcwd()
ssdt_dir = os.path.join(rootdir, 'SSDTs')
dsdt_dsl_path = None

parser = argparse.ArgumentParser(description=f'Generates SSDTs + useful infos starting from a SysReport. Version {version}.', prog='GTools.py')
parser.add_argument('SysReport', help='SysReport folder full path.', nargs='?', type=str)
parser.add_argument('--rebuild-iasl', action='store_true', help='Rebuild iasl module.')
parser.add_argument('--cleanup', action='store_true', help='Cleans up utils/iasl folder and exits.')
parser.add_argument('--iasl-bin', default='iasl-stable', help='Changes the default used iasl binary.', metavar='iasl_binary', type=str)
parser.add_argument('--skip-ssdtgen', action='store_true', help='Skips decompilation of DSDT and SSDTs generation.')
args = parser.parse_args()

if args.cleanup:
	if not downloader.is_iasl_compiled():
		shutil.rmtree(downloader.iasl_bin_path)
		print('Existing bin folder has been removed.')
		sys.exit()
	else:
		print('No previous binary files were found.')
		sys.exit()

if args.rebuild_iasl:
	if not downloader.is_iasl_compiled():
		shutil.rmtree(downloader.iasl_bin_path)
		print('Existing bin folder has been removed.')
	else:
		print('No previous binary files were found.')

iasl_bin = args.iasl_bin if os.path.exists(f'{args.iasl_bin}') else f'{downloader.iasl_bin_path}/{args.iasl_bin}' if os.path.exists(f'{downloader.iasl_bin_path}/{args.iasl_bin}') else sys.exit(1) if not args.iasl_bin in ('iasl-stable', 'iasl-legacy', 'iasl-dev') and args.rebuild_iasl else print('Invalid selected iasl binary. Exiting...') + sys.exit(1)


print('You must specify a SysReport folder. Exiting.') + sys.exit(1) if args.SysReport is None else ...
print('SysReport path doesn\'t exist. Exiting.') + sys.exit(1) if not os.path.exists(args.SysReport) else ...

sr_path = args.SysReport
acpi_path = os.path.join(sr_path, 'SysReport', 'ACPI')
dsdt_path = os.path.join(acpi_path, 'DSDT.aml')

''' Recompile IASL, if necessary '''
downloader.build_iasl() if downloader.is_iasl_compiled() else ...

''' Get OC logs and get CFG Lock / MAT statuses '''
os.chdir(sr_path)
oc_log = logparser.get_opencore_log_filename()
mat_status = logparser.get_mat_support_status(oc_log)
cfg_lock_status = logparser.cfg_lock_status(oc_log)
os.chdir(rootdir)

print('No DSDT.aml or ACPI folder found into the SysReport folder. Unable to proceed.') + sys.exit(1) if not os.path.exists(acpi_path) or not os.path.exists(dsdt_path) and args.skip_ssdtgen is False else ...

### SSDT Generation
if args.skip_ssdtgen is False:
	shutil.rmtree(ssdt_dir) if os.path.exists(ssdt_dir) else os.mkdir(ssdt_dir)
	tbp = {'dsdt': f'{dsdt_path}', 'iasl_bin': f'{iasl_bin}'}
	mkssdt.main(tbp)
else:
	print('DSDT decompilation and SSDT generation has been disabled via flag.')

os.system('clear')

os.system(f'open {ssdt_dir}') and print('The generated SSDT folder has been opened.') if args.skip_ssdtgen is False else ...
print(f'Useful infos regarding this SysReport:')
print(f'''- MAT Status is: {'1' if mat_status else '0'}''')
print(f'''- CFG Lock Status is: {'1' if cfg_lock_status else '0'}''')
print('Finished! Have a good day :)')