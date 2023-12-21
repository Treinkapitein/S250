
import sys,os
sys.path.insert(0,os.pardir)
import pyDCE
import pyDCE.transport
import pyDCE.exception
import pyDCE.endpoint
import pyDCE.protocol
import pyDCE.dcecommon
import pyDCE.dceapp
import threading
from threading import Thread,currentThread,RLock
import pyDCE.config as config
import socket
import select
import errno
from M2Crypto import SSL,X509
import weakref
import time
def DCE_APP():
    return pyDCE.dceapp.DCEApp()

class ConnectionManager(pyDCE.dcecommon.DCEObject):
    def __init__(self):
        pyDCE.dcecommon.DCEObject.__init__(self)
    
    def add_conn(self,conn):
        pass
    
    def del_conn(self,conn):
	    pass
    
    def delete_conn(self,conn):
        pass

class PerConnectionThread(Thread):
    def __init__(self,conn):
        Thread.__init__(self)
        self._conn=conn
        self._conn._stat=TRANSPORT_CONNECTED
 
    def on_recv(self,conn):
       # print "&&&&&&"
        p=pyDCE.protocol.Protocol()
        head_size=p.getHeadSize()
        head=conn.recvall(head_size)
        if len(head) !=head_size:
           # head=self._conn.recv(head_size)
            #print "XXXXXXXXXXXXX length:%i" % len(head)
           DCE_APP().DEBUG("[PerConnectionThread] Connection closed by peer")
	  # conn.close()
           raise pyDCE.exception.CommunicateException("[PerConnectionThread] Connection closed by peer")
        (type,size,codec)=p.parseHead(head)
        print (type,size,codec)
        if size>0:
            body=conn.recvall(size)##raise CommunicateException
            try:
               body=codec.decode(body)
            except:
                raise pyDCE.exception.ProtocolException("[PerConnectionThread] Decode Message Body Error")
            
        if type==pyDCE.protocol.MSG_TYPE_REQUEST or type==pyDCE.protocol.MSG_TYPE_REQUEST_GET_ATTR or type==pyDCE.protocol.MSG_TYPE_REQUEST_SET_ATTR:
            if len(body) < 5:
	        raise pyDCE.exception.ProtocolException("[PerConnectionThread] Message Body Content Error")
            rid=body[0]
	    DCE_APP().DEBUG("[PerConnectionThread] Got Request")
            exp=None
            if conn._adapter:
                try:
                   # print "ret "
                    ret=conn._adapter.dispatch(body,conn,tp=type)
                    print "ret .... ", ret
                except pyDCE.exception.NoMethodException,ex:
		    DCE_APP().DEBUG("[PerConnectionThread] NoMethodException")
                    exp=ex
                except pyDCE.exception.NoAttributeException,ex:
		    DCE_APP().DEBUG("[PerConnectionThread] NoAttributeException")
                    exp=ex
                except pyDCE.exception.CommunicateException,ex:
		    DCE_APP().DEBUG("[PerConnectionThread] CommunicateException")
                    exp=ex
                except pyDCE.exception.ParameterErrorException,ex:
		    DCE_APP().DEBUG("[PerConnectionThread] ParamsterErrorException")
                    exp=ex
		except pyDCE.exception.UserException,ex:
		    DCE_APP().DEBUG("[PerConnectionThread] UserException")
		    exp=ex
                except Exception,ex:
                    DCE_APP().DEBUG("[PerConnectionThread] " + str(ex) )
                    exp=pyDCE.exception.UnknownException(ex)
            else:
                exp=pyDCE.exception.NotImplementedException("")
            
          #  print "*****************^^^"
            if exp:
                DCE_APP().DEBUG("[PerConnectionthread] call exception.........:"+ str(exp))
                s=pyDCE.protocol.DCE_EXCEPTION
                b=exp
            else:
                DCE_APP().DEBUG("[PerConnectionThread] call success")
                s=pyDCE.protocol.SUCCESS
                b=ret
                
            r=pyDCE.protocol.Reply(rid,s,b)
            msg=p.ReplyToRaw(r)
            try:
                conn.lock()
                DCE_APP().DEBUG("[PerConnectionThread] send reply")
                conn.sendall(msg)#CommunicateException
            finally:
                conn.unlock()
                    
        elif type==pyDCE.protocol.MSG_TYPE_REPLY:
            #print "reply body" ,body
            if len(body) < 3:
                raise pyDCE.exception.ProtocolException("Message Body Content Error")
            rid=body[0]
            #print "@#@#@#@#" ,conn._proxy._reply_map
            if conn._proxy._reply_map.has_key(rid):
                try:
                    conn._proxy._reply_map[rid]._cond.acquire()
                    conn._proxy._reply_map[rid]._reply=(body[1],body[2])
                    conn._proxy._reply_map[rid]._cond.notify()
                finally:
                    conn._proxy._reply_map[rid]._cond.release()         
        else:
            DCE_APP().DEBUG("[PerConnectionThread] Unknown Message Ignoring...")
            
    def run(self):
        DCE_APP().DEBUG("[PerConnectionThread] Working...")
        p=select.poll()
        p.register(self._conn,select.POLLIN|select.POLLERR|select.POLLHUP|select.POLLNVAL)
        while True:
            try:
                   ret=p.poll()
            except Exception,x:
                if x.args[0] == errno.EINTR: #or (hasattr(errno, 'WSAEINTR') and x.args[0] == errno.WSAEINTR):
                    continue
                else:
                    raise
            if ret:
		e=0
		"""
		TODO: graceful close when exception
		"""
                for conn in ret:
                    if conn[1] == select.POLLIN:
                       # print "There are new incomming data..."
                        try:
                         #   print "!!!!!!!!!!!!!!!",self._conn_map[conn[0]]
                            self.on_recv(self._conn)
                        except pyDCE.exception.CommunicateException :
			    e=1
			    #self._conn=None
                            #self._conn.close()
                            #return 
                        except pyDCE.exception.ProtocolException:
			    e=1
                            #self._conn.close()
                            #self._conn=None
                            #return
                        except Exception,ex:
			    e=1
                            DCE_APP().FATAL(ex)
                            #return
            
                    elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP or conn[1]==select.POLLNVAL:
                        DCE_APP().DEBUG("[PerConnectionThread] Connection lost, Transport will close")
			e=1
                       # self._conn.close()
                       # self._conn=None
                    if e:
		        try:
			    self._conn.close()
                            self._conn=None
			except:
			    pass
			return  # end

    def __del__(self):
	DCE_APP().DEBUG("[PerConnectionThread] deleted...")

