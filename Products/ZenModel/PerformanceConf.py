#! /usr/bin/env python
##############################################################################
#
# Copyright (C) Zenoss, Inc. 2006-2009, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


__doc__ = """PerformanceConf
The configuration object for Performance servers
"""

import os
import zlib
import socket
from collections import namedtuple
from urllib import urlencode
from ipaddr import IPAddress
import logging
log = logging.getLogger('zen.PerformanceConf')

from Products.ZenUtils.IpUtil import ipwrap

try:
    from base64 import urlsafe_b64encode
    raise ImportError
except ImportError:


    def urlsafe_b64encode(s):
        """
        Encode a string so that it's okay to be used in an URL

        @param s: possibly unsafe string passed in by the user
        @type s: string
        @return: sanitized, url-safe version of the string
        @rtype: string
        """

        import base64
        s = base64.encodestring(s)
        s = s.replace('+', '-')
        s = s.replace('/', '_')
        s = s.replace('\n', '')
        return s


import xmlrpclib
from AccessControl import ClassSecurityInfo
from AccessControl import Permissions as permissions
from Globals import DTMLFile
from Globals import InitializeClass
from Monitor import Monitor
from Products.Jobber.jobs import SubprocessJob
from Products.ZenRelations.RelSchema import ToMany, ToOne
from Products.ZenUtils.Utils import basicAuthUrl, zenPath, binPath
from Products.ZenUtils.Utils import unused
from Products.ZenUtils.Utils import isXmlRpc
from Products.ZenUtils.Utils import executeCommand
from Products.ZenUtils.Utils import addXmlServerTimeout
from Products.ZenUtils.GlobalConfig import getGlobalConfiguration
from Products.ZenModel.ZDeviceLoader import DeviceCreationJob
from Products.ZenWidgets import messaging
from Products.ZenMessaging.audit import audit
from StatusColor import StatusColor

SUMMARY_COLLECTOR_REQUEST_TIMEOUT = float( getGlobalConfiguration().get('collectorRequestTimeout', 5) )

PERF_ROOT = None

"""
Prefix for renderurl if zenoss is running a reverse proxy on the master. Prefix will be stripped when appropriate and
requests for data will be made to the proxy server when appropriate.  Render url should be of the form "rev_proxy:/<path>" eg:
"rev_proxy:/mypath" where /mypath should be proxied to an appropriate zenrender/renderserver by the installed proxy server
"""
REVERSE_PROXY = "rev_proxy:"

ProxyConfig = namedtuple('ProxyConfig', ['useSSL', 'port'])


def performancePath(target):
    """
    Return the base directory where RRD performance files are kept.

    @param target: path to performance file
    @type target: string
    @return: sanitized path to performance file
    @rtype: string
    """
    global PERF_ROOT
    if PERF_ROOT is None:
        PERF_ROOT = zenPath('perf')
    if target.startswith('/'):
        target = target[1:]
    return os.path.join(PERF_ROOT, target)


def manage_addPerformanceConf(context, id, title=None, REQUEST=None,):
    """
    Make a device class

    @param context: Where you are in the Zope acquisition path
    @type context: Zope context object
    @param id: unique identifier
    @type id: string
    @param title: user readable label (unused)
    @type title: string
    @param REQUEST: Zope REQUEST object
    @type REQUEST: Zope REQUEST object
    @return:
    @rtype:
    """
    unused(title)
    dc = PerformanceConf(id)
    context._setObject(id, dc)

    if REQUEST is not None:
        REQUEST['RESPONSE'].redirect(context.absolute_url()
                 + '/manage_main')


addPerformanceConf = DTMLFile('dtml/addPerformanceConf', globals())


