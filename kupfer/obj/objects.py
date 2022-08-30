# -*- coding: UTF-8 -*-

"""
Copyright 2007--2009 Ulrik Sverdrup <ulrik.sverdrup@gmail.com>

This file is a part of the program kupfer, which is
released under GNU General Public License v3 (or any later version),
see the main program file, and COPYING for details.
"""

import os
from os import path

import gobject

from kupfer import icons, launch, utils
from kupfer import pretty
from kupfer.obj.base import Leaf, Action, Source
from kupfer.obj.base import InvalidDataError, OperationError
from kupfer.obj import fileactions
from kupfer.interface import TextRepresentation
from kupfer.kupferstring import tounicode

def ConstructFileLeafTypes():
	""" Return a seq of the Leaf types returned by ConstructFileLeaf"""
	yield FileLeaf
	yield AppLeaf

def ConstructFileLeaf(obj):
	"""
	If the path in @obj points to a Desktop Item file,
	return an AppLeaf, otherwise return a FileLeaf
	"""
	root, ext = path.splitext(obj)
	if ext == ".desktop":
		try:
			return AppLeaf(init_path=obj)
		except InvalidDataError:
			pass
	return FileLeaf(obj)

def _directory_content(dirpath, show_hidden):
	from kupfer.obj.sources import DirectorySource
	return DirectorySource(dirpath, show_hidden)

class FileLeaf (Leaf, TextRepresentation):
	"""
	Represents one file: the represented object is a bytestring (important!)
	"""
	serializable = 1

	def __init__(self, obj, name=None):
		"""Construct a FileLeaf

		The display name of the file is normally derived from the full path,
		and @name should normally be left unspecified.

		@obj: byte string (file system encoding)
		@name: unicode name or None for using basename
		"""
		if obj is None:
			raise InvalidDataError(f"File path for {name} may not be None")
		# Use glib filename reading to make display name out of filenames
		# this function returns a `unicode` object
		if not name:
			name = gobject.filename_display_basename(obj)
		super(FileLeaf, self).__init__(obj, name)

	def __eq__(self, other):
		try:
			return (type(self) == type(other) and
					unicode(self) == unicode(other) and
					path.samefile(self.object, other.object))
		except OSError, exc:
			pretty.print_debug(__name__, exc)
			return False

	def repr_key(self):
		return self.object

	def canonical_path(self):
		"""Return the true path of the File (without symlinks)"""
		return path.realpath(self.object)

	def is_valid(self):
		return os.access(self.object, os.R_OK)

	def _is_executable(self):
		return os.access(self.object, os.R_OK | os.X_OK)

	def is_dir(self):
		return path.isdir(self.object)

	def get_text_representation(self):
		return gobject.filename_display_name(self.object)

	def get_description(self):
		return utils.get_display_path_for_bytestring(self.canonical_path())

	def get_actions(self):
		return fileactions.get_actions_for_file(self)

	def has_content(self):
		return self.is_dir() or Leaf.has_content(self)
	def content_source(self, alternate=False):
		if self.is_dir():
			return _directory_content(self.object, alternate)
		else:
			return Leaf.content_source(self)

	def get_thumbnail(self, width, height):
		if self.is_dir(): return None
		return icons.get_thumbnail_for_file(self.object, width, height)
	def get_gicon(self):
		return icons.get_gicon_for_file(self.object)
	def get_icon_name(self):
		return "folder" if self.is_dir() else "text-x-generic"

class SourceLeaf (Leaf):
	def __init__(self, obj, name=None):
		"""Create SourceLeaf for source @obj"""
		if not name:
			name = unicode(obj)
		Leaf.__init__(self, obj, name)
	def has_content(self):
		return True

	def repr_key(self):
		return repr(self.object)

	def content_source(self, alternate=False):
		return self.object

	def get_description(self):
		return self.object.get_description()

	@property
	def fallback_icon_name(self):
		return self.object.fallback_icon_name

	def get_gicon(self):
		return self.object.get_gicon()

	def get_icon_name(self):
		return self.object.get_icon_name()

