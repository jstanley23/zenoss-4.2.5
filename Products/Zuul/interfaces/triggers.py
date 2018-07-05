##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2009, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


from Products.Zuul.interfaces import IFacade, IInfo
from Products.Zuul.form import schema
from Products.Zuul.utils import ZuulMessageFactory as _t
from zope.component import getUtilitiesFor
from zope.schema.vocabulary import SimpleVocabulary
from Products.ZenModel.interfaces import IAction


class ITriggersFacade(IFacade):
    """
    When dealing with triggers, there are some variables named 'uuid' - these
    are different from uids - uuids are generated by str(uuid.uuid4()). uids
    are used as 'unique identifiers' - unique names and what not to be used by
    humans.
    """
    
    #triggers
    def getTriggers():
        """Get all existing triggers"""

    def getTriggerList():
        """
        Retrieve a list of all triggers regardless of permission.

        @return: Each element in this list will contain the id and uuid of the
                 trigger.
        @rtype: list
        """

    def addTrigger(newId):
        """ 
        Add a trigger given a name
        @return: guid of trigger created
        @rtype: str
        """

    def removeTrigger(uuid):
        """
        Remove a trigger by uuid.
        @return: the number of notifications that were updated to reflect the
        removal of this trigger.
        @rtype: int
        """

    def getTrigger(uuid):
        """Retrieve a trigger by uuid"""
        
    def updateTrigger(uuid, **data):
        """Given a uuid, update a trigger with **data."""
    
    def parseFilter(source):
        """
        Parse a source string for correctness and sanity.
        
        @param source: The source to be parsed and checked.
        @type source: string
        """
    
    # notification subscriptions
    def getNotificationTypes():
        pass
    
    def getNotifications():
        pass
    
    def addNotification(newId):
        pass
    
    def removeNotification(uid):
        pass
    
    def getNotification(uid):
        pass
        
    def updateNotification(**data):
        pass
    
    def getRecipientOptions():
        pass
    
    # subscription windows
    def getWindows(uid):
        pass
    
    def addWindow(contextUid, newId):
        pass
    
    def removeWindow(uid):
        pass
    
    def getWindow(uid):
        pass
    
    def updateWindow(**data):
        pass


def getNotificationBodyTypes():
    return ['html', 'text']

def getNotificationActionVocabulary():
    """
    This needs to inspect the interface stuff and figure out the providers for
    IAction.
    """
    utils = getUtilitiesFor(IAction)
    return [util.id for util in utils]

class INotificationSubscriptionInfo(IInfo):
    """
    Notification information regarding signals that occur as a result of an
    alert tripping a trigger.
    """
    newId = schema.TextLine(
        title=_t(u'newId'),
        xtype='idfield',
        description=_t(u'The name of this notification')
    )
    
    enabled = schema.Bool(title=_t(u'Enabled'))
    
    delay_seconds = schema.Int(title=_t(u'Delay (seconds)'))
    repeat_seconds = schema.Int(title=_t(u'Repeat (seconds)'))
    
    action = schema.Choice(
        title=_t(u'Action'),
        vocabulary=SimpleVocabulary.fromValues(getNotificationActionVocabulary())
    )

    
    # this is a list of the user/group/roles that have subscribed to this
    # notification.
    recipients = schema.List(title=_t(u'Subscribers'));

    globalRead = schema.Bool(title=_t(u'Global View'))
    globalWrite = schema.Bool(title=_t(u'Global Write'))
    globalManage = schema.Bool(title=_t(u'Global Manage Subscriptions'))

    userRead = schema.Bool(title=_t(u'Current User View'))
    userWrite = schema.Bool(title=_t(u'Current User Write'))
    userManage = schema.Bool(title=_t(u'Current User Manage Subscriptions'))
    

class INotificationWindowInfo(IInfo):
    """
    Interface for a notification subscription window.
    """
    newId = schema.TextLine(title=_t(u'Name'))
    
    enabled = schema.Bool(title=_t(u'Enabled'))
    
    start = schema.TextLine(
        title=_t(u'Start'),
        xtype="datefield"
    )
    
    repeat = schema.Choice(
        title=_t(u'Repeat'),
        vocabulary='schedulerepeatvocabulary'
    )
    
    duration = schema.TextLine(
        title=_t(u'Duration'),
        xtype="duration"
    )