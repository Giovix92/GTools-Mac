# Copyright (C) 2021-2022 Giovix92

import argparse
import os
import shutil
import subprocess
import sys

version = 'v1.2'
dsdt       = None
dsdt_raw   = None
dsdt_lines = None
dsdt_paths = []

### FUNCTIONS - START ###

def is_hex(line: str) -> bool:
	return ':' in line.split('//')[0]

def get_line(line: str) -> str:
	# Strip the header and commented end - no space replacing though
	# I don't actually have enough enabled brain cells to create a single line return statement
	line = line.split('//')[0]
	return line.split(':')[1] if ':' in line else line

def get_path_of_type(obj_type: str = 'Device', obj: str = 'HPET') -> list:
	return sorted([path for path in dsdt_paths if path[2].lower() == obj_type.lower() and path[0].upper().endswith(obj.upper())])

def get_device_paths(obj: str = 'HPET') -> list:
	return get_path_of_type(obj_type='Device',obj=obj)

def get_method_paths(obj: str = '_STA') -> list:
	return get_path_of_type(obj_type='Method',obj=obj)

def get_name_paths(obj: str = 'CPU0') -> list:
	return get_path_of_type(obj_type='Name',obj=obj)

def get_processor_paths(obj: str = 'Processor') -> list:
	return get_path_of_type(obj_type='Processor',obj=obj)

def get_device_paths_with_hid(hid: str = 'ACPI000E') -> list:
	starting_indexes = []
	for index,line in enumerate(dsdt_lines):
		if is_hex(line): continue
		if hid.upper() in line.upper():
			starting_indexes.append(index)
	if not starting_indexes: return starting_indexes
	devices = []
	for i in starting_indexes:
		# Walk backwards and get the next parent device
		pad = len(dsdt_lines[i]) - len(dsdt_lines[i].lstrip(' '))
		for sub,line in enumerate(dsdt_lines[i::-1]):
			if 'Device (' in line and len(line)-len(line.lstrip(' ')) < pad:
				# Add it if it's already in our dsdt_paths - if not, add the current line
				device = next((x for x in dsdt_paths if x[1]==i-sub),None)
				devices.append(device) if device else devices.append(line,i-sub)
				break
	return devices

def _normalize_types(line: str) -> str:
	# Replaces Name, Processor, Device, and Method with Scope for splitting purposes
	return line.replace('Name','Scope').replace('Processor','Scope').replace('Device','Scope').replace('Method','Scope')

def get_path_starting_at(starting_index: int=0) -> tuple:
	# Walk the scope backwards, keeping track of changes
	pad = None
	path = []
	obj_type = next((x for x in ('Processor','Method','Scope','Device','Name') if f'{x} (' in dsdt_scope[starting_index][0]),'Unknown Type')
	for scope,original_index in dsdt_scope[starting_index::-1]:
		new_pad = _normalize_types(scope).split('Scope (')[0]
		if pad == None or new_pad < pad:
			pad = new_pad
			obj = _normalize_types(scope).split('Scope (')[1].split(')')[0].split(',')[0]
			path.append(obj)
			if obj in ('_SB','_SB_','_PR','_PR_') or obj.startswith(('\\','_SB.','_SB_.','_PR.','_PR_.')): break # This is a full scope
	path = path[::-1]
	if len(path) and path[0] == '\\': path.pop(0)
	if any(('^' in x for x in path)): # Accommodate caret notation
		new_path = []
		for x in path:
			if x.count('^'):
				# Remove the last Y paths to account for going up a level
				del new_path[-1*x.count('^'):]
			new_path.append(x.replace('^','')) # Add the original, removing any ^ chars
		path = new_path
	path = '.'.join(path)
	path = f'\\{path}' if path[0] != '\\' else path
	return (path, dsdt_scope[starting_index][1], obj_type)

def get_scope(starting_index: int = 0, add_hex: bool = False, strip_comments: bool = False) -> list[str]:
	# Walks the scope starting at starting_index, and returns when
	# we've exited
	brackets = None
	scope = []
	for line in dsdt_lines[starting_index:]:
		if is_hex(line):
			if add_hex:
				scope.append(line)
			continue
		line = get_line(line) if strip_comments else line
		scope.append(line)
		if brackets == None:
			if line.count('{'):
				brackets = line.count('{')
			continue
		brackets = brackets + line.count('{') - line.count('}')
		if brackets <= 0:
			# We've exited the scope
			return scope
	return scope

