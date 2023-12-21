#!/usr/bin/python
"""
By Richard, redesign the protocol and add new features to it
"""
import serial
import time
#from mcommon import TimerThread
import threading
import string
#import time
IGNORE_SEQ=0

class TimerThread(threading.Thread):
    def __init__(self, sleepPeriod, timeOutFunc):
        self._stopEvent = threading.Event()
        self._sleepPeriod = sleepPeriod
        threading.Thread.__init__(self, name="TimerThread")
        self.timeOutFunc = timeOutFunc

    def run(self):
        while not self._stopEvent.isSet():
            self.timeOutFunc()
            time.sleep(self._sleepPeriod)
          #  self._stopEvent.wait(self._sleepPeriod)

    def join(self,timeout=None):
        self._stopEvent.set()
        threading.Thread.join(self, timeout)

class RSEException(Exception):
    def __init(self,msg=""):
        Exception.__init__(self,msg)

class ProtocolException(RSEException):
    def __init(self,msg=""):
        RSEException.__init__(self,msg)
        
class TimeoutException(RSEException):
    def __init(self,msg=""):
        RSEException.__init__(self,msg)

class CommunicateException(RSEException):
    def __init(self,msg=""):
        RSEException.__init__(self,msg)

class NotImplementedException(RSEException):
    def __init(self,msg=""):
        RSEException.__init__(self,msg)

class UnknownException(RSEException):
    def __init(self,msg=""):
        RSEException.__init__(self,msg)
        
class RSerial:
    """ 
    Robust Serial Communication 
    Baudrate: 115200;  Parity: None; Flow Control: No
    Master Slave Mode: Either node can elect to be the master by sending special command HandShake
    Upon receving the Handshake command, the receiving node goes into slave mode
    
    Packet format:
    STX(0x02)   PACKET_DATA   CHECKSUM(two ascii bytes)  ETX(0x03)
    PACKET_DATA:
    TYPE    [SEQ_NUM(2Bytes ascii)]   [ACK_NUM(2Bytes ascii)   CONTENT]

    -SEQ_NUM: sequence number of the packet sender,increased by 1 each time a packet has been acknowledged;
    -ACK_SEQ: in ACK or PENDING packet, the SEQ_NUM of the acknowledged packet;

    TYPE:
    HANDSHAKE('H')|HANDSHAKE_REPLY('Y')|CMD('C')|DAT('D')|ACK('A')|Event('E')|Sync('S')|BEGIN_BINARY('B')|QUERY('Q')

    CMDs(to control board):
    CMD_RESET('R')

    DATs(routed by control board):
    DAT_CONTENT

        Data Packet Format: STX DAT SEQNUM(two ascii bytes) DATA CHECKSUM(two ascii bytes) ETX
        Command Packet Format: STX CMD COMMAND COMMAND ETX
        Ack Packet Format: STX ACK ETX
    The sender sends the handshake command to resync the sequence number if the connection is off
    
    ****************PACKET FORMAT****************
    HANDSHAKE:
    STX TYPE_HANDSHAKE TYPE_HANDSHAKE ETX
    STX TYPE_HANDSHAKE_REPLY TYPE_HANDSHAKE_REPLY ETX
    
    Sender:
    
    CMD:
    STX TYPE_CMD SEQ CMD(one byte) CMD ETX
    DAT
    STX TYPE_DAT SEQ (data) checksum ETX
    SYNC:
    STX TYPE_SYNC SEQ ETX
    EVENT:
    STX TYPE_EVENT SEQ (data) checksum ETX
    EVENT:
    STX TYPE_CANCEL SEQ ETX
    
    Receiver:
    ACK:
    STX ACK SEQ ACK_SEQ STAT(one byte) ETX
    STX RESULT ACK_SEQ (content) ETX
    
    One Sided Packet:
    STX DEBUG SEQ (content) ETX
    STX LOG SEQ (content) ETX  
    
    """
    DEFAULT_TIMEOUT=6.0
    DEFAULT_RETRY=60
    BOUDRATE=57600
    
    STX = 0x02  # start of packet
    ETX = 0x03  # end of packet
    
    TYPE_HANDSHAKE= 0x48  #'H'
    TYPE_HANDSHAKE_REPLY=0x59  #'Y'
    TYPE_CMD= 0x43 #'C'
    TYPE_DAT= 0x44   #'D'
    TYPE_ACK= 0x41  #'A'
    TYPE_RESULT=0x52   #"R"
    TYPE_EVENT= 0x45  #'E'
    TYPE_LOG= 0x4C  #'L'
    TYPE_DEBUG= 0x47  #'G'
    TYPE_SYNC=0x53    #'S'
    TYPE_CANCEL=0x4E  #"N"
    
    ACK_STATE_OK=0x30 #'0'
    ACK_STATE_CHECKSUM_ERR=0x31 #'1'
    ACK_STATE_UNKNOWN_FOAMAT=0x32 #'2'
    
    ##Todo:
    TYPE_BEGIN_BINARY=0x42  #'B'
    TYPE_QUERY=0x51  #'Q'

    SEQ_MIN = 1
    SEQ_MAX = 100
    SEQ_LEN=100

    CMD_RESET = 0x52      # 'R'
