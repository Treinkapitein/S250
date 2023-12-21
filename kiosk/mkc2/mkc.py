#!/usr/bin/env python
"""

MovieMate Kiosk Core V2.0
CopyRight MovieMate, Inc.

Created 2009-07-28 Andrew
andrew.lu@cereson.com

Change Log:
	Mavis 2010-02-01 Delete stopHdmi    
"""

import os
import sys
import time
import signal
import subprocess
import fcntl
import traceback
import logging
import Image

#from linuxCmd import stopHdmi
from proxy.conn_proxy import ConnProxy
from config import KIOSK_HOME, MKC_FLAG

connProxy = ConnProxy.getInstance()

USAGE = "Usage: %s [start|stop|restart] [-f]"
running = True
start_check = False
check_gui = False
terminate = False
MKC_MAIN = "mkc_run.py"
GUI_MAIN = "gui.py"
LOCK_FILE = os.path.join(KIOSK_HOME, "kiosk/tmp/mkcd.lock")
ERROR_BG = os.path.join(KIOSK_HOME, "kiosk/var/gui/sys/bg_outofservice.png")
FACTORY_BG = os.path.join(KIOSK_HOME, "kiosk/var/gui/sys/remotely_maintaining.jpg")

LOG_FILE = os.path.join(KIOSK_HOME, "kiosk/var/log/mkc_daemon.log")
CURRENT_FORM = "DISPLAY=:0.0 xset -b; DISPLAY=:0.0 scrot /home/mm/kiosk/tmp/current_form.jpg"

def initlog():
    logger = logging.getLogger('MKC_DAEMON')
    handle = logging.FileHandler(LOG_FILE)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s : %(name)-7s: %(levelname)-8s %(message)s')
    chf = logging.Formatter('%(levelname)-8s %(message)s')
    handle.setFormatter(formatter)
    ch.setFormatter(chf)
    logger.addHandler(handle)
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)
    
    return logger

log = initlog()