class PerConnectionManager:
    def __init__(self):
        pass
        
    def add_conn(self,conn):
        thd=PerConnectionThread(conn)
        thd.setDaemon(1)
        thd.start()
    
    def del_conn(self,conn):
        pass

#iterative connection manager for bidirectional communication
class ClientConnectionManager(Thread):
    def __init__(self):
        Thread.__init__(self)
        self._conn_map={}
        self._lock=RLock()
        
    def add_conn(self,conn):
	print "add_conn"
        try:
            self._lock.acquire()
            self._conn_map[conn.fileno()]=weakref.proxy(conn)
        finally:
	    pass
            self._lock.release()

    def del_conn(self,conn):
	print "del_conn"
        try:
            self._lock.acquire()
            self._conn_map.pop(conn)
        finally:
            self._lock.release()

    def on_recv(self,conn):
        print "&&&&&&"
        DCE_APP().DEBUG("[ClientThreadManager] on_rec...")
        p=pyDCE.protocol.Protocol()
        head_size=p.getHeadSize()
        print "on_recv2*****************^^^"
        head=conn.recvall(head_size)
        print "on_recv3*****************^^^"
        if len(head) !=head_size:
           # head=self._conn.recv(head_size)
           #print "XXXXXXXXXXXXX length:%i headlength:%i" % (len(head), head_size)
           DCE_APP().DEBUG("[ClientThreadManager] Connection closed by peer")
           raise pyDCE.exception.CommunicateException("Connection closed by peer")
        (type,size,codec)=p.parseHead(head)
        print (type,size,codec)
        if size>0:
            body=conn.recvall(size)##raise CommunicateException
            try:
               body=codec.decode(body)
            except:
	        DCE_APP().DEBUG("[ClientThreadManager] Decode Message Body Error");
                raise pyDCE.exception.ProtocolException("[ClientThreadManager] Decode Message Body Error")
            
        if type==pyDCE.protocol.MSG_TYPE_REQUEST:
	    #print "........REQUEST"
            if len(body) < 5:
                raise pyDCE.exception.ProtocolException("[ClientThreadManager] Message Body Content Error")
            rid=body[0]
            DCE_APP().DEBUG("[ClientThreadManager] Got Request")
            exp=None
            if conn._adapter:
                try:
                   # print "ret "
                    ret=conn._adapter.dispatch(body,conn)
                   # print "ret .... ", ret
                except pyDCE.exception.NoMethodException,ex:
                  #  print "NoMethodException"
                    exp=ex
                except pyDCE.exception.NoAttributeException,ex:
                  #  print "NoAttributeException"
                    exp=ex
                except pyDCE.exception.CommunicateException,ex:
                  #  print "CommunicateException"
                    exp=ex
                except pyDCE.exception.ParameterErrorException,ex:
                    exp=ex
		except pyDCE.exception.UserException,ex:
		    exp=ex
                except Exception,ex:
                    exp=pyDCE.exception.UnknownException("")
            else:
                exp=pyDCE.exception.NotImplementedException("")
            
           # print "*****************^^^"
            if exp:
                DCE_APP().DEBUG("[ClientThreadManager] call exception: "+ str(exp))
                s=pyDCE.protocol.DCE_EXCEPTION
                b=exp
            else:
                DCE_APP().DEBUG("[ClientThreadManager] call success")
                s=pyDCE.protocol.SUCCESS
                b=ret
            
            r=pyDCE.protocol.Reply(rid,s,b)
            msg=p.ReplyToRaw(r)
            try:
                conn.lock()
                conn.sendall(msg)#CommunicateException
            finally:
                conn.unlock()
                    
        elif type==pyDCE.protocol.MSG_TYPE_REPLY:
           # print "reply body" ,body
            if len(body) < 3:
                raise pyDCE.exception.ProtocolException("Message Body Content Error")
            rid=body[0]
            #print "@#@#@#@#" ,conn._proxy._reply_map
            if conn._proxy._reply_map.has_key(rid):
                try:
                    conn._proxy._reply_map[rid]._cond.acquire()
                    conn._proxy._reply_map[rid]._reply=(body[1],body[2])
                    conn._proxy._reply_map[rid]._cond.notify()
                finally:
                    conn._proxy._reply_map[rid]._cond.release()         
        else:
            DCE_APP().DEBUG("[ClientThreadManager] Unknown Message Ignoring...")
            
    def run(self):
        while True:
            p=select.poll()
            
            try:
                self._lock.acquire()
                if len(self._conn_map)==0:
		    time.sleep(0)
                    continue
                for c in self._conn_map:
                    p.register(c,select.POLLIN|select.POLLERR|select.POLLHUP|select.POLLNVAL)
            finally:
                self._lock.release()
         #   print self._conn_map
            ret=p.poll(200) ## add timeout
	    if ret:
	        for conn in ret:
                    e=0
		    if conn[1] == select.POLLIN:
		        print "There are new incomming data..."
		        try:
		            self.on_recv(self._conn_map[conn[0]])
                        except pyDCE.exception.CommunicateException :
                            e=1
			except pyDCE.exception.ProtocolException:
                            e=1
			except Exception,ex:
                            e=1
			    DCE_APP().FATAL(ex)
		    elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP or conn[1]==select.POLLNVAL:
                        e=1
                        DCE_APP().DEBUG("[ClientThreadManager] Connection lost, Transport will close")
                    if e:
                        try:
                            self._lock.acquire()
		   	    try:
                                r=self._conn_map.pop(conn[0])
                                r.close()
                            except:
			        pass
			finally:
	  		    self._lock.release()
           # return 

