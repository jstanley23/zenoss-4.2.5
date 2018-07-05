##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2009, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


from zope.event import notify
from zope.interface import implements
from zope.component import adapter
from zope.container.interfaces import IObjectAddedEvent, IObjectMovedEvent
from zope.container.interfaces import IObjectRemovedEvent
from OFS.interfaces import IObjectWillBeMovedEvent, IObjectWillBeAddedEvent
from interfaces import IIndexingEvent, IGloballyIndexed, ITreeSpanningComponent, IDeviceOrganizer
from paths import devicePathsFromComponent

from Products.ZenRelations.RelationshipBase import RelationshipBase

class IndexingEvent(object):
    implements(IIndexingEvent)
    def __init__(self, object, idxs=None, update_metadata=True):
        self.object = object
        self.idxs = idxs
        self.update_metadata = update_metadata


@adapter(IGloballyIndexed, IIndexingEvent)
def onIndexingEvent(ob, event):
    try:
        catalog = ob.getPhysicalRoot().zport.global_catalog
    except (KeyError, AttributeError):
        # Migrate script hasn't run yet; ignore indexing
        return
    idxs = event.idxs
    if isinstance(idxs, basestring):
        idxs = [idxs]
    try:
        evob = ob.primaryAq()
    except (AttributeError, KeyError), e:
        evob = ob
    path = evob.getPrimaryPath()
    # Ignore things dmd or above
    if len(path)<=3 or path[2]!='dmd':
        return
    catalog.catalog_object(evob, idxs=idxs,
                           update_metadata=event.update_metadata)


@adapter(IGloballyIndexed, IObjectWillBeMovedEvent)
def onObjectRemoved(ob, event):
    """
    Unindex, please.
    """
    if not IObjectWillBeAddedEvent.providedBy(event):
        try:
            catalog = ob.getPhysicalRoot().zport.global_catalog
        except (KeyError, AttributeError):
            # Migrate script hasn't run yet; ignore indexing
            return
        path = ob.getPrimaryPath()
        # Ignore things dmd or above
        if len(path)<=3 or path[2]!='dmd':
            return
        uid = '/'.join(path)
        if catalog.getrid(uid) is None:
            return
        catalog.uncatalog_object(uid)


@adapter(IGloballyIndexed, IObjectAddedEvent)
def onObjectAdded(ob, event):
    """
    Simple subscriber that fires the indexing event for all
    indices.
    """
    notify(IndexingEvent(ob))


@adapter(IGloballyIndexed, IObjectMovedEvent)
def onObjectMoved(ob, event):
    """
    Reindex paths only, don't update metadata.
    """
    if not (IObjectAddedEvent.providedBy(event) or
            IObjectRemovedEvent.providedBy(event)):
        notify(IndexingEvent(ob, 'path', False))


@adapter(IDeviceOrganizer, IObjectWillBeMovedEvent)
def onOrganizerBeforeDelete(ob, event):
    """
    Before we delete the organizer we need to remove its references
    to the devices. 
    """
    if not IObjectWillBeAddedEvent.providedBy(event):
        # get the catalog
        try:
            catalog = ob.getPhysicalRoot().zport.global_catalog
        except (KeyError, AttributeError):
            # Migrate script hasn't run yet; ignore indexing
            return
        
        # remove the device's path from this organizer
        # from the indexes
        for device in ob.devices.objectValuesGen():
            catalog.unindex_object_from_paths(device, [device.getPhysicalPath()])
        

@adapter(ITreeSpanningComponent, IObjectWillBeMovedEvent)
def onTreeSpanningComponentBeforeDelete(ob, event):
    """
    When a component that links a device to another tree is going to
    be removed, update the device's paths.
    """
    if not IObjectWillBeAddedEvent.providedBy(event):
        component = ob
        try:
            catalog = ob.getPhysicalRoot().zport.global_catalog
        except (KeyError, AttributeError):
            # Migrate script hasn't run yet; ignore indexing
            return
        device = component.device()
        if not device:
            # OS relation has already been broken; get by path
            path = component.getPrimaryPath()
            try:
                devpath = path[:path.index('devices')+2]
                device = component.unrestrictedTraverse(devpath)
            except ValueError:
                # We've done our best. Give up.
                return
        if device:
            oldpaths = devicePathsFromComponent(component)
            catalog.unindex_object_from_paths(device, oldpaths)


@adapter(ITreeSpanningComponent, IObjectMovedEvent)
def onTreeSpanningComponentAfterAddOrMove(ob, event):
    if not IObjectRemovedEvent.providedBy(event):
        component = ob
        try:
            catalog = ob.getPhysicalRoot().zport.global_catalog
        except (KeyError, AttributeError):
            # Migrate script hasn't run yet; ignore indexing
            return
        device = component.device()
        if not device:
            # OS relation has been broken or doesn't exist yet; get by path
            path = component.getPrimaryPath()
            try:
                devpath = path[:path.index('devices')+2]
                device = component.unrestrictedTraverse(devpath)
            except ValueError:
                # We've done our best. Give up.
                return
        if device:
            newpaths = devicePathsFromComponent(component)
            catalog.index_object_under_paths(device, newpaths)
