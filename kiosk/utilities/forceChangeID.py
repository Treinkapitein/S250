#!/usr/bin/python
"""
    Change Log:
        2009-08-19 Created by Kitch
            Register its mac with it ID on the server
            download everything of the kiosk ID
            Check if the want-to-be ID kiosk is online or not


"""

__VERSION__ = '0.5.0'

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

log = getLog("forceChangeID.log", "FORCE_CHANGE_ID")


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


def changeID(destKioskId):
    proxy = ConnProxy.getInstance()
    if isLocked():
        print "The kiosk is busy right now. Please retry later."
    else:
        try:
            # check the dest ID and download mkc.db from server
            print "Check and download db from server... "
            print "It will take a bit long time. Please Wait..."
            result = proxy.getRemoteData("forceChangeID", {"dest_kiosk_id":destKioskId}, 180)
            if result["result"] == "ok":
                status = str(result["zdata"])
                log.info("status: %s" % status)
                if status == "1":
                    # success, change the hostname
                    if changeHostName(destKioskId):
                        log.info("Change Host Name %s to %s" % (proxy.kioskId, destKioskId))
                        print "System will reboot in 5 seconds."
                        time.sleep(5)
                        os.system("echo howcute121 | sudo -S reboot")
                    else:
                        print "Change Host Name %s to %s Failed" % (proxy.kioskId, destKioskId)
                elif status == "2":
                    print "Operation failed. The kiosk which you want to change to is online right now."
                else:
                    print "Operation failed. The kiosk which you want to change to does NOT exist."
            elif result["result"] == "timeout":
                print "Connection timed out. Please try again." 
            else:
                print "Something wrong. Please try again."
                log.error("remote: %s" % result["zdata"])
        except Exception, ex:
            log.error(str(ex))

if __name__ == "__main__":
    try:
        if len(sys.argv) == 1:
            print "Usage: ./forceChangeID.py KIOSK_ID"
        else:
            if sys.argv[1].lower() == "-h" or sys.argv[1].lower() == "--help":
                print "Usage: ./forceChangeID.py KIOSK_ID"
            else:
                destKioskId = sys.argv[1].upper()
                if not re.match(r'^[Ss]250-[A-Za-z][0-9]{3}$', destKioskId):
                    print "Wrong Kiosk ID."
                    os.abort()

                confirm = raw_input("This script is very dangerous! Are you sure to continue?(y/N)")
                if confirm.lower() == "y" or confirm.lower() == "yes":
                    password = getpass.getpass("Please type the password:")
                    if base64.b64encode(password) != "aWtub3dpdGlzZGFuZ2Vyb3Vz":
                        print "Wrong password."
                        os.abort()
                else:
                    os.abort()

                changeID(destKioskId)
    except Exception, ex:
        log.error(str(ex))
        print "Sorry! Something wrong. Please try again."