class PerformanceConf(Monitor, StatusColor):
    """
    Configuration for Performance servers
    """
    portal_type = meta_type = 'PerformanceConf'

    monitorRootName = 'Performance'

    security = ClassSecurityInfo()
    security.setDefaultAccess('allow')

    eventlogCycleInterval = 60
    perfsnmpCycleInterval = 300
    processCycleInterval = 180
    statusCycleInterval = 60
    winCycleInterval = 60
    wmibatchSize = 10
    wmiqueryTimeout = 100
    configCycleInterval = 6 * 60

    zenProcessParallelJobs = 10

    pingTimeOut = 1.5
    pingTries = 2
    pingChunk = 75
    pingCycleInterval = 60
    maxPingFailures = 1440

    modelerCycleInterval = 720

    renderurl = '/zport/RenderServer'
    renderuser = ''
    renderpass = ''

    discoveryNetworks = ()

    # make the default rrdfile size smaller
    # we need the space to live within the disk cache
    defaultRRDCreateCommand = (
        'RRA:AVERAGE:0.5:1:600',   # every 5 mins for 2 days
        'RRA:AVERAGE:0.5:6:600',   # every 30 mins for 12 days
        'RRA:AVERAGE:0.5:24:600',  # every 2 hours for 50 days
        'RRA:AVERAGE:0.5:288:600', # every day for 600 days
        'RRA:MAX:0.5:6:600',
        'RRA:MAX:0.5:24:600',
        'RRA:MAX:0.5:288:600',
        )

    _properties = (
        {'id': 'eventlogCycleInterval', 'type': 'int', 'mode': 'w'},
        {'id': 'processCycleInterval', 'type': 'int', 'mode': 'w'},
        {'id': 'statusCycleInterval', 'type': 'int', 'mode': 'w'},
        {'id': 'winCycleInterval', 'type': 'int', 'mode': 'w'},
        {'id': 'wmibatchSize', 'type': 'int', 'mode': 'w',
         'description':"Number of data objects to retrieve in a single WMI query",},
        {'id': 'wmiqueryTimeout', 'type': 'int', 'mode': 'w',
         'description':"Number of milliseconds to wait for WMI query to respond",},
        {'id': 'configCycleInterval', 'type': 'int', 'mode': 'w'},
        {'id': 'renderurl', 'type': 'string', 'mode': 'w'},
        {'id': 'renderuser', 'type': 'string', 'mode': 'w'},
        {'id': 'renderpass', 'type': 'string', 'mode': 'w'},
        {'id': 'defaultRRDCreateCommand', 'type': 'lines', 'mode': 'w'
         },
        {'id': 'zenProcessParallelJobs', 'type': 'int', 'mode': 'w'},
        {'id': 'pingTimeOut', 'type': 'float', 'mode': 'w'},
        {'id': 'pingTries', 'type': 'int', 'mode': 'w'},
        {'id': 'pingChunk', 'type': 'int', 'mode': 'w'},
        {'id': 'pingCycleInterval', 'type': 'int', 'mode': 'w'},
        {'id': 'maxPingFailures', 'type': 'int', 'mode': 'w'},
        {'id': 'modelerCycleInterval', 'type': 'int', 'mode': 'w'},
        {'id': 'discoveryNetworks', 'type': 'lines', 'mode': 'w'},
        )

    _relations = Monitor._relations + (
        ("devices", ToMany(ToOne,"Products.ZenModel.Device","perfServer")),
        )

    # Screen action bindings (and tab definitions)
    factory_type_information = (
        {
            'immediate_view' : 'viewPerformanceConfOverview',
            'actions'        :
            (
                { 'id'            : 'overview'
                , 'name'          : 'Overview'
                , 'action'        : 'viewPerformanceConfOverview'
                , 'permissions'   : (
                  permissions.view, )
                },
                { 'id'            : 'edit'
                , 'name'          : 'Edit'
                , 'action'        : 'editPerformanceConf'
                , 'permissions'   : ("Manage DMD",)
                },
                { 'id'            : 'performance'
                , 'name'          : 'Performance'
                , 'action'        : 'viewDaemonPerformance'
                , 'permissions'   : (permissions.view,)
                },
            )
          },
        )


    security.declareProtected('View', 'getDefaultRRDCreateCommand')
    def getDefaultRRDCreateCommand(self):
        """
        Get the default RRD Create Command, as a string.
        For example:
        '''RRA:AVERAGE:0.5:1:600
        RRA:AVERAGE:0.5:6:600
        RRA:AVERAGE:0.5:24:600
        RRA:AVERAGE:0.5:288:600
        RRA:MAX:0.5:288:600'''

        @return: RRD create command
        @rtype: string
        """
        return '\n'.join(self.defaultRRDCreateCommand)


    def findDevice(self, deviceName):
        """
        Return the object given the name

        @param deviceName: Name of a device
        @type deviceName: string
        @return: device corresponding to the name, or None
        @rtype: device object
        """
        brains = self.dmd.Devices._findDevice(deviceName)
        if brains:
            return brains[0].getObject()


    def getNetworkRoot(self, version=None):
        """
        Get the root of the Network object in the DMD

        @return: base DMD Network object
        @rtype: Network object
        """
        return self.dmd.Networks.getNetworkRoot(version)


    def buildGraphUrlFromCommands(self, gopts, drange):
        """
        Return an URL for the given graph options and date range

        @param gopts: graph options
        @type gopts: string
        @param drange: time range to use
        @type drange: string
        @return: URL to a graphic
        @rtype: string
        """
        newOpts = []
        width = 0
        for o in gopts:
            if o.startswith('--width'):
                width = o.split('=')[1].strip()
                continue
            newOpts.append(o)

        encodedOpts = urlsafe_b64encode(
            zlib.compress('|'.join(newOpts), 9))
        params = {
            'gopts': encodedOpts,
            'drange': drange,
            'width': width,
            }

        url = self._getSanitizedRenderURL()
        if RenderURLUtil(self.renderurl).proxiedByZenoss():
            params['remoteHost'] = self.getRemoteRenderUrl()
            url = '/zport/RenderServer'

        url = '%s/render?%s' % (url, urlencode(params),)
        return url

    def _getSanitizedRenderURL(self):
        """
        remove any keywords/directives from renderurl.
        example is "proxy://host:8091" is changed to "http://host:8091"
        """
        return RenderURLUtil(self.renderurl).getSanitizedRenderURL()

    def performanceGraphUrl(self, context, targetpath, targettype, view, drange):
        """
        Set the full path of the target and send to view

        @param context: Where you are in the Zope acquisition path
        @type context: Zope context object
        @param targetpath: device path of performance metric
        @type targetpath: string
        @param targettype: unused
        @type targettype: string
        @param view: view object
        @type view: Zope object
        @param drange: date range
        @type drange: string
        @return: URL to graph
        @rtype: string
        """
        unused(targettype)
        targetpath = performancePath(targetpath)
        gopts = view.getGraphCmds(context, targetpath)
        return self.buildGraphUrlFromCommands(gopts, drange)


    def getRemoteRenderUrl(self):
        """
        return the full render url with http protocol prepended if the renderserver is remote.
        Return empty string otherwise
        """
        return RenderURLUtil(self.renderurl).getRemoteRenderUrl()

    def _get_render_server(self, allow_none=False,
                           timeout=None):
        if self.getRemoteRenderUrl():
            renderurl = self.getRemoteRenderUrl()
            # Going through the hub or directly to zenrender
            log.info("Remote renderserver at %s", renderurl)
            url = basicAuthUrl(str(self.renderuser),
                               str(self.renderpass), renderurl)
            server = xmlrpclib.Server(url, allow_none=allow_none)
            if timeout is not None:
                addXmlServerTimeout( server, timeout )
        else:
            if not self.renderurl:
                raise KeyError("No render URL is defined")
            server = self.getObjByPath(self.renderurl)
        return server

    def performanceCustomSummary(self, gopts,
                                 timeout=SUMMARY_COLLECTOR_REQUEST_TIMEOUT ):
        """
        Fill out full path for custom gopts and call to server

        @param gopts: graph options
        @type gopts: string
        @param timeout: the connection timeout in seconds. By default the value
                       is 5s or the value for the global property 'collectorRequestTimeout'
                       None translates to the global default
                       socket timeout. 0 would translate to 'never timeout'.
        @type timeout: float
        @return: URL
        @rtype: string
        """
        gopts = self._fullPerformancePath(gopts)
        server = self._get_render_server(timeout=timeout)
        try:
            value = server.summary(gopts)
            return value
        except IOError, e:
            log.error( "Error collecting performance summary from collector %s: %s",
                       self.id, e )
            log.debug( "Error collecting with params %s", gopts )

    def fetchValues(self, paths, cf, resolution, start, end="",
                    timeout=None):
        """
        Return values

        NOTE: This is called for bulk metric fetch which
              needs a more lenient timeout than performanceCustomSummary.

        @param paths: paths to performance metrics
        @type paths: list
        @param cf: RRD CF
        @type cf: string
        @param resolution: resolution
        @type resolution: string
        @param start: start time
        @type start: string
        @param end: end time
        @type end: string
        @param timeout: the connection timeout in seconds. By default the value
                       is None which translates to the global default
                       socket timeout. 0 would translate to 'never timeout'.
        @type timeout: float
        @return: values
        @rtype: list
        """
        server = self._get_render_server(allow_none=True, timeout=timeout)
        return server.fetchValues(map(performancePath, paths), cf,
                                  resolution, start, end)


    def currentValues(self, paths, timeout=SUMMARY_COLLECTOR_REQUEST_TIMEOUT):
        """
        Fill out full path and call to server

        NOTE: This call should be deprecated. The only internal clients
              are now defunct.

        @param paths: paths to performance metrics
        @type paths: list
        @param timeout: the connection timeout in seconds. By default the value
                       is 5s or the value for the global property 'collectorRequestTimeout'
                       None translates to the global default
                       socket timeout. 0 would translate to 'never timeout'.
        @type timeout: float
        @return: values
        @rtype: list
        """
        server = self._get_render_server(timeout=timeout)
        return server.currentValues(map(performancePath, paths))


    def _fullPerformancePath(self, gopts):
        """
        Add full path to a list of custom graph options

        @param gopts: graph options
        @type gopts: string
        @return: full path + graph options
        @rtype: string
        """
        for i in range(len(gopts)):
            opt = gopts[i]
            if opt.find('DEF') == 0:
                opt = opt.split(':')
                (var, file) = opt[1].split('=')
                file = performancePath(file)
                opt[1] = '%s=%s' % (var, file)
                opt = ':'.join(opt)
                gopts[i] = opt
        return gopts


    security.declareProtected('View', 'performanceDeviceList')
    def performanceDeviceList(self, force=True):
        """
        Return a list of URLs that point to our managed devices

        @param force: unused
        @type force: boolean
        @return: list of device objects
        @rtype: list
        """
        unused(force)
        devlist = []
        for dev in self.devices():
            dev = dev.primaryAq()
            if not dev.pastSnmpMaxFailures() and dev.monitorDevice():
                devlist.append(dev.getPrimaryUrlPath(full=True))
        return devlist


    security.declareProtected('View', 'performanceDataSources')
    def performanceDataSources(self):
        """
        Return a string that has all the definitions for the performance DS's.

        @return: list of Data Sources
        @rtype: string
        """
        dses = []
        oidtmpl = 'OID %s %s'
        dstmpl = """datasource %s
        rrd-ds-type = %s
        ds-source = snmp://%%snmp%%/%s%s
        """
        rrdconfig = self.getDmdRoot('Devices').rrdconfig
        for ds in rrdconfig.objectValues(spec='RRDDataSource'):
            if ds.isrow:
                inst = '.%inst%'
            else:
                inst = ''
            dses.append(oidtmpl % (ds.getName(), ds.oid))
            dses.append(dstmpl % (ds.getName(), ds.rrdtype,
                        ds.getName(), inst))
        return '\n'.join(dses)

    def deleteRRDFiles(self, device, datasource=None, datapoint=None):
        """
        Remove RRD performance data files

        @param device: Name of a device or entry in DMD
        @type device: string
        @param datasource: datasource name
        @type datasource: string
        @param datapoint: datapoint name
        @type datapoint: string
        """
        remoteUrl = None
        renderurl = self.getRemoteRenderUrl() or self._getSanitizedRenderURL()
        if renderurl.startswith('http'):
            if datapoint:
                remoteUrl = '%s/deleteRRDFiles?device=%s&datapoint=%s' % (
                     renderurl, device, datapoint)
            elif datasource:
                remoteUrl = '%s/deleteRRDFiles?device=%s&datasource=%s' % (
                     renderurl, device, datasource)
            else:
                remoteUrl = '%s/deleteRRDFiles?device=%s' % (
                     renderurl, device)
        rs = self.getDmd().getParentNode().RenderServer
        rs.deleteRRDFiles(device, datasource, datapoint, remoteUrl)


    def setPerformanceMonitor(self, performanceMonitor=None, deviceNames=None, REQUEST=None):
        """
        Provide a method to set performance monitor from any organizer

        @param performanceMonitor: DMD object that collects from a device
        @type performanceMonitor: DMD object
        @param deviceNames: list of device names
        @type deviceNames: list
        @param REQUEST: Zope REQUEST object
        @type REQUEST: Zope REQUEST object
        """
        if not performanceMonitor:
            if REQUEST:
                messaging.IMessageSender(self).sendToBrowser('Error',
                        'No monitor was selected.',
                        priority=messaging.WARNING)
            return self.callZenScreen(REQUEST)
        if deviceNames is None:
            if REQUEST:
                messaging.IMessageSender(self).sendToBrowser('Error',
                        'No devices were selected.',
                        priority=messaging.WARNING)
            return self.callZenScreen(REQUEST)
        for devName in deviceNames:
            dev = self.devices._getOb(devName)
            dev = dev.primaryAq()
            dev.setPerformanceMonitor(performanceMonitor)
            if REQUEST:
                audit('UI.Device.ChangeCollector', dev, collector=performanceMonitor)
        if REQUEST:
            messaging.IMessageSender(self).sendToBrowser('Monitor Set',
                    'Performance monitor was set to %s.'
                     % performanceMonitor)
            if REQUEST.has_key('oneKeyValueSoInstanceIsntEmptyAndEvalToFalse'):
                return REQUEST['message']
            else:
                return self.callZenScreen(REQUEST)


    security.declareProtected('View', 'getPingDevices')
    def getPingDevices(self):
        """
        Return devices associated with this monitor configuration.

        @return: list of devices for this monitor
        @rtype: list
        """
        devices = []
        for dev in self.devices.objectValuesAll():
            dev = dev.primaryAq()
            if dev.monitorDevice() and not dev.zPingMonitorIgnore:
                devices.append(dev)
        return devices

    def addDeviceCreationJob(self, deviceName, devicePath, title=None,
                             discoverProto="none", manageIp="",
                             performanceMonitor='localhost',
                             rackSlot=0, productionState=1000, comments="",
                             hwManufacturer="", hwProductName="",
                             osManufacturer="", osProductName="", priority = 3,
                             locationPath="", systemPaths=[], groupPaths=[],
                             tag="", serialNumber="", zProperties={}, cProperties={},):

        # Check to see if we got passed in an IPv6 address
        try:
            IPAddress(deviceName)
            if not title:
                title = deviceName
            deviceName = ipwrap(deviceName)
        except ValueError:
            pass

        zendiscCmd = self._getZenDiscCommand(deviceName, devicePath,
                                             performanceMonitor, productionState)

        jobStatus = self.dmd.JobManager.addJob(DeviceCreationJob,
                description="Add device %s" % deviceName,
                kwargs=dict(
                    deviceName=deviceName,
                    devicePath=devicePath,
                    title=title,
                    discoverProto=discoverProto,
                    manageIp=manageIp,
                    performanceMonitor=performanceMonitor,
                    rackSlot=rackSlot,
                    productionState=productionState,
                    comments=comments,
                    hwManufacturer=hwManufacturer,
                    hwProductName=hwProductName,
                    osManufacturer=osManufacturer,
                    osProductName=osProductName,
                    priority=priority,
                    tag=tag,
                    serialNumber=serialNumber,
                    locationPath=locationPath,
                    systemPaths=systemPaths,
                    groupPaths=groupPaths,
                    zProperties=zProperties,
                    cProperties=cProperties,
                    zendiscCmd=zendiscCmd))
        return jobStatus

    def _executeZenDiscCommand(self, deviceName, devicePath= "/Discovered",
                               performanceMonitor="localhost", productionState=1000,
                               background=False, REQUEST=None):
        """
        Execute zendisc on the new device and return result

        @param deviceName: Name of a device
        @type deviceName: string
        @param devicePath: DMD path to create the new device in
        @type devicePath: string
        @param performanceMonitor: DMD object that collects from a device
        @type performanceMonitor: DMD object
        @param background: should command be scheduled job?
        @type background: boolean
        @param REQUEST: Zope REQUEST object
        @type REQUEST: Zope REQUEST object
        @return:
        @rtype:
        """
        zendiscCmd = self._getZenDiscCommand(deviceName, devicePath,
                                             performanceMonitor,
                                             productionState, REQUEST)
        if background:
            log.info('queued job: %s', " ".join(zendiscCmd))
            result = self.dmd.JobManager.addJob(SubprocessJob,
                description="Discover and model device %s" % deviceName,
                args=(zendiscCmd,))
        else:
            result = executeCommand(zendiscCmd, REQUEST)
        return result

    def _getZenDiscCommand(self, deviceName, devicePath,
                           performanceMonitor, productionState, REQUEST=None):

        zm = binPath('zendisc')
        zendiscCmd = [zm]
        zendiscOptions = ['run', '--now','-d', deviceName,
                     '--monitor', performanceMonitor,
                     '--deviceclass', devicePath,
                     '--prod_state', str(productionState)]
        if REQUEST:
            zendiscOptions.append("--weblog")
        zendiscCmd.extend(zendiscOptions)
        log.info('local zendiscCmd is "%s"' % ' '.join(zendiscCmd))
        return zendiscCmd

    def getCollectorCommand(self, command):
        return [binPath(command)]

    def executeCollectorCommand(self, command, args, REQUEST=None, write=None):
        """
        Executes the collector based daemon command.

        @param command: the collector daemon to run, should not include path
        @type command: string
        @param args: list of arguments for the command
        @type args: list of strings
        @param REQUEST: Zope REQUEST object
        @type REQUEST: Zope REQUEST object
        @return: result of the command
        @rtype: string
        """
        cmd = binPath(command)
        daemonCmd = [cmd]
        daemonCmd.extend(args)
        result = executeCommand(daemonCmd, REQUEST, write)
        return result


    def collectDevice(self, device=None, setlog=True, REQUEST=None,
        generateEvents=False, background=False, write=None):
        """
        Collect the configuration of this device AKA Model Device

        @permission: ZEN_MANAGE_DEVICE
        @param device: Name of a device or entry in DMD
        @type device: string
        @param setlog: If true, set up the output log of this process
        @type setlog: boolean
        @param REQUEST: Zope REQUEST object
        @type REQUEST: Zope REQUEST object
        @param generateEvents: unused
        @type generateEvents: string
        """
        xmlrpc = isXmlRpc(REQUEST)
        zenmodelerOpts = ['run', '--now', '--monitor', self.id, '-d', device.id]
        result = self._executeZenModelerCommand(zenmodelerOpts, background,
                                                REQUEST, write)
        if result and xmlrpc:
            return result
        log.info('configuration collected')

        if xmlrpc:
            return 0


    def _executeZenModelerCommand(self, zenmodelerOpts, background=False,
                                  REQUEST=None, write=None):
        """
        Execute zenmodeler and return result

        @param zenmodelerOpts: zenmodeler command-line options
        @type zenmodelerOpts: string
        @param REQUEST: Zope REQUEST object
        @type REQUEST: Zope REQUEST object
        @return: results of command
        @rtype: string
        """
        zm = binPath('zenmodeler')
        zenmodelerCmd = [zm]
        zenmodelerCmd.extend(zenmodelerOpts)
        if background:
            log.info('queued job: %s', " ".join(zenmodelerCmd))
            result = self.dmd.JobManager.addJob(SubprocessJob,
                description="Run zenmodeler %s" % ' '.join(zenmodelerOpts),
                args=(zenmodelerCmd,))
        else:
            result = executeCommand(zenmodelerCmd, REQUEST, write)
        return result

