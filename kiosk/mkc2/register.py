#!/usr/bin/python
"""
MovieMate Kiosk Core V2.0
CopyRight MovieMate, Inc.

Created 2009-03-03 Vincent
vincent.chen@cereson.com

Filename: register.py
Called by linux box startup script to register a kiosk ID into server

Change Log:

"""

# =================================================================
# =    Import
# -----------------------------------------------------------------
import httplib
import urllib
import os
import traceback
import socket
import time
import pexpect
import base64

import proxy.db
from mcommon import initlog
from linuxCmd import changeHostName
from proxy.tools import getEthMac
from proxy.tools import getKioskId
from proxy.conn_proxy import ConnProxy
from config import *

log = initlog("register")
SSH_TIMEOUT = 60 * 60

def serverCommand(ip, func, param={}, port=None, timeout=15):
    http = httplib.HTTPConnection(ip, port)
    headers = {"Content-type": "application/x-www-form-urlencoded",
               "Accept": "text/plain",
               "Kiosk": getKioskId()}
    
    params = {"function_name":func, "params":param}
    urlParams = urllib.urlencode(params)
    
    http.request("POST", "/api", urlParams, headers)
    http.sock.settimeout(timeout)
    r = http.getresponse()
    
    if r.status != 200:
        raise Exception("Invalid Server Api: name = %s, param = %s" % (func, param))
    
    data = r.read()
    result = eval(data)
    if result["result"] != "ok":
        raise Exception(str(result["zdata"]))
    
    return result["zdata"]

def rsync(host, user, password, srcfile, destfile, clean=True, output=None):
    cmd = 'rsync -cavz -e ssh '
    if clean == True:
        cmd += '--delete '
    if user and host:
        cmd += '%s@%s:~/' % (user, host)
    cmd += '%s %s' % (srcfile, destfile)
    
    child = pexpect.spawn(cmd)
    child.logfile = output
    try:
        index = child.expect(['continue connecting', 'password:'], timeout = SSH_TIMEOUT)
        if index == 0:
            child.sendline("yes")
            
            index = child.expect('password:', timeout = SSH_TIMEOUT)
            if index == 0:
                child.sendline(password)
        elif index == 1:
            child.sendline(password)
        else:
            raise Exception("Except Unknown Error")
        
        index = child.expect(['rsync error:', 'Permission denied'], timeout = SSH_TIMEOUT)
        if index == 0:
            raise RsyncException("Rsync Error: Rsync failed")
        elif index == 1:
            raise RsyncException("Rsync Error: Permission denied, please check your username and password.")
    except Exception:
        raise
    finally:
        child.close()

