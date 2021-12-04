# Copyright (C) 2021 Giovix92

import argparse
import getopt, re
import os, sys, shutil
import subprocess, time
# SubModules
from modules import *

from SSDTTime.SSDTTime import SSDT


version = "v1.1"
rootdir = os.getcwd()
ssdt_dir = os.path.join(rootdir, 'SSDTs')
ssdttime_dir = os.path.join(rootdir, 'SSDTTime')

parser = argparse.ArgumentParser(description=f"Generates ready-to-go EFIs starting from a SysReport. Version {version}.", prog="GTools.py")
parser.add_argument("SysReport", nargs='?', help="SysReport folder full path.", type=str)
parser.add_argument("--rebuild-iasl", action='store_true', help="Rebuild iasl module.")
parser.add_argument("--cleanup", action='store_true', help="Cleans up utils/iasl folder and exits.")
parser.add_argument("--iasl-bin", nargs=1, help="Changes the default used iasl binary.", default="iasl-stable", metavar="iasl_binary")
args = parser.parse_args()

#print(args)

if args.cleanup:
	if not downloader.is_iasl_compiled():
		shutil.rmtree(downloader.iasl_bin_path)
		print("Existing bin folder has been removed.")
		sys.exit()
	else:
		print("No previous binary files were found.")
		sys.exit()

if args.rebuild_iasl:
	if not downloader.is_iasl_compiled():
		shutil.rmtree(downloader.iasl_bin_path)
		print("Existing bin folder has been removed.")
	else:
		print("No previous binary files were found.")

if args.iasl_bin != 'iasl-stable':
	if not args.iasl_bin[0] in ('iasl-stable', 'iasl-legacy', 'iasl-dev'):
		print("Invalid selected iasl binary. Exiting.")
		sys.exit(1)

if args.SysReport is None:
	print("You must specify a SysReport folder. Exiting.")
	sys.exit(1)

if not os.path.exists(args.SysReport):
	print("SysReport path doesn't exist. Exiting.")
	sys.exit(1)

sr_path = args.SysReport
acpi_path = os.path.join(sr_path, 'SysReport', 'ACPI')
dsdt_path = os.path.join(acpi_path, 'DSDT.aml')

''' Recompile IASL, if necessary '''
if downloader.is_iasl_compiled():
	downloader.build_iasl()

''' Get OC logs and get CFG Lock / MAT statuses '''
os.chdir(sr_path)
oc_log = logparser.get_opencore_log_filename()
mat_status = logparser.get_mat_support_status(oc_log)
cfg_lock_status = logparser.cfg_lock_status(oc_log)
os.chdir(rootdir)

if not os.path.exists(ssdttime_dir):
	print("Unable to proceed, no SSDTTime repo found. Did you clone using --recursive? Exiting.")
	sys.exit(1)

if not os.path.exists(acpi_path) or not os.path.exists(dsdt_path):
	print("No DSDT.aml or ACPI folder found into the SysReport folder. Unable to proceed.")
	sys.exit(1)

''' Generate SSDTs using SSDTTime '''
try:
    if not os.path.exists(ssdt_dir):
        os.mkdir(ssdt_dir)
    else:
    	shutil.rmtree(ssdt_dir)
    	os.mkdir(ssdt_dir)
except Exception as e:
    print(f'Failed to create bin directory: {e}')

os.chdir(ssdttime_dir)
if os.path.exists(f'{ssdttime_dir}/Results'):
	shutil.rmtree(f'{ssdttime_dir}/Results')

# ssdttime = subprocess.Popen(['./SSDTTime.command'], stdin=subprocess.PIPE, encoding='utf8')
# ssdttime.stdin.write('D\n')
# ssdttime.stdin.write(f'{dsdt_path}\n')
# ssdttime.stdin.write('2\n')
# ssdttime.stdin.write('4\n')
# ssdttime.stdin.write('5\n')
# ssdttime.stdin.write('6\n')
# ssdttime.communicate('Q\n')

SSDTTime_istance = SSDT()
SSDTTime_istance.fake_ec()
# BUG: Va sistemato il sys.stdin.write(f'{dsdt_path}\n') dato che non ho idea di come si possa fixare il manual input del DSDT.aml

os.system(f'cp {ssdttime_dir}/Results/*.aml {ssdt_dir}')
os.chdir(rootdir)
os.system('clear')
print(f'MAT Status is: {"1" if mat_status else "0"}')
print(f'CFG Lock Status is: {"1" if cfg_lock_status else "0"}')
os.system(f'open {ssdt_dir}')
print('The SSDTs folder has been opened.')
print("Finished! Have a good day :)")