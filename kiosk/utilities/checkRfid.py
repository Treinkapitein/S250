#!/usr/bin/env python

import os

KIOSK_CONF = "/etc/kioskhome"
file = open(KIOSK_CONF, 'r')
KIOSK_HOME = file.readline().strip()
MKC_HOME = os.path.join(KIOSK_HOME, "kiosk/mkc2")

if __name__ == "__main__":
    os.system("cd %s;./mkc.py stop" % MKC_HOME)
    os.system("cd %s;python RfidChecker.pyc" % MKC_HOME)
    os.system("cd %s;./mkc.py start" % MKC_HOME)