class Register:
    def __init__(self):
        pass
    
    def _needRegister(self):
        result = 0
        if os.path.exists(LOCK_FILE_PATH):
            result = 1
        return result
    
    def _onRegisterDone(self):
        cmd = "rm %s" % LOCK_FILE_PATH
        os.system(cmd)
        os.system("echo 'howcute121' | sudo -S reboot")
    
    def _sendEmailAlert(self, msg):
        proxy.db.verifyDb()
        connProxy = ConnProxy()
        connProxy.emailAlert("PRIVATE", msg, "andrew.lu@cereson.com", critical=connProxy.UNCRITICAL)
        del connProxy
    
    def _downloadDB(self, mac):
        ret = serverCommand(CONN_SERVICE_URL, "getServerDBParams", {"mac": mac})
        if str(ret["status_code"]) != "1":
            raise Exception(str(ret["msg"]))
        
        host = ret["host"]
        #port = ret["port"]
        user = ret["un"]
        pwd = base64.b64decode(ret["pwd"])
        src = ret["file"]
        
        try:
            rsync(host, user, pwd, src, os.path.join(KIOSK_HOME, "kiosk", "var", "db", "mkc.db"), False)
        except pexpect.TIMEOUT:
            raise RsyncException("Rsync Error: Rsync Timeout!")
        except pexpect.EOF:
            log.info("Rsync Finished!")
        except Exception:
            raise
    
    def _uploadDB(self, mac):
        ret = serverCommand(CONN_SERVICE_URL, "getServerDBParams", {"mac": mac})
        if str(ret["status_code"]) != "1":
            raise Exception(str(ret["msg"]))
        
        host = ret["host"]
        #port = ret["port"]
        user = ret["un"]
        pwd = base64.b64decode(ret["pwd"])
        src = ret["file"]
        
        try:
            dest = "%s@%s:~/%s" % (user, host, src)
            rsync(None, None, pwd, os.path.join(KIOSK_HOME, "kiosk", "var", "db", "mkc.db"), dest, False)
            
            ret = serverCommand(CONN_SERVICE_URL, "uploadKioskDB", {"mac": mac})
            if str(ret["status_code"]) != "1":
                raise Exception(str(ret["msg"]))
        except pexpect.TIMEOUT:
            raise RsyncException("Rsync Error: Rsync Timeout!")
        except pexpect.EOF:
            log.info("Rsync Finished!")
        except Exception:
            raise
    
    def _syncDB(self, mac):
        try:
            proxy.db.verifyDb()
            os.system("sqlite3 /home/mm/kiosk/var/db/sync.db \"UPDATE db_sync SET state=1 WHERE function_name<>'setMonthlySubscptForKiosk';\"")
            #serverCommand(CONN_SERVICE_URL, "resyncDb", timeout=180)
            self._uploadDB(mac)
        except:
            msg = "[Kiosk Rsync Failed after Register]:\n%s" % traceback.format_exc()
            log.error(msg)
            self._sendEmailAlert(msg)
    # =================================================================
    # =    def run
    # -----------------------------------------------------------------
    def run(self):
        try:
            if not self._needRegister():
                print "No need to register, just quit"
                return 1
            
            mac = getEthMac().strip()
            #mac = "vincent.chen"
            kioskID = getKioskId()
            
            params = urllib.urlencode({"mac": mac, "kiosk_id": kioskID, 
                                       "kc": self._get_kiosk_capacity()})
            log.info("Start to call conn register service with param %s" % params)
            conn = httplib.HTTPConnection(CONN_SERVICE_URL)
            conn.request("POST", "/registerKiosk", params)
            response = conn.getresponse()
            
            if str(response.status) != "200":
                raise Exception("Conn server call failed: %s: %s" % (response.status, response.reason))
            
            data = response.read()
            conn.close()
            log.info("Result from registerKiosk %s" % data)
            d = data.split("|")
            if len(d) != 3:
                raise Exception("Invalid result of registerKiosk %s " % data)
            
            errCode = d[0]
            newKioskID = d[2]
            
            if errCode == "0":
                log.info("Current Kiosk ID OK")
            elif errCode == "1":
                if not changeHostName(newKioskID):
                    raise Exception("Change Host Name %s to %s Failed" % (kioskID, newKioskID))
                
                self._syncDB(mac)
                
                log.info("Host name has been changed from %s to %s" % (kioskID, newKioskID))
            elif errCode == "2":
                if not changeHostName(newKioskID):
                    raise Exception("Change Host Name %s to %s Failed" % (kioskID, newKioskID))
                
                self._downloadDB(mac)
                
                msg = "Kiosk ID %s conflict, will be changed to %s and sync db" % (kioskID, newKioskID)
                log.warning(msg)
                self._sendEmailAlert(msg)
            elif errCode == "3":
                raise Exception("Conn service Internal Error")
            else:
                raise Exception("Invalid error code of registerKiosk:%s" % errCode)
            
            self._onRegisterDone()
        except Exception:
            msg = "[Kiosk Register Failed]:\n%s" % traceback.format_exc()
            log.error(msg)
            self._sendEmailAlert(msg)

    def _get_kiosk_capacity(self):
        """ Get the kiosk capacity for registering.
        Its value will be 250 or 500, and 250 as the default.
        """
        kioskCapacity = "250"
        fd = None
        try:
            if os.path.exists(KIOSK_CAPACITY_PATH):
                fd = open(KIOSK_CAPACITY_PATH)
                kioskCapacity = fd.read().strip()
            if not kioskCapacity:
                kioskCapacity = "250"
        finally:
            if fd:
                fd.close()
        return kioskCapacity

class RsyncException(Exception):
    pass

if __name__ == "__main__":
    r = Register()
    r.run()
#=============================================================================
# EOF
#-----------------------------------------------------------------------------
