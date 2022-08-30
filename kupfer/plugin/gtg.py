# -*- coding: UTF-8 -*-
__kupfer_name__ = _("Getting Things GNOME")
__kupfer_sources__ = ("TasksSource", )
__kupfer_actions__ = ("CreateNewTask",)
__description__ = _("Browse and create new tasks in GTG")
__version__ = "2010-05-27"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"


import os

import dbus

from kupfer import plugin_support
from kupfer import pretty
from kupfer import textutils
from kupfer.obj.base import Leaf, Action, Source
from kupfer.obj.objects import TextLeaf
from kupfer.obj.apps import AppLeafContentMixin
from kupfer.obj.helplib import FilesystemWatchMixin

plugin_support.check_dbus_connection()

_SERVICE_NAME = 'org.GTG'
_OBJECT_NAME = '/org/GTG'
_IFACE_NAME = 'org.GTG'
_GTG_HOME = "~/.local/share/gtg/"


def _create_dbus_connection(activate=False):
	''' Create dbus connection to GTG
		@activate: if True, start program if not running
	'''
	interface = None
	sbus = dbus.SessionBus()
	try:
		proxy_obj = sbus.get_object('org.freedesktop.DBus',
				'/org/freedesktop/DBus')
		dbus_iface = dbus.Interface(proxy_obj, 'org.freedesktop.DBus')
		if activate or dbus_iface.NameHasOwner(_IFACE_NAME):
			obj = sbus.get_object(_SERVICE_NAME, _OBJECT_NAME)
			if obj:
				interface = dbus.Interface(obj, _IFACE_NAME)
	except dbus.exceptions.DBusException, err:
		pretty.print_debug(err)
	return interface


def _truncate_long_text(text, maxlen=80):
	return f'{text[:maxlen - 1]}…' if len(text) > maxlen else text


def _load_tasks(interface):
	''' Load task by dbus interface '''
	for task in interface.get_tasks():
		title = task['title'].strip()
		if not title:
			title = task['text'].strip()
		title = _truncate_long_text(title)
		otask = Task(task['id'], title, task['status'])
		otask.duedate = task['duedate']
		otask.startdate = task['startdate']
		otask.tags = task['tags']
		yield otask


def _change_task_status(task_id, status):
	interface = _create_dbus_connection(True)
	task = interface.get_task(task_id)
	task['status'] = status
	interface.modify_task(task_id, task)


class Task (Leaf):
	def __init__(self, task_id, title, status):
		Leaf.__init__(self, task_id, title)
		self.status = status
		self.tags = None
		self.duedate = None
		self.startdate = None

	def get_description(self):
		descr = [self.status]
		if self.duedate:
			descr.append(_("due: %s") % self.duedate)
		if self.startdate:
			descr.append(_("start: %s") % self.startdate)
		if self.tags:
			descr.append(_("tags: %s") % " ".join(self.tags))
		return "  ".join(descr)

	def get_icon_name(self):
		return 'gtg'

	def get_actions(self):
		yield OpenEditor()
		yield Delete()
		yield MarkDone()
		yield Dismiss()


class OpenEditor (Action):
	rank_adjust = 1

	def __init__(self):
		Action.__init__(self, _("Open"))

	def activate(self, leaf):
		interface = _create_dbus_connection(True)
		interface.open_task_editor(leaf.object)

	def get_icon_name(self):
		return 'document-open'

	def get_description(self):
		return _("Open task in Getting Things GNOME!")


class Delete (Action):
	rank_adjust = -10

	def __init__(self):
		Action.__init__(self, _("Delete"))

	def activate(self, leaf):
		interface = _create_dbus_connection(True)
		interface.delete_task(leaf.object)

	def get_icon_name(self):
		return 'edit-delete'

	def get_description(self):
		return _("Permanently remove this task")


class MarkDone (Action):
	def __init__(self):
		Action.__init__(self, _("Mark Done"))

	def activate(self, leaf):
		_change_task_status(leaf.object, 'Done')

	def get_icon_name(self):
		return 'gtk-yes'

	def get_description(self):
		return _("Mark this task as done")


class Dismiss (Action):
	def __init__(self):
		Action.__init__(self, _("Dismiss"))

	def activate(self, leaf):
		_change_task_status(leaf.object, 'Dismiss')

	def get_icon_name(self):
		return 'gtk-cancel'

	def get_description(self):
		return _("Mark this task as not to be done anymore")


class CreateNewTask (Action):
	def __init__(self):
		Action.__init__(self, _("Create Task"))

	def activate(self, leaf):
		interface = _create_dbus_connection(True)
		title, body = textutils.extract_title_body(leaf.object)
		interface.open_new_task(title, body)

	def item_types(self):
		yield TextLeaf

	def get_icon_name(self):
		return 'document-new'

	def get_description(self):
		return _("Create new task in Getting Things GNOME")


class TasksSource (AppLeafContentMixin, Source, FilesystemWatchMixin):
	appleaf_content_id = 'gtg'

	def __init__(self, name=None):
		Source.__init__(self, name or __kupfer_name__)
		self._tasks = []
		self._version = 2

	def initialize(self):
		self.monitor_token = \
			self.monitor_directories(os.path.expanduser(_GTG_HOME))

	def get_items(self):
		interface = _create_dbus_connection()
		if interface is not None:
			self._tasks = list(_load_tasks(interface))
		return self._tasks

	def get_icon_name(self):
		return 'gtg'

	def provides(self):
		yield Task
