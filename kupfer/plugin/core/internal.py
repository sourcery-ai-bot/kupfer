
from kupfer.objects import Source, Leaf
from kupfer.objects import RunnableLeaf
from kupfer import commandexec

__kupfer_sources__ = ("KupferInterals", "CommandResults", )
__author__ = "Ulrik Sverdrup <ulrik.sverdrup@gmail.com>"

class LastCommand (RunnableLeaf):
	"Represented object is the command tuple to run"
	qf_id = "lastcommand"
	def __init__(self, obj):
		RunnableLeaf.__init__(self, obj, _("Last Command"))

	def run(self):
		ctx = commandexec.DefaultActionExecutionContext()
		obj, action, iobj = self.object
		return ctx.run(obj, action, iobj, delegate=True)

class KupferInterals (Source):
	def __init__(self):
		Source.__init__(self, _("Internal Kupfer Objects"))
	def is_dynamic(self):
		return True
	def get_items(self):
		ctx = commandexec.DefaultActionExecutionContext()
		if ctx.last_command is None:
			return
		yield LastCommand(ctx.last_command)
	def provides(self):
		yield LastCommand

class LastResultObject (Leaf):
	"dummy superclass"

def _make_first_result_object(leaf):
	global LastResultObject
	class LastResultObject (LastResultObject):
		qf_id = "lastresult"
		def __init__(self, leaf):
			Leaf.__init__(self, leaf.object, _("Last Result"))
			vars(self).update(vars(leaf))
			self.name = _("Last Result")
			self.__orignal_leaf = leaf
			self.__class__.__bases__ = (leaf.__class__, Leaf)

		def get_gicon(self):
			return None
		def get_icon_name(self):
			return Leaf.get_icon_name(self)
		def get_thumbnail(self, w, h):
			return None
		def get_description(self):
			return unicode(self.__orignal_leaf)

	return LastResultObject(leaf)


class CommandResults (Source):
	def __init__(self):
		Source.__init__(self, _("Command Results"))
	def is_dynamic(self):
		return True
	def get_items(self):
		ctx = commandexec.DefaultActionExecutionContext()
		yield from reversed(ctx.last_results)
		try:
			leaf = ctx.last_results[-1]
		except IndexError:
			return
		yield _make_first_result_object(leaf)

	def provides(self):
		yield Leaf
		yield LastResultObject
