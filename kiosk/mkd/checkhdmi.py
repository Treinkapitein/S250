#!/usr/bin/python

"""
    hdmi monitor
"""

try:
    import psyco
    psyco.full()
except:
    pass

import os
import sys
import time
import threading
import fcntl

import logging
from logging import handlers

import config


def initlog(name):
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)

    hConsole = logging.StreamHandler()
    hConsole.setLevel(logging.DEBUG)
    hConsole.setFormatter(logging.Formatter('%(asctime)s %(name)s  %(levelname)s \t %(message)s'))
    log.addHandler(hConsole)

    hFile = handlers.TimedRotatingFileHandler(config.LOGGING_LOG_FILE, 'D', 1, 3)
    hFile.setLevel(logging.INFO)
    hFile.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s \t %(message)s'))
    log.addHandler(hFile)

    return log

def get_hdmi_port():
    cmd = "echo 'howcute121' | sudo -S sh -c " \
          "\"dmidecode | grep -A8 'Base Board Information$' | grep 'Product Name'\""
    output = commands.getoutput(cmd)
    base_board = output.split(":")
    if base_board[-1].strip() == "DG45FC":  # old base board
        hdmi_port = "HDMI-1"
    else:  # base_board[-1].strip() == "G41", new base board
        hdmi_port = "HDMI-2"
    return hdmi_port

class MPlayer( threading.Thread ):
    def __init__(self):
        threading.Thread.__init__(self, name='MPlayer')
        self.hdmi_port = get_hdmi_port()

    def run(self):
        os.system("DISPLAY=:0.0 /usr/bin/xrandr --output %s --auto" % self.hdmi_port)
        time.sleep(1)
        os.system("DISPLAY=:0.0 /usr/bin/xrandr --output VGA --left-of %s" % self.hdmi_port)
        time.sleep(3)

        while True:
            if os.path.exists(os.path.join(config.USER_ROOT, "kiosk/tmp/hdmi.disconnected")):
                trace.info("HDMI Disconnected")
                os.remove(os.path.join(config.USER_ROOT, "kiosk/tmp/hdmi.disconnected"))
                break
            os.system('DISPLAY=:0.0 su mm -c"/usr/bin/mplayer -geometry 500:0 -fs -zoom -fixed-vo /home/mm/videos/*"')


class HDMIMonitor( threading.Thread ):
    def __init__(self):
        self._stopEvent = threading.Event()
        self._interval = 60
        threading.Thread.__init__(self, name='HDMIMonitor')
        self.lockfile = open(config.HDMI_LOCK_FILE, 'w')

    def lock(self):
        for i in xrange(10):
            try:
                fcntl.lockf(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except:
                time.sleep(0.5)

    def unlock(self):
        fcntl.lockf(self.lockfile, fcntl.LOCK_UN)

    def run(self):
        while not self._stopEvent.isSet():
            self.lock()
            #w, r = os.popen2('DISPLAY=:0.0 /usr/bin/xrandr -q | /bin/grep -i HDMI-1 | /bin/grep -i disconnected')
            w, r = os.popen2('DISPLAY=:0.0 /usr/bin/xrandr -q | /bin/grep -i %s | /bin/grep -w -i connected' % self.hdmi_port)
            data = r.read()
            w.close()
            r.close()
            
            trace.debug('HDMI: %s' %data)
            
            if os.path.exists(os.path.join(config.USER_ROOT, "kiosk/tmp/hdmi.connected")):
                #if data != "":
                if data == "":
                    trace.info("HDMI Disconnected")
                    os.remove(os.path.join(config.USER_ROOT, "kiosk/tmp/hdmi.connected"))
                    os.system("pkill mplayer")
                    os.system("DISPLAY=:0.0 /usr/bin/xrandr --output HDMI-1 --off")
                    os.system("DISPLAY=:0.0 /usr/bin/xrandr --output HDMI-2 --off")
            else:
                if os.path.exists(os.path.join(config.USER_ROOT, "kiosk/tmp/hdmimonitor.start")):
                    #if data == "":
                    if data != "":
                        trace.info("HDMI Connected")
                        os.system("DISPLAY=:0.0 /usr/bin/xrandr --output %s --auto" % self.hdmi_port)
                        time.sleep(1)
                        os.system("DISPLAY=:0.0 /usr/bin/xrandr --output VGA --left-of %s" % self.hdmi_port)
                        time.sleep(3)
                        os.system("/usr/bin/touch %s" % os.path.join(config.USER_ROOT, "kiosk/tmp/hdmi.connected"))
            self.unlock()
                    
            
            self._stopEvent.wait(self._interval)

    def join(self, timeout=None):
        self._stopEvent.set()
        threading.Thread.join(self, timeout)


def main():
    hdmiMonitor = HDMIMonitor()
    hdmiMonitor.start()
    
    while True:
        time.sleep(10)
        #print '......'
    

#########################
##### main rountine #####
#########################
if __name__ == '__main__':
    trace = initlog('MONITOR')
    main()