def getPid(myName):
    """
    is there any mkcMain running.
    """
    fpid = None
    cmd = None
    
    p1 = subprocess.Popen(["ps", "-eo", "pid,command"], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(["grep", myName], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen(["grep", "-v", "grep"], stdin=p2.stdout, stdout=subprocess.PIPE)
    output = p3.communicate()[0]
    
    lines = output.strip().split('\n')
    for line in lines:
        #print "LINE:%s" % line
        line = line.strip()
        if not line:
            continue
        
        pid = line.split()[0]
        if os.getpid() != int(pid):
            #log.info("get pid=%s" % line)
            return pid, line
    
    return fpid, cmd

def killAllPname(myName):
    """
    is there any mkcMain running.
    USE ps -eo pid,command. not command,pid, because it will truncate the output command
    """
    p1 = subprocess.Popen(["ps", "-eo", "pid,command"], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(["grep", myName], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen(["grep", "-v", "grep"], stdin=p2.stdout, stdout=subprocess.PIPE)
    output = p3.communicate()[0]
    
    lines = output.strip().split('\n')
    for line in lines:
        #print "LINE:%s" % line
        line = line.strip()
        if not line:
            return
        
        ret = line.split()
        
        try:
            if ret[1] == "sh" and ret[2] == "-c":
                continue
        except IndexError:
            pass
        
        pid = ret[0]
        if os.getpid() != int(pid):
            log.info("kill process=%s" % line)
            os.system("kill -9 %s" % pid)

def sendSignal(pid, cmd, force):
    sig = 0
    
    if cmd == "start":
        sig = signal.SIGRTMIN
    elif cmd == "stop":
        if not force:
            sig = signal.SIGRTMIN+1
        else:
            sig = signal.SIGRTMIN+2
    elif cmd == "restart":
        if not force:
            sig = signal.SIGRTMIN+3
        else:
            sig = signal.SIGRTMIN+4
    else:
        return
    
    str = "kill -s %d %s" % (sig, pid)
    os.system(str)

def onStart(signum, frame):
    startMkc()

def onStop(signum, frame):
    stopMkc(signum - signal.SIGRTMIN -1)

def onRestart(signum, frame):
    restartMkc(signum - signal.SIGRTMIN -3)

def changeBackground(fullname):
    cmd = "DISPLAY=:0.0 gconftool-2 -t string -s /desktop/gnome/background/picture_filename %s"
    os.system(cmd % fullname)
    cmd2 = "DISPLAY=:0.0 gconftool-2 -t string -s /desktop/gnome/background/picture_options wallpaper"
    os.system(cmd2)

def startMkc():
    global running
    global start_check
    global check_gui
    
    cmd = 'cd %s;./%s start' % (os.path.join(KIOSK_HOME, "kiosk/mkc2"), MKC_MAIN)
    os.system(cmd)
    payment = connProxy._getConfigByKey("payment_options")
    if str(payment) == "sitef":
        cmd = "python %s"%(os.path.join(KIOSK_HOME, "kiosk/mkc2/proxy/clisitef.py"))
        os.system(cmd)
    
    changeBackground(ERROR_BG)
    running = True
    start_check = True
    check_gui = False

def stopMkc(chkLock):
    global running
    global start_check
    
    cmd = 'cd %s;./%s stop' % (os.path.join(KIOSK_HOME, "kiosk/mkc2"), MKC_MAIN)
    
    if chkLock == False:
        cmd = cmd + " -f"
    
    os.system(cmd)
    changeBackground(FACTORY_BG)
    running = False
    start_check = False

def restartMkc(chkLock):
    global running
    global start_check
    global check_gui
    cmd = 'cd %s;./%s restart' % (os.path.join(KIOSK_HOME, "kiosk/mkc2"), MKC_MAIN)
    
    if chkLock == False:
        cmd = cmd + " -f"
    
    os.system(cmd)
    changeBackground(ERROR_BG)
    running = True
    start_check = True
    check_gui = False

def createDaemon():
    # create - fork 1
    try:
        if os.fork() > 0:
            sys.exit(0) # exit father...
    except OSError, error:
        print 'fork #1 failed: %d (%s)' % (error.errno, error.strerror)
        sys.exit(1)
    
    # it separates the son from the father
    os.chdir("/home/mm/kiosk/mkc2")
    os.setsid()
    os.umask(0)
    
    # create - fork 2
    try:
        pid = os.fork()
        if pid > 0:
            msg = 'Daemon PID %d' % pid
            log.info(msg)
            print msg
            sys.exit(0)
    except OSError, error:
        print 'fork #2 failed: %d (%s)' % (error.errno, error.strerror)
        sys.exit(1)

def getLock():
    try:
        file = open(LOCK_FILE, "w")
        fcntl.flock(file.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
        flag = fcntl.fcntl(file, fcntl.F_GETFD)
        fcntl.fcntl(file, fcntl.F_SETFD, flag or fcntl.FD_CLOEXEC)
    except IOError, ex:
        log.error("Cannot lock file %s, another mkc.py is running." % LOCK_FILE)
        return None
    except Exception, ex:
        log.error("Exception caught when getLock: %s" % str(ex))
        return None
    
    log.info("Get the file lock, mkc daemon will listening.")
    return file
    
def compare_tow_image_file(f1, f2):
    im1 = Image.open(f1).convert("L")
    (w1, h1) = im1.size
    pix1 = im1.load()

    im2 = Image.open(f2).convert("L")
    (w2, h2) = im2.size
    pix2 = im2.load()

    sum = 0
    if w1 < 768 or  w2 < 768 or h1 < 1024 or h2 < 1024:
        return False
    else:
        for x in range(760): # not 768, boundary may have some difference
            for y in range(924): # 942 not 1024, don't compare  telephone number
                sum += abs(pix1[x,y] - pix2[x, y])
                
        if (sum*1.0/(760*924) < 10):
            return True
        else:
            return False
            
def checkLoop():
    global running
    global start_check
    global terminate
    global check_gui
    
    checkCount = 0
    log.info("==================== Start Service ======================")
    start_time = time.time()
    hour  = 3600
    mail_submit = 0
    while terminate == False:
        # time sleep first, let mkc_run create 'flag' file
        time.sleep(10)
        if terminate == True:
            break
        
        if running == True:
            try:
                # check if gui.py is running
                guipid, guiname = getPid(GUI_MAIN)
                if not guipid:
                    msg = "gui crashed, restarted it at %s! " % time.strftime("%Y-%m-%d %H:%M:%S")
                    log.info(msg)
                    if mail_submit < 3:
                        mail_submit += 1 
                        connProxy.emailAlert("PRIVATE", msg, "developers@cereson.com", subject="Notification - %s - Restart" % connProxy.kioskId,\
                                critical=connProxy.UNCRITICAL)
                    os.system("cd /home/mm/kiosk/var/log/; cp qt_gui.log qt_gui.log.crash.%s" % time.strftime("%y%m%d%H%M"))
                    restartMkc(False)
                    continue
                if check_gui == False:
                    check_gui = True
                    time.sleep(30)
                else:
                    os.system(CURRENT_FORM)
                    if compare_tow_image_file(ERROR_BG, "/home/mm/kiosk/tmp/current_form.jpg"):
                        msg = "found guipid but gui crashed, restart it! " + time.strftime("%Y-%m-%d %H:%M:%S")
                        log.info(msg)
                        if mail_submit < 3:
                            mail_submit += 1 
                            connProxy.emailAlert("PRIVATE", msg, "developers@cereson.com", critical=connProxy.UNCRITICAL)
                        os.system("cd /home/mm/kiosk/var/log/; cp qt_gui.log qt_gui.log.crash.%s" % time.strftime("%y%m%d%H%M"))
                        restartMkc(False)
                        continue
                
            
                # check if mkc_run.py is running
                mkcpid, mkcname = getPid(MKC_MAIN)
                if not mkcpid:
                    msg = "mkc crashed, restart it! " + time.strftime("%Y-%m-%d %H:%M:%S")
                    log.info(msg)
                    if mail_submit < 3:
                        mail_submit += 1 
                        connProxy.emailAlert("PRIVATE", msg, "developers@cereson.com", critical=connProxy.UNCRITICAL)
                    os.system("cp nohup.out nohup.crash")
                    
                    #stopHdmi()
                    startMkc()
                    continue
                
                if start_check == True:
                    if os.path.exists(os.path.join(KIOSK_HOME, "kiosk/mkc2", MKC_FLAG)):
                        if checkCount < 6:
                            checkCount += 1
                        else:
                            msg = "MKC may have failed to start up at %s, please check it" % time.strftime("%Y-%m-%d %H:%M:%S")
                            if mail_submit < 3:
                                mail_submit += 1 
                                connProxy.emailAlert("PRIVATE", msg, "developers@cereson.com", critical=connProxy.UNCRITICAL)
                            log.error(msg)
                            start_check = False
                            checkCount = 0
                    else:
                        start_check = False
                        checkCount = 0

            except Exception:
                msg = traceback.format_exc()
                connProxy.emailAlert("PRIVATE", msg, "developers@cereson.com", critical=connProxy.UNCRITICAL)
                break
            finally:
                if time.time() - start_time >= hour:        
                    mail_submit = 0
                    start_time = time.time()

def handler(signum, frame):
    global terminate
    log.info('Signal term handler called with signal %s' % signum)
    terminate = True

if __name__ == "__main__":
    command = ""
    chkLock = True
    pname = "mkc.py"
    plen = len(sys.argv)
    
    if plen == 1:
        command = "start"
    elif plen == 2:
        command = sys.argv[1]
    elif plen == 3:
        command = sys.argv[1]
        if sys.argv[2] == "-f":
            chkLock = False
    else:
        print USAGE % pname
        sys.exit(1)
    
    log.info("New Command: %s" % command)
    
    killAllPname(pname)
    
    #If mkc_run.py is already running, kill it and start a new one
    if command == "start":
        startMkc()
    elif command == "stop":
        stopMkc(chkLock)
    elif command == "restart":
        restartMkc(chkLock)
    else:
        print "error parameter"
        print USAGE % pname
        sys.exit(1)

    createDaemon()
    #print "CWD=" + os.getcwd()
    
    #It is first time run this py
#    signal.signal(signal.SIGHUP, signal.SIG_IGN)
#    signal.signal(signal.SIGRTMIN, onStart)
#    signal.signal(signal.SIGRTMIN+1, onStop)
#    signal.signal(signal.SIGRTMIN+2, onStop)
#    signal.signal(signal.SIGRTMIN+3, onRestart)
#    signal.signal(signal.SIGRTMIN+4, onRestart)
    signal.signal(signal.SIGTERM, handler)
    
    file = getLock()
    if file == None:
        sys.exit(1)
    
    checkLoop()