#    CMD_CANCEL = 0x43     #'C'
    
    STATE_INIT=1
    STATE_CONNECTED=2
    STATE_DISCONNECTED=3
    STATE_CLOSEING=4
    
    #only STATE==STATE_CONNECTED then the following value has meaning
    MODE_SLAVE=0
    MODE_MASTER=1
     
    
    def __init__(self, serPort = 0, boudrate=BOUDRATE):
        self.dataCallback = None
        self.resultCallback = None
        self.eventCallback = None
        self.__initVariables()
        self.ser = serial.Serial(serPort, boudrate, parity=serial.PARITY_NONE, timeout=5)
        import fcntl
        o=fcntl.fcntl(self.ser.fd,fcntl.F_GETFD)
        fcntl.fcntl(self.ser.fd,fcntl.F_SETFD,o or fcntl.FD_CLOEXEC)
        self.ser.flushInput()
        self.ser.flushOutput()
        while self.ser.inWaiting():
            self.ser.read()
        self.state=self.STATE_INIT
        self.timer = TimerThread(0.05, self.__timeout)
        self.timer.start()
        #self.mode=mode      
        
    def __initVariables(self):
        self.rxSeqNum = self.SEQ_MIN
        self.txSeqNum = self.SEQ_MIN
        self.rxBuf = []  # [STX... ETX STX... ETX]
        self.txBuf = []
       # self.isAckSet = 0
        
        self.getHandshakeReply=0
        self.inputQ=[] #[packet1,packet2,...]
        self.outputQ=[]
        
        self.ackQ={}
        self.alock=threading.RLock()
        
        #lock for transmit packet
        self.tlock=threading.RLock()
        
        self.rxErr=0

        """        
        self.eventQ=[]
        self.elock=threading.RLock()
        
        self.resultQ=[]
        self.rtlock=threading.RLock()
          """        
         
        
    def __state(self,state=None):
        if not state:
            return self.state
        self.state=state
    
    def __putAck(self,seq):
        #print "__putAck:", seq
        try:
            self.alock.acquire()
            self.ackQ[seq[0]]=seq
        finally:
            self.alock.release()
            
    def __getAck(self,seq):
        try:
            self.alock.acquire()
          #  print "__getAck:",seq, " " ,self.ackQ
            try:
                self.ackQ.pop(seq)
                #print "__gotAck:", seq
                return True
            except:
                return False
        finally:
            self.alock.release()
        return False
 
    """           
    def __getEvent(self):
        p=None
        try:
            self.elock.acquire()
            if len(self.eventQ):
                p=self.eventQ.pop(0)
        finally:
            self.elock.release()
        return p
            
    def __putEvent(self,seq,content):
        try:
            self.elock.acquire()
            self.eventQ.append((seq,content,time.time()))
        finally:
            self.elock.acquire()
   """
        
    def __checksum(self, s):
        return reduce(lambda x, y:x+y, map(ord, s)) & 0xff
        
    def __encodeHexByte(self, num):
        """ encode a one byte hex number into two acsii chars"""
        s = hex(num)
        return s.replace('x', '0')[-2:]
        
    def __decodeHexByte(self, s):
        """ convert a hex Byte to a number """
        return int(s, 16)
        
    def __timeout(self):
        while self.ser.inWaiting():
         #   print "."
            self.rxBuf.append(self.ser.read())
        if len(self.rxBuf)>0:
            print self.rxBuf
        self.__processRxQueue()
    
    def __increaseRSeq(self):
        self.rxSeqNum=self.rxSeqNum + 1
        if self.rxSeqNum  > self.SEQ_MAX:
            self.rxSeqNum=self.SEQ_MIN
        
            
    def __increaseTSeq(self):
        old=self.txSeqNum
        self.txSeqNum=self.txSeqNum + 1
        if self.txSeqNum  > self.SEQ_MAX:
            self.txSeqNum=self.SEQ_MIN
        return old
    
    def __send_lock(self,raw_data):
        try:
            self.tlock.acquire()
            self.ser.write(raw_data)
        finally:
            self.tlock.release()
        return True
    
    def __send(self,raw_data):
        self.ser.write(raw_data)
        return True
    
    def resetSerial(self):
        self.ser = serial.Serial("/dev/ttyS0", 57600, parity=serial.PARITY_NONE, timeout=5)

    def __processRxQueue(self):
        # look for STX
        if not self.rxBuf:
            return 
        packet = []
      #  print "__processRxQueue:",str(self.rxBuf)
        
        while (len(self.rxBuf) > 0):
            if (ord(self.rxBuf[0]) != self.STX):
                self.rxBuf.pop(0)
            else:
                break
            
        while(self.rxBuf) > 0:
            if self.rxBuf.count(chr(self.ETX)) > 0:  # search for ETX, checks for completeness of a packet
                #print ">>>>>>>>>>>>>>>>"
                n = self.rxBuf.index(chr(self.ETX)) + 1
                packet = self.rxBuf[:n]
                if len(packet):
                    self.inputQ.append(packet)
                self.rxBuf = self.rxBuf[n:]
                self.__processRxPacket()
            else:
                return
    
    def __processCMD(self,seq,cmd_type):
        #print "__processCMD CMD type:"
        pass
    
    def __processDAT(self,seq,packet):
        #print "__processDAT"
        if self.dataCallback:
            self.dataCallback(seq,packet)
        
    def __processEvent(self,packet):
        #print "__processEvent"
        if self.eventCallback:
            self.eventCallback(packet)
        else:
            pass
        
    def __processResult(self,ackseq,packet):
       # print "%s",str(ackseq), packet
        s=""
        print "reply: %s" % s.join(packet)
        print "-->"
        if self.resultCallback:
            self.resultCallback(ackseq,packet)
    """
    def __checkSeq(self,seqNum):
        if not IGNORE_SEQ:
            if seqNum!=self.rxSeqNum:
                #print "Invalid Sequence Number:%d, rxSeqNum:%d" % (seqNum ,self.rxSeqNum) 
                return False
                    # when seqNum is > than SEQ_MAX, it becomes SEQ_MIN
            self.__increaseRSeq()
        return True
    """
        
    def __processRxPacket(self):
        #print "Process Packet..."
        while len(self.inputQ):
            
            packet = self.inputQ.pop(0)
         #   print "Process Packet:",str(packet)
            
            try:
                ch = packet.pop(0)  # trim STX
                if ord(ch) != self.STX: 
                    #print "STX not found, packet ignored"
                    continue
                ch = packet.pop()   # trim ETX
                if ord(ch) != self.ETX:
                    #print "ETX not found, packet ignored"
                    continue
              
                ch = packet.pop(0)  # packet type
            
                if  ord(ch) == self.TYPE_HANDSHAKE:
                    #print "Handeshake"
                    if packet[0] == ch:
                        self.handshakeReply()
                        #self.state=self.STATE_CONNECTED
                        return 
                    else:
                        pass
                        #print "Handeshake Packet Error"
                elif ord(ch)==self.TYPE_HANDSHAKE_REPLY:
                    #print "HandeshakeReply"
                    if packet[0] == ch:
                        self.getHandshakeReply=1
                    #    self.state=self.STATE_CONNECTED
                    else:
                        pass
                        #print "Handeshakereply Packet Error"                      
                elif ord(ch) == self.TYPE_CMD:
                   #print "CMD"
                   #In this version CMD is not used so far
                   seqNum=self.__decodeHexByte(string.join(packet[:2], ''))
                   
                   if packet[2] == packet[3]:
                       #print "good format"
                       self.sendAck(seqNum,self.ACK_STATE_OK)
                       self.__processCMD(packet[3])
                   else:
                       #print "CMD checksum error"
                       self.sendAck(seqNum,self.ACK_STATE_CHECKSUM_ERR)
                       
                       
                elif ord(ch) == self.TYPE_DAT:
                   #print "DAT"
                   seqNum=self.__decodeHexByte(string.join(packet[:2], ''))
                   checksum = self.__decodeHexByte(string.join(packet[-2:], ''))
                   calculated_checksum = self.__checksum(packet[2:-2])# remove the two seqnum bytes and two checksum bytes
                   if checksum == calculated_checksum:
                    # process data
                       self.sendAck(seqNum,self.ACK_STATE_OK)
                       self.__processDAT(seqNum,packet[2:-2])
                   else:
                       #print "invalid chechsum"
                        # ignore packets with wrong checksum
                       self.sendAck(seqNum,self.ACK_STATE_CHECKSUM_ERR)
                       
                elif ord(ch) == self.TYPE_EVENT:
                    seqNum=self.__decodeHexByte(string.join(packet[:2], ''))
                    #print("EVENT with seq:%i" % seqNum)
                    checksum = self.__decodeHexByte(string.join(packet[-2:], ''))
                    calculated_checksum = self.__checksum(packet[2:-2])# remove the two seqnum bytes and two checksum bytes
                    if checksum == calculated_checksum:
                        self.sendAck(seqNum,self.ACK_STATE_OK)
                        self.__processEvent(packet[2:-2])
                    else:
                        self.sendAck(seqNum,self.ACK_STATE_CHECKSUM_ERR)
                        # ignore packets with wrong checksum
                        #print "invalid chechsum"  
                elif ord(ch) == self.TYPE_DEBUG or ord(ch) == self.TYPE_LOG :
                   # print "RSerial DEBUG:", packet[2:]         
                    pass
                elif ord(ch) == self.TYPE_ACK:
                    ackSeqNum=self.__decodeHexByte(string.join(packet[:2], ''))
                    stat=packet[2]
                    #print "ACK for seq:%i, stat:%s" % (ackSeqNum,stat)
                    self.__putAck((ackSeqNum,stat))
                elif ord(ch) == self.TYPE_RESULT:
                   seqNum=self.__decodeHexByte(string.join(packet[:2], ''))
                   ackSeq=self.__decodeHexByte(string.join(packet[2:4], ''))
                  # print "RESULT with sequence:", seqNum
                   #check and increase seqNum
                   checksum = self.__decodeHexByte(string.join(packet[-2:], ''))
                   calculated_checksum = self.__checksum(packet[4:-2])# remove the two seqnum bytes and two checksum bytes
                   if checksum == calculated_checksum:
                    # process data
                       self.sendAck(seqNum,self.ACK_STATE_OK)
                       self.__processResult(ackSeq,packet[4:-2])
                   else:
                        # ignore packets with wrong checksum
                       self.sendAck(seqNum,self.ACK_STATE_CHECKSUM_ERR)
                       #print "invalid chechsum"
                else:
                   pass
                  #  print "Unknown or Not Implemented packet,ignored,type:",ord(ch)
            except Exception, ex:
            # packet might not have enough chars for popping, disgard packet
                #print "__processRxPacket exception", ex
                return
    
    def handshake(self):
        packet = chr(self.STX) + chr(self.TYPE_HANDSHAKE) + chr(self.TYPE_HANDSHAKE) + chr(self.ETX)
        counter = 0
        while 1:
            self.getHandshakeReply=0
            #print "Send HANDSHAKE to mcu"
            self.__send_lock(packet)
            st=time.time()
            while True:  
                if self.getHandshakeReply==1:
                  #  print "handshake completed, sequence number is rest"
                    self.__initVariables()
                    self.__state(self.STATE_CONNECTED)
                    return 1
                else:
                    time.sleep(0.5)
                    counter += 1
                    if counter > 100 or (time.time()-st)> self.DEFAULT_TIMEOUT:
                       # print "handshake error"
                        self.__state(self.STATE_DISCONNECTED)
                        return 0
    
    def handshakeReply(self):
       # print "sendHandshakeReply"
        self.__state(self.STATE_CONNECTED)
        packet = chr(self.STX) + chr(self.TYPE_HANDSHAKE_REPLY) + chr(self.TYPE_HANDSHAKE_REPLY) + chr(self.ETX)
        self.__send_lock(packet) 
    
    def sendPacket(self,type,seq=None,data=None,sub_type=None,tx_seq=None):
        try:
            self.tlock.acquire()
            packet=chr(self.STX)+ chr(type)
            if not tx_seq:
                txseq=self.__increaseTSeq()
            else:
                txseq=tx_seq
          #  print "Sending data with sequqnce number:%d "%  txseq
                ## 
            if type==self.TYPE_ACK:
               # print "Send Ack"
                ##STX ACK SEQ ASEQ ETX
                packet+=self.__encodeHexByte(seq)
                packet+=chr(sub_type)
                packet+=chr(self.ETX)
            elif type==self.TYPE_DAT :
               # print "Send DAT"
                ##STX DAT SEQ ASEQ data checksum ETX
                packet+=self.__encodeHexByte(txseq)
                checksum=self.__checksum(data)
                packet+=data
                packet+=self.__encodeHexByte(checksum)
                packet+=chr(self.ETX)
            elif type==self.TYPE_RESULT :
               # print "Send Result"
                ##STX DAT SEQ ASEQ data checksum ETX
               # print "123455", seq
                packet+=self.__encodeHexByte(txseq)
                packet+=self.__encodeHexByte(seq)
                checksum=self.__checksum(data)
                packet+=data
                
                packet+=self.__encodeHexByte(checksum)
                packet+=chr(self.ETX)
            elif type==self.TYPE_CMD:
               # print "Send CMD"
                ##STX DAT SEQ ASEQ data checksum ETX
                packet+=self.__encodeHexByte(txseq)
                packet+=chr(sub_type)
                packet+=chr(sub_type)
                packet+=self.ETX
            elif type==self.TYPE_SYNC:
               # print "Send SYNC"
                ##STX DAT SEQ ASEQ data checksum ETX
                packet+=self.__encodeHexByte(txseq)
                packet+=self.ETX
            elif type==self.TYPE_CANCEL:
              #  print "Send CANCEL"
                ##STX DAT SEQ ASEQ data checksum ETX
                packet+=self.__encodeHexByte(seq)
                packet+=self.ETX
            elif type==self.TYPE_EVENT:
                print "Send Event"
               ##STX EVENT SEQ ASEQ event_type event_ content ETX
                packet+=self.__encodeHexByte(txseq)
                checksum=self.__checksum(data)
                packet+=data
                packet+=self.__encodeHexByte(checksum)
                packet+=chr(self.ETX)
            else:
             #   print "Type: ", type, "has not yet implemented" 
                return None
       
            self.__send(packet)
          #  print "Send Packet:", [packet]
        finally:
            self.tlock.release()   
     #   print "sendPacketok"         
        return txseq 
    
    def sendAck(self,seq,stat):
      #  print "sendAck......."
        return self.sendPacket(type=self.TYPE_ACK, seq=seq,sub_type=stat)
    
    def sendCancel(self,seq):
        return self.sendPacket(type=self.TYPE_CANCEL, seq=seq)
    
    def sendCMD(self,cmd):
        return self.sendPacket(type=self.TYPE_CMD,sub_type=cmd)

    def sendDataSync(self,data,timeout=DEFAULT_TIMEOUT,retry=DEFAULT_RETRY):
       # print "sendDataSync"
        seq=self.sendPacket(type=self.TYPE_DAT,data=data)

        if not seq:
            return -1
         #   raise NotImplementedException("")
        w=timeout/retry
        count=retry
        while count:
            for i in range(0,retry):
                if self.__getAck(seq):
                    return seq
                time.sleep(w)
                if self.__getAck(seq):
                    return seq
            #timeout
            #print "SendData Timeout"
            count=count-1
            seq=self.sendPacket(type=self.TYPE_DAT,data=data,tx_seq=seq)
        self.state=self.STATE_DISCONNECTED
        return -2
        #raise TimeoutException("sendDataSync:",data)
    
    def sendResultSync(self,seqNum,data,timeout=DEFAULT_TIMEOUT,retry=DEFAULT_RETRY):
      #  print "sendResultSync"
        seq=self.sendPacket(type=self.TYPE_RESULT,seq=seqNum,data=data)
        if not seq:
            return -1
            #raise NotImplementedException("")
        w=timeout/retry
        count=retry
        while count:
            for i in range(0,retry):
                if self.__getAck(seq):
                    return seq
                time.sleep(w)
                if self.__getAck(seq):
                    return seq
            #timeout
            print "SendResultSync Timeout"
            count=count-1
            seq=self.sendPacket(type=self.TYPE_RESULT,seq=seqNum,data=data,tx_seq=seq)
        self.state=self.STATE_DISCONNECTED
        return -2
        #raise TimeoutException("SendResultSync:",data)
    
    def sendEvent(self,data,timeout=DEFAULT_TIMEOUT,retry=DEFAULT_RETRY):
        print "sendEvent"
        if self.__state()!=self.STATE_CONNECTED:
            return None
        print "sendEventSync..."
        seq=self.sendPacket(type=self.TYPE_EVENT,data=data)
        if not seq:
            raise NotImplementedException("")       
        w=timeout/retry
        count=retry        
        while count:
            for i in range(0,retry):
                if self.__getAck(seq):
                    return
                time.sleep(w)
            #timeout
            print "SendEvent timeout"
            count=count-1
            seq=self.sendPacket(type=self.TYPE_EVENT,data=data,tx_seq=seq)
        return -2
        raise TimeoutException("sendEventSync:",data)
    