class AppLeaf (Leaf):
	def __init__(self, item=None, init_path=None, app_id=None):
		"""Try constructing an Application for GAppInfo @item,
		for file @path or for package name @app_id.
		"""
		self.init_item = item
		self.init_path = init_path
		self.init_item_id = app_id and f"{app_id}.desktop"
		# finish will raise InvalidDataError on invalid item
		self.finish()
		Leaf.__init__(self, self.object, self.object.get_name())
		self._add_aliases()

	def _add_aliases(self):
		# find suitable alias
		# use package name: non-extension part of ID
		lowername = unicode(self).lower()
		package_name = self._get_package_name()
		if package_name and package_name not in lowername:
			self.kupfer_add_alias(package_name)

	def __hash__(self):
		return hash(unicode(self))

	def __eq__(self, other):
		return (isinstance(other, type(self)) and
				self.get_id() == other.get_id())

	def __getstate__(self):
		self.init_item_id = self.object and self.object.get_id()
		state = dict(vars(self))
		state["object"] = None
		state["init_item"] = None
		return state

	def __setstate__(self, state):
		vars(self).update(state)
		self.finish()

	def finish(self):
		"""Try to set self.object from init's parameters"""
		item = None
		if self.init_item:
			item = self.init_item
		else:
			# Construct an AppInfo item from either path or item_id
			from gio.unix import DesktopAppInfo, desktop_app_info_new_from_filename
			if self.init_path and os.access(self.init_path, os.X_OK):
				# serilizable if created from a "loose file"
				self.serializable = 1
				item = desktop_app_info_new_from_filename(self.init_path)
				try:
					# try to annotate the GAppInfo object
					item.init_path = self.init_path
				except AttributeError, exc:
					pretty.print_debug(__name__, exc)
			elif self.init_item_id:
				try:
					item = DesktopAppInfo(self.init_item_id)
				except RuntimeError:
					pretty.print_debug(__name__, "Application not found:",
							self.init_item_id)
		self.object = item
		if not self.object:
			raise InvalidDataError

	def repr_key(self):
		return self.get_id()

	def _get_package_name(self):
		return gobject.filename_display_basename(self.get_id())

	def launch(self, files=(), paths=(), activate=False):
		"""
		Launch the represented applications

		@files: a seq of GFiles (gio.File)
		@paths: a seq of bytestring paths
		@activate: activate instead of start new
		"""
		try:
			return launch.launch_application(self.object, files=files,
			                                 paths=paths, activate=activate,
			                                 desktop_file=self.init_path)
		except launch.LaunchError as exc:
			raise OperationError(unicode(exc))

	def get_id(self):
		"""Return the unique ID for this app.

		This is the GIO id "gedit.desktop" minus the .desktop part for
		system-installed applications.
		"""
		return launch.application_id(self.object, self.init_path)

	def get_actions(self):
		if launch.application_is_running(self.get_id()):
			yield Launch(_("Go To"), is_running=True)
			yield CloseAll()
		else:
			yield Launch()
		yield LaunchAgain()

	def get_description(self):
		# Use Application's description, else use executable
		# for "file-based" applications we show the path
		app_desc = tounicode(self.object.get_description())
		ret = tounicode(app_desc or self.object.get_executable())
		if self.init_path:
			app_path = utils.get_display_path_for_bytestring(self.init_path)
			return f"({app_path}) {ret}"
		return ret

	def get_gicon(self):
		return self.object.get_icon()

	def get_icon_name(self):
		return "exec"

class OpenUrl (Action):
	rank_adjust = 5
	def __init__(self, name=None):
		if not name:
			name = _("Open URL")
		super(OpenUrl, self).__init__(name)
	
	def activate(self, leaf):
		url = leaf.object
		self.open_url(url)
	
	def open_url(self, url):
		utils.show_url(url)

	def get_description(self):
		return _("Open URL with default viewer")

	def get_icon_name(self):
	  	return "forward"