class Acceptor(pyDCE.dcecommon.DCEObject):
    def __init__(self,endpoint):
        pyDCE.dcecommon.DCEObject.__init__(self)
        self._endpoint=endpoint
        
    def getfd(self):
        pass
    
    def open(self):
        pass
        
    def accept(self):
        pass
    

TRANSPORT_CLOSED=0
TRANSPORT_CONNECTED=1
TRANSPORT_CLOSING=2
"""
abstract class
Currently:
one Transport is at most associate with one adapter and one proxy
"""
class Transport(pyDCE.dcecommon.DCEObject):
    def __init__(self,endpoint):
        pyDCE.dcecommon.DCEObject.__init__(self)
        self._endpoint=endpoint
        self._adapter=None
        self._proxy=None
        self._alive=False
        self._lock=RLock()
	self._local=None #threading.local()
        self._stat=TRANSPORT_CLOSED
    
    def setStorage(self):
	self._local=threading.local()

    def getStorage(self):
	if not self._local:
	    self._local=threading.local()
	return self._local

    def setAdapter(self,apt=None):
        try:
            self._lock.acquire()
            self._adapter=apt
        finally:
            self._lock.release()
    """
    def createProxy(self,objname):
        try:
            self._lock.acquire()
	    import proxy
            self._proxy=proxy.Proxy(conn=self,obj=objname)
	    #r=proxy.Proxy(conn=self,obj=objname)
            #self._proxy=weakref(r)
        finally:
            self._lock.release()
        return  r #self._proxy
    """
    def setProxy(self,prx=None):
        try:
            self._lock.acquire()
            self._proxy=weakref.proxy(prx) 
        finally:
            self._lock.release()
   
    def lock(self):
        self._lock.acquire()
        
    def unlock(self):
        self._lock.release()
        
    def open(self):
	pass
    
    def close(self):
        pass
    
    def send(self,buf,timeout=0):
        pass
    
    def recv(self,size,timeout=0):
        pass
    
    def sendall(self,buf,timeout=0):
        pass
    
    def recvall(self,size,timeout=0):
        pass
    
    def connected(self):
        if self._stat==TRANSPORT_CONNECTED:
            return True
        else:
            return False
    
    def fileno(self):
        pass
    
