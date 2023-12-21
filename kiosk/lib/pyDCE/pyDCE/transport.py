

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
from threading import Thread, currentThread, RLock
import pyDCE.config as config
import socket
import select
import errno
from M2Crypto import SSL,X509
import weakref
import time
import util
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
#        self.name='PerConnectionThread'
 
    def on_recv(self,conn):
       # print "&&&&&&"
        DCE_APP().DEBUG("[PerConnectionThread] on_recv ...")
        p=pyDCE.protocol.Protocol()
        head_size=p.getHeadSize()
        head=conn.recvall(head_size)
        DCE_APP().DEBUG("[PerConnectionThread] recv head")
        if len(head) !=head_size:
           # head=self._conn.recv(head_size)
            #print "XXXXXXXXXXXXX length:%i" % len(head)
           DCE_APP().DEBUG("[PerConnectionThread] recv exception, connection may be closed by peer")
          # conn.close()
           raise pyDCE.exception.CommunicateException("[PerConnectionThread] Connection closed by peer")
        DCE_APP().DEBUG("[PerConnectionThread] parsing head")
        (type,size,codec)=p.parseHead(head)
        print (type,size,codec)
        if size>0:
            DCE_APP().DEBUG("[PerConnectionThread] recv body size:" + str(size))
            body=conn.recvall(size)##raise CommunicateException
            DCE_APP().DEBUG("[PerConnectionThread] recved body")
            try:
               body=codec.decode(body)
            except:
                DCE_APP().DEBUG("[PerConnectionThread] decode exception")
                raise pyDCE.exception.ProtocolException("[PerConnectionThread] Decode Message Body Error")
            
        if type==pyDCE.protocol.MSG_TYPE_REQUEST or type==pyDCE.protocol.MSG_TYPE_REQUEST_GET_ATTR or type==pyDCE.protocol.MSG_TYPE_REQUEST_SET_ATTR:
            if len(body) < 5:
                DCE_APP().DEBUG("[PerConnectionThread] decode body length error: too small size")
                raise pyDCE.exception.ProtocolException("[PerConnectionThread] Message Body Content Error")
            rid=body[0]
            DCE_APP().DEBUG("[PerConnectionThread] Got Request")
            exp=None
            if conn._adapter:
                try:
                   # print "ret "
                    DCE_APP().DEBUG("[PerConnectionThread] dispatch...")
                    ret=conn._adapter.dispatch(body,conn,tp=type)
                    DCE_APP().DEBUG("[PerConnectionThread] dispatch result: "+ str(ret))
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
                DCE_APP().DEBUG("[PerConnectionthread] dispatch exception: "+ str(exp))
                s=pyDCE.protocol.DCE_EXCEPTION
                b=exp
            else:
                DCE_APP().DEBUG("[PerConnectionThread] dispatch  successfully")
                s=pyDCE.protocol.SUCCESS
                b=ret
                
            r=pyDCE.protocol.Reply(rid,s,b)
            msg=p.ReplyToRaw(r)
            try:
                conn.lock()
                DCE_APP().DEBUG("[PerConnectionThread] send reply")
                conn.sendall(msg,timeout=20000)#CommunicateException
                DCE_APP().DEBUG("[PerConnectionThread] sent reply")
            finally:
                conn.unlock()
                    
        elif type==pyDCE.protocol.MSG_TYPE_REPLY:
            #print "reply body" ,body
            if len(body) < 3:
                DCE_APP().DEBUG("[PerConnectionThread] reply message too small")
                raise pyDCE.exception.ProtocolException("Message Body Content Error")
            rid=body[0]
            #print "@#@#@#@#" ,conn._proxy._reply_map
            if conn._proxy._reply_map.has_key(rid):
                try:
                    conn._proxy._reply_map[rid]._cond.acquire()
                    conn._proxy._reply_map[rid]._reply=(body[1],body[2])
                    conn._proxy._reply_map[rid]._cond.notify()
                    DCE_APP().DEBUG("[PerConnectionThread] notified the proxy waiting for the reply")
                except:
                    conn._proxy._reply_map[rid]._cond.release()         
                conn._proxy._reply_map[rid]._cond.release()         
        else:
            DCE_APP().DEBUG("[PerConnectionThread] Unknown Message Ignoring...")

    def _poll (self):
        cc=0
        while True:
            p=select.poll()
            try:
                p.register(self._conn._sock,select.POLLIN|select.POLLERR|select.POLLHUP|select.POLLNVAL)
            except:
                return # connection may be closed
            e=0
            ret=0
            try:
                 DCE_APP().DEBUG("[PerConnectionThread] Polling...fd:" + str(self._conn._sock.fileno()))
                 ret=p.poll(config.DEFAULT_TCP_POLL_TIMEOUT)
                 DCE_APP().DEBUG("[PerConnectionThread] Polling finished")
                 cc=cc+1
            except Exception,x:
                DCE_APP().DEBUG("[PerConnectionThread] Poll Exception...")
                if x.args[0] == errno.EINTR: #or (hasattr(errno, 'WSAEINTR') and x.args[0] == errno.WSAEINTR):
                    continue
                else:
                    try:
                        self._conn.close()
                        self._conn=None
                    except:
                        pass
                        DCE_APP().DEBUG("[PerConnectionThread] return and exit")
                        return  # end
            if ret:

                DCE_APP().DEBUG("[PerConnectionThread] Polling return :" +str(ret))
                """
                TODO: graceful close when exception
                """
                for conn in ret:
                    if conn[1] == select.POLLIN:
                        DCE_APP().DEBUG( "[PerConnectionThread] There are new incomming data")
                        try:
                         #   print "!!!!!!!!!!!!!!!",self._conn_map[conn[0]]
                            if self._conn._sock.fileno()==conn[0]:
                                DCE_APP().DEBUG("[PerConnectionThread] on_recv..." + threading.currentThread.__name__)
                                self.on_recv(self._conn)
                                DCE_APP().DEBUG("[PerConnectionThread] on_recv... out " + threading.currentThread.__name__)
                            else:
                                e=1
                        except pyDCE.exception.CommunicateException :
                            DCE_APP().DEBUG("[PerConnectionThread] CommunicateException")
                            e=1
                        except pyDCE.exception.ProtocolException:
                            DCE_APP().DEBUG("[PerConnectionThread] ProtocolException")
                            e=1
                        except Exception,ex:
                            e=1
                            DCE_APP().FATAL("[PerConnectionThread] " + str(ex) )
            
                    elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP or conn[1]==select.POLLNVAL or 1:
                        DCE_APP().DEBUG("[PerConnectionThread] Connection lost, Transport will close")
                        e=1
                       # self._conn.close()
                       # self._conn=None
            else:
                if cc > 20:
                    DCE_APP().DEBUG("[PerConnectionThread] timout many times")
                    cc=0
                time.sleep(0)
            if e:
                try:
                    self._conn.close()
                    self._conn=None
                except:
                    pass
                DCE_APP().DEBUG("[PerConnectionThread] return and exit")
                return  # end

    def _select (self):
        while True:
            readsocks=[self._conn]
            writesocks=[]
            exceptsocks=[self._conn]
            e=0
            try:
                r,w,ex=select.select(readsocks,writesocks,exceptsocks,2)
                if r:
                    try:
                        self.on_recv(self._conn)
                    except pyDCE.exception.CommunicateException :
                        e=1
                    except pyDCE.exception.ProtocolException:
                        e=1
                    except Exception,ex:
                        e=1
                        DCE_APP().FATAL(ex)
                elif w:
                    pass
                elif ex:
                    e=1
                else:
                    time.sleep(0.1)
            except:
                e=1
            if e:
                try:
                    self._conn.close()
                    self._conn=None
                except:
                    pass
                return  # end

    def run(self):
        threading.currentThread.__name__="[Per]" + str(util.uuid.uuid4())
        DCE_APP().DEBUG("[PerConnectionThread] Working...:"+ threading.currentThread.__name__)
        try:
            if sys.platform=='win32':
                return self._select()
            else:
                return self._poll()  
        except Exception,ex:
            DCE_APP().DEBUG("[PerConnectionThread] exit on exception: "+str(ex) )
            return
        except: 
            DCE_APP().DEBUG("[PerConnectionThread] exit on unknown exception: ")

    def __del__(self):
        DCE_APP().DEBUG("[PerConnectionThread] deleted... name is : " + threading.currentThread.__name__)

