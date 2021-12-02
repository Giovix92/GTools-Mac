# Copyright (C) 2021 Giovix92

import argparse
import getopt, re
import os, sys, shutil
# SubModules
# import downloader

version = "v1.0"

parser = argparse.ArgumentParser(description=f"Generates ready-to-go SSDTs starting from a SysReport. Version {version}.", prog="GTools.py")
parser.add_argument("SysReport", action='store_true', help="SysReport folder full path.")
parser.add_argument("--rebuild-iasl", action='store_true', help="Rebuild iasl module.")
args = parser.parse_args()

if args.rebuild_iasl:
	print("jello")

if args.SysReport is None:
	print("No SysReport was given as input. Exiting.")
	sys.exit()