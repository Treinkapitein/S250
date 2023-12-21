#!/usr/bin/python
"""
MovieMate Kiosk Core V2.0
CopyRight MovieMate, Inc.

Created 2008-10-07 Vincent
vincent.chen@cereson.com

Filename: mkc.py
The Main Entry of MKC

Change Log:
    Vincent 2009-04-17 Move startHdmi() to startMkc
    Vincent 2009-03-04 Add an option to skip lock chk
    Vincent 2009-02-28 For #1583
	Mavis 2010-02-01 Delete stopHdmi, pkill mplayer
"""

# =================================================================
# =    Import
# -----------------------------------------------------------------
import os
import signal
import sys
import time

from mcommon import initlog
from mcommon import startHdmi
#from mcommon import stopHdmi
from proxy.tools import isLocked
from proxy.conn_proxy import ConnProxy
from config import QTGUI

log = initlog("mkc")
connProxy = ConnProxy.getInstance()

MKC_VERSION = "V2 0.5.1"

#=============================================================================
# Functions
#-----------------------------------------------------------------------------
def getPid():
    """
    returns the current Pid
    """
    cmd = "ps -eo pid,command | grep '^.*mkc_run.py *[test]*$'"
    wfd, rfd = os.popen2(cmd)
    try:
        try:
            lines = rfd.read().split('\n')
            for line in lines:
                pid = line.split()[0]
                log.debug(("line pid", pid, line))
                if os.getpid() != int(pid):
                    log.debug(("none match", os.getpid(), pid))
                    return pid
            return None
        except:
            return None
     
    finally:
        wfd.close()
        rfd.close()

def stopMkc(chkLock):
    print 'stopping mkc...'
    
    pid = getPid()
    print "MKC PID:", pid
    
    if pid == None:
        print 'MKC is NOT running'
        return True
    else:
        if chkLock and isLocked():
            answer = raw_input('LOCK file found, MKC might be busy, kill it anyway? yes|NO ')
            if answer != 'yes':
                print 'You chose not to kill, MKC will live on'
                return False
        
        connProxy.logMkcEvent(category="system", action="startup", data1="MKC Stop")
        cmd = 'kill -9 ' + str(pid)
        os.system(cmd)
        print 'MKC stopped'
        
        cmd = "pkill -f %s" % QTGUI
        os.system(cmd)
        #cmd = "pkill -f %s" % "mplayer"
        #os.system(cmd)

        #stopHdmi()
        
        return True

def startMkc():
    print 'Starting mkc...'
    
    if getPid() == None:
        cmd = 'nohup ./mkc_run.py >nohup.out 2>&1 &'
        os.system(cmd)
        print 'MKC started'
        print "Starting HDMI ....."
        #time.sleep(5)
        startHdmi()
    else:
        print 'MKC is already running'
        print "please use './mkc.py stop' to stop the previous MKC instance"

#=============================================================================
#    Main 
#-----------------------------------------------------------------------------
if __name__ == "__main__":
    # Ignore a hangup signal, so when program can be started from a terminal screen
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "start":
            startMkc()               

        elif command == "stop":
            chkLock = 1
            if len(sys.argv) > 2:
                if str(sys.argv[2]) == "-f":
                    chkLock = 0
            stopMkc(chkLock)
            
        elif command == "restart":
            chkLock = 1
            if len(sys.argv) > 2:
                if str(sys.argv[2]) == "-f":
                    chkLock = 0
            if stopMkc(chkLock) == True:            
                startMkc()
            print 'Done!'

        else:
            print "Invalid parameter one, try 'restart', 'stop', to start omit parameters "
    else:
        if getPid() == None:
            from main import start
            print "MKC Version: %s" % MKC_VERSION
            
            start()
        else:
            print "MKC is already running"
            print "please use './mkc.py stop' to stop the previous MKC instance"

#=============================================================================
# EOF
#-----------------------------------------------------------------------------
