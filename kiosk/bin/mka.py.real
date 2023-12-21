#!/usr/bin/python
"""
Change Log:
    2012-03-14 Modified by Tim
        get the tunnel config from remote server
"""

__VERSION__ = '0.40'

try:
    import psyco
    psyco.full()
except:
    pass

import logging
from logging import handlers

import os
import sys
import time
import pexpect
import httplib
import urllib
import threading
import signal
import pwd

# Config for mka.
MAX_DUP = 120
current_dup = 0
last_text = None
TUNNEL_INTERVAL = 30
# The URL for getting the config for the tunnels
CONFIG_HOST = "cereson.mydvdkiosks.net"
CONFIG_URL = "/api/get_mka_conf"
# define middle server for reverse tunnel, and account info
TUNNEL_SERVER = "remote.cereson.com"
SYNC_TUNNEL_SERVER = "remote2.cereson.com"
TUNNEL_USER = "mka"
TUNNEL_PASSWORD = "howcute121"

DEBUG = 0
INFO = 1
ERROR = 2

# Config for mka2.
TUNNEL_PAIRS = {
        "CONN": {"ACCESS_NODE_PORT":10080, "KIOSK_PORT":20080,},
        "MOVIE": {"ACCESS_NODE_PORT":10380, "KIOSK_PORT":20380,},
        "UMG": {"ACCESS_NODE_PORT":10580, "KIOSK_PORT":20580,},
        "UPG": {"ACCESS_NODE_PORT":10280, "KIOSK_PORT":20280,},
        "UMS": {"ACCESS_NODE_PORT":10180, "KIOSK_PORT":20180,},
        "PYDCE": {"ACCESS_NODE_PORT":10680, "KIOSK_PORT":20680,},
        }

USER_ROOT = "/home/mm/"
try:
    f = open("/etc/kioskhome")
    USER_ROOT = f.read().strip()
    f.close()
except:
    pass

def initlog(logfile):
    log = logging.getLogger('MKA')
    log.setLevel(logging.DEBUG)

    hConsole = logging.StreamHandler()
    hConsole.setLevel(logging.DEBUG)
    hConsole.setFormatter(logging.Formatter('%(asctime)s  %(name)s  %(levelname)s \t %(message)s'))
    log.addHandler(hConsole)

    hFile = handlers.RotatingFileHandler(logfile, 'a', 5242880, 7) # 5M
    hFile.setLevel(logging.INFO)
    hFile.setFormatter(logging.Formatter('%(asctime)s  %(name)s  %(levelname)s \t %(message)s'))
    log.addHandler(hFile)

    #hSocket = handlers.SocketHandler('127.0.0.1', handlers.DEFAULT_TCP_LOGGING_PORT)
    #hSocket.setLevel(logging.DEBUG)
    #hSocket.setFormatter(logging.Formatter('%(asctime)s  %(name)s  %(levelname)s \t %(message)s'))
    #log.addHandler(hSocket)

    return log

# init log
log = initlog(os.path.join(USER_ROOT, "kiosk/var/log/mka.log"))
log.info("MKA VERSION: %s" % __VERSION__)

