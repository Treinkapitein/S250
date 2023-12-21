#!/usr/bin/env python

import httplib
import sys
import os

KIOSK_CONF = "/etc/kioskhome"
file = open(KIOSK_CONF, 'r')
KIOSK_HOME = file.readline().strip()

PROXY_DIR = os.path.join(KIOSK_HOME, "kiosk", "mkc2", "proxy")
sys.path.append(PROXY_DIR)

from conn_proxy import ConnProxy

URL1 = "cereson.mydvdkiosks.net"
URL2 = "/api/getIp"

if __name__ == "__main__":
    proxy = ConnProxy.getInstance()
    
    try:
        http = httplib.HTTPConnection(URL1)
        http.request("GET", URL2)
        http.sock.settimeout(5)
        
        res = http.getresponse()
        if res.status == 200:
            ip = res.read()
            proxy.setExternalIP(ip)
            print ip
        else:
            print "Failed to reach the server."
            sys.exit(-1)
    except Exception:
        print "Unknown error."
        sys.exit(-1)
    
    sys.exit(0)