class TCPTransport(Transport):
    def __init__(self,endpoint,client=1):
        Transport.__init__(self,endpoint)
        self._sock=None
        self._client=client
        self._stat=TRANSPORT_CLOSED
    
    def attach(self,sock):
        self._alive=True
        self._sock=sock;
        
    def fileno(self):
        if self._sock:
            return self._sock.fileno()
        return None 
    
    def close(self):
        DCE_APP().DEBUG("[TCPTransport] socket closing")
        self._stat=TRANSPORT_CLOSED
	if self._proxy:
	       try:
	           self._proxy.on_connection_lost()
	       except:
		   pass
        if self._adapter:
               try:
                  self._adapter.on_connection_lost()
               except:
		   pass
        if self._sock:
            self._sock.close()
            self._sock=None
        
        
    def waitr(self,timeout=0):            
        p=select.poll()
        p.register(self,select.POLLIN|select.POLLERR|select.POLLHUP)
        ret=p.poll(timeout)
        if ret:
            for conn in ret:
                if conn[1] == select.POLLIN:
                    return
                elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP:
                    raise pyDCE.exception.CommunicateException("Read Poll Error")
        else:
            raise pyDCE.exception.TimeoutException("Read Poll Wait Timeout")
    
    def waitw(self,timeout):
            #raise exception.CommunicateException("Connection Closed")
        p=select.poll()
        p.register(self,select.POLLOUT|select.POLLERR|select.POLLHUP)
        ret=p.poll(timeout)
        if ret:
            for conn in ret:
                if conn[1] == select.POLLOUT:
                    return
                elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP:
                    raise pyDCE.exception.CommunicateException("Write Poll Error")
        else:
            raise pyDCE.exception.TimeoutException("Read Poll Write Timeout")
        
    def send(self,buf,timeout=0):
        self.open()
        if timeout!=0:
            self.waitw(timeout)
        try:
            return self._sock.send(buf)
        except:
            raise pyDCE.exception.CommunicateException("Send Error")
    
    def recv(self,size,timeout=0):
        self.open()
        if timeout!=0:
            self.waitr(timeout)
        try:
            return self._sock.recv(size)
        except:
            raise pyDCE.exception.CommunicateException("Recv Error")
    
    def sendall(self,buf,timeout=0):
     #   print "****************************send"
        self.open()
        if timeout!=0:
            self.waitw(timeout)
        try:
            if not self._sock.sendall(buf):
                return None
            else:
                raise Exception()
        except:
            raise pyDCE.exception.CommunicateException("SendALL Error")
            
    
    def recvall(self,size,timeout=0):
        self.open()
        if timeout!=0:
            self.waitr(timeout)
        try:
            return self._sock.recv(size,socket.MSG_WAITALL)
        except:
            raise pyDCE.exception.CommunicateException("RecvALL Error")

        
    def open(self):
         if self._client and self._stat!=TRANSPORT_CONNECTED:
           # print "MMMMMMMMMMMMMMMMMMMMMMMMMMM"
           # print "**********************connect %i %i" % (self._client,self._stat)
            self._sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM,0)
            while True:
                ret=self._sock.connect_ex(self._endpoint.getSockAddr())
                if ret==0:
                    self._stat=TRANSPORT_CONNECTED
		    try:
                        self._proxy._conn_mgr.add_conn(self)
                    except:
		        pass
                    return 
                elif ret==errno.EINTR:
                    continue
                else:
                    raise pyDCE.exception.CommunicateException("Cannot Connect to Destination")

    def _del_(self):
	self.close()
       # if self._stat!=TRANSPORT_CLOSED:
       #     print "delete socket......................"