######################################################################################
###Unit Test###
######################################################################################



class Control(threading.Thread):
    def __init__(self,ser):
        threading.Thread.__init__(self,name="control")
        self.ser=ser
        self.ser.resultCallback=self.resultCallback
        self.ser.resultCallback=self.eventCallback
        self.current=None
        self.got=False
        self.resultQ={}
        self.lock=threading.Lock()
 
    def eventCallback(self,packet):
        print "in event callback"
        print packet
    
    def resultCallback(self,seq,data):
        print "resultCallback:",seq
        try:
            self.lock.acquire()
            self.resultQ[seq]=data
        finally:
            self.lock.release()

    def getResult(self,seq):
        r=None
        try:
            self.lock.acquire()
            if self.resultQ.has_key(seq):
                r=self.resultQ.pop(seq)
        finally:
            self.lock.release()
        return r

    def run(self):
        while True:
            if ser.handshake():
                break
            time.sleep(3)
        while True:
            try:
                current=ser.sendDataSync("Test Data")
                print "Sent Data with seq:", current
                while not self.getResult(current):
                    time.sleep(0.1)
                print "Got Result"
            except TimeoutException,ex:
                print "$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$"
                sys.exit()
                ser.handshake()
                print "timeout:",ex,"handshake again"
               # sys.exit()
                
            time.sleep(0.2)
            
