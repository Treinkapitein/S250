#!/usr/bin/python
"""
    Change Log:
        2009-05-21 Created by Kitch
            cancel a reservation, mark as cenceled

"""

__VERSION__ = '0.4.6'

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
import config
from conn_proxy import ConnProxy
from tools import *

log = getLog("cancel_reservation.log", "CANCEL_RESERVATION")

def error(message):
    print message

def cancelReservation():
    proxy = ConnProxy.getInstance()

    try:
        # get slot number
        while True:
            try:
                # Input slot number
                sn_input = raw_input("Please enter Slot No(\"a\" for abort):")
                if sn_input.lower() == "a":
                    os.abort()
                if not sn_input.isdigit():
                    error("The input value is wrong.")
                    continue
                slotNumber = int(sn_input)
                # get rfid
                sql = "SELECT rfid FROM slots WHERE id=?;"
                row = proxy.mkcDb.query(sql, "one", (slotNumber, ))
                if row is None:
                    error("The slot does NOT exist.")
                    continue
                rfid, = row
                if not rfid:
                    error("No disc in the slot.")
                    continue

                # get reserve info
                sql = "SELECT R.title, C.display, S.id, S.reserve_time, S.state " \
                      "FROM rfids AS R, cc AS C, reservations AS S " \
                      "WHERE R.rfid=S.rfid AND S.cc_id=C.id AND R.rfid=? " \
                      "ORDER BY S.reserve_time DESC LIMIT 1;"
                row = proxy.mkcDb.query(sql, "one", (rfid, ))
                if row is None:
                    error("The disc has NOT been reserved.")
                    continue
                title, ccName, rId, reserveTime, state = row
                if state == "picked":
                    error("The disc has been picked up.")
                    continue
                elif state == "expired":
                    error("The reservation has expired.")
                    continue
                elif state == "canceled":
                    error("The reservation has been canceled.")
                    continue

                print "The slot id: %s\ntitle: %s\ncc name: %s\nreserve time: %s\n" \
                      % (slotNumber, title, ccName, reserveTime)
                break
            except Exception, ex:
                error("An error occured: %s" % str(ex))
                continue

        # confirm
        confirm = raw_input("Are you sure to cancel this reservation?[Y/n]")
        if confirm.lower() != "n":
            # update database
            sqlList = []
            sql = "UPDATE rfids SET state='in' WHERE rfid='%s';" % rfid
            sqlList.append(sql)
            sql = "UPDATE reservations SET state='canceled' where id='%s';" % rId
            sqlList.append(sql)
            proxy.mkcDb.updateTrs(sqlList)
    
            # sync to node
            params = {}
            params["rfid"] = rfid
            params["reserve_id"] = rId
            proxy.syncData("dbSyncCancelReservation", params)
    
            print "Update local DB ...... OK"
            print "Push the changes into sync queue ...... OK"
            print "All Done."
            print "The server side should reflect the changes in less than 15 minutes."
        else:
            os.abort()
    except Exception, ex:
        log.error("cancelReservation: %s" % str(ex))
        raise



if __name__ == "__main__":
    cancelReservation()


