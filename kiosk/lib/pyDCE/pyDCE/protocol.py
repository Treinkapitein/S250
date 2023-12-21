

"""
classes for encode/decode DCE messages
We use cpickle as our marshalling mechanism for easy implementation
the function of cpickle is limited, e.g. it cannot marshall binary message body and 
both the server and client should be implemented with Python.
In the next version we will use Common Data Representation (CDR) as our marshalling 
protocol.
message format:

head body(pickled)

head:
int magic(0xdce0)
unsigned char protocol_major
unsigned char protocol_minor
unsigned char encoding_major
unsigned_char endoding_minor
unsighed char msg_type
unsigned char compression_stat
unsigned long long     size

struct fromat:
!iBBBBBBQ



msg_type:
request(client->server)
reply(server->client)
batch request(client->server)
validate_challenge(server->client)
validate_connection(client->server)
close connection(server/client->client/server)

body:
[request]
(request_uuid(0 for one-way),object_name,method_name,context,(params))

[reply]
(request_uuid,reply status,body)
reply status:
success
dce exception
Unknown exception

[validate challenge]
(challenge_type,(param) )
A server sends a validate connection message when it receives a new connection.
The message indicates that the server is ready to receive requests; the client must
not send any messages on the connection until it has received the validate connec-
tion message from the server. No reply to the message is expected by the server.

[validate connection]
"""
import sys,os
sys.path.insert(0,os.pardir)
import struct
import cPickle
import pyDCE
import pyDCE.dcecommon
import pyDCE.exception

def DCE_APP():
    import pyDCE.dceapp
    return pyDCE.dceapp.DCEApp()

#from pyDCE.global_include import *

#######################################################################################
#dCeP
MAGIC=0x64436550

MSG_TYPE_REQUEST=0x01
MSG_TYPE_REQUEST_SET_ATTR=0x11  # for setattr
MSG_TYPE_REQUEST_GET_ATTR=0x21  # for setattr
MSG_TYPE_REPLY=0x02
MSG_TYPE_BATCH_REQUEST=0x03
MSG_TYPE_VALIDATE_CHALLENGE=0x04
MSG_TYPE_VALIDATE_CONNECTION=0x05
MSG_TYPE_CLOSE=0x06
MSG_TYPE_UNKNOWN=0xff

PROTOCOL_MAJOR=1
PROTOCOL_MINOR=0

SUCCESS=0
DCE_EXCEPTION=1
UNKNOWN_EXCEPTION=2

COMPRESS_NO=0

ENCODE_CPICKLE=0
"""
minor version is only for maintain.
all codecs with same major number SHOULD be COMPATIBLE
"""
ENCODE_MAJOR=ENCODE_CPICKLE
ENCODE_MINOR=0

class DCECodec(pyDCE.dcecommon.DCEObject):
    def __init__(self):
        pyDCE.dcecommon.DCEObject.__init__(self)
        
    def getCodec(e_maj,compress=COMPRESS_NO,e_min=0):
        if e_maj==ENCODE_CPICKLE:
            return CPICKLE_CODEC(e_min,compress)
        else:
            raise pyDCE.exception.NotImplementedException("CPICKLE is the only codec we support currently")
    
    def encode(self,body):
        pass
    
    def decode(self,msg):
        pass
    getCodec=staticmethod(getCodec)
    
class CPICKLE_CODEC(DCECodec):
    def __init__(self,e_min,compress):
        DCECodec.__init__(self)
        self._e_min=e_min
        self._compress=compress
        
    def encode(self,body):
        return cPickle.dumps(body)
    
    def decode(self,msg):
        return cPickle.loads(msg)
    
