# Copyright (C) 2021-2022 Giovix92

import argparse
import getopt, re
import os, sys, shutil
import subprocess, time
import binascii, getpass

version = 'v1.0'
dsdt       = None
dsdt_raw   = None
dsdt_lines = None
dsdt_scope = []
dsdt_paths = []

### FUNCTIONS - START ###

def is_hex(line):
	return ':' in line.split('//')[0]

def get_hex_from_int(total, pad_to = 4):
	hex_str = hex(total)[2:].upper().rjust(pad_to,'0')
	return ''.join([hex_str[i:i + 2] for i in range(0, len(hex_str), 2)][::-1])

def get_hex(line):
	# strip the header and commented end
	return line.split(':')[1].split('//')[0].replace(' ','')

def get_line(line):
	# Strip the header and commented end - no space replacing though
	line = line.split('//')[0]
	return line.split(':')[1] if ':' in line else line

def get_hex_bytes(line):
	return binascii.unhexlify(line)

def get_path_of_type(dsdt_paths, obj_type='Device', obj='HPET'):
	paths = []
	for path in dsdt_paths:
		if path[2].lower() == obj_type.lower() and path[0].upper().endswith(obj.upper()):
			paths.append(path)
	return sorted(paths)

def get_device_paths(dsdt_paths, obj='HPET'):
	return get_path_of_type(dsdt_paths, obj_type='Device',obj=obj)

def get_method_paths(dsdt_paths, obj='_STA'):
	return get_path_of_type(dsdt_paths, obj_type='Method',obj=obj)

def get_name_paths(dsdt_paths, obj='CPU0'):
	return get_path_of_type(dsdt_paths, obj_type='Name',obj=obj)

def get_processor_paths(dsdt_paths, obj='Processor'):
	return get_path_of_type(dsdt_paths, obj_type='Processor',obj=obj)

def get_device_paths_with_hid(dsdt_lines, dsdt_paths, hid='ACPI000E'):
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
				if device: devices.append(device)
				else: devices.append((line,i-sub))
				break
	return devices

def _normalize_types(line):
	# Replaces Name, Processor, Device, and Method with Scope for splitting purposes
	return line.replace('Name','Scope').replace('Processor','Scope').replace('Device','Scope').replace('Method','Scope')

def get_path_starting_at(starting_index=0):
	# Walk the scope backwards, keeping track of changes
	pad = None
	path = []
	obj_type = next((x for x in ('Processor','Method','Scope','Device','Name') if x+' (' in dsdt_scope[starting_index][0]),'Unknown Type')
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
	path = '\\'+path if path[0] != '\\' else path
	return (path, dsdt_scope[starting_index][1], obj_type)

def get_scope(dsdt_lines, starting_index=0, add_hex=False, strip_comments=False):
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

def get_unique_device(dsdt_paths, path, base_name, starting_number=0, used_names = []):
	# Appends a hex number until a unique device is found
	while True:
		hex_num = hex(starting_number).replace('0x','').upper()
		name = base_name[:-1*len(hex_num)]+hex_num
		if not len(get_device_paths(dsdt_paths, '.'+name)) and not name in used_names:
			return (name,starting_number)
		starting_number += 1


def find_previous_hex(dsdt_lines, index=0):
	# Returns the index of the previous set of hex digits before the passed index
	start_index = -1
	end_index   = -1
	old_hex = True
	for i,line in enumerate(dsdt_lines[index::-1]):
		if old_hex:
			if not is_hex(line):
				# Broke out of the old hex
				old_hex = False
			continue
		# Not old_hex territory - check if we got new hex
		if is_hex(line): # Checks for a :, but not in comments
			end_index = index-i
			hex_text,start_index = get_hex_ending_at(dsdt_lines, end_index)
			return (hex_text, start_index, end_index)
	return ('',start_index,end_index)

