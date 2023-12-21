#!/usr/bin/python
"""
    Change Log:
        2011-03-04 Created by Tim
            vacuum the database to decrease the database locked error

    usage:
    vacuum all database(mkc, new_upc, sync): ./vacuum_database.py
    vacuum database mkc: ./vacuum_database.py mkc
    vacuum database new_upc: ./vacuum_database.py upc
    vacuum database sync: ./vacuum_database.py sync
    help: ./vacuum_database.py --help(-h)

"""

__VERSION__ = '0.0.1'

import os
import sys
import shutil

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
from mda import Db
from tools import getLog, isLocked

log = getLog("vacuum_database.log", "VACUUM")

USAGE = """Usage: ./vacuum_database.py [mkc|upc|sync|-h|--help]
"""

def vacuum_database(db_path):
    db = None
    try:
        db = Db(db_path)
        db.update("vacuum;")
    except Exception, ex:
        log.error("vacuum_database(%s): %s" % (db_path, ex))
    del db

def main():
    try:
        # check if some guys have been using the kiosk, if it is used, then exit
        if isLocked():
            print "The kiosk is busy right now. Please retry later."
            return

        # valid command list
        cmds = ["all", "mkc", "upc", "sync", "-h", "--help"]
        cmd = "all"
        if len(sys.argv) > 2:  # the command is error
            print USAGE
            return

        if len(sys.argv) == 2:  # the command is entered in
            cmd = sys.argv[1]

        # check if the command is invalid
        fmt_cmd = cmd.lower()  # format the command to check if it is valid
        if fmt_cmd not in cmds:
            print "Invalid command: %s" % cmd
            print USAGE
            return

        if fmt_cmd in ("-h", "--help"):
            print USAGE
            return
        if fmt_cmd in ("all", "mkc"):
            print "vacuuming mkc.db ..."
            vacuum_database(config.MKC_DB_PATH)
        if fmt_cmd in ("all", "upc"):
            print "vacuuming new_upc.db ..."
            vacuum_database(config.UPC_DB_PATH)
        if fmt_cmd in ("all", "sync"):
            print "vacuuming sync.db ..."
            vacuum_database(config.SYNC_DB_PATH)

        print "vacuum successfully..."
    except Exception, ex:
        log.error("vacuum_database: %s" % ex)
        print "Sorry, something wrong. Please retry."



if __name__ == "__main__":
    main()
