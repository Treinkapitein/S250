#!/usr/bin/python

"""
    network monitor
"""

try:
    import psyco
    psyco.full()
except:
    pass

import os
import sys
import time
import threading
import struct
import fcntl
from socket import *

import logging
from logging import handlers

#import config
# Read the home dir
def homePath():
  KIOSK_HOME = '/etc/kioskhome'
  fd = file(KIOSK_HOME, 'r')
  KIOSK_HOME_DIR = fd.readline().rstrip()
  fd.close()
  return KIOSK_HOME_DIR

LOGGING_LOG_FILE = homePath()+'/kiosk/var/log/netmonitor.log'

TEST_ONCE_TIMEOUT = 5
TEST_HOST_PORT_PAIRS = [('upg1.waven.com', 443),('umg.cereson.com',
8673),('umgdl.waven.com', 80),('atlas.cereson.com',
7675),('atlas.cereson.com', 22)]

TEST_DNS_SERVER_IP = ("192.33.4.12", "192.33.4.12", "202.96.209.5")

NET_INTERFACE = 'eth0'

HDD = '/dev/sda'


def initlog(name):
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)

    hConsole = logging.StreamHandler()
    hConsole.setLevel(logging.DEBUG)
    hConsole.setFormatter(logging.Formatter('%(asctime)s %(name)s  %(levelname)s \t %(message)s'))
    log.addHandler(hConsole)

    hFile = handlers.TimedRotatingFileHandler(config.LOGGING_LOG_FILE, 'D', 1, 3)
    hFile.setLevel(logging.INFO)
    hFile.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s \t %(message)s'))
    log.addHandler(hFile)

    return log


