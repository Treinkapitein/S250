#!/usr/bin/python
""" Access agent.
##
##  Change Log:
##      2009-11-03 Modified by Tim
##          Add watch dog for the kiosk side.
##
"""

__version__ = "0.0.1"

# Import from standard library.
import uuid
import cPickle
import socket
import select
import struct
import time
import logging
import logging.handlers
import pwd
import signal

#======================================================
#                    Configuration.
#======================================================
#dCeP
MAGIC = 0x64436550

MSG_TYPE_REQUEST = 0x01
MSG_TYPE_REPLY=0x02
MSG_TYPE_BATCH_REQUEST=0x03
MSG_TYPE_VALIDATE_CHALLENGE=0x04
MSG_TYPE_VALIDATE_CONNECTION=0x05
MSG_TYPE_CLOSE=0x06
MSG_TYPE_UNKNOWN=0xff

SUCCESS=0
AGENT_EXCEPTION=1
UNKNOWN_EXCEPTION=2

TRANSPORT_CLOSED=0
TRANSPORT_CONNECTED=1
TRANSPORT_CLOSING=2

DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_KIOSK_HOST = "127.0.0.1"
DEFAULT_KIOSK_PORT = 5001

DEFAULT_TIMEOUT = 15 # second

MAX_MESSAGE_LENGTH = 10485760 #10M

# Default log config.
USER_ROOT = "/home/mm/"
LOG_FILE_ROOT = "/home/mm/kiosk/var/log/"
LOG_LEVEL = logging.DEBUG
LOG_CONSOLE_LEVEL = logging.DEBUG
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
LOG_FILE_NAME = 'access_agent.log'
LOG_ROTATE_SIZE = 10*1024*1024 # 10M
LOG_ROTATE_COUNT = 5

from agent_config import *
from agent_exception import *

#======================================================
#                    getLogger
#======================================================
def getLogger(name=LOG_FILE_NAME,
              log_file_root=LOG_FILE_ROOT,
              format=LOG_FORMAT,
              level=LOG_LEVEL):
    logging.basicConfig(level=level,
                        format=format,
                        filemode='a')
    rootLogger=logging.getLogger(name)
    formatter=logging.Formatter(format)
    if 1:
        console=logging.StreamHandler()
        console.setLevel(LOG_CONSOLE_LEVEL)
        console.setFormatter(formatter)
        rootLogger.addHandler(console)
    if LOG_ROTATE_SIZE:
        rotateHandler=logging.handlers.RotatingFileHandler(os.path.join(log_file_root,name),
                                                'a',LOG_ROTATE_SIZE, LOG_ROTATE_COUNT)
        #rotateHandler.setLevel(level)
        rotateHandler.setFormatter(formatter)
        rootLogger.addHandler(rotateHandler)
    return rootLogger

log = getLogger()

#======================================================
#                    BaseObj
#======================================================
class AgentBase( object ):
    """ Base object.
    """
    def __init__(self, _uuid=None):
        if _uuid:
            self._id = _uuid
        else:
            self._id = str(uuid.uuid4())
        self.log = None
        self.log = log

    def __del__(self):
        #del self.log
        pass

    def _getID(self):
        return self._id

#======================================================
#      Protocol, DCECodec, Request, Reply
#======================================================
class AgentCodec( AgentBase ):
    """ Codec """
    def __init__(self):
        AgentBase.__init__(self)

    def __del__(self):
        AgentBase.__del__(self)

    def encode(self, body):
        try:
            return cPickle.dumps(body)
        except Exception, ex:
            raise CodecException(str(ex))

    def decode(self, msg):
        try:
            return cPickle.loads(msg)
        except Exception, ex:
            raise CodecException(str(ex))

class Request( AgentBase ):
    """ Request """
    def __init__(self, method_name, params, one_way=0, _type=MSG_TYPE_REQUEST):
        AgentBase.__init__(self)
        self._method_name = method_name
        self._params = params
        self._one_way = one_way
        self._type = _type

    def __del__(self):
        AgentBase.__del__(self)

class Reply( AgentBase ):
    """ Reply """
    def __init__(self, reqId, status, body, _type=MSG_TYPE_REPLY):
        AgentBase.__init__(self)
        self._rid = reqId
        self._status = status
        self._body = body
        self._type = _type

    def __del__(self):
        AgentBase.__del__(self)