def get_unique_device(base_name: str, starting_number: int = 0, used_names: list = []) -> tuple[str, int]:
	# Appends a hex number until a unique device is found
	while True:
		hex_num = hex(starting_number).replace('0x','').upper()
		name = base_name[:-1*len(hex_num)]+hex_num
		if not len(get_device_paths(f'.{name}')) and not name in used_names:
			return (name,starting_number)
		starting_number += 1

def write_ssdt(ssdt_name: str, ssdt: str, iasl_bin: str, results_folder: str) -> bool:
	if not ssdt:
		print(f'Unable to generate {ssdt_name}!')
		return False
	temporary_dsl_path = os.path.join(results_folder, f'{ssdt_name}.dsl')
	with open(temporary_dsl_path, 'w') as f:
		f.write(ssdt)
	print('Compiling...')
	try:
		subprocess.check_call([f'{iasl_bin}', f'{temporary_dsl_path}'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
	except:
		print(f'Unable to compile {ssdt_name}!')
		return False
	return True

def fake_ec() -> str or bool: 
	print('\nLocating PNP0C09 (EC) devices...')
	ec_list = get_device_paths_with_hid('PNP0C09')
	ec_to_patch  = []
	lpc_name = None
	if len(ec_list):
		lpc_name = '.'.join(ec_list[0][0].split('.')[:-1])
		print(f' - Got {len(ec_list)}')
		print(' - Validating...')
		for x in ec_list:
			device = x[0]
			print(f' --> {device}')
			if device.split('.')[-1] == 'EC':
				print(' ----> EC called EC. Renaming')
				device = '.'.join(device.split('.')[:-1]+['EC0'])
			scope = '\n'.join(get_scope(x[1], strip_comments=True))
			# We need to check for _HID, _CRS, and _GPE
			if all((y in scope for y in ['_HID','_CRS','_GPE'])):
				print(' ----> Valid EC Device')
				sta = get_method_paths(f'{device}._STA')
				if len(sta):
					print(' ----> Contains _STA method. Skipping')
					continue
				ec_to_patch.append(device)
			else:
				print(' ----> NOT Valid EC Device')
	else:
		print(' - None found - only needs a Fake EC device')
	print('Locating LPC(B)/SBRG...')
	if lpc_name == None:
		for x in ('LPCB', 'LPC0', 'LPC', 'SBRG', 'PX40'):
			try:
				lpc_name = get_device_paths(x)[0][0]
				break
			except: pass
	if not lpc_name:
		print(' - Could not locate LPC(B)! Aborting!\n')
		return False
	print(f' - Found {lpc_name}')
	print('Creating SSDT-EC...')
	ssdt = '''
DefinitionBlock ("", "SSDT", 2, "CORP ", "SsdtEC", 0x00001000)
{
External ([[LPCName]], DeviceObj)
'''.replace('[[LPCName]]',lpc_name)
	for x in ec_to_patch:
		ssdt += f'    External ({x}, DeviceObj)\n'
	# Walk them again and add the _STAs
	for x in ec_to_patch:
		ssdt += '''
Scope ([[ECName]])
{
	Method (_STA, 0, NotSerialized)  // _STA: Status
	{
		If (_OSI ("Darwin"))
		{
			Return (0)
		}
		Else
		{
			Return (0x0F)
		}
	}
}
'''.replace('[[LPCName]]',lpc_name).replace('[[ECName]]',x)
	# Create the faked EC
	ssdt += '''
Scope ([[LPCName]])
{
	Device (EC)
	{
		Name (_HID, "ACID0001")  // _HID: Hardware ID
		Method (_STA, 0, NotSerialized)  // _STA: Status
		{
			If (_OSI ("Darwin"))
			{
				Return (0x0F)
			}
			Else
			{
				Return (Zero)
			}
		}
	}
}
}
'''.replace('[[LPCName]]',lpc_name)
	return ssdt

def plugin_type() -> str or bool:
	print('\nDetermining CPU name scheme...')
	try: cpu_name = get_processor_paths('')[0][0]
	except: cpu_name = None
	if not cpu_name:
		print(' - Could not locate Processor object! Aborting!\n')
		return False
	else:
		print(f' - Found {cpu_name}')
	print('Creating SSDT-PLUG...')
	ssdt = '''
//
// Based on the sample found at https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/SSDT-PLUG.dsl
//
DefinitionBlock ("", "SSDT", 2, "CORP", "CpuPlug", 0x00003000)
{
External ([[CPUName]], ProcessorObj)
Scope ([[CPUName]])
{
	If (_OSI ("Darwin")) {
		Method (_DSM, 4, NotSerialized)  // _DSM: Device-Specific Method
		{
			If (!Arg2)
			{
				Return (Buffer (One)
				{
					0x03
				})
			}
			Return (Package (0x02)
			{
				"plugin-type", 
				One
			})
		}
	}
}
}'''.replace('[[CPUName]]',cpu_name)
	return ssdt

def ssdt_pmc() -> str or bool:
	print('\nLocating LPC(B)/SBRG...')
	ec_list = get_device_paths_with_hid('PNP0C09')
	lpc_name = '.'.join(ec_list[0][0].split('.')[:-1]) if len(ec_list) else None
	if lpc_name == None:
		for x in ('LPCB', 'LPC0', 'LPC', 'SBRG', 'PX40'):
			try:
				lpc_name = get_device_paths(dsdt_paths, x)[0][0]
				break
			except: pass
	if not lpc_name:
		print(' - Could not locate LPC(B)! Aborting!\n')
		return False
	print(f' - Found {lpc_name}')
	print('Creating SSDT-PMC...')
	ssdt = '''//
// SSDT-PMC source from Acidanthera
// Original found here: https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/SSDT-PMC.dsl
//
// Uses the CORP name to denote where this was created for troubleshooting purposes.
//
DefinitionBlock ("", "SSDT", 2, "CORP", "PMCR", 0x00001000)
{
External ([[LPCName]], DeviceObj)
Scope ([[LPCName]])
{
	Device (PMCR)
	{
		Name (_HID, EisaId ("APP9876"))  // _HID: Hardware ID
		Method (_STA, 0, NotSerialized)  // _STA: Status
		{
			If (_OSI ("Darwin"))
			{
				Return (0x0B)
			}
			Else
			{
				Return (Zero)
			}
		}
		Name (_CRS, ResourceTemplate ()  // _CRS: Current Resource Settings
		{
			Memory32Fixed (ReadWrite,
				0xFE000000,         // Address Base
				0x00010000,         // Address Length
				)
		})
	}
}
}'''.replace('[[LPCName]]',lpc_name)
	return ssdt

def ssdt_awac() -> str or bool:
	print('\nLocating ACPI000E (AWAC) devices...')
	awac_list = get_device_paths_with_hid('ACPI000E')
	if not len(awac_list):
		print(' - Could not locate any ACPI000E devices!  SSDT-AWAC not needed!\n')
		return False
	awac = awac_list[0]
	root = awac[0].split('.')[0]
	print(f' - Found {awac[0]}')
	print(' --> Verifying _STA...')
	sta  = get_method_paths(f'{awac[0]}._STA')
	xsta = get_method_paths(f'{awac[0]}.XSTA')
	has_stas = False
	lpc_name = None
	if not len(sta) and len(xsta):
		print(' --> _STA already renamed to XSTA!  Aborting!\n')
		return False
	if len(sta):
		scope = '\n'.join(get_scope(sta[0][1], strip_comments=True))
		if 'STAS' in scope:
			# We have an STAS var, and should be able to just leverage it
			has_stas = True
			print(' --> Has STAS variable')
		else: print(' --> Does NOT have STAS variable')
	else:
		print(' --> No _STA method found')

	print('Locating PNP0B00 (RTC) devices...')
	rtc_list  = get_device_paths_with_hid('PNP0B00')
	rtc_fake = True

	if len(rtc_list):
		rtc_fake = False
		print(f' - Found at {rtc_list[0][0]}')
	else: print(' - None found - fake needed!')
	if rtc_fake:
		print('Locating LPC(B)/SBRG...')
		ec_list = get_device_paths_with_hid('PNP0C09')
		if len(ec_list):
			lpc_name = '.'.join(ec_list[0][0].split('.')[:-1])
		if lpc_name == None:
			for x in ('LPCB', 'LPC0', 'LPC', 'SBRG', 'PX40'):
				try:
					lpc_name = get_device_paths(x)[0][0]
					break
				except: pass
		if not lpc_name:
			print(' - Could not locate LPC(B)! Aborting!\n')
			return False
	# At this point - we need to do the following:
	# 1. Change STAS if needed
	# 2. Setup _STA with _OSI and call XSTA if needed
	# 3. Fake RTC if needed
	print('Creating SSDT-AWAC...')
	ssdt = '''//
// SSDT-AWAC source from Acidanthera
// Originals found here:
//  - https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/SSDT-AWAC.dsl
//  - https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/SSDT-RTC0.dsl
//
// Uses the CORP name to denote where this was created for troubleshooting purposes.
//
DefinitionBlock ("", "SSDT", 2, "CORP", "AWAC", 0x00000000)
{
'''
	if has_stas:
		ssdt += '''    External (STAS, IntObj)
Scope ([[Root]])
{
	Method (_INI, 0, NotSerialized)  // _INI: Initialize
	{
		If (_OSI ("Darwin"))
		{
			STAS = One
		}
	}
}
'''.replace('[[Root]]',root)
	elif len(sta):
		# We have a renamed _STA -> XSTA method - let's leverage it
		ssdt += '''    External ([[AWACName]], DeviceObj)
External ([[AWACName]].XSTA, MethodObj)
Scope ([[AWACName]])
{
	Name (ZSTA, 0x0F)
	Method (_STA, 0, NotSerialized)  // _STA: Status
	{
		If (_OSI ("Darwin"))
		{
			Return (Zero)
		}
		// Default to 0x0F - but return the result of the renamed XSTA if possible
		If ((CondRefOf ([[AWACName]].XSTA)))
		{
			Store ([[AWACName]].XSTA(), ZSTA)
		}
		Return (ZSTA)
	}
}
'''.replace('[[AWACName]]',awac[0])
	else:
		# No STAS, and no _STA - let's just add one
		ssdt += '''    External ([[AWACName]], DeviceObj)
Scope ([[AWACName]])
{
	Method (_STA, 0, NotSerialized)  // _STA: Status
	{
		If (_OSI ("Darwin"))
		{
			Return (Zero)
		}
		Else
		{
			Return (0x0F)
		}
	}
}
'''.replace('[[AWACName]]',awac[0])
	if rtc_fake:
		ssdt += '''    External ([[LPCName]], DeviceObj)    // (from opcode)
Scope ([[LPCName]])
{
	Device (RTC0)
	{
		Name (_HID, EisaId ("PNP0B00"))  // _HID: Hardware ID
		Name (_CRS, ResourceTemplate ()  // _CRS: Current Resource Settings
		{
			IO (Decode16,
				0x0070,             // Range Minimum
				0x0070,             // Range Maximum
				0x01,               // Alignment
				0x08,               // Length
				)
			IRQNoFlags ()
				{8}
		})
		Method (_STA, 0, NotSerialized)  // _STA: Status
		{
			If (_OSI ("Darwin")) {
				Return (0x0F)
			} Else {
				Return (0);
			}
		}
	}
}
'''.replace('[[LPCName]]',lpc_name)
	ssdt += '}'
	return ssdt

def ssdt_rhub() -> str or bool:
	illegal_names = ('XHC1','EHC1','EHC2','PXSX')
	print('\nGathering RHUB/HUBN/URTH devices...')
	rhubs = get_device_paths('RHUB')
	rhubs.extend(get_device_paths('HUBN'))
	rhubs.extend(get_device_paths('URTH'))
	if not len(rhubs):
		print(' - None found!  Aborting...\n')
		return False
	print(f' - Found {len(rhubs)}')
	# Gather some info
	tasks = []
	used_names = []
	xhc_num = 2
	ehc_num = 1
	for x in rhubs:
		task = {'device':x[0]}
		print(f''' --> {'.'.join(x[0].split('.')[:-1])}''')
		name = x[0].split('.')[-2]
		if name in illegal_names or name in used_names:
			print(' ----> Needs rename!')
			# Get the new name, and the path to the device and its parent
			task['device'] = '.'.join(task['device'].split('.')[:-1])
			task['parent'] = '.'.join(task['device'].split('.')[:-1])
			if name.startswith('EHC'):
				task['rename'],ehc_num = get_unique_device('EH01',ehc_num,used_names)
				ehc_num += 1 # Increment the name number
			else:
				task['rename'],xhc_num = get_unique_device('XHCI',xhc_num,used_names)
				xhc_num += 1 # Increment the name number
			used_names.append(task['rename'])
		else:
			used_names.append(name)
		# Let's try to get the _ADR
		scope_adr = get_name_paths(f"{task['device']}._ADR")
		task['address'] = dsdt_lines[scope_adr[0][1]].strip() if len(scope_adr) else 'Name (_ADR, Zero)  // _ADR: Address'
		tasks.append(task)
	ssdt = '''//
// SSDT to disable RHUB/HUBN/URTH devices and rename PXSX, XHC1, EHC1, and EHC2 devices
//
DefinitionBlock ("", "SSDT", 2, "CORP", "UsbReset", 0x00001000)
{
'''
	# Iterate the USB controllers and add external references
	# Gather the parents first - ensure they're unique, and put them in order
	parents = sorted(list(set([x['parent'] for x in tasks if x.get('parent',None)])))
	for x in parents:
		ssdt += f'    External ({x}, DeviceObj)\n' 
	for x in tasks:
		ssdt += f'''    External ({x['device']}, DeviceObj)\n'''
	# Let's walk them again and disable RHUBs and rename
	for x in tasks:
		if x.get('rename',None):
			# Disable the old controller
			ssdt += '''
Scope ([[device]])
{
	Method (_STA, 0, NotSerialized)  // _STA: Status
	{
		If (_OSI ("Darwin"))
		{
			Return (Zero)
		}
		Else
		{
			Return (0x0F)
		}
	}
}

Scope ([[parent]])
{
	Device ([[new_device]])
	{
		[[address]]
		Method (_STA, 0, NotSerialized)  // _STA: Status
		{
			If (_OSI ("Darwin"))
			{
				Return (0x0F)
			}
			Else
			{
				Return (Zero)
			}
		}
	}
}
'''.replace('[[device]]',x['device']).replace('[[parent]]',x['parent']).replace('[[address]]',x.get('address','Name (_ADR, Zero)  // _ADR: Address')).replace('[[new_device]]',x['rename'])
		else:
			# Only disabling the RHUB
			ssdt += '''
Scope ([[device]])
{
	Method (_STA, 0, NotSerialized)  // _STA: Status
	{
		If (_OSI ("Darwin"))
		{
			Return (Zero)
		}
		Else
		{
			Return (0x0F)
		}
	}
}
'''.replace('[[device]]',x['device'])
	ssdt += '\n}'
	return ssdt

### FUNCTIONS - END ###

### BLOCCO MAIN - START ###

def main(args: dict) -> None:
	dsdt = args['dsdt']
	iasl_bin = args['iasl_bin']
	print(f'Decompiling {dsdt}...')

	tmp_dir = os.path.join(os.getcwd(), 'tmp')
	shutil.rmtree(tmp_dir) if os.path.exists(tmp_dir) else None
	os.mkdir(tmp_dir)

	results_folder = os.path.join(os.getcwd(), 'SSDTs')
	
	shutil.rmtree(results_folder) if os.path.exists(results_folder) else None
	os.mkdir(results_folder)
	
	subprocess.check_call(['cp', f'{dsdt}', f'{tmp_dir}'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
	subprocess.check_call([f'{iasl_bin}', '-da', '-dl', '-l', f'{tmp_dir}/DSDT.aml'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

	# dsdt.load() - aml part
	dsdt_raw_fo = open(dsdt, 'rb')
	dsdt_raw = dsdt_raw_fo.read()

	# dsdt.load() - dsl part
	dsdt_dsl = os.path.join(tmp_dir, 'DSDT.dsl')
	
	dsdt_fo = open(dsdt_dsl, 'r')
	dsdt = dsdt_fo.read()

	global dsdt_lines
	dsdt_lines = dsdt.split('\n')

	global dsdt_scope
	dsdt_scope = [(line,index) for index,line in enumerate(dsdt_lines) if any(x in line for x in ('Processor (','Scope (','Device (','Method (','Name (')) if not is_hex(line)]
		
	#Unfortunately continue statement cannot be used inside a list comprehension for whatever reason...
	starting_indexes = []
	for index,scope in enumerate(dsdt_scope):
		if not scope[0].strip().startswith(('Processor (','Device (','Method (','Name (')): continue
		# Got a device - add its index
		starting_indexes.append(index)


	if not len(starting_indexes): return None
	global dsdt_paths
	dsdt_paths = sorted([get_path_starting_at(x) for x in starting_indexes])

	write_ssdt('SSDT-EC', fake_ec(), iasl_bin, results_folder)
	write_ssdt('SSDT-PLUG', plugin_type(), iasl_bin, results_folder)
	write_ssdt('SSDT-PMC', ssdt_pmc(), iasl_bin, results_folder)
	write_ssdt('SSDT-AWAC', ssdt_awac(), iasl_bin, results_folder)
	write_ssdt('SSDT-USB-Reset', ssdt_rhub(), iasl_bin, results_folder)

	shutil.rmtree(tmp_dir)
	dsdt_raw_fo.close()
	dsdt_fo.close()

# The parser is only called if this script is called as a script/executable (via command line) but not when imported by another script
if __name__=='__main__':
	parser = argparse.ArgumentParser(description=f'Generates SSDTs starting from a DSDT. Version {version}.', prog='mkssdt.py')
	parser.add_argument('--dsdt', help='Path of DSDT.aml file', metavar='DSDT.dsl', type=str)
	parser.add_argument('--iasl-bin', help='Full path of the iasl binary.', metavar='iasl_path', type=str)
	args = parser.parse_args()
	main(vars(args))
	sys.exit(0)

### BLOCCO MAIN - END ###