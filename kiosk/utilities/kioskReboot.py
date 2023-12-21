#!/usr/bin/python
"""
Created on 2010-11-4
@author: andrew.lu@cereson.com
"""

import os
import sys
import time

KIOSK_CONF = "/etc/kioskhome"
file = open(KIOSK_CONF, 'r')
KIOSK_HOME = file.readline().strip()

sys.path.append(os.path.join(KIOSK_HOME, "kiosk", "sbin"))
from misc import INFO_WIDTH, createDaemon, initLog
from misc import getFileLock, releaseFileLock, emailAlert, isMkcLocked

REBOOT_BG = os.path.join(KIOSK_HOME, "kiosk/var/gui/sys/remote_reboot.jpg")
REBOOT_LOCK = os.path.join(KIOSK_HOME, "kiosk/tmp/rreboot.lock")

def changeBackground(fullname):
    cmd = "DISPLAY=:0.0 gconftool-2 -t string -s /desktop/gnome/background/picture_filename %s"
    os.system(cmd % fullname)
    cmd2 = "DISPLAY=:0.0 gconftool-2 -t string -s /desktop/gnome/background/picture_options wallpaper"
    os.system(cmd2)

if __name__ == '__main__':
    log = initLog("remote_reboot.log", "RR")
    
    hasLock = False
    for i in range(5):
        try:
            _flock = getFileLock(REBOOT_LOCK)
        except IOError, ex:
            msg = "another process is running."
            print msg
            log.error(msg)
            time.sleep(2)
            continue
        except Exception, ex:
            msg = "Exception caught when get file lock: %s" % str(ex)
            print msg
            log.error(msg)
            time.sleep(2)
            continue
        
        hasLock = True
        break
    
    if hasLock == False:
        msg = "Remote reboot daemon cannot get file lock, exit."
        print msg
        log.error(msg)
        emailAlert(msg, "andrew.lu@cereson.com")
        sys.exit(-1)
    
    createDaemon()
    
    try:
        log.info(" reboot kisok ... ".center(INFO_WIDTH, '='))
        
        while isMkcLocked():
            log.info("mkc is locked.")
            time.sleep(2)
        
        log.info("start reboot kisok right now.")
        os.chdir(os.path.join(KIOSK_HOME, "kiosk/mkc2"))
        os.system("./mkc.py stop -f")
        
        changeBackground(REBOOT_BG)
        time.sleep(10)
    finally:
        releaseFileLock(_flock)
    
    os.system("echo howcute121 | sudo -S reboot")
    sys.exit(0)
