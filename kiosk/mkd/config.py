#!/usr/bin/python

import os

USER_ROOT = "/home/mm/"
try:
    f = open("/etc/kioskhome")
    USER_ROOT = f.read().strip()
    f.close()
except:
    pass
LOGGING_LOG_FILE = os.path.join(USER_ROOT, "kiosk/var/log/hdmimonitor.log")
HDMI_LOCK_FILE = os.path.join(USER_ROOT, "kiosk/tmp/hdmi.lock")