class MKA( object ):

    def __init__(self, mkaType):
        """ init """
        self.hostname = gethostname()
        self._type = mkaType
        self.last_text = ""
        self.current_dup = 0
        self.cmd = self.get_cmd()
        self.tunnel = None
        self.reset_file = ""
        self.alive_file = ""

    def open_tunnel(self):
        """ open tunnel """
        try:
            # Remove the .ssh/known_hosts
            try:
                os.remove('%s/.ssh/known_hosts' % os.environ['HOME'])
            except:
                pass

            self.log("[open]enter open_tunnel func", DEBUG)

            self.kill_tunnel()

            if not self.cmd:
                self.log("[open]can not get the cmd", ERROR)
                return False
            self.tunnel = pexpect.spawn(self.cmd)

            """
            # for debug
            try:
                self.tunnel.setlog(sys.stdout)
            except:
                self.tunnel.logfile = sys.stdout
            """

            index = self.tunnel.expect([pexpect.TIMEOUT, 'RSA key', 'password:'])

            if index == 0: # timeout
                self.log('[open]open_tunnel error, stage 0, timeout', INFO)
                return False
            elif index == 1: # 'first login'
                self.tunnel.sendline('yes\n')
                index = self.tunnel.expect([pexpect.TIMEOUT, 'password:'])

                if index == 0: # timeout
                    self.log('[open]open_tunnel error, stage 1, timeout', INFO)
                    return False

            self.tunnel.sendline(TUNNEL_PASSWORD+'\n')
            time.sleep(0.1)
            index = self.tunnel.expect(['[%s|mm]@.*'%TUNNEL_USER, 'forwarding', pexpect.TIMEOUT])

            if index == 0: # open tunnel successfully
                return True
            elif index == 1: # other tunnels may be opened
                self.kill_tunnel()
                self.log('[open]remote forwarding deny!', INFO)
                return False
            else: # timeout or something
                self.kill_tunnel()
                self.log('[open]login timeout', INFO)
                return False
        except Exception, ex:
            self.kill_tunnel()
            self.log('open_tunnel exception: %s' % ex, INFO)
            time.sleep(0.5)
            return False

    def check_tunnel(self):
        """ Check if the tunnel is alive. """
        if not self.tunnel:
            # the tunnel has not open
            self.kill_tunnel()
            return

        if not self.tunnel.isalive():
            self.log('[check](re)open tunnel failed', INFO)
            self.kill_tunnel()
            return

        # clear some obstruct
        self.tunnel.sendline("\n")
        index = self.tunnel.expect([pexpect.TIMEOUT, '\$'])
        if index == 0:# timeout
            self.kill_tunnel()
            return

        # Check if it is alive, 5 times.
        RETRY_TIME = 5
        for i in range(RETRY_TIME):
            time.sleep(1)
            self.tunnel.sendline("rm %s\r\n" % self.reset_file)
            index = self.tunnel.expect([pexpect.TIMEOUT, '\$'])

            if index == 0:# timeout
                self.log("[check]send rm command, but wait timeout, " \
                         "reset tunnel", INFO)
                self.kill_tunnel()
                return
            elif index == 1:
                pass

            try:
                result = self.tunnel.read_nonblocking(8192, 10)

                if result.find('No such file or directory') != -1:
                    #self.log('tunnel checking ok, sleeping\n', INFO)
                    pass
                elif result.count(self.reset_file) == 1:
                    self.log("[check]reset command:%s" % repr(result), DEBUG)
                    self.log("[check]recv reboot command, reset tunnel, " \
                             "time %s" % (i+1), INFO)
                    if i < RETRY_TIME-1:
                        continue
                    self.log("[check]recv reboot command, reset tunnel", INFO)
                    self.kill_tunnel()
                    return
                else:
                    self.log("[check]unexcept: %s\n" % repr(result), DEBUG)

                self.tunnel.sendline("touch %s\n" % self.alive_file)
                break
            except Exception, ex:
                self.log("[check]error: %s, reset tunnel" % ex, ERROR)
                self.kill_tunnel()
                return

        self.log("[check]checking tunnel OK", INFO)
        return True

    def close_tunnel(self):
        """ Close the tunnel. """
        try:
            if hasattr(self.tunnel, "close"): self.tunnel.close()
        except Exception, ex:
            self.log("[close] error: %s" % ex, ERROR)

    def kill_tunnel(self):
        """ Kill the tunnel. """
        pass

    def log(self, txt, log_type=INFO):
        """ log information
        txt(str):
        log_type(int): INFO/ERROR/DEBUG
        """
        txt = "MKA%s: %s" % (self._type, txt)

        if log_type == INFO:
            if self.last_text == txt:
                if self.current_dup < MAX_DUP:
                    log.debug(txt)
                    self.current_dup += 1
                else:
                    log.info(txt)
                    self.current_dup = 0
            else:
                self.last_text = txt
                log.info(txt)
                self.current_dup = 0
        elif log_type == ERROR:
            log.error(txt)
        else: # debug
            log.debug(txt)

    def hostname2port(self, prefix=2):
        """ Get the port according to hostname. """
        hostname = self.hostname

        tmp = chr(ord(hostname[5]) - 0x10)  # cover A to 1, B to 2, etc
        tmp += hostname[6:]

        return str(prefix) + tmp

    def get_cmd(self):
        """ Get linux command of mka or mka2. """
        return ""

class MKA1( MKA ):

    def __init__(self):
        """ Reverse ssh """
        super(MKA1, self).__init__(mkaType=1)
        self.reset_file = 'reset/%s' % self.hostname
        self.alive_file = 'online/%s' % self.hostname

    def get_cmd(self):
        """ Get linux command. """
        global TUNNEL_USER
        global TUNNEL_SERVER
        return "ssh -R %s:localhost:22 -R %s:localhost:5001 %s@%s" % (self.hostname2port(2),
                                                                      self.hostname2port(1),
                                                                      TUNNEL_USER,
                                                                      TUNNEL_SERVER)

    def kill_tunnel(self):
        """ Kill the tunnel. """
        try:
            i = 0
            while (os.system('pkill -9 -f "ssh -R"') == 0) or i >= 5:
                i += 1
                break
            self.close_tunnel()
        except Exception, ex:
            self.log("[killer]kill failed: %s" % ex, ERROR)