class Slave(threading.Thread):
    def __init__(self,ser):
        threading.Thread.__init__(self,name="slave")
        self.ser=ser
        self.ser.dataCallback=self.dataCallback
        self.lock=threading.Lock()
        self.request=[]
        
    def dataCallback(self,seq,data):
        try:
            self.lock.acquire()
            self.request.append((seq,data))
        finally:
            self.lock.release()
        print "XXXXXXXXXXXXXXX"

    def run(self):
        while True:
            time.sleep(2)
            q=None
            try:
                self.lock.acquire()
                if len(self.request) > 0:
                    q=self.request
                    self.request=[]
            finally:
                self.lock.release()
            while q and len(q):
                (seq,data)=q.pop(0)
                self.ser.sendResultSync(seq, "RESULT")

class Control_Debug(threading.Thread):
    def __init__(self,ser):
        threading.Thread.__init__(self,name="control")
        self.ser=ser
        self.ser.resultCallback=self.resultCallback
        self.ser.eventCallback=self.eventCallback
        self.current=None
        self.got=False
        self.resultQ={}
        self.lock=threading.Lock()
    
    def eventCallback(self,packet):
        print "in event call back"
        print packet
    
    def resultCallback(self,seq,data):
        print "resultCallback:",seq
        s=""
        try:
            self.lock.acquire()
            for i in range(0,len(data)):
                s=s+data[i]
            self.resultQ[seq]=s
        finally:
            self.lock.release()

    def getResult(self,seq):
        r=None
        try:
            self.lock.acquire()
            if self.resultQ.has_key(seq):
                r=self.resultQ.pop(seq)
        finally:
            self.lock.release()
        return r
    
    def clearResult(self):
        r=None
        try:
            self.lock.acquire()
            self.resultQ.clear()
        finally:
            self.lock.release()
        return r

    def _do_cmd(self,command,async=False):
         try:
            current=ser.sendDataSync(command)
            if async:
                return current
            print "Sent Data with seq:", current
            import time
            r=0
            tick=time.time()
            while time.time() - tick < 60:
                r=self.getResult(current)
                if r:
                    break
                time.sleep(0.2)
            if r:
                print "Got Result"
                if r.find("err") !=-1:
                   import sys
                   sys.exit(-1)
                   print "Error executed"
                   return 1
                return 0
            else:
                print "Get Result Timeout"
                return -1
         except TimeoutException,ex:
            print "$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$"
            return -1


    def rack_to_rack(self,slot_from ,slot_to):
        self._do_cmd("move_debug control goto_slot_retrieve " +str(slot_from))
        self._do_cmd("move_debug carriage retrieve")
        self._do_cmd("move_debug control goto_slot_insert " +str(slot_to))
        self._do_cmd("move_debug carriage insert ")


    def action(self,slot_no):
