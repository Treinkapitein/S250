
import sys,os
sys.path.insert(0,os.pardir)
import pyDCE
import pyDCE.protocol
import pyDCE.exception
import pyDCE.dceapp
import pyDCE.dcecommon
from threading import Event,RLock,Condition
import pyDCE.config as config
import time
def DCE_APP():
    return pyDCE.dceapp.DCEApp()

class RemoteMethod:
    def __init__(self,proxy,obj,method,one_way,compress,ctx,timeout=config.DCE_DEFAULT_TIMEOUT,async=0 ):
        self._obj=obj
        self._proxy = proxy
        self._method = method
        self._one_way=one_way
        self._ctx=ctx
        self._compress=compress
        self._timeout=timeout
        self._async=async
    def __call__(self, *args, **kwargs):
        DCE_APP().DEBUG("RemoteMethod:%s,%s " % (args,kwargs) )
      #  return self.__send(self.__name, args, kwargs)
	to=self._timeout
	try:
	    to=kwargs['dce_timeout']
	except:
	    pass
        return self._proxy.dce_invoke(self._obj,self._method,self._one_way,self._compress,self._ctx,to,self._async,args,kwargs)
       # print "RemoteMethod",r
	#return r
"""
class RemoteMethodAttr:
    def __init__(self,prx,obj,name,value):
	self._proxy=prx
	self._obj=obj
	self._name=name
	self._value=value

    def __call__(self, *args, **kwargs):
        DCE_APP().DEBUG("RemoteMethodAttr:%s,%s " % (args,kwargs) )
        return self._proxy.dce_setattr(self._obj,self._name,self._value,args,kwargs)
""" 

class ReplyQItem:
    def __init__(self,cond,reply=None):
        self._cond=cond
        self._reply=reply

"""
a proxy is a stub of adapter
limitation:
a proxy can not be called corrently.
"""
class Proxy(pyDCE.dcecommon.DCEObject):
    def __init__(self,obj="",conn=None):
        pyDCE.dcecommon.DCEObject.__init__(self)
        self._conn=conn
        self._obj=obj #objectname
        self._lock=RLock()
        self._reply_map={}
        self._conn_mgr=None
	self.connectionLost=0
 
    def on_connection_lost(self):
	self.connectionLost=1

    def setConnectionManager(self,mgr):
        self._conn_mgr=mgr
   
    def _isReplyGot(self,rid):
        result=False
        try:
          #  self._lock.acquire()
            if self._reply_map[rid]._reply:
                result=True
        except:
            result=False
       # finally:
       #     self._lock.release()
        return result
    
    def _removeReq(self,rid):
        pass
    
