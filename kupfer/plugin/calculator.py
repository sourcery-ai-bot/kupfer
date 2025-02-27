from __future__ import division
__kupfer_name__ = _("Calculator")
__kupfer_actions__ = ("Calculate", )
__description__ = _("Calculate expressions starting with '='")
__version__ = ""
__author__ = "Ulrik Sverdrup <ulrik.sverdrup@gmail.com>"


import cmath
import math

from kupfer.objects import Source, Action, TextLeaf
from kupfer import pretty


class IgnoreResultException (Exception):
	pass

class KupferSurprise (float):
	"""kupfer

	cleverness to the inf**inf
	"""
	def __call__(self, *args):
		from kupfer import utils, version
		utils.show_url(version.WEBSITE)
		raise IgnoreResultException

class DummyResult (object):
	def __unicode__(self):
		return u"<Result of last expression>"

class Help (object):
	"""help()

	Show help about the calculator
	"""
	def __call__(self):
		import textwrap

		from kupfer import uiutils

		environment = make_environment(last_result=DummyResult())
		docstrings = []
		for attr in sorted(environment):
			if attr != "_" and attr.startswith("_"):
				continue
			val = environment[attr]
			if not callable(val):
				docstrings.append(f"{attr} = {val}")
				continue
			try:
				docstrings.append(val.__doc__)
			except AttributeError:
				pass
		formatted = []
		maxlen = 72
		left_margin = 4
		for docstr in docstrings:
			# Wrap the description and align continued lines
			docsplit = docstr.split("\n", 1)
			if len(docsplit) < 2:
				formatted.append(docstr)
				continue
			wrapped_lines = textwrap.wrap(docsplit[1].strip(),
					maxlen - left_margin)
			wrapped = (u"\n" + u" "*left_margin).join(wrapped_lines)
			formatted.append("%s\n    %s" % (docsplit[0], wrapped))
		uiutils.show_text_result("\n\n".join(formatted), _("Calculator"))
		raise IgnoreResultException

	def __complex__(self):
		return self()

def make_environment(last_result=None):
	"Return a namespace for the calculator's expressions to be executed in."
	environment = vars(math) | vars(cmath)
	# define some constants missing
	if last_result is not None:
		environment["_"] = last_result
	environment["help"] = Help()
	environment["kupfer"] = KupferSurprise("inf")
	# make the builtins inaccessible
	environment["__builtins__"] = {}
	return environment

def format_result(res):
	cres = complex(res)
	parts = []
	if cres.real:
		parts.append(f"{cres.real}")
	if cres.imag:
		parts.append(f"{complex(0, cres.imag)}")
	return u"+".join(parts) or f"{res}"

class Calculate (Action):
	# since it applies only to special queries, we can up the rank
	rank_adjust = 10
	def __init__(self):
		Action.__init__(self, _("Calculate"))
		self.last_result = None

	def has_result(self):
		return True
	def activate(self, leaf):
		expr = leaf.object.lstrip("= ")

		# try to add missing parantheses
		brackets_missing = expr.count("(") - expr.count(")")
		if brackets_missing > 0:
			expr += ")"*brackets_missing
		environment = make_environment(self.last_result)

		pretty.print_debug(__name__, "Evaluating", repr(expr))
		try:
			result = eval(expr, environment)
			resultstr = format_result(result)
			self.last_result = result
		except IgnoreResultException:
			return
		except Exception, exc:
			pretty.print_error(__name__, type(exc).__name__, exc)
			resultstr = unicode(exc)
		return TextLeaf(resultstr)

	def item_types(self):
		yield TextLeaf
	def valid_for_item(self, leaf):
		text = leaf.object
		return text and text.startswith("=")

	def get_description(self):
		return None
