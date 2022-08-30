from time import time
import os
import cPickle as pickle

import gtk
import gobject

from kupfer import pretty, config
from kupfer import scheduler
from kupfer import desktop_launch
from kupfer.ui import keybindings
from kupfer import terminal

try:
	import wnck
except ImportError, e:
	pretty.print_info(__name__, "Disabling window tracking:", e)
	wnck = None

class LaunchError (Exception):
	"Error launching application"


default_associations = {
	"evince" : "Document Viewer",
	"file-roller" : "File Roller",
	#"gedit" : "Text Editor",
	"gnome-keyring-manager" : "Keyring Manager",
	"nautilus-browser" : "File Manager",
	"rhythmbox" : "Rhythmbox Music Player",
}


_seq = [0]
_latest_event_time = 0

def make_startup_notification_id():
	time = _current_event_time()
	_seq[0] = _seq[0] + 1
	return "%s-%d-%s_TIME%d" % ("kupfer", os.getpid(), _seq[0], time)

def _current_event_time():
	_time = gtk.get_current_event_time() or keybindings.get_current_event_time()
	global _latest_event_time
	if _time > 0:
		_latest_event_time = _time
	else:
		_time = _latest_event_time
	return _time


def application_id(app_info, desktop_file=None):
	"""Return an application id (string) for GAppInfo @app_info"""
	app_id = app_info.get_id()
	if not app_id:
		app_id = desktop_file or ""
	if app_id.endswith(".desktop"):
		app_id = app_id[:-len(".desktop")]
	return app_id

def launch_application(app_info, files=(), uris=(), paths=(), track=True,
	                   activate=True, desktop_file=None):
	"""
	Launch @app_rec correctly, using a startup notification

	you may pass in either a list of gio.Files in @files, or 
	a list of @uris or @paths

	if @track, it is a user-level application
	if @activate, activate rather than start a new version

	@app_rec is either an GAppInfo or (GAppInfo, desktop_file_path) tuple

	Raises LaunchError on failed program start.
	"""
	assert app_info

	from gio import File
	from glib import GError

	if paths:
		files = [File(p) for p in paths]
	if uris:
		files = [File(p) for p in uris]

	svc = GetApplicationsMatcherService()
	app_id = application_id(app_info, desktop_file)

	if activate and svc.application_is_running(app_id):
		svc.application_to_front(app_id)
		return True

	# An launch callback closure for the @app_id
	def application_launch_callback(argv, pid, notify_id, files, timestamp):
		pretty.print_debug(__name__, "Launched", argv, pid, notify_id, files)
		is_terminal = terminal.is_known_terminal_executable(argv[0])
		pretty.print_debug(__name__, argv, "is terminal:", is_terminal)
		if not is_terminal:
			svc.launched_application(app_id, pid)

	launch_callback = application_launch_callback if track else None
	try:
		desktop_launch.launch_app_info(app_info, files,
			   timestamp=_current_event_time(), desktop_file=desktop_file,
			   launch_cb=launch_callback)
	except desktop_launch.SpawnError as exc:
		raise LaunchError(unicode(exc))
	return True

def application_is_running(app_id):
	svc = GetApplicationsMatcherService()
	return svc.application_is_running(app_id)

def application_close_all(app_id):
	svc = GetApplicationsMatcherService()
	return svc.application_close_all(app_id)