class Protocol( object ):
    """ Protocol of Agent. """
    head_fmt = "!iBQ"
    head_size = struct.calcsize(head_fmt)
    def __init__(self):
        pass

    def RequestToRaw(self,req):
        if req._one_way:
            _id = "00000000-0000-0000-0000-000000000000"
        else:
            _id = str(req._id)
        codec = AgentCodec()
        body = codec.encode((_id, req._method_name, req._params))
        l = len(body)
        #print "body in RequestToRaw: %s %s" % (l, body)
        head = struct.pack(self.head_fmt, MAGIC, req._type, l)
        #print "head in RequestToRaw:", head
        return (_id, head+body)

    def ReplyToRaw(self, reply):
        codec = AgentCodec()
        body = codec.encode((reply._rid,reply._status,reply._body))
        l = len(body)
        #print "body in ReplyToRaw: %s %s" % (l, body)
        head=struct.pack(self.head_fmt, MAGIC, reply._type, l)
        #print "head in ReplyToRaw:", head
        return head+body

    def parseHead(self,head):
        try:
            head_info = struct.unpack(self.head_fmt, head)

            if head_info[0] != MAGIC:
                raise ProtocolException("Magic number error")

            codec = AgentCodec()
            #(type,bodysize,codec)
            return (head_info[1],head_info[2],codec)
        except Exception,ex:
            raise ProtocolException(str(ex))

    def getHeadSize(self):
        return self.head_size

#======================================================
#                  Endpoint
#======================================================
class Endpoint( AgentBase ):
    """ Endpoint server side or kiosk side. """
    def __init__(self, kioskId, timeout, side="server"):
        AgentBase.__init__(self)
        self.kioskId = kioskId
        self.timeout = timeout
        self._sock = None
        if side.lower() not in ("server", "kiosk"):
            raise UnkownException("Invalid Endpoint side %s"%side)
        self.side = side

    def __del__(self):
        AgentBase.__del__(self)

    def getHostPort(self):
        """ Get port. side is server/kiosk """
        port = ""
        host = "127.0.0.1"
        if self.side.lower() == "server":
            prefix = 1
            tmp = chr(ord(self.kioskId[5]) - 0x10)  # cover A to 1, B to 2, etc
            tmp += self.kioskId[6:]
            port = str(prefix) + tmp
            host = DEFAULT_SERVER_HOST
        elif self.side.lower() == "kiosk":
            port = str(DEFAULT_KIOSK_PORT)
            host = DEFAULT_KIOSK_HOST
        else:
            raise CommunicateException("Cannot get the port for %s" % side)

        if port and port.isdigit():
            return (host, int(port))
        else:
            raise CommunicateException("Invalid port %s" % port)

    def parseReqest(self, request):
        """ Parse request. """
        pass

    def parseReply(self, reply):
        """ Parse reply. """
        pass

    def onRecv(self, timeout=0):
        pass

    def recvall(self, size):
        pass

#======================================================
#                  Server side
#======================================================
class Server( Endpoint ):
    """ Server side. """
    def __init__(self, kioskId, timeout=DEFAULT_TIMEOUT):
        Endpoint.__init__(self, kioskId, timeout, "server")

    def __del__(self):
        try:
            Endpoint.__del__(self)
            if hasattr(self.sock, "close"):
                self.sock.close()
            del self.sock
        except:
            pass

    def doCommand(self, kioskId, funcName, params=()):
        """ Do command for kiosk.
        kioskId is just compatible to the DCE access node.
        """
        return self.__call__(funcName, params)

    def isOnline(self, kioskId):
        """ Check if the kiosk is online """
        return self.doCommand(kioskId, "isOnline")

    def __call__(self, funcName, params):
        """ """
        try:
            req = Request(funcName, params)
            protocol = Protocol()
            reqId, sendMsg = protocol.RequestToRaw(req)
            self.log.info("request(%s): %s %s" % (reqId,funcName, params))
            #print reqId, sendMsg
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            host, port = self.getHostPort()
            #print host, port
            self.sock.connect((host, port))
            self.sock.settimeout(self.timeout)
            # Retry 2 times.
            for i in range(2):
                self.sock.sendall(sendMsg)
                replyId, replyBody = self.onRecv()
                if replyId == reqId:
                    replyStatus, replyMsg = replyBody
                    if replyStatus == SUCCESS:
                        self.log.info("call success(%s)" % reqId)
                        return replyMsg
                    elif replyStatus == AGENT_EXCEPTION:
                        raise replyMsg
            if replyId != reqId:
                m = "Reply RID not matched, wanted:%s, got:%s" %(reqId,replyId)
                self.log.error(m)
                raise ProtocolException(m)
        except socket.error, ex:
            self.log.error("Socket error when execute %s %s: %s"%(funcName, params, ex))
            raise
        except Exception, ex:
            self.log.error("Error when execute %s %s: %s"%(funcName, params, ex))
            raise

    def onRecv(self, timeout=0):
        """ recieve reply. """
        protocol = Protocol()
        headSize = protocol.getHeadSize()
        head = self.recvall(headSize)
        #print "head", head
        if len(head) != headSize:
            raise CommunicateException("Connection may be closed by peer")

        _type, size, codec = protocol.parseHead(head)
        body = ""

        while size > 0:
            buf = self.recvall(size)##raise CommunicateException
            body = body + buf
            size = size - len(buf)

        try:
            body=codec.decode(body)
        except Exception, ex:
            raise ProtocolException("Decode Message Body Error: %s" % ex)

        if _type == MSG_TYPE_REPLY:
            if len(body) < 3:
                raise ProtocolException("Message Body Content Error")
            reply_rid = body[0]
            reply_body = (body[1],body[2])
            return reply_rid, reply_body
        else:
            raise ProtocolException("Message Type Error")

    def recvall(self, size):
        """ recieve all. """
        try:
            s = size
            buf = ""
            while True:
                b = self.sock.recv(s)
                buf = buf + b
                s = s - len(b)
                if s==0 or not b:
                    return buf
        except Exception,ex:
            raise CommunicateException("RecvALL Error:%s" % ex)

