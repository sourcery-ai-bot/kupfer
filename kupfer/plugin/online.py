# -*- coding: UTF-8 -*-
# vim: set noexpandtab ts=8 sw=8:
__kupfer_name__ = _("Online Event")
__kupfer_sources__ = ()
__kupfer_actions__ = ()

from events import EventSource, EventLeaf

OnlineEvent = EventLeaf('contact_is_online', _('Contact is Online'))

EventSource.register_event(OnlineEvent)
