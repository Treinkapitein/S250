
"""
Endpoint is an abstraction of Address or SAP, 
which represents not only network address but also LPC address etc.
"""
import sys,os
sys.path.insert(0,os.pardir)
#import dcecommon
import pyDCE
import pyDCE.transport
import pyDCE.dceapp
import pyDCE.exception
import pyDCE.config as config
import pyDCE.dynode as dynode
import pyDCE.nodeclient
def DCE_APP():
    return pyDCE.dceapp.DCEApp()


class Endpoint:
    def __init__(self):
        pass
    
    # tcp 192.168.1.1:9900
    def getEndpoint(s):
        s=s.strip()
        DCE_APP().DEBUG( "[Endpoint.getEndPoint] input:%s" % str(s) )
        if not s:
            DCE_APP().DEBUG("none endpoint")
            return None
        addr=s.split()
           
        if addr[0].strip().lower() == "tcp":
            addr=addr[1].strip().split(":")
            ip=pyDCE.util.getIPAddress(addr[0].strip())
            port=int(addr[1].strip())
            DCE_APP().DEBUG("[Endpoint.getEndPoint] TCP ip:%s,port:%s" % (ip,port))
            return TCPEndpoint(ip,port)
        elif addr[0].strip().lower() == "ssl":
            addr=addr[1].strip().split(":")
            ip=pyDCE.util.getIPAddress(addr[0].strip())
            port=int(addr[1].strip())
            DCE_APP().DEBUG("[Endpoint.getEndPoint] SSL ip:%s,port:%s" % (ip,port))
            return SSLEndpoint(ip,port)
        elif addr[0].strip().lower() == "sns":
       # print "getEndpoint sns"
            addr=addr[1].strip().split(":")
            ip=pyDCE.util.getIPAddress(addr[0].strip())
            port=int(addr[1].strip())
            type=addr[2].strip()
            #print "type:", type
            t=dynode.NODE_TYPE_UNKNOWN

            if type.lower()=="accessnode":
        #    print "accessnode..."
                t=dynode.NODE_TYPE_ACCESS
            elif type.lower()=="dbnode":
                t=dynode.NODE_TYPE_DB
            elif type.lower()=="dbnode_r":
                t=dynode.NODE_TYPE_DB_REPORT
            elif type.lower()=="monitornode":
                t=dynode.NODE_TYPE_MONITOR
            ad="registry@ssl %s:%i" % (ip,port) 
            DCE_APP().DEBUG("looking into "+str(ad))
            (ip,port)=pyDCE.nodeclient.NodeClient.get_node(ad,node_type=t)
            #print "got node"
            #print str(ip), str(port)
            DCE_APP().DEBUG("[Endpoint.getEndPoint] SNS ip:%s,port:%s" % (str(ip),str(port)))
            return SSLEndpoint(ip,int(port))
        elif addr[0].strip().lower() == "ns":
            #print "getEndpoint ns"
            addr=addr[1].strip().split(":")
            ip=pyDCE.util.getIPAddress(addr[0].strip())
            port=int(addr[1].strip())
            type=addr[2].strip()
            #print "type:", type
            t=dynode.NODE_TYPE_UNKNOWN

            if type.lower()=="accessnode":
     #   print "accessnode..."
                t=dynode.NODE_TYPE_ACCESS
            elif type.lower()=="dbnode":
                t=dynode.NODE_TYPE_DB
            elif type.lower()=="dbnode_r":
                t=dynode.NODE_TYPE_DB_REPORT
            elif type.lower()=="monitornode":
                t=dynode.NODE_TYPE_MONITOR

            ad="registry@tcp %s:%i" % (ip,port) 
            DCE_APP().DEBUG("looking into"+str(ad))
            (ip,port)=pyDCE.nodeclient.NodeClient.get_node(ad,node_type=t)
            #print str(ip), str(port)
            DCE_APP().DEBUG("[Endpoint.getEndPoint] NS ip:%s,port:%s" % (str(ip),str(port)))
            return TCPEndpoint(ip,int(port))
        else:
            raise pyDCE.exception.NotImplementedException("TCP(NS), SSL(SNS) are the only transport protocols we currently support")
           
    def getSockAddr(self):
        raise pyDCE.exception.NotImplementedException("Abstract class Endpoint cannot be instanced")
    
    def createAcceptor(self):
        raise pyDCE.exception.NotImplementedException("Abstract class Endpoint cannot be instanced")
           
    def createTransport(self):
        raise pyDCE.exception.NotImplementedException("Abstract class Endpoint cannot be instanced")
    
    getEndpoint=staticmethod(getEndpoint)

class TCPEndpoint(Endpoint):
    def __init__(self,ip="",port=config.PYDCE_DEFAULT_TCP_PORT):
        #Endpoint.__init__(self)
        self._ip=ip
        self._port=port
    
    def createAcceptor(self):
        return pyDCE.transport.TCPAcceptor(self)
    
    def createTransport(self): 
        return pyDCE.transport.TCPTransport(self)
    
    def getSockAddr(self):
        #print "getSockAddr"
        return (self._ip,self._port)
    
class SSLEndpoint(TCPEndpoint):
    def __init__(self,ip="",port=config.PYDCE_DEFAULT_SSL_PORT):
        #TCPEndpoint.__init__(self)
        self._ip=ip
        self._port=port
    
    def createAcceptor(self):
        return pyDCE.transport.SSLAcceptor(self)
    
    def createTransport(self): 
        return pyDCE.transport.SSLTransport(self)
    