class TCPAcceptor(Acceptor):
    def __init__(self,endpoint):
        Acceptor.__init__(self,endpoint)
        self._sock=None
        self._conn_list=[]
        
    def open(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            pyDCE.util.reuse_addr(self._sock)
            self._sock.bind((self._endpoint._ip,self._endpoint._port))
            self._sock.listen(config.DCE_LISTEN_BACKLOG)
        except socket.error,err:
            raise pyDCE.exception.CommunicateException(err)
    
    def accept(self):
        csock, addr = self._sock.accept()
        transport=TCPTransport( pyDCE.endpoint.TCPEndpoint(addr[0],addr[1]) )
        transport.attach(csock)
        transport._client=0
        transport._stat=TRANSPORT_CONNECTED
        return transport
    
    def handle_connection(self,adapt,timeout=0):
        p=select.poll()
        p.register(self,select.POLLIN|select.POLLERR|select.POLLHUP)
        while True:
         #   print "***********in handle_connection"
            try:
                if timeout:
                   ret=p.poll(timeout)
                else:
                   ret=p.poll()
            except Exception,x:
                if x.args[0] == errno.EINTR: # or (hasattr(errno, 'WSAEINTR') and x.args[0] == errno.WSAEINTR):
                    continue
                else:
                    raise
            if ret:
                for conn in ret:
                    if conn[1] == select.POLLIN:
		        try:
                            trans=self.accept()
                            trans.setAdapter(adapt)
                            adapt.on_accept(trans)
                        except:
			    pass
        
    def fileno(self):
        if self._sock:
            return self._sock.fileno()
        return None


class SSLCTX(object):
    def __new__(cls,*args,**kwargs):
        if '_inst' not in vars(cls):
            cls._inst=object.__new__(cls,*args,**kwargs)
        return cls._inst
    def __init__(self):
	    self._ctx = SSL.Context()
            self._ctx.load_cert(os.path.join(config.CERT_DIR, config.CLIENT_CERT),os.path.join(config.CERT_DIR, config.CLIENT_KEY_FILE),passphraseCallback)
            self._ctx.load_client_ca(os.path.join(config.CERT_DIR, config.CA_FILE))
            self._ctx.load_verify_info(os.path.join(config.CERT_DIR, config.CA_FILE))


class SSLTransport(TCPTransport):
    def __init__(self,endpoint,client=1):
        TCPTransport.__init__(self,endpoint,client)
        self._sock=None
        self._client=client
	self._ctx=None
        self._stat=TRANSPORT_CLOSED
    
    def attach(self,sock):
        self._alive=True
        self._sock=sock;
        
    def fileno(self):
        if self._sock:
            return self._sock.fileno()
        return None    
    def waitr(self,timeout=0):          
        DCE_APP().DEBUG("WAITR........")
        p=select.poll()
        p.register(self,select.POLLIN|select.POLLERR|select.POLLHUP)
        ret=p.poll(timeout)
        if ret:
            for conn in ret:
                if conn[1] == select.POLLIN:
                    return
                elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP:
                    raise pyDCE.exception.CommunicateException("Read Poll Error")
        else:
            raise pyDCE.exception.TimeoutException("Read Poll Wait Timeout")
    
    def waitw(self,timeout):
            #raise exception.CommunicateException("Connection Closed")
        p=select.poll()
        p.register(self,select.POLLOUT|select.POLLERR|select.POLLHUP)
        ret=p.poll(timeout)
        if ret:
            for conn in ret:
                if conn[1] == select.POLLOUT:
                    return
                elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP:
                    raise pyDCE.exception.CommunicateException("Write Poll Error")
        else:
            raise pyDCE.exception.TimeoutException("Read Poll Write Timeout")
    
    def close(self):
        #print "$$$$$$$$$$$$$$$$$$$$$$$$$$socket closing..."
	if self._proxy:
	    try:
                self._proxy.on_connection_lost()
            except:
                pass
        if self._adapter:
            try:
                self._adapter.on_connection_lost()
            except:
                pass
        self._stat=TRANSPORT_CLOSED
        if self._sock:
            try:
                #os.close(self._sock.fileno())
		self._sock.close()
                self._sock=None
            except:
                pass 
        

    def send(self,buf,timeout=0):
        self.open()
        if timeout!=0:
            self.waitw(timeout)
        try:
            return self._sock.send(buf)
        except:
            raise pyDCE.exception.CommunicateException("Send Error")
    
    def recv(self,size,timeout=0):
        self.open()
        if timeout!=0:
            self.waitr(timeout)
        try:
            return self._sock.recv(size)
        except:
            raise pyDCE.exception.CommunicateException("Recv Error")
    
    def sendall(self,buf,timeout=0):
     #   print "****************************send"
        self.open()
        if timeout!=0:
            self.waitw(timeout)
        try:
            self._sock.sendall(buf)
            #    return None
            #else:
            #    raise Exception()
        except Exception,ex:
         #   print "NNNNNNNNNNNNN"
	 #   print ex
	 #   self.close()
            raise pyDCE.exception.CommunicateException("SendALL Error: "+str(ex))
            
    
    def recvall(self,size,timeout=0):
	#print "recvall"
        self.open()
        if timeout!=0:
            self.waitr(timeout)
        try:
            return self._sock.recv(size)
        except  Exception,ex:
	 #   print "recvall exception", ex
	#    self.close()
            raise pyDCE.exception.CommunicateException("RecvALL Error: "+str(ex))
    
    def _get_context(self):
	self._ctx=SSLCTX()._ctx
        
    def open(self):
        if self._client and self._stat!=TRANSPORT_CONNECTED:
           # print "**********************connect %i %i" % (self._client,self._stat)
            self._get_context()
            self._sock=SSL.Connection(self._ctx)
            self._sock.postConnectionCheck=None
         #cert=s.get_peer_cert()
         #   self._sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM,0)
            while True:
	        print self._endpoint.getSockAddr()
                ret=self._sock.connect(self._endpoint.getSockAddr())
                print ret
		#break
               # ret=self._sock.connect_ex(self._endpoint.getSockAddr())
                if ret:
                    self._stat=TRANSPORT_CONNECTED
		    try:
                        self._proxy._conn_mgr.add_conn(self)
                    except:
		        pass
                    return 
               # elif ret==errno.EINTR:
               #     continue
                else:
                    raise pyDCE.exception.CommunicateException("Cannot Connect to Destination")

       
    def _del_(self):
	self.close()
#	print "@@@@@@@@@@@@@@@@@@@@@@@@@@@@ Connection close"
 #       if self._stat!=TRANSPORT_CLOSED:
 #           print "delete socket......................"


def passphraseCallback(v):
    return config.KEY_PASSPHRASE


class SSLAcceptor(TCPAcceptor):
    def __init__(self,endpoint):
        TCPAcceptor.__init__(self,endpoint)
        self.ctx=None
#        self._sock=None
#        self._conn_list=[]
    
    def _get_context(self):
	 if not self.ctx:
		try:                
		    self.ctx = SSL.Context('sslv23')
		    self.ctx.load_cert(os.path.join(config.CERT_DIR, config.SERVER_CERT),os.path.join(config.CERT_DIR, config.SERVER_KEY_FILE),passphraseCallback)
		    self.ctx.load_client_ca(os.path.join(config.CERT_DIR, config.CA_FILE))
		    self.ctx.load_verify_info(os.path.join(config.CERT_DIR, config.CA_FILE))
		
		    self.ctx.set_verify(SSL.verify_peer | SSL.verify_fail_if_no_peer_cert,10)
		    self.ctx.set_allow_unknown_ca(1)
		except Exception,ex:
		    print ex
		    raise pyDCE.exception.SSLException(ex) 
    
    def open(self):
	self._get_context()
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            pyDCE.util.reuse_addr(self._sock)
            self._sock.bind((self._endpoint._ip,self._endpoint._port))
            self._sock.listen(config.DCE_LISTEN_BACKLOG)
        except socket.error,err:
            raise pyDCE.exception.CommunicateException(err) ##shoud be system exception?
    
    def accept(self):
        csock, addr = self._sock.accept()
        transport=SSLTransport(pyDCE.endpoint.SSLEndpoint(addr[0],addr[1]) )
        _sock=SSL.Connection(self.ctx,csock)
        _sock.setup_addr(addr)
        _sock.set_accept_state()
        _sock.setup_ssl()
        _sock.accept_ssl()
        transport.attach(_sock)
        transport._client=0
        transport._stat=TRANSPORT_CONNECTED
        return transport
    
    """ 
    def handle_connection(self,adapt,timeout=0):
        p=select.poll()
        p.register(self,select.POLLIN|select.POLLERR|select.POLLHUP)
        while True:
         #   print "***********in handle_connection"
            try:
                if timeout:
                   ret=p.poll(timeout)
                else:
                   ret=p.poll()
            except Exception,x:
                if x.args[0] == errno.EINTR or (hasattr(errno, 'WSAEINTR') and x.args[0] == errno.WSAEINTR):
                    continue
                else:
                    raise
            if ret:
                for conn in ret:
                    if conn[1] == select.POLLIN:
                        trans=self.accept()
                        trans.setAdapter(adapt)
                        adapt.on_accept(trans)                        
           
    def fileno(self):
        if self._sock:
            return self._sock.fileno()
        return None
    """

    