def find_next_hex(dsdt_lines, index=0):
	# Returns the index of the next set of hex digits after the passed index
	start_index = -1
	end_index   = -1
	old_hex = True
	for i,line in enumerate(dsdt_lines[index:]):
		if old_hex:
			if not is_hex(line):
				# Broke out of the old hex
				old_hex = False
			continue
		# Not old_hex territory - check if we got new hex
		if is_hex(line): # Checks for a :, but not in comments
			start_index = i+index
			hex_text,end_index = get_hex_starting_at(dsdt_lines, start_index)
			return (hex_text, start_index, end_index)
	return ('',start_index,end_index)

def get_hex_starting_at(dsdt_lines, start_index):
	# Returns a tuple of the hex, and the ending index
	hex_text = ''
	index = -1
	for i,x in enumerate(dsdt_lines[start_index:]):
		if not is_hex(x):
			break
		hex_text += get_hex(x)
		index = i+start_index
	return (hex_text, index)

def get_hex_ending_at(dsdt_lines, start_index):
	# Returns a tuple of the hex, and the ending index
	hex_text = ''
	index = -1
	for i,x in enumerate(dsdt_lines[start_index::-1]):
		if not is_hex(x):
			break
		hex_text = get_hex(x)+hex_text
		index = start_index-i
	return (hex_text, index)

def get_shortest_unique_pad(dsdt_lines, dsdt_raw, current_hex, index, instance=0):
	try:    left_pad  = get_unique_pad(dsdt_lines, dsdt_raw, current_hex, index, False, instance)
	except: left_pad  = None
	try:    right_pad = get_unique_pad(dsdt_lines, dsdt_raw, current_hex, index, True, instance)
	except: right_pad = None
	try:    mid_pad   = get_unique_pad(dsdt_lines, dsdt_raw, current_hex, index, None, instance)
	except: mid_pad   = None
	if left_pad == right_pad == mid_pad == None: raise Exception('No unique pad found!')
	# We got at least one unique pad
	min_pad = None
	for x in (left_pad,right_pad,mid_pad):
		if x == None: continue # Skip
		if min_pad == None or len(x[0]+x[1]) < len(min_pad[0]+min_pad[1]):
			min_pad = x
	return min_pad

def get_unique_pad(dsdt_lines, dsdt_raw, current_hex, index, direction=None, instance=0):
	# Returns any pad needed to make the passed patch unique
	# direction can be True = forward, False = backward, None = both
	start_index = index
	line,last_index = get_hex_starting_at(dsdt_lines, index)
	if not current_hex in line:
		raise Exception('{} not found in DSDT at index {}-{}!'.format(current_hex,start_index,last_index))
	padl = padr = ''
	parts = line.split(current_hex)
	if instance >= len(parts)-1:
		raise Exception('Instance out of range!')
	linel = current_hex.join(parts[0:instance+1])
	liner = current_hex.join(parts[instance+1:])
	last_check = True # Default to forward
	while True:
		# Check if our hex string is unique
		check_bytes = get_hex_bytes(padl+current_hex+padr)
		if dsdt_raw.count(check_bytes) == 1: # Got it!
			break
		if direction == True or (direction == None and len(padr)<=len(padl)):
			# Let's check a forward byte
			if not len(liner):
				# Need to grab more
				liner, _index, last_index = find_next_hex(dsdt_lines, last_index)
				if last_index == -1: raise Exception('Hit end of file before unique hex was found!')
			padr  = padr+liner[0:2]
			liner = liner[2:]
			continue
		if direction == False or (direction == None and len(padl)<=len(padr)):
			# Let's check a backward byte
			if not len(linel):
				# Need to grab more
				linel, start_index, _index = find_previous_hex(dsdt_lines, start_index)
				if _index == -1: raise Exception('Hit end of file before unique hex was found!')
			padl  = linel[-2:]+padl
			linel = linel[:-2]
			continue
		break
	return (padl,padr)