class NetworkMonitor( threading.Thread ):
    def __init__(self):
        self._stopEvent = threading.Event()
        self._interval = 5
        threading.Thread.__init__(self, name='NetworkMonitor')
        
        self.last_rx = 0
        self.last_tx = 0
        self.rx_rate = 0
        self.tx_rate = 0
       
        data = self._get_current_ip()
        fd = open("./ipadrress", 'w')
        fd.write(data)
	fd.close()

    def _get_current_ip(self,ifname=config.NET_INTERFACE):
        """
        w,r = os.popen2("/sbin/ifconfig eth0")
        data = r.read()
        r.close()
        w.close()
        num = data.find("inet addr:")+10
        num2 = data.find("Bcast:")
        data = data[num:num2].split()[0]
	"""
        """
        w,r = os.popen2("/sbin/ifconfig  %s | sed -n 's/.*inet addr:\\([^ ]*\\).*/\\1/p'" %(config.NET_INTERFACE))
        data = r.read()
        r.close()
        w.close()
	"""	

        s = socket(AF_INET, SOCK_DGRAM)
        try:
            data = inet_ntoa(fcntl.ioctl( s.fileno(), 0x8915,  # SIOCGIFADDR
            struct.pack("256s", ifname[:15]))[20:24])
        except:
            data = "0.0.0.0"

	return data
    """
    def _check_ethernet_link(self,ifname=config.NET_INTERFACE):
        w,r = os.popen2("/sbin/mii-tool  %s | grep 'link ok'" %(ifname))
        data = r.read()
        r.close()
        w.close()

        return data
    """

    def _check_ethernet_link(self,ifname=config.NET_INTERFACE):
        w,r = os.popen2("/usr/sbin/ethtool  %s | grep 'Link detected: yes'" %(ifname))
        data = r.read()
        r.close()
        w.close()

        return data     

    def _check_network_byicmp(self, ip):
        count = 1
        w,r = os.popen2("ping %s -c%d" %(ip,count))
        data = r.read()
        r.close()
        w.close()
        res = data.find("ttl")
        if res != -1:
           return True
        else:
	   return False

    
    def _get_gateway_ip(self):
        w,r = os.popen2("/sbin/route -n")
        data = r.readline().split()
        while data:
            gw = data[1]
            data = r.readline().split()

        r.close()
        w.close()

        return gw

    def _ip_conflict_detection(self, ip, ifname=config.NET_INTERFACE):
        count = 1
        w,r = os.popen2("arping %s -D -c%d -I%s" %(ip,count,ifname))
        data = r.read()
        r.close()
        w.close()
        res = data.find("reply")
        if res != -1:
           return True
        else:
	   return False
    
    def _dig(self, url):
        ttl = ""
        w,r = os.popen2("dig %s | grep %s | grep -v DiG" %(url, url))
        data = r.readline().split()
        while data:
            ttl = data[1]
            data = r.readline().split()
        r.close()
        w.close()
        if ttl == "":
            return -1
        elif ttl == '0':
            return -2
        else:
            return 0 

    def run(self):
        while not self._stopEvent.isSet():

	    res = self.check_network()
            if res == -1:
                self.restart_network()
	    elif res == -2:	
	        continue
            else:
                self.update_statistic()
            
            self._stopEvent.wait(self._interval)

            current_ip = self._get_current_ip()
            fd = open("./ipadrress", 'r')
	    old_ip = fd.readline()
	    fd.close()
	    if current_ip == old_ip:
                trace.debug("[NetworkMonitor check_network] IP no change")
	    else:
                trace.warning("[NetworkMonitor check_network] IP has been change")
                fd = open("./ipadrress", 'w')
                fd.write(current_ip)
                fd.close()

    def join(self, timeout=None):
        self._stopEvent.set()
        threading.Thread.join(self, timeout)

    def check_network(self):
        if self._check_ethernet_link() != "":
            if os.path.exists("/tmp/link.disconnected"):
	        trace.info("[NetworkMonitor check_network] Link ok")
                os.remove("/tmp/link.disconnected")
                
        else:
            for i in xrange(10):
                if self._check_ethernet_link() == "" and os.path.exists("/tmp/link.disconnected"):
                    time.sleep(1)
                    return -2
                elif self._check_ethernet_link() == "" and i == 9:
	            trace.info("[NetworkMonitor check_network] No link")
                    os.system("touch /tmp/link.disconnected")
                    os.system("date > /tmp/link.disconnected")
                    time.sleep(1)
                    return -2
                elif self._check_ethernet_link() != "":
                    if os.path.exists("/tmp/link.disconnected"):
                        os.remove("/tmp/link.disconnected")
                        break
                else:
                    time.sleep(1)

        res = self._check_network_byicmp("127.0.0.1")
	if res == True:
            #trace.info("[NetworkMonitor check_network] TCP/IP protocol stack is ok")
            pass
	else:
            trace.error("[NetworkMonitor check_network] TCP/IP protocol stack is error")
	    return -2

        gw = self._get_gateway_ip()

        res = self._check_network_byicmp(gw)
	if res == True and gw != "0.0.0.0":
            #trace.info("[NetworkMonitor check_network] Local network is ok")
            pass
	else:
            trace.warning("[NetworkMonitor check_network] LAN connection failure,please check your network equipment and Driver")
            os.system("pkill dhclient3")
            os.system("dhclient3")
            gw = self._get_gateway_ip()
            res = self._check_network_byicmp(gw)
	    if res == True and gw != "0.0.0.0":
                trace.info("[NetworkMonitor check_network] DHCP bound ip ok")
	    else:
                trace.warning("[NetworkMonitor check_network] DHCP request failure")
            

        current_ip = self._get_current_ip()
        for i in xrange(10):
            res = self._ip_conflict_detection(current_ip,config.NET_INTERFACE)
	    if res == True:
                trace.warning("[NetworkMonitor check_network] Local area network IP conflicts")
	        break
            else:
                pass

        for pair in config.TEST_HOST_PORT_PAIRS:
            sd = socket(AF_INET, SOCK_STREAM)
            sd.settimeout(config.TEST_ONCE_TIMEOUT)
            try:
                sd.connect(pair)
                trace.debug('[NetworkMonitor check_network] Connect %s with port %d is ok' %(pair[0], pair[1]))
            except Exception, ex:
                trace.warning('[NetworkMonitor check_network] connect error: %s' %ex)
                res = self._dig(pair[0])
                if res == 0:
                    trace.warning("[NetworkMonitor check_network] Can not connect %s with port %d"  %(pair[0], pair[1]))
                elif res == -1:
                    flag = 0
                    for s in config.TEST_DNS_SERVER_IP:
                        r = self._check_network_byicmp(s)
	                if r == True:
                            trace.warning("[NetworkMonitor check_network] Network can connect, but the DNS server can not connect")
                            flag = 1
                            break
                    if flag == 0:
                        trace.warning("[NetworkMonitor check_network] Network can not connect")
                        return -1
                else:
                    trace.warning("[NetworkMonitor check_network] DNS datebase error")
        #return -1
    
    def restart_network(self):
        trace.info('[NetworkMonitor restart_network] ready to restart network')
        cmd = "/etc/init.d/networking restart"
        rev = os.system(cmd)
        print "rev ->", rev

    def update_statistic(self):
        #data = open('/proc/net/dev').readlines()[-1].split()
        fd = open("/proc/net/dev","r")
        data = fd.readline().split()
	ifname = ""
        while data:
	    if data[0].find(':') != -1:
	        ifname = data[0].split(':')[0]
	        rx = data[0].split(':')[1]

            if ifname == config.NET_INTERFACE:
	        if rx == "":
                    current_rx = int(data[1])
		else:    
                    current_rx = int(rx)
                current_tx = int(data[9])
        
                self.rx_rate = (current_rx - self.last_rx) / 5
                self.tx_rate = (current_tx - self.last_tx) / 5
        
                self.last_rx = current_rx
                self.last_tx = current_tx
        
                trace.debug('rx rate: %d' %self.rx_rate)
                trace.debug('tx rate: %d' %self.tx_rate)

	        fd.close()
		return
	    else:    
                data=fd.readline().split()
	
	fd.close()
        trace.warning('[Statistics net transfer rate] Can not find network interface : %s' %config.NET_INTERFACE)

	
def main():
    networkMonitor = NetworkMonitor()
    networkMonitor.start()
    
    while True:
        time.sleep(1)
        print '......'
    

#########################
##### main rountine #####
#########################
if __name__ == '__main__':
    trace = initlog('MONITOR')
    main()
