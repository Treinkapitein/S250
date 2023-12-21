#!/usr/bin/python
"""
    Change Log:
        2009-12-15 Modified by Kitch
            add confirmation "I_confirm_there_is_no_disc_in_the_slot"
        2009-03-03 Modified by Kitch
            move to ~/utilities/
        2008-12-25 Created by Kitch
            clear slot(s)

    e.g.
    clear one slot: ./clear_slot.py -s 102
    clear some slots: ./clear_slot.py -s 102,103,256
    clear all: ./clear_slot.py --all|-a
    help: ./clear_slot.py --help|-h

"""

__VERSION__ = '0.0.2'

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

log = getLog("clear_slot.log", "CLEAR_SLOT")

def clearSlots(slots=None):
    if slots:
        print "Processing..."
        proxy = ConnProxy.getInstance()

        # backup mkc.db
        bakFileName = config.MKC_DB_PATH + ".bak." + getCurTime("%Y-%m-%d")
        if not os.path.exists(bakFileName):
            shutil.copy(config.MKC_DB_PATH, bakFileName)
        print "Backing up DB ...... OK"

        if str(slots).lower() == "all":
            sql = "SELECT S.id, R.rfid, R.upc, R.title FROM slots AS S, rfids AS R " \
                  "WHERE S.rfid=R.rfid;"
        else:
            # get slots info
            if len(slots) == 1:
                strSlots = "('" + str(slots[0]) + "')"
            else:
                strSlots = str(tuple(slots))
            sql = "SELECT S.id, R.rfid, R.upc, R.title FROM slots AS S, rfids AS R " \
                  "WHERE S.rfid=R.rfid AND S.id in %s;" % strSlots
        rows = proxy.mkcDb.query(sql)
        rfidList = []
        eventIdList = []
        try:
            for slotId, rfid, upc, title in rows:
                rfidList.append(rfid)
                eventId = proxy.logEvent(category="operation", action="clear", \
                                         data1=slotId, data2=rfid, data3=upc, data4=title)
                eventIdList.append(eventId)

            # clear local db
            if rfidList:
                sqlList = []
                if len(rfidList) == 1:
                    strRfidList = "('" + str(rfidList[0]) + "')"
                else:
                    strRfidList = str(tuple(rfidList))
                sql = "UPDATE slots SET rfid='', state='empty' WHERE rfid in %s;" % strRfidList
                sqlList.append(sql)
                sql = "DELETE FROM rfids WHERE rfid in %s;" % strRfidList
                sqlList.append(sql)
                sql = "DELETE FROM reservations WHERE rfid in %s;" % strRfidList
                sqlList.append(sql)
                proxy.mkcDb.updateTrs(sqlList)
    
                # sync to dbnode
                params = {}
                params["rfid_list"] = rfidList
                eventList = []
                for eventId in eventIdList:
                    eventList.append(proxy._getEventByEventId(eventId))
                params["event_list"] = eventList
                proxy.syncData("dbSyncClearSlots", params)
            print "Cleaning local DB ..... OK"
            print "Push the changes into sync queue ...... OK"
            print "All Done."
            print "The server side should reflect the changes in less than 15 minutes."
        except Exception, ex:
            log.error("clearSlots: %s" % str(ex))
            # roll back the event table
            if len(eventIdList) == 1:
                strEventIdList = "('" + str(eventIdList[0]) + "')"
            else:
                strEventIdList = str(tuple(eventIdList))
            sql = "DELETE FROM events WHERE id in %s;" % strEventIdList
            proxy.mkcDb.update(sql)
            raise



if __name__ == "__main__":
    try:
        slots = None
        if len(sys.argv) == 1:
            print "Usage: ./clear_slot.py [-s slot_ID(_List)] [--all|-a] [--help|-h]"
        else:
            if sys.argv[1].lower() == "-v" or sys.argv[1].lower() == "--version":
                print "VERSION:", __VERSION__
            elif sys.argv[1].lower() == "-a" or sys.argv[1].lower() == "--all":
                cusInput = raw_input("Are you sure to clear all slots? (y/N):")
                if cusInput.lower() == "y" or cusInput.lower() == "yes":
                    slots = "all"
                else:
                    os.abort()
            elif sys.argv[1].lower() == "-s" or sys.argv[1].lower() == "--slots":
                slotList = range(101, 841)
                if len(sys.argv) == 2:
                    cusInput = raw_input("Please input the slot(s) to be cleared (SLOT_ID[,SLOT_ID,SLOT_ID,...]):")
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
                if slots[0] != "":
                    cusInput = raw_input("Are you sure to clear slot(s) %s? (y/N):" % ",".join(slots))
                    if cusInput.lower() != "y" and cusInput.lower() != "yes":
                        os.abort()
                    cusInput = raw_input("Please type: I_confirm_there_is_no_disc_in_the_slot\n:")
                    if cusInput != "I_confirm_there_is_no_disc_in_the_slot":
                        os.abort()
                else:
                    os.abort()
            elif sys.argv[1].lower() == "-h" or sys.argv[1].lower() == "--help":
                print """e.g.
clear one slot: ./clear_slot.py -s SLOT_ID
clear some slots: ./clear_slot.py -s SLOT_ID,SLOT_ID,SLOT_ID (slots list without blank)
clear all: ./clear_slot.py --all|-a
help: ./clear_slot.py --help|-h"""
            else:
                print "Usage: ./clear_slot.py [-s slot_ID(_List)] [--all|-a] [--help|-h]"
    
        clearSlots(slots)
    except Exception, ex:
        log.error(str(ex))
        print "Sorry! Something wrong. Please try again."
