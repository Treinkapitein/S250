
import sys,os,time,random
sys.path.insert(0,os.pardir)
from threading import Thread
from config import *
from dynode import *
import pyDCE.exception
#import sys,os
import base64
import zlib
USER='kiosk'
PASSWORD='howcute121'
import dceapp

def DCE_APP():
    return dceapp.DCEApp()


class NodeClient:
    def init():
        pass
    """
    @param node_type: see dynode.py
    @return the node required
    note: we only find the address of the node but donot really connect to it,
          so if the first call of node failed you SHOULD CALL  get_node again
    """
    def get_node(ns ,node_type=NODE_TYPE_UNKNOWN):
	raise exception.CommunicationException("Can not get node address")