"""
class Message(dcecommon.DCEObject):
    def __init__(self,msg_type,comp_stat=COMPRESS_NO,e_maj=ENCODE_MAJOR,e_min=ENCODE_MINOR,body=None,codec=ENCODE_CPICKLE):
        dcecommon.DCEObject.__init__(self)
        self._type=msg_type
        self._comp_stat=comp_stat
        self._body_size=size
        self._body=body
        self._e_maj=e_maj
        self._e_min=e_min
        self._codec=codec
        
    def getBodySize(self):
        return self._body_size
    
    ##Todo decompress
    def getBody(self,body=None):
        codec=DCECodec.getCodec(self._e_maj, self._e_min)
        if body:
            codec.decode(body)
"""

class Request(pyDCE.dcecommon.DCEObject):
    def __init__(self,obj_name,method_name,params,context={},one_way=0,compress=0,codec=ENCODE_CPICKLE,type=MSG_TYPE_REQUEST):
        pyDCE.dcecommon.DCEObject.__init__(self)
        self._obj_name=obj_name
        self._method_name=method_name
        self._params=params
        self._context=context
        self._one_way=one_way
        self._comp_stat=compress
        self._codec=codec
        self._type=type

class Reply(pyDCE.dcecommon.DCEObject):
    def __init__(self,rid,status=SUCCESS,body=None,compress=0,codec=ENCODE_CPICKLE,type=MSG_TYPE_REPLY):
        pyDCE.dcecommon.DCEObject.__init__(self)
        self._rid=rid
        self._status=status
        self._body=body
        self._comp_stat=compress
        self._codec=codec
        self._type=type


class Protocol:
    head_fmt="!iBBBBBBQ"
    head_size=struct.calcsize(head_fmt)
    def __init__(self,p_maj=PROTOCOL_MAJOR,p_min=PROTOCOL_MINOR):
        self._p_maj=p_maj
        self._p_min=p_min  
    
    #(request_uuid(0 for one-way),object_name,method_name,context,(params))
    def RequestToRaw(self,req):
        if req._one_way:
            u="00000000-0000-0000-0000-000000000000"
        else:
            u=str(req._uuid)
        codec=DCECodec.getCodec(req._codec,req._comp_stat)
        body=codec.encode((u,req._obj_name,req._method_name,req._context,req._params))
        l=len(body)
       # print "RequestToRaw body length=%i" % l
        head=struct.pack(self.head_fmt,MAGIC,self._p_maj,self._p_min,ENCODE_MAJOR,ENCODE_MINOR,req._type,req._comp_stat,l)
        return (u,head+body)
     
    def ReplyToRaw(self,reply):
         codec=DCECodec.getCodec(reply._codec,reply._comp_stat)
         body=codec.encode((reply._rid,reply._status,reply._body))
         l=len(body)
       # print "RequestToRaw body length=%i" % l
         head=struct.pack(self.head_fmt,MAGIC,self._p_maj,self._p_min,ENCODE_MAJOR,ENCODE_MINOR,reply._type,reply._comp_stat,l)
         return head+body
    
    def parseHead(self,head):
        try:
            head_info=struct.unpack(self.head_fmt, head)
            
            if head_info[0]!=MAGIC:
                DCE_APP().ERROR("Magic number error")
                raise pyDCE.exception.ProtocolException("Magic number error")
            if head_info[1]>self._p_maj:
                DCE_APP().ERROR("Protocol Version Not Supported")
                raise pyDCE.exception.ProtocolException("Protocol Version %i Not Supported" % head_info[1])
        
            codec=DCECodec.getCodec(head_info[3],head_info[4],head_info[6])
        #(type,bodysize,codec)
            return (head_info[5],head_info[7],codec)
        except Exception,ex:
            raise pyDCE.exception.ProtocolException(ex)
    
    def getHeadSize(self):
        return self.head_size
    
    
if __name__=="__main__":
    req=Request("testobj","testmethod",(20))
    p=Protocol()
    r=p.RequestToRaw(req)
    print r
    
    length=p.getHeadSize()
    head=r[:length]
    h=p.parseHead(head)
    print h
    
    type=h[0]
    size=h[1]
    codec=h[2]
    body=r[length:]
    b=codec.decode(body)
    print b