class RenderURLUtil(object):

    def __init__(self, renderurl):
        self._renderurl = renderurl

    def getSanitizedRenderURL(self):
        """
        remove any keywords/directives from renderurl.
        example is "proxy://host:8091" is changed to "http://host:8091"
        """
        renderurl = self._renderurl
        if renderurl.startswith('proxy'):
            renderurl = renderurl.replace('proxy', 'http')
        elif renderurl.startswith(REVERSE_PROXY):
            renderurl = renderurl.replace(REVERSE_PROXY, '', 1)
        return renderurl

    def getRemoteRenderUrl(self):
            """
            return the full render url with http protocol prepended if the renderserver is remote.
            Return empty string otherwise
            """
            renderurl = str(self._renderurl)
            if renderurl.startswith('proxy'):
                renderurl = renderurl.replace('proxy', 'http')
            elif renderurl.startswith(REVERSE_PROXY):
                renderurl =  self._get_reverseproxy_renderurl()
            else:
                # lookup utilities from zenpacks
                if renderurl.startswith('/remote-collector/'):
                    renderurl =  self._get_reverseproxy_renderurl(force=True)

            if renderurl.lower().startswith('http'):
                return renderurl
            return ''

    def proxiedByZenoss(self):
        """
        Should the render request be proxied by zenoss/zope
        """
        return self._renderurl.startswith('proxy')

    def _get_reverseproxy_renderurl(self, force=False):
        # DistributedCollector + WebScale scenario
        renderurl = self._renderurl
        if not force and not renderurl.startswith(REVERSE_PROXY):
            raise Exception("Renderurl, %s, should start with %s to be proxied", renderurl, REVERSE_PROXY)
        config = self._get_reverseproxy_config()
        kwargs = dict(fqdn=socket.getfqdn(),
                      port=config.port,
                      protocol= 'https' if config.useSSL else 'http',
                      path=str(self.getSanitizedRenderURL()).strip("/") + "/")
        # take into account https
        return '{protocol}://{fqdn}:{port}/{path}'.format(**kwargs)

    def _get_reverseproxy_config(self):
        use_ssl = False
        http_port = 8080
        ssl_port = 443
        conf_path = zenPath("etc", "zenwebserver.conf")
        if not os.path.exists(conf_path):
            return http_port
        with open(conf_path) as file_:
            for line in (l.strip() for l in file_):
                if line and not line.startswith('#'):
                    key, val = line.split(' ', 1)
                    if key == "useSSL":
                        use_ssl = val.lower() == 'true'
                    elif key == "httpPort":
                        http_port = int(val.strip())
                    elif key == "sslPort":
                        ssl_port = int(val.strip())
        return ProxyConfig(useSSL=use_ssl,
                           port= ssl_port if use_ssl else http_port)


InitializeClass(PerformanceConf)
