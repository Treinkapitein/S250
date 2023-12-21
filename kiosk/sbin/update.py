#!/usr/bin/env python

import optparse
import os
import sys
import fcntl
import logging
import pexpect
import traceback
import httplib
import urllib
import socket

KIOSK_CONF = "/etc/kioskhome"
file = open(KIOSK_CONF, 'r')
KIOSK_HOME = file.readline().strip()

LOCK_FILE = os.path.join(KIOSK_HOME, "kiosk/tmp/update.lock")
LOG_FILE = os.path.join(KIOSK_HOME, "kiosk/var/log/update.log")

UPDATE_SCRIPT_NAME = "kioskUpdate.py"
UPDATE_SCRIPT_TAR = "update.tar.gz"
UPDATE_OPERATE_FOLDER = os.path.join(KIOSK_HOME, "kiosk/tmp")

UPDATE_SERVER_REAL = "update.cereson.com"
UPDATE_SERVER_TEST = "cereson.51vip.biz"
UPDATE_SERVER_USER = "update"
UPDATE_PWD_REAL = "update5810"
UPDATE_PWD_TEST = "howcute121"

class Update:
    def __init__(self, test, version):
        self.test = test
        self.version = version
        
        self.user = UPDATE_SERVER_USER
        if self.test == True:
            self.server = UPDATE_SERVER_TEST
            self.pwd = UPDATE_PWD_TEST
        else:
            self.server = UPDATE_SERVER_REAL
            self.pwd = UPDATE_PWD_REAL
        
        self.reset_log_partition()
        self._initLog()
    
    def _selfLock(self):
        try:
            self.file = open(LOCK_FILE, "w")
            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
        except IOError, ex:
            raise FilelockException("Cannot lock file %s, another update.py is running." % LOCK_FILE)
        except Exception, ex:
            self.logger.error("Exception caught when _selfLock: %s" % str(ex))
            raise
        
        self.logger.info("Get the file lock, and start update.")
    
    def _selfUnlock(self):
        if self.file:
            self.file.close()
            os.remove(LOCK_FILE)
            
            msg = "Release the file lock, and update ends."
            self.logger.info(msg)
    
    def _initLog(self):
        self.logger = logging.getLogger('UPDATOR')
        handle = logging.FileHandler(LOG_FILE)
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s : %(name)-7s: %(levelname)-8s %(message)s')
        chf = logging.Formatter('%(levelname)-8s %(message)s')
        handle.setFormatter(formatter)
        ch.setFormatter(chf)
        self.logger.addHandler(handle)
        self.logger.addHandler(ch)
        self.logger.setLevel(logging.INFO)
    
    def _getKioskId(self):
        file = open("/etc/hostname",'r')
        id = file.readline().strip()
        return id
    
    def _getRealLatest(self):
        http = httplib.HTTPConnection("127.0.0.1", "20080")
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Accept": "text/plain",
                   "Kiosk": self._getKioskId()}
        
        params = {"function_name":"getLatestVersion", "params":{}}
        urlParams = urllib.urlencode(params)
        
        try:
            http.request("POST", "/api", urlParams, headers)
            http.sock.settimeout(15)
            r = http.getresponse()
            
            if r.status != 200:
                raise Exception("Cannot get latest version NO. from update server")
            
            data = r.read()
            try:
                result = eval(data)
                self.version = result["zdata"]["version"]
            except Exception:
                raise
        except socket.timeout:
            raise
        except Exception:
            raise
    
    def _getUpdateScript(self):
        if self.version == "latest":
            if self.test == True:
                self._rsync("S250-A/latest/version", UPDATE_OPERATE_FOLDER)
                
                fn = os.path.join(UPDATE_OPERATE_FOLDER, "version")
                file = open(fn,'r')
                self.version = file.readline().strip()
            else:
                self._getRealLatest()
        
        src = os.path.join("S250-A", self.version, UPDATE_SCRIPT_TAR)
        self._rsync(src, UPDATE_OPERATE_FOLDER)
    
    def _rsync(self, src, dest):
        cmd = 'rsync -cavz -e ssh %s@%s:~/%s %s' % (self.user, self.server, src, dest)
        self.logger.info("DO COMMAND: %s" % cmd)
        
        child = pexpect.spawn(cmd)
        try:
            child.setlog(sys.stdout)
        except:
            child.logfile=sys.stdout
        
        pwdSent = False
        try:
            index = child.expect(['continue connecting', 'password:'], timeout = 3600)
            if index == 0:
                child.sendline("yes")
                
                index = child.expect('password:', timeout = 3600)
                if index == 0:
                    child.sendline(self.pwd)
                    pwdSent = True
            elif index == 1:
                child.sendline(self.pwd)
                pwdSent = True
            else:
                raise Exception("Except Unknown Error")
            
            if pwdSent == False:
                raise Exception("Rsync failed: unknown error!")
            
            index = child.expect(['rsync error:', 'Permission denied'], timeout = 3600)
            if index == 0:
                raise RsyncException("Rsync Error: Rsync failed")
            elif index == 1:
                raise RsyncException("Rsync Error: Permission denied, please check your username and password.")
        
        except pexpect.TIMEOUT:
            raise RsyncException("Rsync Error: Rsync Timeout!")
        except pexpect.EOF:
            self.logger.info("Rsync Finished!")
        except Exception:
            self.logger.error("Rsync Error: %s" % traceback.format_exc())
            raise
        finally:
            child.close()
    
    def _doCommand(self, cmd):
        self.logger.info("command: %s" % cmd)
        os.system(cmd)
        
    def _update(self):
        self.logger.info("Doing update...")
        
        os.chdir("%s" % UPDATE_OPERATE_FOLDER)
        self._doCommand("tar -zxvf %s" % (UPDATE_SCRIPT_TAR))
        
        if self.test == True:
            self._doCommand("./%s -t -v %s" % (UPDATE_SCRIPT_NAME, self.version))
        else:
            self._doCommand("./%s -r -v %s" % (UPDATE_SCRIPT_NAME, self.version))
        
        self.logger.info("Update Done.")
    
    def reset_log_partition(self):
        if os.path.exists("/mmvar"):
            if os.path.exists(os.path.join(KIOSK_HOME, "kiosk/var")):
                if not os.path.islink(os.path.join(KIOSK_HOME, "kiosk/var")):
                    raise "Conflict between /home/mm/kiosk/var and /mmvar/var, please check kiosk var data."                
            else:
                os.system("ln -s /mmvar/var %s"%(os.path.join(KIOSK_HOME, "kiosk/var")))

    def reset_bin_partition(self):
        if  os.path.exists("/cereson"):
            if not os.path.islink(os.path.join(KIOSK_HOME, "kiosk/bin")):
                os.system("echo howcute121|sudo -S rm /cereson/bin -rf;echo howcute121|sudo -S mv %s %s" %(os.path.join(KIOSK_HOME, "kiosk/bin"),"/cereson/"))
                os.system("ln -s /cereson/bin %s"%(os.path.join(KIOSK_HOME, "kiosk/bin")))
        
   
	    
		
    def run(self):
        try:
            self._selfLock()
            os.system("rm ~/.ssh/known_hosts")
            
            self._getUpdateScript()
            self._update()
            self.reset_bin_partition()
        except Exception, ex:
            self.logger.info(str(ex))
        finally:
            self._selfUnlock()
    
class RsyncException(Exception):
    pass

class FilelockException(Exception):
    pass

if __name__ == "__main__":
    usage = "usage: %prog [-r real]|[-t test] [-v version]"
    
    parser = optparse.OptionParser(usage)
    parser.add_option("-r", "--real", action="store_false",
                      dest="test", help="update kiosk from released version.", default=False)
    parser.add_option("-t", "--test", action="store_true",
                      dest="test", help="update kiosk from test version.")
    parser.add_option("-v", "--version", action="store",
                      dest="version", help="set release version.", default="latest")
    
    options, args = parser.parse_args()
    if len(args) != 0:
        parser.error("invalid arguments\ntry \"update -h\" for more information")
    
    u = Update(options.test, options.version)
    u.run()
    
    sys.exit(0)

