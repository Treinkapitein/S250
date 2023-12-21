
"""
DCEApp represents the DCE runtime
"""
import sys,os
sys.path.insert(0,os.pardir)
import pyDCE
import pyDCE.dcecommon
import pyDCE.transport
import pyDCE.exception
import pyDCE.proxy
import pyDCE.endpoint
import pyDCE.log
import pyDCE.adapter
import pyDCE.config
import threading
#global LOG

class QUIET:
    def __init__(self):
        pass
    def __call__(self):
        pass


class DCEApp(pyDCE.dcecommon.UApplication):
    def on_init(self):
        self._log=pyDCE.log.init_log(pyDCE.config.LOG_FILE_NAME)
        self._trace1=self._log.debug
        self._trace2=self._log.debug
        self._trace3=self._log.debug
        self._client_conn_mgr=None
       # LOG=self._log
    
    def __getattr__(self,name):
 #       self._log.debug("ThreadID:"+ threading.currentThread.__name__)
        if name=="TRACE" or name=="DEBUG":
            return self._log.debug
        if name=="TRACE1" :
            return self._trace1
        if name=="TRACE2" :
            return self._trace2
        if name=="TRACE3" :
            return self._trace3
        elif name=="WARN":
            return self._log.warn
        elif name=="ERROR":
            return self._log.error
        elif name=="FATAL":
            return self._log.fatal
#        else:
#            return QUIET()
     #@param addr "proxy_name@protocol address"
     # "dbnode@ssl 192.168.1.188:8000"        
     # "dbnode@ns 192.168.1.188:8000"        
     # "dbnode@sns 192.168.1.188:8000"        
    def stringToProxy(self,addr="",simple=False):
        #print "stringToProxy ", addr     
        try:
            addr=addr.split("@")
            name=addr[0].strip()
            addr=addr[1]
            ed=pyDCE.endpoint.Endpoint.getEndpoint(addr)
        except Exception,ex:
            self.ERROR(ex)
            raise ex
        tp=ed.createTransport()
 
        if not simple:
            p=pyDCE.proxy.Proxy(conn=tp , obj=name)
            tp.setProxy(p) 
        else:
            p=pyDCE.proxy.SimpleProxy(conn=tp,obj=name)
        #tp.createProxy(name) # createProxy is not used for it cannot return weakref
          # currently there can be only one ConnectionManager in the client 
        if not self._client_conn_mgr and not simple:
            self._client_conn_mgr=pyDCE.transport.ClientConnectionManager()
            self._client_conn_mgr.start()
        if not simple:
            tp._proxy.setConnectionManager(self._client_conn_mgr)
        if not addr:#reverse proxy
            tp._client=0
        return   p    #tp._proxy
    
    def stringToAdapter(self,str=""):
        #print "stringToAdapter"
        try:
            str=str.split("@")
            name=str[0].strip()
            str=str[1]
            print str
            ed=pyDCE.endpoint.Endpoint.getEndpoint(str)
          #  print "got endpoint"
        except Exception,ex:
            self.ERROR(ex)
            ed=None #reverse adapter
        ad=pyDCE.adapter.Adapter(ed,name)
        # PerConnectionThread, so far
        if ed: # reverse adapter shares the global connection manager(ClienetConnectionManager) with APP
         #   print "setConnectionManager"
            ad.setConnectionManager(pyDCE.transport.PerConnectionManager())
        return ad
    
    def createProxy(self):
        pass
    
    def terminate(self):
        pass
    
    def on_exit(self):
        pass
    def do_loop(self):
        pass
    

        
