#!/usr/bin/python
"""
    Change Log:
        2011-05-04 Created by Kitch

"""

__VERSION__ = '1.0.006'

import os
import sys
import re
import base64
import getpass
import time

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
from db import verifyDb

log = getLog("s250h.log", "S250H")


def getKioskSoftVersion():
    softVersion = ""
    f = None
    try:
        f = open(os.path.join(USER_ROOT, "kiosk", "var", "version.ini"))
        softVersion = f.read().strip()
    except:
        pass
    finally:
        if hasattr(f, "close"):
            f.close()
    return softVersion

def changeHostName(name):
    # Return 1(int) for OK, 0(int) for any kind of fail
    if not name:
        return 0

    else:
        cmd = "echo "+name+" > /tmp/hostname.tmp;echo howcute121 | sudo -S  mv /tmp/hostname.tmp /etc/hostname"
        os.system(cmd)
        cmd = "echo howcute121 | sudo -S hostname "+name
        os.system(cmd)
        cmd = "cat /etc/hosts | grep -v S250 > /tmp/hosts.tmp;echo howcute121 | sudo -S mv /tmp/hosts.tmp /etc/hosts;echo howcute121 | sudo -S echo 127.0.0.1 "+name+" >> /etc/hosts"
        os.system(cmd)
        wfd, rfd = os.popen2("hostname")
        hostname = rfd.read().split('\n')
        if hostname[0] == name:      
            return 1
        else:
            return 0

def changeKioskCapacity(capacity):
    cmd = "echo " + capacity + " > /tmp/kioskcapacity.tmp; echo howcute121 | sudo -S  mv /tmp/kioskcapacity.tmp /etc/kioskcapacity"
    os.system(cmd)


def change250h():
    try:
        proxy = ConnProxy.getInstance()
        # backup DB
        print "Backup DB... "
        mkcdbPath = os.path.join(USER_ROOT, "kiosk", "var", "db", "mkc.db")
        mkcdbPathBak = os.path.join(USER_ROOT, "kiosk", "var", "db", "mkc.db.s250")
        os.system("cp %s %s" % (mkcdbPath, mkcdbPathBak))

        # change kiosk capacity
        changeKioskCapacity("500")

        # clear table slots
        print "Updating local db..."
        proxy.mkcDb.update("DELETE FROM slots;")
        proxy.mkcDb.update("DELETE FROM rfids;")
        proxy.mkcDb.update("UPDATE reservations SET state='canceled' WHERE state='reserved';")
        # fill the slots
        verifyDb()
        # update all sync state to 1
        sql = "UPDATE db_sync SET state=1 WHERE function_name<>'setMonthlySubscptForKiosk';"
        proxy.syncDb.update(sql)

        # get the new Kiosk ID from Server
        print "Checking and uploading db from server... "
        print "It will take a bit long time. Please Wait..."
        result = proxy.getRemoteData("change250h", {"mac":getEthMac()}, 300)
        if result["result"] == "ok":
            print "Stop the mkc and downloading the new firmware..."
            os.system(os.path.join(USER_ROOT, "kiosk/mkc2/mkc.py stop"))
            if os.system(os.path.join(USER_ROOT, "kiosk/utilities/downloader.py")) == 0:
                newKioskId = result["zdata"]
                log.info("new Kiosk ID: %s" % newKioskId)
                # change the hostname
                if changeHostName(newKioskId):
                    print "The Kiosk ID has been changed to %s." % newKioskId
                    log.info("Change Host Name %s to %s" % (proxy.kioskId, newKioskId))
                    print "System will reboot in 5 seconds."
                    time.sleep(5)
                    os.system("echo howcute121 | sudo -S reboot")
                else:
                    print "Change Host Name %s to %s Failed" % (proxy.kioskId, newKioskId)
            else:
                print "Downloading the new firmware failed. Please manully download it later."
                print "Stop the mkc first, then run ~/kiosk/utilities/downloader.py"
                log.error("download firmware failed")
        elif result["result"] == "timeout":
            print "Connection timed out. Please try again."
            print "Rollback..."
            os.system("cp %s %s" % (mkcdbPathBak, mkcdbPath))
            changeKioskCapacity("250")
        else:
            print "Something wrong. Please try again."
            log.error("remote: %s" % result["zdata"])
            print "Rollback..."
            os.system("cp %s %s" % (mkcdbPathBak, mkcdbPath))
            changeKioskCapacity("250")
    except Exception, ex:
        print "Something wrong. Please try again."
        log.error(str(ex))
        print "Rollback..."
        os.system("cp %s %s" % (mkcdbPathBak, mkcdbPath))
        changeKioskCapacity("250")

if __name__ == "__main__":
    try:
        # check the kiosk capacity
        if getKioskCapacity() == "500":
            print "The Kiosk is already S250-H."
            os.abort()

        # check the software version
        if getKioskSoftVersion() < "1.0.003":
            print "The software of the Kiosk does NOT support S250-H. Please upgrade first."
            os.abort()

        # check whether someone is using the Kiosk
        if isLocked():
            print "The kiosk is busy right now. Please retry later."
            os.abort()

        # check the password for security
        confirm = raw_input("This script is very dangerous! Are you sure the Kiosk's hardware has been changed for S250-H?(y/N)")
        if confirm.lower() == "y" or confirm.lower() == "yes":
            password = getpass.getpass("Please type the password:")
            if base64.b64encode(password) != "YWxsc3VwcG9ydHMyNTBo":
                print "Wrong password."
                os.abort()
        else:
            os.abort()

        change250h()
    except Exception, ex:
        log.error(str(ex))
        print "Sorry! Something wrong. Please try again."