class ApplicationsMatcherService (pretty.OutputMixin):
	"""Handle launching applications and see if they still run.
	This is a learning service, since we have no first-class application
	object on the Linux desktop
	"""
	def __init__(self):
		self.register = {}
		self._get_wnck_screen_windows_stacked()
		scheduler.GetScheduler().connect("finish", self._finish)
		self._load()

	@classmethod
	def _get_wnck_screen_windows_stacked(cls):
		if not wnck:
			return ()
		screen = wnck.screen_get_default()
		return screen.get_windows_stacked()

	def _get_filename(self):
		# Version 1: Up to incl v203
		# Version 2: Do not track terminals
		version = 2
		return os.path.join(config.get_cache_home(),
				"application_identification_v%d.pickle" % version)
	def _load(self):
		reg = self._unpickle_register(self._get_filename())
		self.register = reg or default_associations
		# pretty-print register to debug
		if self.register:
			self.output_debug("Learned the following applications")
			self.output_debug("\n{\n%s\n}" % "\n".join(
				("  %-30s : %s" % (k,v)
					for k,v in self.register.iteritems())
				))
	def _finish(self, sched):
		self._pickle_register(self.register, self._get_filename())
	def _unpickle_register(self, pickle_file):
		try:
			pfile = open(pickle_file, "rb")
		except IOError, e:
			return None
		try:
			source = pickle.loads(pfile.read())
			assert isinstance(source, dict), "Stored object not a dict"
			self.output_debug("Reading from %s" % (pickle_file, ))
		except (pickle.PickleError, Exception), e:
			source = None
			self.output_info("Error loading %s: %s" % (pickle_file, e))
		return source

	def _pickle_register(self, reg, pickle_file):
		with open(pickle_file, "wb") as output:
			self.output_debug(f"Saving to {pickle_file}")
			output.write(pickle.dumps(reg, pickle.HIGHEST_PROTOCOL))
		return True

	def _store(self, app_id, window):
		# FIXME: Store the 'res_class' name?
		application = window.get_application()
		store_name = application.get_name()
		self.register[app_id] = store_name
		self.output_debug("storing application", app_id, "as", store_name)

	def _has_match(self, app_id):
		return app_id in self.register

	def _is_match(self, app_id, window):
		application = window.get_application()
		res_class = window.get_class_group().get_res_class()
		reg_name = self.register.get(app_id)
		if reg_name and reg_name in (application.get_name(), res_class):
			return True
		return app_id in (application.get_name().lower(), res_class.lower())

	def launched_application(self, app_id, pid):
		if self._has_match(app_id):
			return
		timeout = time() + 15
		gobject.timeout_add_seconds(2, self._find_application, app_id, pid, timeout)
		# and once later
		gobject.timeout_add_seconds(30, self._find_application, app_id, pid, timeout)

	def _find_application(self, app_id, pid, timeout):
		if self._has_match(app_id):
			return False
		self.output_debug("Looking for window for application", app_id)
		for w in self._get_wnck_screen_windows_stacked():
			app = w.get_application()
			app_pid = app.get_pid()
			if not app_pid:
				app_pid = w.get_pid()
			if app_pid == pid:
				self._store(app_id, w)
				return False
		return time() <= timeout

	def application_name(self, app_id):
		return self.register[app_id] if self._has_match(app_id) else None

	def application_is_running(self, app_id):
		return any(
			w.get_application() and self._is_match(app_id, w)
			for w in self._get_wnck_screen_windows_stacked()
		)

	def get_application_windows(self, app_id):
		return [
			w
			for w in self._get_wnck_screen_windows_stacked()
			if w.get_application() and self._is_match(app_id, w)
		]

	def application_to_front(self, app_id):
		application_windows = self.get_application_windows(app_id)
		if not application_windows:
			return False

		# for now, just take any window
		evttime = _current_event_time()
		for w in application_windows:
			# we special-case the desktop
			# only show desktop if it's the only window of this app
			if w.get_name() == "x-nautilus-desktop":
				if len(application_windows) != 1:
					continue
				screen = wnck.screen_get_default()
				screen.toggle_showing_desktop(True)
			if wspc := w.get_workspace():
				wspc.activate(evttime)
			w.activate(evttime)
			break

	def application_close_all(self, app_id):
		application_windows = self.get_application_windows(app_id)
		evttime = _current_event_time()
		for w in application_windows:
			if not w.is_skip_tasklist():
				w.close(evttime)


_appl_match_service = None
def GetApplicationsMatcherService():
	"""Get the (singleton) ApplicationsMatcherService"""
	global _appl_match_service
	if not _appl_match_service:
		_appl_match_service = ApplicationsMatcherService()
	return _appl_match_service

