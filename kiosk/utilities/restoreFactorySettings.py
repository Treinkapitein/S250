#!/usr/bin/python
"""
    Change Log:
        2012-08-09 Created by Kitch
            Restore Factory Settings


"""

import os
import sys
import random

USER_ROOT = "/home/mm/"
try:
    f = open("/etc/kioskhome")
    USER_ROOT = f.read().strip()
    f.close()
except:
    pass

PROXY_DIR = os.path.join(USER_ROOT, "kiosk", "mkc2", "proxy")
sys.path.append(PROXY_DIR)
from conn_proxy import ConnProxy
from tools import *

log = getLog("restore_factory_settings.log", "RESTORE_FACTORY_SETTINGS")



def restore():
    proxy = ConnProxy.getInstance()
    if isLocked():
        print "The kiosk is busy right now. Please retry later or not try any more."
    else:
        try:
            proxy.initDb("121")
            log.info("restored")
        except Exception, ex:
            log.error(str(ex))

if __name__ == "__main__":
    try:
        confirm = raw_input("This script is very dangerous! Are you sure to continue?(y/N)")
        if confirm.lower() == "y" or confirm.lower() == "yes":
            nums = range(1, 11)
            random.shuffle(nums)
            nums = nums[:3]
            result = raw_input("%s + %s + %s = " % tuple(nums))
            try:
                result = int(result)
            except:
                print "%s is not a digit." % result
                os.abort()
            if result != sum(nums):
                print "Wrong Result"
                os.abort()
        else:
            os.abort()

        restore()
    except Exception, ex:
        log.error(str(ex))
        print "Sorry! Something wrong. Please try again."
