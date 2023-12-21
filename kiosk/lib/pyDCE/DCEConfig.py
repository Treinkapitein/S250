import os
import logging
import logging.handlers

import pyDCE.config as conf

USER_ROOT = "/home/mm/"
try:
    f = open("/etc/kioskhome")
    USER_ROOT = f.read().strip()
    f.close()
except:
    pass

dce_config={
'DEBUG_RUN':1,

##############Log Configuration############
'LOG_FILE_NAME':'DCELog.log',
'LOG_MODE_TTY':1,       # print the message int tty
#'LOG_MODE_REMOTE':2,    # remote debugging

'LOG_FORMAT':'%(asctime)s %(levelname)s %(message)s',
'LOG_REMOTE_HOST':'localhost',
'LOG_REMOTE_PORT':logging.handlers.DEFAULT_TCP_LOGGING_PORT,
'LOG_LEVEL':logging.DEBUG,
'LOG_CONSOLE_LEVEL':logging.DEBUG,
'LOG_FORMAT':'%(asctime)s %(levelname)s %(message)s',
'LOG_FILE_ROOT':os.path.join(USER_ROOT, 'kiosk/var/log/'),
'LOG_MODE':conf.LOG_MODE_TTY|conf.LOG_MODE_REMOTE,
###########################################

'NODE_HEART_BEAT':20.0,

'DCE_LISTEN_BACKLOG':200,
'DCE_ACCEPT_READ_TIMEOUT':5000,
'DCE_POLL_TIMEOUT':5000,
'DCE_SEND_MSG_TIMEOUT':5000,
'DCE_GET_RESPONSE_TIMEOUT':5000,

'DCE_DEFAULT_TIMEOUT_MS':120000,
'DCE_DEFAULT_TIMEOUT':120,

####################################

'CERT_DIR':os.path.join(USER_ROOT, "kiosk/lib/pyDCE/certs"),
'CLIENT_CERT':'client.pem',
'SERVER_CERT':'server.pem',
'CA_FILE':'ca.pem',
'SERVER_KEY_FILE':"server_key.pem",
'CLIENT_KEY_FILE':"client_key.pem",
'KEY_PASSPHRASE':"12345",

'ALLOW_UNKOWN_CA':0,

####################################

'PYDCE_DEFAULT_TCP_PORT':9990,
'PYDCE_DEFAULT_SSL_PORT':9900,

####################################
###configuration for dynamic node###
'NODE_HEART_BEAT':20,

#'REGISTRY_URL':"access@tcp 127.0.0.1:20680",
#'REGISTRY_URL':"access@tcp 192.168.1.53:38888",
'REGISTRY_URL':"access@ns registry.cereson.com:28800:accessnode",
#'REGISTRY_URL':"access@sns 192.168.1.53:29900:accessnode",

'LOCAL_REGISTRY_URL':"access@tcp 127.0.0.1:20680:accessnode",
}

MKC_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/mkc.db")
UPC_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/upc.db")
SYNC_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/sync.db")
MEDIA_DB_PATH = os.path.join(USER_ROOT, "kiosk/var/db/media.db")





