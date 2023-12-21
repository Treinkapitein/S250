#!/usr/bin/python
"""
##  Config of kiosk side for access agent.
##
##  File name: config.py
##
"""

import os
import logging

USER_ROOT = "/home/mm/"
try:
    f = open("/etc/kioskhome")
    USER_ROOT = f.read().strip()
    f.close()
except:
    pass

MKC_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/mkc.db")
NEW_UPC_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/new_upc.db")
UPC_DB_PATH = NEW_UPC_DB_PATH #os.path.join(USER_ROOT, "kiosk/var/db/upc.db")
SYNC_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/sync.db")
MEDIA_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/media.db")

DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_KIOSK_HOST = "127.0.0.1"
DEFAULT_KIOSK_PORT = 5001

# The config of log
LOG_FILE_ROOT = "/home/mm/kiosk/var/log/"
LOG_LEVEL = logging.DEBUG
LOG_CONSOLE_LEVEL = logging.DEBUG
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
LOG_FILE_NAME = 'access_agent.log'
LOG_ROTATE_SIZE = 10*1024*1024 # 10M
LOG_ROTATE_COUNT = 5

