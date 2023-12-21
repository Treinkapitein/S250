#!/usr/bin/python
"""
    Change Log:
        2009-11-24 Created by Kitch
            move a disc to a empty slot

"""

__VERSION__ = '1.0.0'

import os
import sys
import shutil
import base64
import getpass

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

log = getLog("moveDisc.log", "MOVE_DISC")

def move(orig, dest):
    print "Processing..."
    proxy = ConnProxy.getInstance()

    try:
        # check the two slots' state
        sql = "SELECT rfid, state FROM slots WHERE id=?;"
        row = proxy.mkcDb.query(sql, "one", (orig, ))
        if row and (row[0] == "" or str(row[0]) == "None"):
            print "The original slot %s is empty." % orig
            os.abort()

        row = proxy.mkcDb.query(sql, "one", (dest, ))
        if row and row[1] != "empty":
            print "The destination slot %s is NOT empty." % dest
            os.abort()

        # backup mkc.db
        bakFileName = config.MKC_DB_PATH + ".bak." + getCurTime("%Y-%m-%d")
        if not os.path.exists(bakFileName):
            shutil.copy(config.MKC_DB_PATH, bakFileName)
        print "Backing up DB ...... OK"

        proxy.moveSlot(orig, dest)
        
        print "Updating local DB ..... OK"
        print "Push the changes into sync queue ...... OK"
        print "All Done."
        print "The server side should reflect the changes in less than 15 minutes."
        log.info("move disc: %s -> %s" % (orig, dest))
    except Exception, ex:
        log.error("move: %s" % str(ex))
        raise



if __name__ == "__main__":
    try:
        password = getpass.getpass("Please type the password:")
        if base64.b64encode(password) != "bWFyY293YW50c3RvbW92ZQ==":
            print "Wrong password."
            os.abort()

        slotList = range(101, 171)
        slotList.extend(range(228, 271))
        slotList.extend(range(501, 571))
        slotList.extend(range(601, 671))

        orig = raw_input("Please input the original slot:")
        # check the slot
        try:
            orig = int(orig.strip())
        except:
            print "Detected invalid slot %s." % orig
            os.abort()
        if orig and orig not in slotList:
            print "Detected invalid slot %s." % orig
            os.abort()

        dest = raw_input("Please input the destination slot:")
        # check the slot
        try:
            dest = int(dest.strip())
        except:
            print "Detected invalid slot %s." % dest
            os.abort()
        if dest and dest not in slotList:
            print "Detected invalid slot %s." % dest
            os.abort()
        move(orig, dest)
    except Exception, ex:
        log.error(str(ex))
        print "Sorry! Something wrong. Please try again."



