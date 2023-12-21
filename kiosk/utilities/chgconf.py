#!/usr/bin/python
"""
    Change Log:
        2009-03-03 Modified by Kitch
            move to ~/utilities/
        2009-02-06 Created by Kitch
            change config and sync to server

"""

__VERSION_ = '0.0.2'

import os
import sys

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
from tools import getLog

log = getLog("change_config.log", "CHANGE_CONFIG")

OFFSET_SETTINGS = ("pulses_per_slot", "top_offset", "bottom_offset", "exchange_offset", \
                   "back_offset", "sensor_distance", "sensor_distance_fl", "distance1", \
                   "distance2", "offset2xx", "offset6xx")

def changeConfig():
    try:
        proxy = ConnProxy.getInstance()
        sql = "SELECT id, variable, value FROM config WHERE variable<>'kiosk_logo' AND variable<>'terms_and_conditions';"
        rows = proxy.mkcDb.query(sql)
        print "All configs..."
        print "ID\tConfig\t\t\tValue"
        idList = []
        for row in rows:
            print "%s\t%s\t%s\t" % row
            idList.append(row[0])
    
        confId = raw_input("Please input the config ID which to be changed:")
        try:
            confId = int(confId)
        except:
            print 'DoNOT test me!! I am NOT baby!'
            print 'I just need a number'
            os.abort()
    
        if confId not in idList:
            print 'The number is out of my range!'
            os.abort()
    
        sql = "SELECT id, variable, value FROM config WHERE id=?;"
        row = proxy.mkcDb.query(sql, "one", (confId, ))
        confId, confVariable, confOldValue = row
    
        print "The config(%s) old value is: %s." % (confVariable, confOldValue)
        confNewValue = raw_input("Please input the new value:")

        if confVariable in OFFSET_SETTINGS:
            try:
                float(confNewValue)
            except:
                print 'Wrong input, please check.'
                os.abort()

        proxy.setConfig({confVariable:confNewValue})

        # check speaker_volume and change it
        if confVariable == "speaker_volume":
            os.system("amixer set Master %s%%" % int(confNewValue))
            os.system("echo 'howcute121' | sudo -S alsactl store")

        msg = "Changed the config(%s) from %s to %s successfully." % (confVariable, confOldValue, confNewValue)
        print msg
        log.info(msg)
    except Exception, ex:
        log.error(str(ex))
        raise


if __name__ == "__main__":
    changeConfig()

