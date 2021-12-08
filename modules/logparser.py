import linecache
import os
import re

def search_log(log_filename: str, pattern: str) -> str or None:
	pattern = re.compile(pattern)
	opencore_log_file = open(log_filename, 'r')
	result = ''

	for line in opencore_log_file.readlines():
		if (re.search(pattern, line) != None):
			result = re.search(pattern, line).group(1)

	opencore_log_file.close()
	return result
	
def get_mat_support_status(filename: str):
	return True if search_log(filename, 'OCABC: MAT support is (\d)') == '1' else False
	
def cfg_lock_status(filename: str):
	return True if search_log(filename, 'EIST CFG Lock (\d)') == '1' else False

def get_opencore_log_filename():
	'''
	What can distinguish the opencore log from the other files is the fact that it starts with opencore-xxxxxxxxxx.txt AND is a file.
	More validation can be added but to be fair i'm a little bit stoned rn and don't have much brain cells functioning kekw
	'''

	cwd = os.getcwd()
	ls_dir = os.listdir(cwd)
	for log in ls_dir:
		if log.startswith('opencore-'):
			if os.path.isfile(log):
				return log
	return ''
