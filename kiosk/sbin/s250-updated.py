#!/usr/bin/env python

import os
import sys
import time
import signal
import traceback
from misc import *
from kioskDownloader import KioskDownloader
from kioskDeployManager import KioskDeployManager
from inotify import Watcher, ISDIR, CREATE

CHECK_INTERVAL = 60 * 60 * 2

if __name__ == '__main__':
    def handler(signum, frame):
        # use alarm to wake up time.sleep()
        pass
    
    def up(event):
        global instantUpdate
        
        head, tail = os.path.split(event.path)
        if tail != "need_update":
            return
        if event.mask & ISDIR:
            return
        
        instantUpdate = True
        signal.alarm(1)
    
    signal.signal(signal.SIGALRM, handler)
    
    log = initLog("s250-updated.log", "UD")
    log.info(" s250 update daemon start here. ".center(INFO_WIDTH, '='))
    instantUpdate = False
    
    hasLock = False
    for i in range(5):
        try:
            _flock = getFileLock(DAEMON_LOCK)
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
        msg = "Auto update daemon cannot get file lock, exit."
        print msg
        log.error(msg)
        emailAlert(msg, "tim.guo@cereson.com")
        sys.exit(-1)
    
    createDaemon()
    os.system("rm ~/.ssh/known_hosts")
    # sleep 6 minutes to avoid update firmware and mkc initRobot conflict
    time.sleep(60 * 6)
    
    try:
        log.info(" s250 update daemon initialize. ".center(INFO_WIDTH, '='))
        downloader = KioskDownloader(log)
        deployMan = KioskDeployManager(log)
        watcher = Watcher(log)
        watcher.add(os.path.join(KIOSK_HOME, "kiosk", "tmp"), CREATE, up, False)
        
        if os.path.exists(os.path.join(KIOSK_HOME, "kiosk", "tmp", "need_update")):
            instantUpdate = True
    except:
        log.error(traceback.format_exc())
    
    try:
        while True:
            downfail = False
            if downloader.hasNewVersion() == True:
                try:
                    downloader.download()
                    deployMan.notify()
                    downfail = False
                except FilelockException, ex:
                    log.error("can not get file lock, new version is downloading ...")
                except:
                    downfail = True
                    msg = "Download kiosk new version %s failed at %s:\n%s" % (downloader.newVersion, time.strftime("%Y-%m-%d %H:%M:%S"), traceback.format_exc())
                    log.error(msg)
                    emailAlert(msg)
            
            if not deployMan.isAlive():
                deployMan.start()
                # sleep 2 seconds to wait deployManager start up
                time.sleep(2)
            
            if instantUpdate:
                os.remove(os.path.join(KIOSK_HOME, "kiosk", "tmp", "need_update"))
                instantUpdate = False
                
                if downfail == False:
                    log.info("start update kisok right now.")
                    deployMan.updateNow()
            
            time.sleep(CHECK_INTERVAL)
            log.info("hello update daemon.")
    except:
        msg = "kiosk downloader deamon failed at %s:\n%s" % (time.strftime("%Y-%m-%d %H:%M:%S"), traceback.format_exc())
        log.error(msg)
        emailAlert(msg, "tim.guo@cereson.com")
        sys.exit(-1)
    finally:
        releaseFileLock(_flock)
    
    sys.exit(0)


