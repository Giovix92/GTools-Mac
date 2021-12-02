'''This file will help getting the latest stable iasl version available for the system'''

import os
import subprocess
import sys
import wget

def is_iasl_compiled() -> bool:
    '''Returns true if the iasl binary is not compiled'''
    if not os.path.exists(os.path.join(os.getcwd(), 'utils', 'iasl', 'bin')):
        return True

def download_compiling_scripts() -> bool:

    '''This functions ensures that the scripts are downloaded before executing them'''

    dir_ls = os.listdir()

    if 'build_iasl.sh' not in dir_ls:
        print('WARNING: build_iasl.sh script not found. Downloading it...')
        try:
            wget.download('https://raw.githubusercontent.com/acidanthera/MaciASL/master/Dist/build_iasl.sh')
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

def compile_iasl() -> None:
    '''If iasl binaries are not installed in bin subdirectory then compile them'''

    dir_ls = os.listdir()
    curdir = os.getcwd()

    if not all(x in os.listdir(os.path.join(curdir, 'bin')) for x in ['iasl-stable', 'iasl-legacy', 'iasl-dev']):
        print('Missing iasl binaries. Recompiling them from scratch...')
        subprocess.run(['/bin/bash', 'build_iasl.sh'], stderr=subprocess.STDOUT)
        try:
            if not os.path.exists(os.path.join(curdir, 'bin')):
                os.mkdir(os.path.join(curdir, 'bin'))        
        except Exception as e:
            print(f'Failed to create bin directory: {e}')
        os.rename('iasl-dev', 'bin/iasl-dev')
        os.rename('iasl-legacy', 'bin/iasl-legacy')
        os.rename('iasl-stable', 'bin/iasl-stable')

def build_iasl() -> bool:
    os.chdir(os.path.join(os.getcwd(), 'utils', 'iasl')) # TODO: questo va in un main dioputtana
    download_compiling_scripts()
    compile_iasl()

    print(os.listdir())

build_iasl()