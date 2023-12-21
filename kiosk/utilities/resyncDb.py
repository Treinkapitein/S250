#!/usr/bin/python
"""
    Change Log:
        2009-11-26 Modified by Kitch
            add need sync function: setMonthlySubscptForKiosk
        2009-08-04 Created by Kitch
            resync the mkc.db

"""

__VERSION__ = '0.5.2'

import os
import sys

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
from upg_proxy import UPGProxy
from tools import *

log = getLog("resync_db.log", "RESYNC_DB")

def resyncDb():
    proxy = ConnProxy.getInstance()
    if isLocked():
        print "The kiosk is busy right now. Please retry later."
    else:
        try:
            # update all sync state to 1
            print "Updating local db..."
            sql = "UPDATE db_sync SET state=1 WHERE function_name not in ('setMonthlySubscptForKiosk', 'dbSyncAIStatus');"
            proxy.syncDb.update(sql)
            
            # resync db
            print "Syncing db to server... "
            print "It will take a bit long time. Please Wait..."
            result = proxy.getRemoteData("resyncDb", {}, 180)
            if result["result"] == "ok":
                # rm sync log of upg service
                ret = UPGProxy.getInstance().getRemoteData("rmSyncLogForResync", {}, 180)
                if ret["result"] != "ok":
                    log.error("remote(upg): %s" % ret["zdata"])
                msg = "Re-sync db done."
                print msg
                log.info(msg)
            elif result["result"] == "timeout":
                print "Connection timed out. Please try again."
            else:
                print "Something wrong. Please try again."
                log.error("remote: %s" % result["zdata"])
        except Exception, ex:
            log.error(str(ex))
    
if __name__ == "__main__":
    resyncDb()