#        self._do_cmd("move_debug exchange inH")
        """
        
        self._do_cmd("move_debug control goto_slot_retrieve " +str(slot_no))


        self._do_cmd("move_debug control goto_slot_retrieve " +str(slot_no))
        self._do_cmd("move_debug qd_read ")
        self._do_cmd("move_debug control goto_home")
        time.sleep(2)
        self._do_cmd("move_debug qd_read ")
        self._do_cmd("move_debug control goto_slot_insert " +str(slot_no))
        self._do_cmd("move_debug qd_read ")
        self._do_cmd("move_debug control goto_home")
        time.sleep(2)
        self._do_cmd("move_debug qd_read ")
        return
    
        self._do_cmd("move_debug carriage retrieve")
        self._do_cmd("move_debug qd_read")
        self._do_cmd("move_debug carriage claw_on")
        self._do_cmd("move_debug control goto_slot_insert "+ str(slot_no))
        self._do_cmd("move_debug carriage insert")
 #       self._do_cmd("move_debug carriage goto_col 0")
        self._do_cmd("move_debug control goto_home")
        self._do_cmd("move_debug carriage goto_col 0")
        
        self._do_cmd("move_debug exchange door_open")
        self._do_cmd("move_debug exchange door_close")
        
        self._do_cmd("move_debug control goto_slot_retrieve  "+str(slot_no))
        self._do_cmd("move_debug carriage retrieve")
        self._do_cmd("move_debug qd_read")
        self._do_cmd("move_debug carriage claw_on")
        self._do_cmd("move_debug control goto_home")
        self._do_cmd("move_debug carriage goto_col 0")
        self._do_cmd("move_debug carriage insert")
#        self._do_cmd("move_debug exchange outH")
        self._do_cmd("move_debug exchange door_open")
        self._do_cmd("move_debug exchange door_close")
        
        """
        self._do_cmd("move_debug control exchange_to_rack %i" % slot_no)
        


        self._do_cmd("move_debug control rack_to_exchange %i" % slot_no)
     
        self._do_cmd("move_debug exchange rfid")
        #self._do_cmd("move_debug exchange  door_open")
        #self._do_cmd("move_debug exchange  door_close")
            
    def run(self):
        ser.sendDataSync("move_debug cancel")
        self._do_cmd("move_debug exchange_cancel")
        self._do_cmd("move_debug exchange door_close")
        while True:
            ser.sendDataSync("move_debug exchange accept")
            time.sleep(2)
            while True:
                r1=ser.sendDataSync("move_debug cancel")
                print "AAAAAAAAAAAAAAAAAAAAAAAAAAAA"
                self.clearResult();
                print "send cancel to exchange..."
                self._do_cmd("move_debug exchange_cancel")
                r1=ser.sendDataSync("move_debug exchange hello")
                t=time.time()
                while time.time() - t < 5:
                    status = self.getResult(r1)
                    if status:
                        break;
                print status
                if status and status.find('ok')!=-1:
                    print "MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM"
                    break
            self._do_cmd("move_debug exchange door_close")

        
        while True:
            if ser.handshake():
                break
        self._do_cmd("move_debug  control exchange_offset 2050 ")
        """
        #self._do_cmd("move_debug seek_bottom");
        self._do_cmd("move_debug qd_zero");
        self._do_cmd("move_debug goto_pos 18470");
        self._do_cmd("move_debug carriage home_left")
        self._do_cmd("move_debug exchange accept");
        self._do_cmd("move_debug goto_pos 25005");
        self._do_cmd("move_debug carriage goto_col 1");
        self._do_cmd("move_debug carriage retrieve")
        self._do_cmd("move_debug goto_pos 18470");
        self._do_cmd("move_debug carriage goto_col 0")
        """

        while True:
            """
            self._do_cmd("move_debug carriage home_back")
            self._do_cmd("move_debug carriage home_left")
            self._do_cmd("move_debug exchange  door_close")
            self._do_cmd("move_debug  control bottom_offset -20 ")
            self._do_cmd("move_debug  control exchange_offset 2050 ")
            self._do_cmd("move_debug  seek_top ")
            self._do_cmd("move_debug  control goto_home ")
            #self._do_cmd("move_debug seek_bottom")
            """
         #   self._do_cmd("move_debug control exchange_offset 2050")
         #   self._do_cmd("move_debug control bottom_offset -50 ")
         #   self._do_cmd("move_debug control goto_home")
            for i in xrange(101, 169):
               # self.rack_to_rack(i,i+1)
                if i > 169:
                    print "Out of range!"
                else:
                    self.action(i)   

            #self.rack_to_rack(170,228)
       
            for i in xrange(228,269):
               # self.rack_to_rack(i,i+1)
                if i > 269:
                    print "Out of range!"
                else:
                    self.action(i)   
        
            #self.rack_to_rack(270,501)
             
            for i in xrange(501,568):
               # self.rack_to_rack(i,i+1)
                if i > 568:
                    print "Out of range!"
                else:
                    self.action(i)   

            #self.rack_to_rack(569,601)
            
            for i in xrange(601,668):
               # self.rack_to_rack(i,i+1)
                if i > 668:
                    print "Out of range!"
                else:
                    self.action(i)   
            
           # self.rack_to_rack(669,101)
            
        """
        while True:
            for i in xrange(501,569):
                self._do_cmd("move_debug control exchange_to_rack %i" %i)
                self._do_cmd("move_debug qd_read")
                self._do_cmd("move_debug control rack_to_exchange %i" %i)
                self._do_cmd("move_debug qd_read")
         #   self._do_cmd("move_debug exchange door_open")
         #   self._do_cmd("move_debug exchange rfid")
         #   self._do_cmd("move_debug exchange door_close")
        
            for i in xrange(228,270):
                self._do_cmd("move_debug control exchange_to_rack %i" %i)
                self._do_cmd("move_debug qd_read")
                self._do_cmd("move_debug control rack_to_exchange %i" %i)
                self._do_cmd("move_debug qd_read")
        #    self._do_cmd("move_debug exchange door_open")
            #self._do_cmd("move_debug exchange rfid")
            for i in xrange(101,170):
                self._do_cmd("move_debug control exchange_to_rack %i" %i)
                self._do_cmd("move_debug qd_read")
                self._do_cmd("move_debug control rack_to_exchange %i" %i)
                self._do_cmd("move_debug qd_read")
            for i in xrange(601,669):
                self._do_cmd("move_debug control exchange_to_rack %i" %i)
                self._do_cmd("move_debug qd_read")
                self._do_cmd("move_debug control rack_to_exchange %i" %i)
                self._do_cmd("move_debug qd_read")
            # self._do_cmd("move_debug exchange door_close")
        """ 
