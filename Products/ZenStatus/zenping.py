#! /usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2007, 2010, 2011, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


__doc__ = """zenping

Determines the availability of a IP addresses using ping (ICMP).

"""
import os.path
import re
import socket
import time
import logging
log = logging.getLogger("zen.zenping")

import Globals
import zope.interface
import zope.component

from Products import ZenStatus
from Products.ZenCollector import daemon 
from Products.ZenCollector import interfaces 
from Products.ZenCollector import tasks 
from Products.ZenUtils import IpUtil
from Products.ZenUtils.FileCache import FileCache

# perform some imports to allow twisted's PB to serialize these objects
from Products.ZenUtils.Utils import unused, zenPath
from Products.ZenCollector.services.config import DeviceProxy
from Products.ZenHub.services.PingPerformanceConfig import PingPerformanceConfig
unused(DeviceProxy)
unused(PingPerformanceConfig)

# define some constants strings
COLLECTOR_NAME = "zenping"
CONFIG_SERVICE = 'Products.ZenHub.services.PingPerformanceConfig'

class PerIpAddressTaskSplitter(tasks.SubConfigurationTaskSplitter):
    subconfigName = 'monitoredIps'

    def makeConfigKey(self, config, subconfig):
        return (config.id, subconfig.cycleTime, IpUtil.ipunwrap(subconfig.ip))

def getPingBackend():
    """
    Introspect the command line args to find --ping-backend because
    buildOptions doesn't get called until later.
    """
    import sys
    backend = 'nmap'
    try:
        for i, arg in enumerate(sys.argv):
            if arg == '--ping-backend':
                return sys.argv[i+1]
            elif arg.startswith('--ping-backend='):
                return arg.split('=', 1)[1]
    except IndexError:
        pass
    return backend


if __name__ == '__main__':

    # load zcml for the product
    import Products.ZenossStartup
    from Products.Five import zcml
    zcml.load_site()
    pingBackend = getPingBackend()
    
    myPreferences = zope.component.getUtility(ZenStatus.interfaces.IPingCollectionPreferences, pingBackend)
    myTaskFactory = zope.component.getUtility(ZenStatus.interfaces.IPingTaskFactory, pingBackend)
    myTaskSplitter = PerIpAddressTaskSplitter(myTaskFactory)
    myDaemon = daemon.CollectorDaemon(
        myPreferences,
        myTaskSplitter,
        stoppingCallback=myPreferences.preShutdown,
    )

    # add trace cache to preferences, so tasks can find it
    traceCachePath = zenPath('var', 'zenping', myDaemon.options.monitor)
    myPreferences.options.traceCache = FileCache(traceCachePath)

    myDaemon.run()
