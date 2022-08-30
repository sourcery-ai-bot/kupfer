# -*- coding: utf-8 -*-

from __future__ import with_statement

import os
import re
from ConfigParser import RawConfigParser

from kupfer import pretty

__version__ = "2011-01-20"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"

'''
Module provide function to read Thunderbird's address book.

Concept for mork parser from:
	- demork.py by Kumaran Santhanam
	- mork.cs from GnomeDo by Pierre Östlund
'''

THUNDERBIRD_HOME = map(os.path.expanduser,
		('~/.mozilla-thunderbird/', '~/.thunderbird', '~/.icedove/'))

THUNDERBIRD_PROFILES = [
		(thome, os.path.join(thome, 'profiles.ini'))
		for thome in THUNDERBIRD_HOME]


RE_COLS = re.compile(r'<\s*<\(a=c\)>\s*(\/\/)?\s*(\(.+?\))\s*>')
RE_CELL = re.compile(r'\((.+?)\)')
RE_ATOM = re.compile(r'<\s*(\(.+?\))\s*>')
RE_TABLE = re.compile(
		r'\{-?(\d+):\^(..)\s*\{\(k\^(..):c\)\(s=9u?\)\s*(.*?)\}\s*(.+?)\}')
RE_ROW = re.compile(r'(-?)\s*\[(.+?)((\(.+?\)\s*)*)\]')
RE_CELL_TEXT = re.compile(r'\^(.+?)=(.*)')
RE_CELL_OID = re.compile(r'\^(.+?)\^(.+)')
RE_TRAN_BEGIN = re.compile(r'@\$\$\{.+?\{\@')
RE_TRAN_END = re.compile(r'@\$\$\}.+?\}\@')


COLS_TO_KEEP = (
		'DisplayName',
		'FirstName',
		'LastName',
		'PrimaryEmail',
		'SecondEmail',
)

SPECIAL_CHARS = (
		('\\\\', '\\'),
		('\\$', '$'),
		('\\t', chr(9)),
		('\\n', chr(10)),
)

RE_ESCAPED = re.compile(r'(\$[a-f0-9]{2})', re.IGNORECASE)
RE_HEADER = re.compile(r'// <!-- <mdb:mork:z v="(.*)"/> -->')


class _Table(object):
	def __init__(self, tableid):
		self.tableid = tableid
		self.rows = {}

	def __repr__(self):
		return 'Table %r: %r' % (self.tableid, self.rows)

	def add_cell(self, rowid, col, atom):
		if ':' in rowid:
			rowid = rowid.split(':')[0]
		row = self.rows.get(rowid)
		if not row:
			row = self.rows[rowid] = {}
		row[col] = _unescape_data(atom)

	def del_row(self, rowid):
		if ':' in rowid:
			rowid = rowid.split(':')[0]
		if rowid in self.rows:
			del self.rows[rowid]


def _unescape_character(match):
	value = match.group()
	try:
		return chr(int(value[1:], 16))
	except ValueError:
		return value


def _unescape_data(instr):
	for src, dst in SPECIAL_CHARS:
		instr = instr.replace(src, dst)
	return RE_ESCAPED.sub(_unescape_character, instr)


