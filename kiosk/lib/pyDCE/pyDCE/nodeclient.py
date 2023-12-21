
import sys,os,time,random
sys.path.insert(0,os.pardir)
from threading import Thread
from pyDCE.config import *
from pyDCE.dynode import *
import pyDCE.exception
import pyDCE.dceapp
import base64
import zlib
USER='kiosk'
PASSWORD='howcute121'

def DCE_APP():
    return pyDCE.dceapp.DCEApp()


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
	r=None
	for i in range(0,3):
	 #   print "MMMMM", ns
            obj = DCE_APP().stringToProxy(ns,simple=True)
            r=obj.get_node_by_type(node_type)
	    #del obj
	    if r:
		break
	   # time.sleep(2)
	     
	if not r:
	    raise pyDCE.exception.CommunicateException("Can not get node address")
	(ip,port)=r
	#obj._conn.close()
	DCE_APP().DEBUG( "get_node address: "+str(ip)+":" + str( port))
	#print "MMMMMMMMMMMMMM"
	return (ip,port)
    
    def decode_buffer_col(col):
        return base64.b64decode(col)
        return  zlib.decompress(base64.b64decode(col),3)
    
    init = staticmethod(init)
    get_node = staticmethod(get_node)
    decode_buffer_col=staticmethod(decode_buffer_col)
    
    
if  __name__=="__main__":
    NodeClient.get_node("registry@ssl 127.0.0.1:9900",node_type=NODE_TYPE_ACCESS)
