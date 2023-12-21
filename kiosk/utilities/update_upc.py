#!/usr/bin/python
"""
    Change Log:
        2009-03-10 Created by Tim
            Announce the movie service to update the upc.db 
            and pic for the kiosk.

"""

__VERSION_ = '0.0.1'

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
from movie_proxy import MovieProxy
from tools import getLog

log = getLog("update_upc.log", "USER")

def main():
    """ Announce the movie service to update the upc.db 
    and pic for the kiosk.
    """
    try:
        need = raw_input("Do you want to announce server to update upc.db?(yes)/no:")
        if need.lower().strip() in ("", "yes"):
            log.info("Update upc.db.")
            proxy = MovieProxy.getInstance()
            proxy.updateUpcDb()
            del proxy
            print 
            print "The server will update upc.db in 10 minutes."
            print "Thanks."
            print
        else:
            os.abort()
    except Exception, ex:
        log.error("Error in main: %s"%ex)
        print "Error occurs: ", ex
        print "Please try again."

if __name__ == "__main__":
    main()
