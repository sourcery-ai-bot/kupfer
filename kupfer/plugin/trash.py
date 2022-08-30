__kupfer_name__ = _("Trash")
__kupfer_sources__ = ("TrashSource", )
__description__ = _("Access trash contents")
__version__ = "2009-12-06"
__author__ = "Ulrik Sverdrup <ulrik.sverdrup@gmail.com>"

import gio

from kupfer.objects import Leaf, Action, Source, SourceLeaf, FileLeaf
from kupfer.obj.fileactions import Open
from kupfer import utils, icons, pretty



TRASH_URI = 'trash://'

class RestoreTrashedFile (Action):
	def __init__(self):
		Action.__init__(self, _("Restore"))

	def has_result(self):
		return True

	def activate(self, leaf):
		orig_path = leaf.get_orig_path()
		if not orig_path:
			return
		orig_gfile = gio.File(orig_path)
		cur_gfile = leaf.get_gfile()
		if orig_gfile.query_exists():
			raise IOError(f"Target file exists at {orig_gfile.get_path()}")
		pretty.print_debug(__name__, f"Move {cur_gfile} to {orig_gfile}")
		ret = cur_gfile.move(orig_gfile)
		pretty.print_debug(__name__, f"Move ret={ret}")
		return FileLeaf(orig_gfile.get_path())

	def get_description(self):
		return _("Move file back to original location")
	def get_icon_name(self):
		return "edit-undo"

class TrashFile (Leaf):
	"""A file in the trash. Represented object is a file info object"""
	def __init__(self, trash_uri, info):
		name = info.get_display_name()
		Leaf.__init__(self, info, name)
		self._trash_uri = trash_uri
	def get_actions(self):
		if self.get_orig_path():
			yield RestoreTrashedFile()
	def get_gfile(self):
		return gio.File(self._trash_uri).get_child(self.object.get_name())
	def get_orig_path(self):
		try:
			return self.object.get_attribute_byte_string("trash::orig-path")
		except AttributeError:
			pass
		return None

	def is_valid(self):
		return self.get_gfile().query_exists()

	def get_description(self):
		orig_path = self.get_orig_path()
		return utils.get_display_path_for_bytestring(orig_path) if orig_path \
				else None
	def get_gicon(self):
		return self.object.get_icon()
	def get_icon_name(self):
		return "text-x-generic"

class TrashContentSource (Source):
	def __init__(self, trash_uri, name):
		Source.__init__(self, name)
		self._trash_uri = trash_uri

	def is_dynamic(self):
		return True
	def get_items(self):
		gfile = gio.File(self._trash_uri)
		enumerator = gfile.enumerate_children("standard::*,trash::*")
		for info in enumerator:
			yield TrashFile(self._trash_uri, info)
	def should_sort_lexically(self):
		return True
	def get_gicon(self):
		return icons.get_gicon_for_file(self._trash_uri)

class SpecialLocation (Leaf):
	""" Base class for Special locations (in GIO/GVFS),
	such as trash:/// Here we assume they are all "directories"
	"""
	def __init__(self, location, name=None, description=None, icon_name=None):
		"""Special location with @location and
		@name. If unset, we find @name from filesystem
		@description is Leaf description"""
		gfile = gio.File(location)
		info = gfile.query_info(gio.FILE_ATTRIBUTE_STANDARD_DISPLAY_NAME)
		name = (info.get_attribute_string(gio.FILE_ATTRIBUTE_STANDARD_DISPLAY_NAME) or location)
		Leaf.__init__(self, location, name)
		self.description = description
		self.icon_name = icon_name
	def get_actions(self):
		yield Open()
	def get_description(self):
		return self.description or self.object
	def get_gicon(self):
		# Get icon
		return icons.get_gicon_for_file(self.object)
	def get_icon_name(self):
		return "folder"

class Trash (SpecialLocation):
	def __init__(self, trash_uri, name=None):
		SpecialLocation.__init__(self, trash_uri, name=name)

	def has_content(self):
		return self.get_item_count()
	def content_source(self, alternate=False):
		return TrashContentSource(self.object, name=unicode(self))

	def get_item_count(self):
		gfile = gio.File(self.object)
		info = gfile.query_info(gio.FILE_ATTRIBUTE_TRASH_ITEM_COUNT)
		return info.get_attribute_uint32(gio.FILE_ATTRIBUTE_TRASH_ITEM_COUNT)

	def get_description(self):
		item_count = self.get_item_count()
		return (
			ngettext(
				"Trash contains one file", "Trash contains %(num)s files", item_count
			)
			% {"num": item_count}
			if item_count
			else _("Trash is empty")
		)

class InvisibleSourceLeaf (SourceLeaf):
	"""Hack to hide this source"""
	def is_valid(self):
		return False

class TrashSource (Source):
	def __init__(self):
		Source.__init__(self, _("Trash"))
	def get_items(self):
		yield Trash(TRASH_URI)
	def get_leaf_repr(self):
		return InvisibleSourceLeaf(self)
	def provides(self):
		yield SpecialLocation
