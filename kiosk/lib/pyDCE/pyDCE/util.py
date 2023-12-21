
import socket
import uuid
import os,sys

"""
import httplib
import urllib
from xml.dom import minidom
from global_include import *
"""

"""
#get external ip of a machine itself in the cloud
def get_amazon_external_ip():
    conn = httplib.HTTPConnection("169.254.169.254")
    conn.request("GET", "/2007-08-29/meta-data/public-ipv4")
    res=conn.getresponse()

#get external using dydns's service    
def get_global_ip():
        try:
            proxies = {'http': 'http://localhost:3129'}
            dom = minidom.parse(urllib.urlopen('http://checkip.dyndns.com/',proxies=proxies))
            ip_line= dom.getElementsByTagName('body').item(0).firstChild.data;
            temp_list=ip_line.split(':')
            current_ip=temp_list[1]
            return current_ip.strip()
        except:
            DCE_APP().error("Error in Fetching data from checkip.dyndns.com ")
        return None 

"""

def getuuid():
    return uuid.uuid4()

"""
global help functions for network communication
"""
def getHostname(ip=None):
    try:
        if ip:
            (hn,alias,ips) = socket.gethostbyaddr(ip)
            return hn
        else:
            return socket.gethostname()
    except socket.error:
        return None

def getIPAddress(host=None):
    try:
        return socket.gethostbyname(host or getHostname())
    except socket.error:
        return None

def reuse_addr(sock):
    if os.name not in ('nt','dos','ce') and sys.platform!='cygwin':
        # only do this on a non-windows platform. Windows screws things up with REUSEADDR...
        try:
            sock.setsockopt ( socket.SOL_SOCKET, socket.SO_REUSEADDR,
                sock.getsockopt (socket.SOL_SOCKET, socket.SO_REUSEADDR) | 1)
        except:
            pass