#======================================================
#                  Kiosk side
#======================================================
class Kiosk( Endpoint ):
    """ Kiosk side.
    """
    def __init__(self, kioskId, timeout=DEFAULT_TIMEOUT):
        Endpoint.__init__(self, kioskId, timeout, "kiosk")
        self._alive = True

    def __del__(self):
        Endpoint.__del__(self)
        self.setAlive(False)

    def run(self):
        try:
            all = []
            kioskSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            host, port = self.getHostPort()
            kioskSock.bind((host, port))
            kioskSock.listen(5)
            while True:
                self.setAlive(True)
                time.sleep(0.01)
                sock, addr = kioskSock.accept()
                #print sock, addr
                self.sock = sock
                try:
                    try:
                        self.onRecv()
                    finally:
                        self.sock.close()
                except Exception, ex:
                    self.log.error("Error onRecv for %s: %s"%(addr, ex))
        except Exception, ex:
            self.log.error("[Kiosk] Error in run: %s" % ex)
            self.setAlive(False)
            
    def isalive(self):
        return self._alive
        
    def setAlive(self, alive=True):
        self._alive = alive

    def recvall(self, size):
        """ recieve all. """
        try:
            s = size
            buf = ""
            while True:
                b = self.sock.recv(s)
                buf = buf + b
                s = s - len(b)
                if s==0 or not b:
                    return buf
        except Exception,ex:
            e = "RecvALL Error:%s" % ex
            self.log.error(e)
            raise CommunicateException(e)

    def onRecv(self):
        """ recieve request and return reply. """
        protocol = Protocol()
        headSize = protocol.getHeadSize()
        head = self.recvall(headSize)
        if len(head) != headSize:
           raise CommunicateException("Connection closed by peer")

        _type,size,codec = protocol.parseHead(head)

        if size > 0 and size < MAX_MESSAGE_LENGTH:
            ##print "request size:", size
            body = self.recvall(size) ##raise CommunicateException
            ##print "request body", body
            try:
               body = codec.decode(body)
            except Exception, ex:
                e = "Decode Request Message Body Error: %s" % ex
                self.log.error(e)
                raise ProtocolException(e)
        else:
            raise pyDCE.exception.CommunicateException("size error: "+str(size))

        if _type == MSG_TYPE_REQUEST:
            if len(body) != 3:
                raise ProtocolException("Request Message Body Content Error")

            # break up the request
            reqId, funcName, params = body

            # get the result for the request
            res = None
            exp = None
            try:
                import kiosk_utils
                self.log.info("request: %s %s %s" % (reqId, funcName, params))
                kioskUtil = kiosk_utils.KioskUtils(self.kioskId, self.log)
                func = getattr(kioskUtil, funcName, None)
                del kioskUtil

                if func is not None:
                    if hasattr(func, "__call__"):
                        try:
                            res = func(*params)
                            self.log.info("call success: %s" % reqId)
                        except Exception, ex:
                            self.log.error("Error when execute func(%s): %s"%(funcName, ex))
                            raise UserException(str(ex))
                    else:
                        raise NoMethodException("% can not be callable" % funcName)
                else:
                    raise NoMethodException("No function or attr %s" % funcName)
            except Exception, ex:
                self.log.error("except(%s):: %s" % (reqId, ex))
                exp = ex

            #print "reqid, result: ", reqId, res

            if exp is None:
                replyStatus = SUCCESS
                replyMsg = res
            else:
                replyStatus = AGENT_EXCEPTION
                replyMsg = exp

            reply = Reply(reqId, replyStatus, replyMsg)
            msg = protocol.ReplyToRaw(reply)
            #print "reply msg: ", msg
            self.sock.sendall(msg)#CommunicateException
        else:
            self.log.error("Unknown Message Ignoring...")

    def test(self, a):
        #print "sleep %s second" % 10
        time.sleep(10)
        return "This is a reply: %s" % a