def eventCallback(event):
    print "************evenetCallback"
    print event


if __name__=="__main__":
    import sys
    import readline
    import os
    if len(sys.argv)>1 and sys.argv[1]=="test":
        import sys
        import readline
        if len(sys.argv) >2:
            ser=RSerial(serPort=sys.argv[2])
        else:
            ser=RSerial(serPort="/dev/ttyS0")
        thread=Control_Debug(ser)
        thread.start()
        thread.join()
        sys.exit(0)
    elif len(sys.argv)>1 and  sys.argv[1]=="update":
        r=raw_input( "this method has been obsoleted by downloader.py, are you still want to go on?[y/N]")
        if r.lower()!="y":
            sys.exit(0)
        port="/dev/ttyS0"
        if len(sys.argv) > 2:
            port=sys.argv[2]
        ser=RSerial(serPort=port)
        ser.sendDataSync("robot reboot")
        ser.ser.close()
        ser.timer.join()
        os.system("minicom")
        sys.exit(0)
    elif len(sys.argv)>1 and  sys.argv[1]=="reboot_machine":
        r=raw_input("machine will be power cycled, are you sure?[y/N]")
        if r.lower()=="y":
            ser=serial.Serial("/dev/ttyUSB0",9600,parity=serial.PARITY_NONE,timeout=5)
            buf=chr(0x02)+chr(0x50)+chr(0x4f)+chr(0x4e)+chr(0x03)
            ser.write(buf)
            r=ser.read()
            buf=chr(0x02)+r+chr(0x03)
            ser.write(buf)
            r=ser.read()
            print r
            buf=chr(0x02)+chr(0x53)+chr(0x54)+chr(0x41)+chr(0x03)
            ser.write(buf)
            ser.close()
        sys.exit(0)

    elif len(sys.argv)>1 and  sys.argv[1]=="reboot_control":
        r=raw_input("will reset control board, are you sure?[y/N]")
        if r.lower()=="y":
            ser=serial.Serial("/dev/ttyUSB0",9600,parity=serial.PARITY_NONE,timeout=5)
            buf=chr(0x02)+chr(0x50)+chr(0x4f)+chr(0x4e)+chr(0x03)
            ser.write(buf)
            r=ser.read()
            buf=chr(0x02)+r+chr(0x03)
            ser.write(buf)
            r=ser.read()
            print r
            buf=chr(0x02)+chr(0x4d)+chr(0x52)+chr(0x45)+chr(0x03)
            ser.write(buf)
            ser.close()
        sys.exit(0)
    if len(sys.argv) >1:         
        ser=RSerial(serPort=sys.argv[1])
    else:
        ser=RSerial("/dev/ttyS0")
    ser.eventCallback=eventCallback
    if len(sys.argv) > 2:
        if sys.argv[2]=="control":
            thread=Control(ser)
        else:
            thread=Slave(ser)
    
        thread.start()
        thread.join()
    else:
        ser.handshake()
        while True:
            s=raw_input("-->")
            if s:
                ser.sendDataSync(s)