#(request_uuid,reply status,body)
    def _return_reply(self,reply):
        (status,body)=reply
        DCE_APP().DEBUG("_return_reply: %i, %s" % (status,body) )
        if status==pyDCE.protocol.SUCCESS:
            return body
        elif status==pyDCE.protocol.DCE_EXCEPTION:
            raise body
        
    def dce_invoke(self,obj,method,dce_one_way,dce_compress,dce_ctx,dce_timeout,dce_async,vargs,kargs):
       # print method,vargs, kargs
       if kargs.has_key('dce_timeout'):
	       kargs.pop('dce_timeout')
       if kargs.has_key('dce_compress'):
	       kargs.pop('dce_compress')

       req=pyDCE.protocol.Request(obj,method,(vargs,kargs),dce_ctx,dce_one_way,dce_compress)
       p=pyDCE.protocol.Protocol()
       (rid,r)=p.RequestToRaw(req)
       DCE_APP().DEBUG("Send Reauest rid:"+ (rid) )
       
       if not dce_one_way:
           cond=Condition()
           try:
               self._lock.acquire()
               self._reply_map[rid]=ReplyQItem(cond)
           finally:
               self._lock.release()
      # print "in self : ", self._reply_map
       
       try:
           self._conn.lock()
           DCE_APP().DEBUG( "Sent Out Message length: %i" % len(r))
           self._conn.sendall(r,timeout=dce_timeout)#raise CommunicationException, TimeoutException
           DCE_APP().DEBUG("connection fd: "+ str(self._conn.fileno()))
       except Exception,ex:
           DCE_APP().ERROR("[Proxy] Error when sending message to remote")
           self._conn.close()
           self._conn.unlock()
           raise ex
       """
       except exception.CommunicateException,ex:
           self._conn.close()
           self._conn.unlock()
           raise ex
       except exception.TimeoutException,ex:
           self._conn.close()
           self._conn.unlock()
           raise ex
       """
    #   finally:
       self._conn.unlock()
           
       if dce_one_way:
           return
       cond.acquire()
       if self._isReplyGot(rid):
           cond.release()
           ret= self._return_reply(self._reply_map[rid]._reply)
           try:
               self._lock.acquire()
               self._reply_map.pop(rid)
           finally:
               self._lock.release()
           return ret
       if dce_timeout==0:
           DCE_APP().DEBUG("waiting #############")
           #cond.wait(config.DCE_DEFAULT_TIMEOUT)
	   import time
	   tick=time.time()
	   while time.time() - tick < config.DCE_DEFAULT_TIMEOUT:
	       cond.wait(2)
               if self._isReplyGot(rid):
		   break
	       #time.sleep(0)
	       if not self._conn._sock:
	           cond.release()
	           raise pyDCE.exception.TimeoutException("Call %s.%s timeout" % (obj,method))
       else:
	   tick=time.time()
	   while time.time() - tick < dce_timeout:
	       cond.wait(2)
	       if self._isReplyGot(rid):
	           break
	       if not self._conn._sock:
	           cond.release()
	       raise pyDCE.exception.TimeoutException("Call %s.%s timeout" % (obj,method))

       DCE_APP().DEBUG("waited #############")
       if self._isReplyGot(rid):
           ret= self._return_reply(self._reply_map[rid]._reply)
           try:
               self._lock.acquire()
               self._reply_map.pop(rid)
           finally:
               self._lock.release()
	   DCE_APP().DEBUG("proxy got result")
           return ret
       else:
           cond.release()
           raise pyDCE.exception.TimeoutException("Call %s.%s timeout" % (obj,method))
    
    def _invoke_sync(self):
        pass
    
    def _invoke_async(self):
        pass
    
    def __getattr__(self,dce_method_name,dce_one_way=0,dce_compress=0,dce_ctx={},dce_timeout=0,dce_async=0):
        return RemoteMethod(self,self._obj,dce_method_name,dce_one_way,dce_compress,dce_ctx,dce_timeout,dce_async)

    def __copy__(self):            # create copy of current proxy object
       # print "__copy__"
        p = Proxy(self._obj,self._conn)
        p._uuid=self._uuid
        return p
    def __deepcopy__(self, arg):
        #print "__deepcopy__"
        raise pyDCE.exception.NotImplementedException("cannot deepcopy a proxy")

    def __repr__(self):
       # print "__repr__"
        return "<"+self.__class__.__name__+" for "+str(self._uuid)+">"
    
    def __str__(self):
        #print "__str__"
        return repr(self)
    
    def __del__(self):
	#pass
#	import weakref
#	print "####proxy delete, connection ref: ", weakref.getweakrefcount(self._conn)
#	import sys
#	sys.exit(0)

	DCE_APP().DEBUG("connection fd to delete: " + str(self._conn.fileno()))
        try:
	    pass
	  #  self._conn_mgr.del_conn(self_conn) #will delete in ClientThreadManager  # may raise exception 
	except:
            pass
	try:
	    pass
	    
	#    self._conn.close()
     #       del self._conn 
        except:
	    pass
	   
    
    def __hash__(self):
        #print "__hash__"
        # makes it possible to use this class as a key in a dict
        return hash(self._uuid)
    
    def __eq__(self,other):
        #print "__eq__"
        # makes it possible to compare two proxies using objectID
        return hasattr(other,"_uuid") and self._uuid==other._uuid
    
    def __ne__(self,other):
       # print "__ne__"
        # makes it possible to compare two proxies using objectID
        return not hasattr(other,"_uuid") or self._uuid!=other._uuid
    
    def __nonzero__(self):
        #print "__nonzero__"
        return 1
    
    def __coerce__(self,other):
       # print "__coerce__"
        # makes it possible to compare two proxies using objectID (cmp)
        if hasattr(other,"_uuid"):
            return (self._uuid, other._uuid)
        return None

    # Pickling support, otherwise pickle uses __getattr__:
    def __getstate__(self):
        #print "__getstate__"
        # for pickling, return a non-connected copy of ourselves:
        copy = self.__copy__()
        copy._release()
        return copy.__dict__
    

    def __setstate__(self, args):
        #print "__setstate__"
        # this appears to be necessary otherwise pickle won't work
        self.__dict__=args

class SimpleProxy(Proxy):
    def __init__(self,obj="",conn=None):
        self.__dict__['_remoteattr_']=()
        Proxy.__init__(self,obj=obj,conn=conn)
#	self.__dict__["_localattr_"]=('_remoteattr','_obj','_conn','_lock','_reply_map','_conn_mgr')
	print "attr.........", self.__dict__
#	self.__dict__["_remoteattr"]=('test')
#	self._obj=None
    def __getattr__(self,name,dce_one_way=0,dce_compress=0,dce_ctx={},dce_timeout=0,dce_async=0):
