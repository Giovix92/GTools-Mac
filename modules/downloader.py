'''This file will help getting the latest stable iasl version available for the system'''

import os
import subprocess
import sys
import wget

iasl_path = os.path.join(os.getcwd(), 'utils', 'iasl')
iasl_bin_path = os.path.join(iasl_path, 'bin')
main_dir = os.getcwd()

def is_iasl_compiled() -> bool:
	'''Returns true if the iasl binary is not compiled'''
	return True if not os.path.exists(iasl_bin_path) else False

def download_compiling_scripts() -> None:

	'''This functions ensures that the scripts are actually downloaded before executing them'''

	dir_ls = os.listdir(iasl_path)
	os.chdir(iasl_path)

	if 'build_iasl.sh' not in dir_ls:
		print('WARNING: build_iasl.sh script not found. Downloading it...')
		try:
			wget.download('https://raw.githubusercontent.com/Giovix92/MaciASL/master/Dist/build_iasl.sh')
			print('\n')
		except Exception as e:
			print(f'An error occurred while downloading the file: {e}')
			sys.exit(1)

	if 'acpica-legacy.diff' not in dir_ls:
		print('WARNING: acpica-legacy.diff file not found. Downloading it...')
		try:
			wget.download('https://raw.githubusercontent.com/acidanthera/MaciASL/master/Dist/acpica-legacy.diff')
			print('\n')
		except Exception as e:
			print(f'An error occurred while downloading the file: {e}')
			sys.exit(1)

	os.chdir(main_dir)

def compile_iasl() -> None:
	'''If iasl binaries are not installed in bin subdirectory then compile them'''
	
	dir_ls = os.listdir(iasl_path)

	try:
		if not os.path.exists(iasl_bin_path):
			os.mkdir(iasl_bin_path)        
	except Exception as e:
		print(f'Failed to create bin directory: {e}')
	if not all(x in os.listdir(iasl_bin_path) for x in ['iasl-stable', 'iasl-legacy', 'iasl-dev']):
		print('Missing iasl binaries. Recompiling them from scratch...')
		os.chdir(iasl_path)
		subprocess.run(['/bin/bash', f'{iasl_path}/build_iasl.sh'], stderr=subprocess.STDOUT)
		os.rename('iasl-dev', 'bin/iasl-dev')
		os.rename('iasl-legacy', 'bin/iasl-legacy')
		os.rename('iasl-stable', 'bin/iasl-stable')
		os.system('rm -rf iasl-*.*64')
		os.chdir(main_dir)

def build_iasl() -> None:
	download_compiling_scripts()
	compile_iasl()