#======================================================
#                  Maintain Kiosk side
#======================================================
class MaintainKioskSide( object ):

    def __init__(self, checkInterval=60):
        self.log = log
        self.kioskId = self.getKioskId()
        self.last_check_time = time.time()
        self.kioskObj = None
        self.checkInterval = checkInterval
        self.pid = self.getpid()

    def __del__(self):
        pass
        
    def maintain(self):
        """ Maintain kiosk side.
        """
        while True:
            self.kioskObj = None
            try:
                self.kioskObj = Kiosk(self.kioskId)
                # Kill old process.
                self.killall(self.pid)
                
                # Fork a child thread.
                pid = os.fork()
                if pid > 0:
                    # Parent thread.
                    try:
                        cpid, status = os.waitpid(pid, 0)
                    except Exception, ex:
                        self.log.error("Error in parent(%s) when wait for " \
                                       "child(%s): %s" % (self.pid,pid, ex))
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except Exception, ex:
                            self.log.error("Error when kill child " \
                                           "process(%s): %s"%(pid, ex))
                    time.sleep(5)
                else:
                    # Child thread.
                    self.setEnviVar()
                    self.kioskObj.run()
            except Exception, ex:
                self.log.error("Except in maintain: %s" % ex)
                try:
                    self.killall(self.pid)
                except:
                    pass
                time.sleep(20)
                
    def setEnviVar(self):
        """ Set the environment variable.
        """
        obj = pwd.getpwnam("mm")
        mmuid = obj.pw_uid
        mmgid = obj.pw_gid
        os.setgid(mmgid)
        os.setegid(mmgid)
        os.setgroups([4, 20, 24, 25, 29, 30, 44, 46, 107, 109, 115, 1000])
        os.setuid(mmuid)
        os.seteuid(mmuid)
        os.putenv("HOME","/home/mm")
        
    def getKioskId(self):
        """ Get kiosk id.
        """
        kioskId = ""
        f = None
        try:
            f = open("/etc/hostname")
            kioskId = f.read().strip()
        finally:
            f.close()
        return kioskId
        
    def getpid(self):
        return os.getpid()
        
    def killall(self, exppid):
        """ Kill all other processes.
        """
        pids = self._getPid(exppid)
        if pids:
            self.log.info("Other process of the kiosks: %s" % pids)
            for pid in pids:
                self._killProcess(pid)

    def _getPid(self, pid):
        """ Get the pid except the parent.
        """
        pids = []
        try:
            fileName = os.path.basename(__file__)
            cmd = "ps aux | grep %s | grep -v 'grep %s'" % (fileName, fileName)
            w, r = os.popen2(cmd)
            try:
                lines = r.read()
                for line in lines.split("\n"):
                    if line.strip() != "":
                        lis = line.strip().split()
                        if str(lis[1]) != str(pid):
                            pids.append(int(lis[1]))
            finally:
                w.close()
                r.close()
        except Exception, ex:
            self.log.error("error in _getPid: %s"%ex)
        return pids

    def _killProcess(self, pid):
        """ Kill the thread.
        """
        if pid:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception, ex:
                self.log.error("%s:error when kill %s:%s" % (self.pid, pid, ex))


def main():
    """
    kioskId = open("/etc/hostname").read().strip()
    #kioskId = "S250-A911"
    kiosk = Kiosk(kioskId)
    kiosk.run()
    """
    log.info("Access Agent VERSION %s" % __version__)
    mks = MaintainKioskSide()
    mks.maintain()

if __name__ == "__main__":
    main()