class MKA2( MKA ):

    def __init__(self):
        """ ssh """
        super(MKA2, self).__init__(mkaType=2)
        self.reset_file = 'reset/%s' % self.hostname
        self.alive_file = 'online/alive_%s' % self.hostname

    def get_cmd(self):
        """ Get linux command. """
        global TUNNEL_PAIRS
        global TUNNEL_USER
        global SYNC_TUNNEL_SERVER
        cmd = ""
        for tunnelName in TUNNEL_PAIRS.keys():
            cmd += "-L %s:localhost:%s " % (TUNNEL_PAIRS[tunnelName]["KIOSK_PORT"],
                                            TUNNEL_PAIRS[tunnelName]["ACCESS_NODE_PORT"],)
            if cmd == "":
                raise Exception("[getCmd]Error when get cmd from %s"%TUNNEL_PAIRS)
        cmd = "ssh %s %s@%s" % (cmd, TUNNEL_USER, SYNC_TUNNEL_SERVER)
        #cmd = "ssh %s mm@cereson.51vip.biz" % cmd
        return cmd

    def kill_tunnel(self):
        """ Kill the tunnel. """
        try:
            i = 0
            while (os.system('pkill -9 -f "ssh -L"') == 0) or i >= 5:
                i += 1
                break
            self.close_tunnel()
        except Exception, ex:
            self.log("[killer]kill failed: %s" % ex, ERROR)
            
def get_mka_conf():
    """ get the mka config from ZOPE of UMS
    """
    global TUNNEL_SERVER
    global SYNC_TUNNEL_SERVER 
    global TUNNEL_USER
    global TUNNEL_PAIRS
    http = None
    i = 1
    kiosk_id = gethostname()
    headers = {"Content-type": "application/x-www-form-urlencoded",
               "Accept": "text/plain",
               "Kiosk": kiosk_id}
    params = urllib.urlencode({"kiosk_id": kiosk_id})
    log.info("get mka config from server")
    downloaded = False
    while i <= 10:
        try:
            http = httplib.HTTPConnection(CONFIG_HOST)
            http.request("POST", CONFIG_URL, params, headers)
            http.sock.settimeout(30)
            res = http.getresponse()
            if res.status == 200:
                conf = eval(res.read())
                if conf.get("result") != "ok":
                    raise Exception(conf.get("zdata", ""))
                result = conf.get("zdata")
                log.info("conf: %s" % result)
                if result.get("TUNNEL_SERVER", ""):
                    TUNNEL_SERVER = result["TUNNEL_SERVER"]
                if result.get("SYNC_TUNNEL_SERVER", ""):
                    SYNC_TUNNEL_SERVER = result["SYNC_TUNNEL_SERVER"]
                if result.get("TUNNEL_PAIRS", ""):
                    TUNNEL_PAIRS = result["TUNNEL_PAIRS"]
                downloaded = True
                break
            else:
                raise Exception("can not get the config: status %s" % res.status)
        except Exception, ex:
            log.error("get_mka_conf %s: %s" % (i, ex))
            time.sleep(i)
        i += 1
    if not downloaded:
        log.warning("can not download the conf from server, use the default one")

def gethostname():
    """ Get the hostname of the kiosk. """
    f = open('/proc/sys/kernel/hostname', "r")
    try:
        hostname = f.read().strip()
    finally:
        f.close()
    return hostname

def maintain_tunnel():
    mka1 = MKA1()
    mka2 = MKA2()

    while True:
        log.debug("[maintain](re)open tunnel")
        try:
            # open tunnel for mka1
            i = 0
            if not mka1.check_tunnel():
                while not mka1.open_tunnel():
                    i += 1
                    log.error("[maintain]open failed for mka1, time %s" % i)
            # open tunnel for mka2
            i = 0
            if not mka2.check_tunnel():
                while not mka2.open_tunnel():
                    i += 1
                    log.error("[maintain]open failed for mka2, time %s" % i)

            # maintain the tunnels
            while True:
                # check the tunnels, if one of mka1 and mka2 is down, break
                if (not mka1.check_tunnel()) or (not mka2.check_tunnel()):
                    break
                time.sleep(TUNNEL_INTERVAL)
        except Exception, ex:
            log.error("[maintain] error: %s" % ex)

def main():
    """ main entry """
    get_mka_conf()
    maintain_tunnel()
    sys.exit(0)

if __name__ == "__main__":
    main()
