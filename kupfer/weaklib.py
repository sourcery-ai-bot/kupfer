"""
This module is a part of the program Kupfer, see the main program file for
more information.
"""
import weakref

class WeakCallback (object):
	"""A Weak Callback object that will keep a reference to
	the connecting object with weakref semantics.

	This allows object A to pass a callback method to object S,
	without object S keeping A alive.
	"""
	def __init__(self, mcallback):
		"""Create a new Weak Callback calling the method @mcallback"""
		obj = mcallback.im_self
		attr = mcallback.im_func.__name__
		self.wref = weakref.ref(obj, self.object_deleted)
		self.callback_attr = attr
		self.token = None

	def __call__(self, *args, **kwargs):
		if obj := self.wref():
			attr = getattr(obj, self.callback_attr)
			attr(*args, **kwargs)
		else:
			self.default_callback(*args, **kwargs)

	def default_callback(self, *args, **kwargs):
		"""Called instead of callback when expired"""
		pass

	def object_deleted(self, wref):
		"""Called when callback expires"""
		pass

class DbusWeakCallback (WeakCallback):
	"""
	Will use @token if set as follows:
		token.remove()
	"""
	def object_deleted(self, wref):
		if self.token:
			self.token.remove()
			self.token = None

def dbus_signal_connect_weakly(bus, signal, mcallback, **kwargs):
	"""
	Connect method @mcallback to dbus signal using a weak callback

	Connect to @signal on @bus, passing on all keyword arguments
	"""
	weak_cb = DbusWeakCallback(mcallback)
	weak_cb.token = bus.add_signal_receiver(weak_cb, signal, **kwargs)

class GobjectWeakCallback (WeakCallback):
	"""
	Will use @token if set as follows:
		sender.disconnect(token)
	"""
	__senders = {}

	def object_deleted(self, wref):
		if sender := self.__senders.pop(self.token, None):
			sender.disconnect(self.token)

	@classmethod
	def _connect(cls, sender, signal, mcallback, *user_args):
		# We save references to the sender in a class variable,
		# this is the only way to have it accessible when obj expires.
		wc = cls(mcallback)
		wc.token = sender.connect(signal, wc, *user_args)
		cls.__senders[wc.token] = sender

def gobject_connect_weakly(sender, signal, mcallback, *user_args):
	"""Connect weakly to GObject @sender's @signal,
	with a callback method @mcallback

	>>> import gtk
	>>> btn = gtk.Button()
	>>> class Handler (object):
	...   def handle(self): pass
	...   def __del__(self): print "deleted"
	...
	>>> h = Handler()
	>>> gobject_connect_weakly(btn, "clicked", h.handle)
	>>> del h
	deleted
	>>>
	"""
	GobjectWeakCallback._connect(sender, signal, mcallback, *user_args)

if __name__ == '__main__':
	import doctest
	doctest.testmod()