class PerConnectionManager:
    def __init__(self):
        pass
        
    def add_conn(self,conn):
        thd=PerConnectionThread(conn)
        thd.setDaemon(1)
   #     import time
   #     thd.name="PerConnectionThreadListen" + str(time.time())
        thd.start()
    
    def del_conn(self,conn):
        pass

#iterative connection manager for bidirectional communication
class ClientConnectionManager(Thread):
    def __init__(self):
        Thread.__init__(self)
        self._conn_map={}
        self._lock=RLock()

    def _select(self):
        pass
        while True:
            readsocks=[]
            writesocks=[]
            exceptsocks=[]
            e=0
            try:
                self._lock.acquire()
                if len(self._conn_map)==0:
                    time.sleep(0)
                    continue
                for c in self._conn_map.keys():
                    readsocks.append(c)
                    exceptsocks.append(c)
            finally:
                self._lock.release()
            DCE_APP().DEBUG("[ClientConnectionManager] select...")
            r,w,ex=select.select(readsocks,writesocks,exceptsocks,2)
            sk=None
            
            if r:
                try:
                    DCE_APP().DEBUG('[ClientConnectionManager] got data')
                    self.on_recv(self._conn_map[r[0]])
                except (pyDCE.exception.CommunicateException,pyDCE.exception.ProtocolException):
                    sk=r[0]
                    e=1
                except Exception,ex:
                    e=1
                    sk=r[0]
                    DCE_APP().FATAL(ex)
            elif ex:
                e=1
                sk=ex[0]
            else:
                time.sleep(0.1)
            if e:
                try:
                    self._lock.acquire()
                    try:
                        r=self._conn_map.pop(sk)
                        r.close()
                    except:
                        pass
                finally:
                    self._lock.release()

    def add_conn(self,conn):
        print "add_conn"
        try:
            self._lock.acquire()
            self._conn_map[conn.fileno()]=weakref.proxy(conn)
        finally:
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
        if size>0 and size < config.MAX_MESSAGE_LENGTH :
            body=conn.recvall(size)##raise CommunicateException
            try:
               body=codec.decode(body)
            except:
                DCE_APP().DEBUG("[ClientThreadManager] Decode Message Body Error");
                raise pyDCE.exception.ProtocolException("[ClientThreadManager] Decode Message Body Error")
        else:
            DCE_APP().DEBUG("[ClientThreadManager] size error: " + str(size) )
            raise pyDCE.exception.CommunicateException("size error: " + str(size))

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
    
    def _poll(self):
        while True:
            p=select.poll()
            try:
                self._lock.acquire()
                if len(self._conn_map)==0:
                    time.sleep(0)
                    continue
                for c in self._conn_map.keys():
                    try:
                       # if weakref.getweakrefcount(self._conn_map[c]) < 1:
                       #     pass
                           # raise Exception("weakref<1")
                        p.register(c,select.POLLIN|select.POLLERR|select.POLLHUP|select.POLLNVAL)
                    except Exception,ex:
                        DCE_APP().DEBUG("[ClientThreadManage] " + str(ex))
                        self._conn_map.pop(c)
            finally:
                self._lock.release()
         #   print self._conn_map
            ret=0
            ret=p.poll( ) #config.DEFAULT_TCP_POLL_TIMEOUT) ## add timeout
            if ret:
                for conn in ret:
                    e=0
                    if conn[1] == select.POLLIN:
                        print "There are new incomming data..."
                        try:
                            self.on_recv(self._conn_map[conn[0]])
                        except (pyDCE.exception.CommunicateException,pyDCE.exception.ProtocolException):
                            e=1
                        except Exception,ex:
                            e=1
                            DCE_APP().FATAL(ex)
                    elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP or conn[1]==select.POLLNVAL or 1:
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
            
    def run(self):
        if sys.platform=='win32':
            return self._select()
        else:
            return self._poll()

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
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
            del(self._sock)
            self._sock=-1
        except:
            pass
     #   if self._sock:
     #       self._sock.close()
     #       self._sock=-1
        
        
    def waitr(self,timeout=0):
        return 
        if  sys.platform!='win32':
            p=select.poll()
            p.register(self,select.POLLIN|select.POLLERR|select.POLLHUP)
            if timeout:
                ret=p.poll(timeout)
            else:
                ret=p.poll()
            if ret:
                for conn in ret:
                    if conn[1] == select.POLLIN:
                        return
                    elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP:
                        raise pyDCE.exception.CommunicateException("Read Poll Error")
            else:
                raise pyDCE.exception.TimeoutException("Read Poll Wait Timeout")
        else:
            rs=[self]
            ws=[]
            es=[self]
            r,w,ex=select.select(rs,ws,es,timeout)
            if r:
                return
            elif ex:
                raise pyDCE.exception.CommunicateException("Read Poll Error")
            else:
                raise pyDCE.exception.TimeoutException("Read Poll Wait Timeout")

    
    def waitw(self,timeout):
        return
            #raise exception.CommunicateException("Connection Closed")
        if  sys.platform!='win32':
            p=select.poll()
            p.register(self,select.POLLOUT|select.POLLERR|select.POLLHUP)
            if timeout:
                ret=p.poll(timeout)
            else:
                ret=p.poll()
            if ret:
                for conn in ret:
                    if conn[1] == select.POLLOUT:
                        return
                    elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP:
                        raise pyDCE.exception.CommunicateException("Write Poll Error")
            else:
                raise pyDCE.exception.TimeoutException("Read Poll Write Timeout")
        else:
            rs=[]
            ws=[self]
            es=[self]
            r,w,ex=select.select(rs,ws,es,timeout)
            if w:
                return
            elif ex:
                raise pyDCE.exception.CommunicateException("Read Poll Error")
            else:
                raise pyDCE.exception.TimeoutException("Read Poll Wait Timeout")

        
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
    
    def sendall(self,buf,timeout=config.DEFAULT_POLL_WRITE_TIMEOUT):
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
            
    
    def recvall(self,size,timeout=config.DEFAULT_POLL_READ_TIMEOUT):
        self.open()
        if timeout!=0:
            self.waitr(timeout)
        try:
          #  if sys.platform!='win32':
          #      return self._sock.recv(size,socket.MSG_WAITALL)
          #  else:
          #  return self._sock.recv(size)
            s=size
            buf=""
            while True:
                b=self._sock.recv(s)
                buf=buf+b
                s=s-len(b)
                if s==0 or not b:
                    return buf
        except Exception,ex:
            raise pyDCE.exception.CommunicateException("RecvALL Error:%s" % (str(ex)) )

        
    def open(self):
         if self._client and self._stat!=TRANSPORT_CONNECTED:
           # print "MMMMMMMMMMMMMMMMMMMMMMMMMMM"
           # print "**********************connect %i %i" % (self._client,self._stat)
            self._sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM,0)
            self._sock.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,1)
            self._sock.setblocking(1)
    
            """
            self._sock.setsockopt(socket.SOL_S0CKET,socket.SO_RCVTIMEO,config.DEFAULT_TCP_RECV_TIMEOUT)
            self._sock.setsockopt(socket.SOL_S0CKET,socket.SO_SNDTIMEO,config.DEFAULT_TCP_SEND_TIMEOUT)
            self._sock.setsockopt(socket.SOL_S0CKET,socket.SO_RCVBUF,config.DEFAULT_TCP_RECV_BUFFER)
            self._sock.setsockopt(socket.SOL_S0CKET,socket.SO_SNDBUF,config.DEFAULT_TCP_SEND_BUFFER)
            """
        #    print config.DEFAULT_TCP_KEEPALIVE_INTERVAL
            if sys.platform!='win32':
                self._sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL,config.DEFAULT_TCP_KEEP_INTERVAL)
                self._sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT,config.DEFAULT_TCP_KEEP_COUNT)
                self._sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE,config.DEFAULT_TCP_KEEP_IDLE)
            
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
        csock.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,1)
        if sys.platform!='win32':
            csock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL,config.DEFAULT_TCP_KEEP_INTERVAL)
            csock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT,config.DEFAULT_TCP_KEEP_COUNT)
            csock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE,config.DEFAULT_TCP_KEEP_IDLE)
        transport=TCPTransport( pyDCE.endpoint.TCPEndpoint(addr[0],addr[1]) )
        transport.attach(csock)
        transport._client=0
        transport._stat=TRANSPORT_CONNECTED
        return transport
    
    def handle_connection(self,adapt,timeout=0):
        if sys.platform=='win32':
            while True:
                readsocks=[self]
                writesocks=[]
                exceptsocks=[self]
                try:
                    #DCE_APP().DEBUG("Select Accept...")
                    r,w,ex=select.select(readsocks,writesocks,exceptsocks,2)
                    if r:
                        try:
                            trans=self.accept()
                            trans.setAdapter(adapt)
                            adapt.on_accept(trans)
                            DCE_APP().DEBUG("New connection Accepted")
                        except:
                            DCE_APP().DEBUG("accept error")
                            pass
                    elif w:
                        pass
                    elif ex:
                        pass
                    else:
                        time.sleep(0)
                except:
                    pass
        else:
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
        if  sys.platform!='win32':
            DCE_APP().DEBUG("WAITR........fd:"+str(self.fileno()) )
            p=select.poll()
            p.register(self,select.POLLIN|select.POLLERR|select.POLLHUP)
            if timeout:
                ret=p.poll(timeout)
            else:
                ret=p.poll()
            if ret:
                for conn in ret:
                    if conn[1] == select.POLLIN:
                        return
                    elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP:
                        raise pyDCE.exception.CommunicateException("Read Poll Error")
            else:
                raise pyDCE.exception.TimeoutException("Read Poll Wait Timeout")
        else:
            rs=[self]
            ws=[]
            es=[self]
            r,w,ex=select.select(rs,ws,es,timeout)
            if r:
                return
            elif ex:
                raise pyDCE.exception.CommunicateException("Read Poll Error")
            else:
                raise pyDCE.exception.TimeoutException("Read Poll Wait Timeout")

    
    def waitw(self,timeout):
            #raise exception.CommunicateException("Connection Closed")
        if  sys.platform!='win32':
            p=select.poll()
            p.register(self,select.POLLOUT|select.POLLERR|select.POLLHUP)
            if timeout:
                ret=p.poll(timeout)
            else:
                ret=p.poll()
            if ret:
                for conn in ret:
                    if conn[1] == select.POLLOUT:
                        return
                    elif conn[1]==select.POLLERR or conn[1]==select.POLLHUP:
                        raise pyDCE.exception.CommunicateException("Write Poll Error")
                    else:
                        raise pyDCE.exception.CommunicateException("Write Poll Unknown Error")

            else:
                raise pyDCE.exception.TimeoutException("Write Poll Timeout")
        else:
            rs=[]
            ws=[self]
            es=[self]
            r,w,ex=select.select(rs,ws,es,timeout)
            if w:
                return
            elif ex:
                raise pyDCE.exception.CommunicateException("Write Poll Error")
            else:
                raise pyDCE.exception.TimeoutException("Write Poll Timeout")

    
    def close(self):
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
        try:
            self._sock.close()
            del(self._sock)
            self._sock=-1
        except:
            pass
        """
        if self._sock:
            try:
                #os.close(self._sock.fileno())
                self._sock.close()
                self._sock=-1
            except:
                pass 
        """

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
    
    def sendall(self,buf,timeout=config.DEFAULT_POLL_WRITE_TIMEOUT):
        self.open()
        if timeout!=0:
            self.waitw(timeout)
        try:
            return self._sock.sendall(buf)
            """
            while True:
                self._sock.sendall(buf)
                if ret<1:
                    raise pyDCE.exception.CommunicateException("SendALL Error: "+str(ex))
                elif ret!=len(buf):
                    buf=buf[ret:]
                else:
                    return 
            #    return None
            #else:
            #    raise Exception()
            """
        except Exception,ex:
     #   print ex
     #   self.close()
            raise pyDCE.exception.CommunicateException("SendALL Error: "+str(ex))
            
    
    def recvall(self,size,timeout=config.DEFAULT_POLL_READ_TIMEOUT):
    #print "recvall"
        self.open()
        if timeout!=0:
            pass      #perhaps SSL has already received all the data
                      #so we can not simply call sock's poll
                      #or we will get timeout exception
                      #but is there an equivalent in SSL's interface?,TODO!!!
          #  self.waitr(timeout)
        buffer=""
        try:
           # return self._sock.recv(size)
            while size>0:
                DCE_APP().DEBUG("*********************** SSL RECV:"+str(size))
                b=self._sock.recv(size)
             #   if len(b)<1:
             #       raise pyDCE.exception.CommunicateException("RecvALL Error: "+str(ex))
                buffer=buffer+b
                size=size-len(b)
                if size==0 or not b:
                    return buffer
        except  Exception,ex:
    #   print "recvall exception", ex
    #    self.close()
            raise pyDCE.exception.CommunicateException("RecvALL Error: "+str(ex))
    
    def _get_context(self):
        self._ctx=SSLCTX()._ctx
        
    def open(self):
        if self._client and self._stat!=TRANSPORT_CONNECTED:
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
#    print "@@@@@@@@@@@@@@@@@@@@@@@@@@@@ Connection close"
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
        _sock.setblocking(1)
       # _sock.set_socket_write_timeout(config.DEFAULT_TCP_SEND_TIMEOUT)
       # _sock.set_socket_read_timeout(config.DEFAULT_TCP_RECV_TIMEOUT)
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

    

