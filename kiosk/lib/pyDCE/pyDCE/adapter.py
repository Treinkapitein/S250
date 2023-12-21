
import sys,os
sys.path.insert(0,os.pardir)
import pyDCE
import pyDCE.protocol
import pyDCE.dcecommon
import pyDCE.exception
import pyDCE.dceapp
from threading import Thread,currentThread,RLock

def DCE_APP():
    return pyDCE.dceapp.DCEApp()

class Servant(pyDCE.dcecommon.DCEObject):
    def __init__(self,name):
        pyDCE.dcecommon.DCEObject.__init__(self)
        self.name=name
        
    def getName(self):
        return self.name


"""
when _endpoint_list==None, the adapter is a reverse adapter
"""
class Adapter(pyDCE.dcecommon.DCEObject, Thread):
    def __init__(self,endpoint=None,name=""):
        pyDCE.dcecommon.DCEObject.__init__(self)
        Thread.__init__(self)
        self._obj_map={}
        self._endpoint_list=[]
        self._lock=RLock()
        self._acceptor=None
        self._conn_mgr=None;
        self._name=name
        self.connectionLost=0
        if endpoint:
            self._endpoint_list.append(endpoint)
    
    def setConnectionManager(self,mgr):
        self._conn_mgr=mgr
    
    """
   currently we only support one endpoint per adapter
   this method is for future use
    """
    def addEndpoint(self,endpoint):
        self._endpoint_list.append(endpoint)
        
    """
    this method is used to set the transport for reverse adapter
    """
    def setTransport(self,transport):
        self._transport=transport
    
    def addObj(self,obj):
        try:
            self._lock.acquire()
            self._obj_map[obj.name]=obj
        finally:
            self._lock.release()
    
    def removeObj(self,name):
         try:
            self._lock.acquire()
            self._obj_map.pop(name)
         finally:
            self._lock.release()
                       
    def run(self):
        DCE_APP().DEBUG("Adapter running...")
        if self._endpoint_list:
            # run as normal adapter
            print "adapter running" 
            self._run()
        else:
            # run as reverse adapter 
            self._run_reverse()
            
    def dispatch(self,body,trans,tp=pyDCE.protocol.MSG_TYPE_REQUEST):
       # print body
        (u,obj_name,method_name,ctx,params)=body
        DCE_APP().DEBUG("Call %s.%s(%s)" % (obj_name,method_name,params)  )
        if self._obj_map.has_key(obj_name):
            try:
                ctx["_conn"]=trans
       # try:
                if tp==pyDCE.protocol.MSG_TYPE_REQUEST:
                    r=getattr(self._obj_map[obj_name],method_name)(ctx,*params[0],**params[1])
                elif tp==pyDCE.protocol.MSG_TYPE_REQUEST_GET_ATTR:
                    r=getattr(self._obj_map[obj_name],method_name)
                elif tp==pyDCE.protocol.MSG_TYPE_REQUEST_SET_ATTR:
                    print "**********", params
                    setattr(self._obj_map[obj_name],method_name,params)
                    print ">>>>>>>>>>", getattr(self._obj_map[obj_name],method_name)
                    r=""
           # except Exception,ex:
       #     r=getattr(self._obj_map[obj_name],method_name)(*params[0],**params[1])
                return r
            except AttributeError,ex:
                raise pyDCE.exception.NoMethodException("Object %s has no member function %s" % (obj_name,method_name))
            except TypeError,ex:
                print ex
                raise pyDCE.exception.ParameterErrorException(ex)
            except Exception,ex:
                raise
        else:
            raise pyDCE.exception.NoObjectException("No object found with name:%s" % obj_name)
        
    def on_connection_lost(self):
        self.connectionLost=1
        pass

    def on_read(self,trans):
        pass
    
    def on_accept(self,trans):
        DCE_APP().DEBUG("[Adapter.on_accept] got new connection")
        self._conn_mgr.add_conn(trans)
    
    def _run(self):
        # only the first endpoint is used, so far
        ed=self._endpoint_list[0]
        self._acceptor=ed.createAcceptor()
        while True:
            try:
                self._acceptor.open()
            except pyDCE.exception.CommunicateException,ex:
                DCE_APP().ERROR("[Adapter._run] %s" % ex)    
                continue
            try:
                self._acceptor.handle_connection(self)  #really not a good design
            except:
                DCE_APP().ERROR("[Adapter.run] got accept error")
                self._acceptor._sock.close()

    
    def _run_reverse(self):
        pass
