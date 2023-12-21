#!/usr/bin/python
"""
    Change Log:
        2009-08-18 Created by Kitch
            clear slot(s)

    e.g.
    cancel one slot: ./cancelBadSlot.py -s 102
    cancel some slots: ./cancelBadSlot.py -s 102,103,256
    cancel all: ./cancelBadSlot.py --all|-a
    help: ./cancelBadSlot.py --help|-h

"""

__VERSION__ = '0.5.0'

import os
import sys
import shutil

USER_ROOT = "/home/mm/"
try:
    f = open("/etc/kioskhome")
    USER_ROOT = f.read().strip()
    f.close()
except:
    pass

PROXY_DIR = os.path.join(USER_ROOT, "kiosk", "mkc2", "proxy")
sys.path.append(PROXY_DIR)
import config
from conn_proxy import ConnProxy
from tools import getCurTime, getLog

log = getLog("cancelBadSlot.log", "CANCEL_BAD_SLOT")

def cancelBadSlots(slots=None):
    if slots:
        print "Processing..."
        proxy = ConnProxy.getInstance()

        if str(slots).lower() == "all":
            sql = "SELECT id, rfid FROM slots WHERE state='bad';"
        else:
            # get slots info
            if len(slots) == 1:
                strSlots = "('" + str(slots[0]) + "')"
            else:
                strSlots = str(tuple(slots))
            sql = "SELECT id, rfid FROM slots WHERE state='bad' AND id in %s;" % strSlots
        rows = proxy.mkcDb.query(sql)
        try:
            if rows:
                # backup mkc.db
                bakFileName = config.MKC_DB_PATH + ".bak." + getCurTime("%Y-%m-%d")
                if not os.path.exists(bakFileName):
                    shutil.copy(config.MKC_DB_PATH, bakFileName)
                print "Backing up DB ...... OK"
                
                slotList = []
                pList = []
                for slotId, rfid in rows:
                    slotList.append(str(slotId))

                    # clear local db
                    if rfid:
                        state = "occupied"
                    else:
                        state = "empty"
                    p = (state, slotId)
                    pList.append(p)
                    
                sql = "UPDATE slots SET state=? WHERE id=?;"
                proxy.mkcDb.updateMany(sql, pList)
        
                # sync to dbnode
                params = {}
                params["p_list"] = pList
                proxy.syncData("dbSyncCancelBadSlots", params)
                print "Cleaning local DB ..... OK"
                print "Push the changes into sync queue ...... OK"
                print "All Done."
                print "The server side should reflect the changes in less than 15 minutes."
                log.info("cancel bad slot(s): %s" % ", ".join(slotList))
            else:
                print "No bad slots."
        except Exception, ex:
            log.error("cancelBadSlots: %s" % str(ex))
            raise



if __name__ == "__main__":
    try:
        slots = None
        if len(sys.argv) == 1:
            print "Usage: ./cancelBadSlot.py [-s slot_ID(_List)] [--all|-a] [--help|-h]"
        else:
            if sys.argv[1].lower() == "-v" or sys.argv[1].lower() == "--version":
                print "VERSION:", __VERSION__
            elif sys.argv[1].lower() == "-a" or sys.argv[1].lower() == "--all":
                cusInput = raw_input("Are you sure to cancel all bad slots? (y/N):")
                if cusInput.lower() == "y" or cusInput.lower() == "yes":
                    slots = "all"
                else:
                    os.abort()
            elif sys.argv[1].lower() == "-s" or sys.argv[1].lower() == "--slots":
                slotList = range(101, 841)
                if len(sys.argv) == 2:
                    cusInput = raw_input("Please input the bad slot(s) to be canceled (SLOT_ID[,SLOT_ID,SLOT_ID,...]):")
                    slots = cusInput.split(",")
                else:
                    slots = sys.argv[2].split(",")
    
                # check the slots
                for slot in slots:
                    try:
                        if slot:
                            slot = int(slot.strip())
                    except:
                        print "Detected invalid slot %s." % slot
                        os.abort()
                    if slot and slot not in slotList:
                        print "Detected invalid slot %s." % slot
                        os.abort()
            elif sys.argv[1].lower() == "-h" or sys.argv[1].lower() == "--help":
                print """e.g.
cancel one slot: ./cancelBadSlot.py -s SLOT_ID
cancel some slots: ./cancelBadSlot.py -s SLOT_ID,SLOT_ID,SLOT_ID (slots list without blank)
cancel all: ./cancelBadSlot.py --all|-a
help: ./cancelBadSlot.py --help|-h"""
            else:
                print "Usage: ./cancelBadSlot.py [-s slot_ID(_List)] [--all|-a] [--help|-h]"
    
        cancelBadSlots(slots)
    except Exception, ex:
        log.error(str(ex))
        print "Sorry! Something wrong. Please try again."
