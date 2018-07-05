##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2007, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


import Migrate

class DeviceTemplatesProperty(Migrate.Step):
    version = Migrate.Version(2, 0, 0)

    def cutover(self, dmd):
        if not dmd.Devices.hasProperty("zDeviceTemplates"):
            dmd.Devices._setProperty("zDeviceTemplates", ["Device"],
                                     type="lines")

DeviceTemplatesProperty()
