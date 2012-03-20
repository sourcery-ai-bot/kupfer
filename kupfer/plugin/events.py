__kupfer_name__ = _("Events")
__kupfer_actions__ = (
    "AddEvent",
)
__description__ = _("Adds custom events to trigger objects")
__version__ = "2009-12-30"
__author__ = "Jakh Daven <tuxcanfly@gmail.com>"

import gtk
import glib

from kupfer.objects import Action, Source
from kupfer.objects import Leaf, TextLeaf, RunnableLeaf
from kupfer.objects import OperationError
from kupfer.obj.compose import ComposedLeaf
from kupfer import puid
from kupfer import kupferstring
from kupfer import task


class EventLeaf(Leaf):
    pass

class EventSource(Source):

    events = []

    def __init__(self):
        Source.__init__(self, _("Events"))

    @classmethod
    def register_event(self, event):
        self.events.append(event)

    def get_items(self):
        for event in self.events:
            yield event

    def provides(self):
        yield EventLeaf


class AddEvent (Action):
    def __init__(self):
        Action.__init__(self, _("Run when..."))

    def activate(self, leaf, iobj):
        pass

    def item_types(self):
        yield ComposedLeaf

    def get_icon_name(self):
        return "insert-object"

    def requires_object(self):
        return True

    def object_types(self):
        yield EventLeaf

    def object_source(self, for_item=None):
        return EventSource()