#	print "getattr..." , name
	if name not in ("__getinitargs__", "__hash__","__eq__","__ne__"):
	    result=self.findattr(name)
            if result==1: # method
                DCE_APP().DEBUG( "remote method..." + str(name) )
                return RemoteMethod(self,self._obj,name,dce_one_way,dce_compress,dce_ctx,dce_timeout,dce_async)
            elif result: #remote attr
	        DCE_APP().DEBUG( "remote get attr..."+str(name) )
	        return self.dce_getsetattr(name,tp=pyDCE.protocol.MSG_TYPE_REQUEST_GET_ATTR)
	raise AttributeError

    def __setattr__(self,name,value):
	if name not in self.__dict__['_remoteattr_']:
	    self.__dict__[name]=value
	else:
	    DCE_APP().DEBUG( "remote set attr:"+str(name)+ " "+str( value ) )
	    return self.dce_getsetattr(name,value=value,tp=pyDCE.protocol.MSG_TYPE_REQUEST_SET_ATTR)

    def setRemoteAttrList(self,attr_list):
	self.__dict__['_remoteattr_']=attr_list


    def findattr(self, attr):
	if attr in self.__dict__['_remoteattr_']:
	    return 2
	return 1


    def dce_getsetattr(self,name,tp,value=""):
       req=pyDCE.protocol.Request(self._obj,name,(value),type=tp)
       p=pyDCE.protocol.Protocol()
       (rid,r)=p.RequestToRaw(req)
       DCE_APP().DEBUG("[SimpleProxy]Send getsetattr with rid:"+ (rid) )
       try:
           #print "Sent Out Message length: %i" % len(r)
           self._conn.sendall(r)#raise CommunicationException, TimeoutException
           DCE_APP().DEBUG("connection fd: "+ str(self._conn.fileno()))
         #  self._conn.waitr(timeout=dce_timeout)
           (reply_rid, reply_body)= self.on_recv()
           if reply_rid==rid:
	       return self._return_reply(reply_body)
	   raise pyDCE.exception.ProtocolException("AttrReply RID not matched")
       except Exception,ex:
           self._conn.close()
           self._conn=None
           raise ex

    def dce_invoke(self,obj,method,dce_one_way,dce_compress,dce_ctx,dce_timeout,dce_async,vargs,kargs):
       # print method,vargs, kargs
       if kargs.has_key('dce_timeout'):
           kargs.pop('dce_timeout')
       if kargs.has_key('dce_compress'):
           kargs.pop('dce_compress')
       req=pyDCE.protocol.Request(obj,method,(vargs,kargs),dce_ctx,dce_one_way,dce_compress)
       p=pyDCE.protocol.Protocol()
       (rid,r)=p.RequestToRaw(req)
       DCE_APP().DEBUG("[SimpleProxy]Send Reauest with rid:"+ (rid) )

       try:
           #print "Sent Out Message length: %i" % len(r)
           self._conn.sendall(r,timeout=dce_timeout)#raise CommunicationException, TimeoutException
           DCE_APP().DEBUG("connection fd: "+ str(self._conn.fileno()))
         #  self._conn.waitr(timeout=dce_timeout)
           (reply_rid, reply_body)= self.on_recv()
           if reply_rid==rid:
	       return self._return_reply(reply_body)
	   raise pyDCE.exception.ProtocolException("Reply RID not matched")
       except Exception,ex:
           self._conn.close()
           self._conn=None
           raise ex
	   
#    def __setattr__(self,name,value):
#        self.dce_setattr(name,value)


    def on_recv(self):
        DCE_APP().DEBUG("[SimpleProxy] on_rec...")
        p=pyDCE.protocol.Protocol()
	head_size=p.getHeadSize()
        print "on_recv2*****************^^^"
	head=self._conn.recvall(head_size)
	print "on_recv3*****************^^^"
	if len(head) !=head_size:
	    DCE_APP().DEBUG("[SimpleProxy] Connection closed by peer")
            raise pyDCE.exception.CommunicateException("Connection closed by peer")
        (type,size,codec)=p.parseHead(head)
        print (type,size,codec)
	body=""
        while size>0:
            buf=self._conn.recvall(size)##raise CommunicateException
	    body=body+buf
	    size = size - len(buf)
        try:
            body=codec.decode(body)
        except:
            DCE_APP().DEBUG("[SimpleProxy] Decode Message Body Error");
            raise pyDCE.exception.ProtocolException("[ClientThreadManager] Decode Message Body Error")

        if type==pyDCE.protocol.MSG_TYPE_REPLY:
            # print "reply body" ,body
            if len(body) < 3:
                raise pyDCE.exception.ProtocolException("Message Body Content Error")
            reply_rid=body[0]
            reply_body=(body[1],body[2])
            return (reply_rid, reply_body)
	else:
	    DCE_APP().ERROR("[SimpleProxy] Reply Message Wanted..")
	    raise pyDCE.exception.ProtocolException("Message Type Error")
    
    def __del__(self):
       try:
          self._conn.close()
       except:
           pass	   


if __name__=="__main__":
    prx=Proxy()
    prx.method("2",ll=[1,2])