class Launch (Action):
	""" Launches an application (AppLeaf) """
	rank_adjust = 5
	def __init__(self, name=None, is_running=False, open_new=False):
		"""
		If @is_running, style as if the app is running (Show application)
		If @open_new, always start a new instance.
		"""
		if not name:
			name = _("Launch")
		Action.__init__(self, name)
		self.is_running = is_running
		self.open_new = open_new
	
	def activate(self, leaf):
		leaf.launch(activate=not self.open_new)

	def get_description(self):
		if self.is_running:
			return _("Show application window")
		return _("Launch application")

	def get_icon_name(self):
		return "go-jump" if self.is_running else Action.get_icon_name(self)

class LaunchAgain (Launch):
	rank_adjust = 0
	def __init__(self, name=None):
		if not name:
			name = _("Launch Again")
		Launch.__init__(self, name, open_new=True)
	def item_types(self):
		yield AppLeaf
	def valid_for_item(self, leaf):
		return launch.application_is_running(leaf.get_id())
	def get_description(self):
		return _("Launch another instance of this application")

class CloseAll (Action):
	"""Attempt to close all application windows"""
	rank_adjust = -10
	def __init__(self):
		Action.__init__(self, _("Close"))
	def activate(self, leaf):
		return launch.application_close_all(leaf.get_id())
	def item_types(self):
		yield AppLeaf
	def valid_for_item(self, leaf):
		return launch.application_is_running(leaf.get_id())
	def get_description(self):
		return _("Attempt to close all application windows")
	def get_icon_name(self):
		return "window-close"

class UrlLeaf (Leaf, TextRepresentation):
	def __init__(self, obj, name):
		super(UrlLeaf, self).__init__(obj, name)

	def get_actions(self):
		return (OpenUrl(), )

	def get_description(self):
		return self.object

	def get_icon_name(self):
		return "text-html"

class RunnableLeaf (Leaf):
	"""Leaf where the Leaf is basically the action itself,
	for items such as Quit, Log out etc.
	"""
	def __init__(self, obj=None, name=None):
		Leaf.__init__(self, obj, name)
	def get_actions(self):
		yield Perform()
	def run(self):
		raise NotImplementedError
	def repr_key(self):
		return ""
	def get_gicon(self):
		if iname := self.get_icon_name():
			return icons.get_gicon_with_fallbacks(None, (iname, ))
		return icons.ComposedIcon("kupfer-object", "gtk-execute")
	def get_icon_name(self):
		return ""

class Perform (Action):
	"""Perform the action in a RunnableLeaf"""
	rank_adjust = 5
	def __init__(self, name=None):
		# TRANS: 'Run' as in Perform a (saved) command
		if not name: name = _("Run")
		super(Perform, self).__init__(name=name)
	def activate(self, leaf):
		return leaf.run()
	def get_description(self):
		return _("Perform command")

class TextLeaf (Leaf, TextRepresentation):
	"""Represent a text query
	The represented object is a unicode string
	"""
	serializable = 1
	def __init__(self, text, name=None):
		"""@text *must* be unicode or UTF-8 str"""
		text = tounicode(text)
		if not name:
			lines = [l for l in text.splitlines() if l.strip()]
			name = lines[0] if lines else text
		if len(text) == 0:
			name = _("(Empty Text)")
		Leaf.__init__(self, text, name)

	def get_actions(self):
		return ()

	def repr_key(self):
		return hash(self.object)

	def get_description(self):
		lines = [l for l in self.object.splitlines() if l.strip()]
		desc = lines[0] if lines else self.object
		numlines = len(lines) or 1

		# TRANS: This is description for a TextLeaf, a free-text search
		# TRANS: The plural parameter is the number of lines %(num)d
		return ngettext('"%(text)s"', '(%(num)d lines) "%(text)s"',
			numlines) % {"num": numlines, "text": desc }

	def get_icon_name(self):
		return "edit-select-all"