def write_ssdt(ssdt_name, ssdt, iasl_bin, results_folder):
	if not ssdt:
		print(f'Unable to generate {ssdt_name}!')
		return
	temporary_dsl_path = os.path.join(results_folder, ssdt_name+'.dsl')
	with open(temporary_dsl_path, 'w') as f:
		f.write(ssdt)
	print('Compiling...')
	try:
		subprocess.check_call([f'{iasl_bin}', f'{temporary_dsl_path}'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
	except:
		print(f'Unable to compile {ssdt_name}!')
		return
	return True

def fake_ec(dsdt_lines, dsdt_paths):
	print('')
	print('Locating PNP0C09 (EC) devices...')
	ec_list = get_device_paths_with_hid(dsdt_lines, dsdt_paths, 'PNP0C09')
	ec_to_patch  = []
	lpc_name = None
	if len(ec_list):
		lpc_name = '.'.join(ec_list[0][0].split('.')[:-1])
		print(' - Got {}'.format(len(ec_list)))
		print(' - Validating...')
		for x in ec_list:
			device = x[0]
			print(' --> {}'.format(device))
			if device.split('.')[-1] == 'EC':
				print(' ----> EC called EC. Renaming')
				device = '.'.join(device.split('.')[:-1]+['EC0'])
			scope = '\n'.join(get_scope(dsdt_lines, x[1], strip_comments=True))
			# We need to check for _HID, _CRS, and _GPE
			if all((y in scope for y in ['_HID','_CRS','_GPE'])):
				print(' ----> Valid EC Device')
				sta = get_method_paths(dsdt_paths, device+'._STA')
				if len(sta):
					print(' ----> Contains _STA method. Skipping')
					continue
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
		print(' - Could not locate LPC(B)! Aborting!')
		print('')
		return False
	print(' - Found {}'.format(lpc_name))
	comment = 'SSDT-EC'
	oc = {'Comment':comment,'Enabled':True,'Path':'SSDT-EC.aml'}
	print('Creating SSDT-EC...')
	ssdt = '''
DefinitionBlock ("", "SSDT", 2, "CORP ", "SsdtEC", 0x00001000)
{
External ([[LPCName]], DeviceObj)
'''.replace('[[LPCName]]',lpc_name)
	for x in ec_to_patch:
		ssdt += '    External ({}, DeviceObj)\n'.format(x)
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

def plugin_type(dsdt_lines, dsdt_paths):
	print('')
	print('Determining CPU name scheme...')
	try: cpu_name = get_processor_paths(dsdt_paths, '')[0][0]
	except: cpu_name = None
	if not cpu_name:
		print(' - Could not locate Processor object! Aborting!')
		print('')
		return False
	else:
		print(' - Found {}'.format(cpu_name))
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

def ssdt_pmc(dsdt_lines, dsdt_paths):
	print('')
	print('Locating LPC(B)/SBRG...')
	ec_list = get_device_paths_with_hid(dsdt_lines, dsdt_paths, 'PNP0C09')
	lpc_name = None
	if len(ec_list):
		lpc_name = '.'.join(ec_list[0][0].split('.')[:-1])
	if lpc_name == None:
		for x in ('LPCB', 'LPC0', 'LPC', 'SBRG', 'PX40'):
			try:
				lpc_name = get_device_paths(dsdt_paths, x)[0][0]
				break
			except: pass
	if not lpc_name:
		print(' - Could not locate LPC(B)! Aborting!')
		print('')
		return False
	print(' - Found {}'.format(lpc_name))
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

def ssdt_awac(dsdt_lines, dsdt_paths, dsdt_raw):
	print('')
	print('Locating ACPI000E (AWAC) devices...')
	awac_list = get_device_paths_with_hid(dsdt_lines, dsdt_paths, 'ACPI000E')
	if not len(awac_list):
		print(' - Could not locate any ACPI000E devices!  SSDT-AWAC not needed!')
		print('')
		return False
	awac = awac_list[0]
	root = awac[0].split('.')[0]
	print(' - Found {}'.format(awac[0]))
	print(' --> Verifying _STA...')
	sta  = get_method_paths(dsdt_paths, awac[0]+'._STA')
	xsta = get_method_paths(dsdt_paths, awac[0]+'.XSTA')
	has_stas = False
	lpc_name = None
	patches = []
	if not len(sta) and len(xsta):
		print(' --> _STA already renamed to XSTA!  Aborting!')
		print('')
		return False
	if len(sta):
		scope = '\n'.join(get_scope(dsdt_lines, sta[0][1], strip_comments=True))
		if 'STAS' in scope:
			# We have an STAS var, and should be able to just leverage it
			has_stas = True
			print(' --> Has STAS variable')
		else: print(' --> Does NOT have STAS variable')
	else:
		print(' --> No _STA method found')
	# Let's find out of we need a unique patch for _STA -> XSTA
	if len(sta) and not has_stas:
		print(' --> Generating _STA to XSTA patch')
		sta_index = find_next_hex(dsdt_lines, sta[0][1])[1]
		print(' ----> Found at index {}'.format(sta_index))
		sta_hex  = '5F535441'
		xsta_hex = '58535441'
		padl,padr = get_shortest_unique_pad(dsdt_lines, dsdt_raw, sta_hex, sta_index)
		patches.append({'Comment':'AWAC _STA to XSTA Rename','Find':padl+sta_hex+padr,'Replace':padl+xsta_hex+padr})
	print('Locating PNP0B00 (RTC) devices...')
	rtc_list  = get_device_paths_with_hid(dsdt_lines, dsdt_paths, 'PNP0B00')
	rtc_fake = True
	if len(rtc_list):
		rtc_fake = False
		print(' - Found at {}'.format(rtc_list[0][0]))
	else: print(' - None found - fake needed!')
	if rtc_fake:
		print('Locating LPC(B)/SBRG...')
		ec_list = get_device_paths_with_hid(dsdt_lines, dsdt_paths, 'PNP0C09')
		if len(ec_list):
			lpc_name = '.'.join(ec_list[0][0].split('.')[:-1])
		if lpc_name == None:
			for x in ('LPCB', 'LPC0', 'LPC', 'SBRG', 'PX40'):
				try:
					lpc_name = get_device_paths(dsdt_paths, x)[0][0]
					break
				except: pass
		if not lpc_name:
			print(' - Could not locate LPC(B)! Aborting!')
			print('')
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

def ssdt_rhub(dsdt_lines, dsdt_paths, dsdt_raw):
	illegal_names = ('XHC1','EHC1','EHC2','PXSX')
	print('')
	print('Gathering RHUB/HUBN/URTH devices...')
	rhubs = get_device_paths(dsdt_paths, 'RHUB')
	rhubs.extend(get_device_paths(dsdt_paths, 'HUBN'))
	rhubs.extend(get_device_paths(dsdt_paths, 'URTH'))
	if not len(rhubs):
		print(' - None found!  Aborting...')
		print('')
		return False
	print(' - Found {:,}'.format(len(rhubs)))
	# Gather some info
	patches = []
	tasks = []
	used_names = []
	xhc_num = 2
	ehc_num = 1
	for x in rhubs:
		task = {'device':x[0]}
		print(' --> {}'.format('.'.join(x[0].split('.')[:-1])))
		name = x[0].split('.')[-2]
		if name in illegal_names or name in used_names:
			print(' ----> Needs rename!')
			# Get the new name, and the path to the device and its parent
			task['device'] = '.'.join(task['device'].split('.')[:-1])
			task['parent'] = '.'.join(task['device'].split('.')[:-1])
			if name.startswith('EHC'):
				task['rename'],ehc_num = get_unique_device(dsdt_paths, task['parent'],'EH01',ehc_num,used_names)
				ehc_num += 1 # Increment the name number
			else:
				task['rename'],xhc_num = get_unique_device(dsdt_paths, task['parent'],'XHCI',xhc_num,used_names)
				xhc_num += 1 # Increment the name number
			used_names.append(task['rename'])
		else:
			used_names.append(name)
		sta_method = get_method_paths(dsdt_paths, task['device']+'._STA')
		# Let's find out of we need a unique patch for _STA -> XSTA
		if len(sta_method):
			print(' ----> Generating _STA to XSTA patch')
			sta_index = find_next_hex(dsdt_lines, sta_method[0][1])[1]
			print(' ------> Found at index {}'.format(sta_index))
			sta_hex  = '5F535441'
			xsta_hex = '58535441'
			padl,padr = get_shortest_unique_pad(dsdt_lines, dsdt_raw, sta_hex, sta_index)
			patches.append({'Comment':'{} _STA to XSTA Rename'.format(task['device'].split('.')[-1]),'Find':padl+sta_hex+padr,'Replace':padl+xsta_hex+padr})
		# Let's try to get the _ADR
		scope_adr = get_name_paths(dsdt_paths, task['device']+'._ADR')
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
		ssdt += '    External ({}, DeviceObj)\n'.format(x)
	for x in tasks:
		ssdt += '    External ({}, DeviceObj)\n'.format(x['device'])
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

def main(args):
	dsdt = args['dsdt']
	iasl_bin = args['iasl_bin']
	print(f'Decompiling {dsdt}...')
	tmp_dir = os.path.join(os.getcwd(), 'tmp')
	if os.path.exists(tmp_dir):
		shutil.rmtree(tmp_dir)
	os.mkdir(tmp_dir)
	results_folder = os.path.join(os.getcwd(), 'SSDTs')
	if os.path.exists(results_folder):
		shutil.rmtree(results_folder)
	os.mkdir(results_folder)
	subprocess.check_call(['cp', f'{dsdt}', f'{tmp_dir}'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
	subprocess.check_call([f'{iasl_bin}', '-da', '-dl', '-l', f'{tmp_dir}/DSDT.aml'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

	# dsdt.load() - aml part
	dsdt_raw = open(dsdt, 'rb').read()

	# dsdt.load() - dsl part
	dsdt_dsl = os.path.join(tmp_dir, 'DSDT.dsl')
	with open(dsdt_dsl, 'r') as f:
		dsdt = f.read()
		dsdt_lines = dsdt.split('\n')

		# dsdt.get_scopes()
		for index,line in enumerate(dsdt_lines):
			if is_hex(line): continue
			if any(x in line for x in ('Processor (','Scope (','Device (','Method (','Name (')):
				dsdt_scope.append((line,index))

	# dsdt.get_paths()
	starting_indexes = []
	for index,scope in enumerate(dsdt_scope):
		if not scope[0].strip().startswith(('Processor (','Device (','Method (','Name (')): continue
		# Got a device - add its index
		starting_indexes.append(index)
	if not len(starting_indexes): return None
	paths = []
	for x in starting_indexes:
		paths.append(get_path_starting_at(x))
	paths = sorted(paths)
	dsdt_paths = paths

	write_ssdt('SSDT-EC', fake_ec(dsdt_lines, dsdt_paths), iasl_bin, results_folder)
	write_ssdt('SSDT-PLUG', plugin_type(dsdt_lines, dsdt_paths), iasl_bin, results_folder)
	write_ssdt('SSDT-PMC', ssdt_pmc(dsdt_lines, dsdt_paths), iasl_bin, results_folder)
	write_ssdt('SSDT-AWAC', ssdt_awac(dsdt_lines, dsdt_paths, dsdt_raw), iasl_bin, results_folder)
	write_ssdt('SSDT-USB-Reset', ssdt_rhub(dsdt_lines, dsdt_paths, dsdt_raw), iasl_bin, results_folder)

	shutil.rmtree(tmp_dir)

# The parser is only called if this script is called as a script/executable (via command line) but not when imported by another script
if __name__=='__main__':
	parser = argparse.ArgumentParser(description=f'Generates SSDTs starting from a DSDT. Version {version}.', prog='mkssdt.py')
	parser.add_argument('--dsdt', help='Path of DSDT.aml file', metavar='DSDT.dsl', type=str)
	parser.add_argument('--iasl-bin', help='Full path of the iasl binary.', metavar='iasl_path', type=str)
	args = parser.parse_args()
	main(vars(args))
	sys.exit(0)

### BLOCCO MAIN - END ###