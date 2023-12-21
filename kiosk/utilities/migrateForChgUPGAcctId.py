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
import traceback

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

log = getLog("migrate_mkc_db.log", "UPG_ACCT_ID")

def migrateForChgUPGAcctId():
    status = 0
    proxy = UPGProxy.getInstance()
    if isLocked():
        print "The kiosk is busy right now. Please retry later."
    else:
        # get the changed upg account id
        acctId = proxy.getUpgAcctId()
        if not acctId:
            print "You have NOT set any UPG account ID for the kiosk."
        else:
            try:
                trs = []
                # update transactions
                sql = "UPDATE transactions SET upg_account_id=:upg_acct_id " \
                      "WHERE upg_account_id!=:upg_acct_id AND state!='closed';"
                trs.append({"sql": sql, "params":{'upg_acct_id': acctId}})
                # update declinedq
                sql = "UPDATE declinedq SET acct_id=:upg_acct_id WHERE " \
                      "transaction_id IN (SELECT id FROM transactions WHERE " \
                      "upg_account_id=:upg_acct_id AND state!='closed');"
                trs.append({"sql": sql, "params":{'upg_acct_id': acctId}})
                # update postauthq
                sql = "UPDATE postauthq SET acct_id=:upg_acct_id WHERE " \
                      "transaction_id IN (SELECT id FROM transactions WHERE " \
                      "upg_account_id=:upg_acct_id AND state!='closed');"
                trs.append({"sql": sql, "params":{'upg_acct_id': acctId}})
                # update upg
                sql = "UPDATE upg SET acct_id=:upg_acct_id WHERE " \
                      "id IN (SELECT upg_id FROM transactions WHERE " \
                      "upg_account_id=:upg_acct_id AND state!='closed');"
                trs.append({"sql": sql, "params":{'upg_acct_id': acctId}})
                proxy.mkcDb.updateTrs2(trs)

                if resyncDb():
                    status = 1
            except Exception, ex:
                log.error("migrateForChgUPGAcctId: %s" % traceback.format_exc())
            if status != 1:
                print "Migrate failed, please try again."
            else:
                print "Migrate successfully."

def resyncDb():
    status = 0
    proxy = ConnProxy.getInstance()
    if isLocked():
        print "The kiosk is busy right now. Please retry later."
    else:
        try:
            # update all sync state to 1
            print "Updating local db..."
            sql = "UPDATE db_sync SET state=1 WHERE function_name<>'setMonthlySubscptForKiosk';"
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
                status = 1
            elif result["result"] == "timeout":
                print "Connection timed out. Please try again."
            else:
                print "Something wrong. Please try again."
                log.error("remote: %s" % result["zdata"])
        except Exception, ex:
            log.error("resyncDb: %s" % str(ex))
        return status

if __name__ == "__main__":
    migrateForChgUPGAcctId()
