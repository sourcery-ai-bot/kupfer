
"""
Implementation of unescaping and unquoting of the Exec= key in
the Desktop Entry Specification (As of March 2011, version 1.1-draft)
http://standards.freedesktop.org/desktop-entry-spec/latest/ar01s06.html
http://standards.freedesktop.org/desktop-entry-spec/desktop-entry-spec-1.1.html#exec-variables

The unescaping we are doing is only one way.. so we unescape according to the
rules, but we accept everything, if validly quoted or not.
"""


# This is the "string" type encoding escapes
# this is unescaped before we process anything..
escape_table = {
	r'\s': ' ',
	r'\n': '\n',
	r'\t': '\t',
	r'\r': '\r',
	'\\\\': '\\',
}

# quoted are those chars that need a backslash in front
# (inside a double-quoted section, that is)
quoted = r""" " ` $ \ """.split()
quoted_table = {
	r'\"': '"',
	r'\`': '`',
	r'\$': '$',
	'\\\\': '\\',
}

'''
# reserved are those that need to be inside quotes
# note that all the quoted are also reserved, of course

We don't use these at all
reserved = r""" " ' \ > < ~ | & ; $ * ? # ( ) ` """.split()
reserved.extend([' ', '\t', '\n'])
'''

def rmquotes(s):
	"remove first and last char if we can"
	return s[1:-1] if len(s) > 1 and s[0] == s[-1] and s[0] in '"\'' else s

def two_part_unescaper(s, reptable):
	"Scan @s two characters at a time and replace using @reptable"
	if not s:
		return s
	def _inner():
		it = iter(zip(s, s[1:]))
		for cur, nex in it:
			key = cur+nex
			if key in reptable:
				yield reptable[key]
				try:
					it.next()
				except StopIteration:
					return
			else:
				yield cur
		yield s[-1]
	return ''.join(_inner())

def quote_scanner(s, reptable):
	"Scan @s two characters at a time and replace using @reptable"
	qstr = r'"'
	eqstr = '\\' + qstr

	parts = []  # A list of arguments

	if not s:
		return parts

	def add_part(is_quoted, part):
		_ps = "".join(part)
		if is_quoted:
			parts.append(two_part_unescaper(rmquotes(_ps), reptable))
		else:
			parts.extend(_ps.split())


	is_quoted = False
	it = iter(zip(s, s[1:]))
	part = []
	for cur, nex in it:
		part.append(cur)
		if cur+nex == eqstr:
			# Skip along if we see an escaped quote (\")
			part.append(nex)
			try:
				it.next()
			except StopIteration:
				break
		elif cur == qstr:
			if is_quoted:
				add_part(is_quoted, part)
				part = []
				is_quoted = not is_quoted
			else:
				head = part[:-1]
				if head:
					add_part(is_quoted, head)
					part = [part[-1]]
				is_quoted = not is_quoted
	else:
		# This is a for-else: we did not 'break'
		# Emit the last if it wasn't already
		part.append(s[-1])
	add_part(is_quoted, part)
	return parts


def unescape(s):
	"Primary unescape of control sequences"
	return two_part_unescaper(s, escape_table)

def unquote_inside(s):
	"unquote reserved chars inside a quoted string"
	slash = '\\'
	t = {slash+rep: rep for rep in quoted}
	return two_part_unescaper(s, t)

def test_unescape():
	r"""
	>>> t = r'"This \\$ \\\\ \s\\\\"'
	>>> unescape(t)
	'"This \\$ \\\\  \\\\"'
	>>> unescape(r'\t\s\\\\')
	'\t \\\\'
	"""
	pass

def test_unquote_inside():
	r"""
	>>> unquote_inside(r'\$ \\ \" \`')
	'$ \\ " `'
	>>> unquote_inside(r'abc \q')
	'abc \\q'
	"""
	pass

def parse_argv(instr):
	"Parse quoted @instr into an argv"
	return quote_scanner(instr, quoted_table)

def parse_unesc_argv(instr):
	"Parse quoted @instr into an argv after unescaping it"
	return quote_scanner(unescape(instr), quoted_table)

'''
print escaped
print reserved

t = r'"This \\$ \\\\ \s\\\\"'
print repr(t)
print t
print unescape(t)
print unquote_inside(rmquotes(unescape(t)))

print two_part_unescaper(t, escape_table)

print quote_scanner(r'"hi \"there" I am you\"', inside_table)
print quote_scanner(r'Now "\"this\" will be interesting"""', inside_table)
print quote_scanner(unescape(r'"\\$"'), inside_table)

'''

if __name__ == "__main__":
	import doctest
	doctest.testmod()