def _read_mork(filename):
	''' Read mork file, return tables from file '''
	data = []
	with open(filename, 'rt') as mfile:
		header = mfile.readline().strip()
		# check header
		if not RE_HEADER.match(header):
			pretty.print_debug(__name__, '_read_mork: header error', header)
			return {}
		for line in mfile:
			# remove blank lines and comments
			line = line.strip()
			if not line:
				continue
			# remove comments
			comments = line.find('// ')
			if comments > -1:
				line = line[:comments].strip()
			if line:
				data.append(line)
		data = ''.join(data)

	if not data:
		return {}

	data = data.replace('\\)', '$29')

	# decode data
	cells = {}
	atoms = {}
	tables = {}
	pos = 0
	active_trans = False
	while data:
		data = data[pos:].lstrip()
		if not data:
			break

		# cols
		match = RE_COLS.match(data)
		if match:
			for cell in RE_CELL.findall(match.group()):
				key, val = cell.split('=', 1)
				if val in COLS_TO_KEEP:  # skip necessary columns
					cells[key] = val
			pos = match.span()[1]
			continue

		# atoms
		match = RE_ATOM.match(data)
		if match:
			for cell in RE_CELL.findall(match.group()):
				if '=' in cell:
					key, val = cell.split('=', 1)
					atoms[key] = val
			pos = match.span()[1]
			continue

		# tables
		match = RE_TABLE.match(data)
		if match:
			tableid = ':'.join(match.groups()[:2])
			table = tables.get(tableid)
			if not table:
				table = tables[tableid] = _Table(tableid)
			for row in RE_ROW.findall(match.group()):
				tran, rowid = row[:2]
				if active_trans and rowid[0] == '-':
					rowid = rowid[1:]
					table.del_row(rowid)
				if not active_trans or tran != '-':
					rowdata = row[2:]
					for rowcell in rowdata:
						for cell in RE_CELL.findall(rowcell):
							atom, col = None, None
							match = RE_CELL_TEXT.match(cell)
							if match:
								col = cells.get(match.group(1))
								atom = match.group(2)
							else:
								match = RE_CELL_OID.match(cell)
								if match:
									col = cells.get(match.group(1))
									atom = atoms.get(match.group(2))
							if col and atom:
								table.add_cell(rowid, col, atom)
			pos = match.span()[1]
			continue

		# transaction
		match = RE_TRAN_BEGIN.match(data)
		if match:
			active_trans = True
			continue

		if match := RE_TRAN_END.match(data):
			tran = True
			continue

		if match := RE_ROW.match(data):
			row = match.groups()
			tran, rowid = row[:2]
			table = tables.get('1:80')  # bind to default table
			if rowid[0] == '-':
				rowid = rowid[1:]
				if table:
					table.del_row(rowid)
			if tran != '-':
				rowdata = row[2:]
				if not table:
					table = tables['1:80'] = _Table('1:80')
				for rowcell in rowdata:
					for cell in RE_CELL.findall(rowcell):
						atom, col = None, None
						match = RE_CELL_TEXT.match(cell)
						if match:
							col = cells.get(match.group(1))
							atom = match.group(2)
						else:
							match = RE_CELL_OID.match(cell)
							if match:
								col = cells.get(match.group(1))
								atom = atoms.get(match.group(2))
						if col and atom:
							table.add_cell(rowid, col, atom)
			pos = match.span()[1]
			continue

		pos = 1
	return tables


def _mork2contacts(tables):
	''' Get contacts from mork table prepared by _read_mork '''
	if not tables:
		return

	for table in tables.itervalues():
		for row in table.rows.itervalues():
			display_name = row.get('DisplayName')
			if not display_name:
				first_name = row.get('FirstName', '')
				last_name = row.get('LastName', '')
				display_name = ' '.join((first_name, last_name))

			display_name = display_name.strip()
			if not display_name:
				continue
			for key in ('PrimaryEmail', 'SecondEmail'):
				if email := row.get(key):
					yield (display_name, email)


def get_addressbook_dir():
	''' Get path to addressbook file from default profile. '''
	thunderbird_home = None
	for thome, tprofile in THUNDERBIRD_PROFILES:
		if os.path.isfile(tprofile):
			thunderbird_home = thome
			break
	if not thunderbird_home:
		return None
	config = RawConfigParser()
	config.read(tprofile)
	path = None
	for section in config.sections():
		if config.has_option(section, "Default") and \
				config.get(section, "Default") == "1" and \
				config.has_option(section, "Path"):
			path = config.get(section, "Path")
			break
		elif config.has_option(section, "Path"):
			path = config.get(section, "Path")
	if path:
		path = os.path.join(thunderbird_home, path)
	# I thought it was strange to return something that is constant here
	return path


def get_addressbook_files():
	''' Get full path to all Thunderbird address book files. '''
	path = get_addressbook_dir()
	if not path:
		return
	files = os.listdir(path)
	for filename in files:
		if filename.endswith('.mab'):
			fullpath = os.path.join(path, filename)
			if os.path.isfile(fullpath):
				yield fullpath


def get_contacts():
	''' Get all contacts from all Thunderbird address books as
		((contact name, contact email)) '''
	for abook in get_addressbook_files():
		try:
			tables = _read_mork(abook)
		except IOError, err:
			pretty.print_error(__name__, 'get_contacts error', abook, err)
		else:
			for item in _mork2contacts(tables):
				yield item


if __name__ == '__main__':
	print '\n'.join(map(str, sorted(get_contacts())))
