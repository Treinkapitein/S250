#!/usr/bin/python
"""
Simple flash downloader for S250

By Richard, file downloader for Rabbit ,HEX format

I know someone already implemented it 1 year ago
but it can not work, and I do not want to just modify it.
So I write a simple one for myself.

revise history:
2009 5-12: ignore signals, stop/start mkc
2009 5-26: 
"""
import serial
import time
import threading
import string
import fcntl
import os.path, sys
import signal
import errno


batch_mode=0

MODULE = sys.modules[__name__]

COLORS = "BLUE GREEN CYAN RED MAGENTA YELLOW WHITE BLACK".split()
# List of terminal controls, you can add more to the list.
CONTROLS = {
    'BOL':'cr', 'UP':'cuu1', 'DOWN':'cud1', 'LEFT':'cub1', 'RIGHT':'cuf1',
    'CLEAR_SCREEN':'clear', 'CLEAR_EOL':'el', 'CLEAR_BOL':'el1',
    'CLEAR_EOS':'ed', 'BOLD':'bold', 'BLINK':'blink', 'DIM':'dim',
    'REVERSE':'rev', 'UNDERLINE':'smul', 'NORMAL':'sgr0',
    'HIDE_CURSOR':'cinvis', 'SHOW_CURSOR':'cnorm'
}

# List of numeric capabilities
VALUES = {
    'COLUMNS':'cols', # Width of the terminal (None for unknown)
    'LINES':'lines',  # Height of the terminal (None for unknown)
    'MAX_COLORS': 'colors',
}

def default():
    """Set the default attribute values"""
    for color in COLORS:
        setattr(MODULE, color, '')
        setattr(MODULE, 'BG_%s' % color, '')
    for control in CONTROLS:
        setattr(MODULE, control, '')
    for value in VALUES:
        setattr(MODULE, value, None)

def setup():
    """Set the terminal control strings"""
    # Initializing the terminal
    curses.setupterm()
    # Get the color escape sequence template or '' if not supported
    # setab and setaf are for ANSI escape sequences
    bgColorSeq = curses.tigetstr('setab') or curses.tigetstr('setb') or ''
    fgColorSeq = curses.tigetstr('setaf') or curses.tigetstr('setf') or ''

    for color in COLORS:
        # Get the color index from curses
        colorIndex = getattr(curses, 'COLOR_%s' % color)
        # Set the color escape sequence after filling the template with index
        setattr(MODULE, color, curses.tparm(fgColorSeq, colorIndex))
        # Set background escape sequence
        setattr(
            MODULE, 'BG_%s' % color, curses.tparm(bgColorSeq, colorIndex)
        )
    for control in CONTROLS:
        # Set the control escape sequence
        setattr(MODULE, control, curses.tigetstr(CONTROLS[control]) or '')
    for value in VALUES:
        # Set terminal related values
        setattr(MODULE, value, curses.tigetnum(VALUES[value]))

def render(text):
    """Helper function to apply controls easily
    Example:
    apply("%(GREEN)s%(BOLD)stext%(NORMAL)s") -> a bold green text
    """
    return text % MODULE.__dict__

try:
    import curses
    setup()
except Exception, e:
    # There is a failure; set all attributes to default
    print 'Warning: %s' % e
    default()


class ProgressBar(object):
    """Terminal progress bar class"""
    TEMPLATE = (
    #  '%(percent)-2s%% %(color)s%(progress)s%(normal)s%(empty)s %(message)s\n'
     '%(color)s[%(progress)s%(normal)s%(empty)s ]%(message)s\n'
    )
    PADDING = 7
 
    def __init__(self, color=None, width=None, block='=', empty=' '):
        """
        color -- color name (BLUE GREEN CYAN RED MAGENTA YELLOW WHITE BLACK)
        width -- bar width (optinal)
        block -- progress display character (default ' ')
        empty -- bar display character (default ' ')
        """
        if color:
            self.color = color.upper()
        else:
            self.color = ''
        if width and width < COLUMNS - self.PADDING:
            self.width = width
        else:
            # Adjust to the width of the terminal
            self.width = COLUMNS - self.PADDING
        self.block = block
        self.empty = empty
        self.progress = None
        self.lines = 0
 
    def render(self, percent, message = ''):
        """Print the progress bar
        percent -- the progress percentage %
        message -- message string (optional)
        """
        inline_msg_len = 0
        if message:
            # The length of the first line in the message
            inline_msg_len = len(message.splitlines()[0])
        if inline_msg_len + self.width + self.PADDING > COLUMNS:
            # The message is too long to fit in one line.
            # Adjust the bar width to fit.
            bar_width = COLUMNS - inline_msg_len -self.PADDING
        else:
            bar_width = self.width
 
        # Check if render is called for the first time
        if self.progress != None:
            self.clear()
        self.progress = (bar_width * percent) / 100
        data = self.TEMPLATE % {
            'percent': percent,
            'color': self.color,
            'progress': self.block * self.progress,
            'normal': NORMAL,
            'empty': self.empty * (bar_width - self.progress),
            'message': message
        }
        sys.stdout.write(data)
        sys.stdout.flush()
        # The number of lines printed
        self.lines = len(data.splitlines())
 
    def clear(self):
        """Clear all printed lines"""
        sys.stdout.write(
            self.lines * (UP + BOL + CLEAR_EOL)
        )


DEFAULT_BAUDRATE=57600
DEFAULT_TIMEOUT=6.0
DEFAULT_RETRY=5
DEFAULT_PORT="/dev/ttyS0"
XONXOFF=1
REBOOT_COMMAND="robot reboot"

class Downloader:
    def __init__(self,downfile, serPort =DEFAULT_PORT, boudrate=DEFAULT_BAUDRATE):
        self.ser = serial.Serial(serPort, boudrate, parity=serial.PARITY_NONE,xonxoff=XONXOFF ,timeout=DEFAULT_TIMEOUT)
        o=fcntl.fcntl(self.ser.fd,fcntl.F_GETFD)
        fcntl.fcntl(self.ser.fd,fcntl.F_SETFD,o or fcntl.FD_CLOEXEC)
        self.ser.flushInput()
        self.ser.flushOutput()
        while self.ser.inWaiting():
            self.ser.read()
        self._download_file=downfile

    def run(self):
        print "start..."
        r=self.reboot_mcu()
        if r!=0:
            r=self.reboot_mcu(send_cmd=False)
            if r!=0:
                print "cannot reboot mcu"
                return -3
        r=self.download()
        if r!=0:
            print "error accured when downloading"
            return -4
        print "downloaded successfully"
        return 0
    
    def __checksum(self, s):
        return reduce(lambda x, y:x+y, map(ord, s)) & 0xff
        
    def __encodeHexByte(self, num):
        s = hex(num)
        return s.replace('x', '0')[-2:]
        
    def __decodeHexByte(self, s):
        return int(s, 16)

    """
    Download Manager Menu                  
1) Enter password                      
2) Set password                        
3) Download and run program            
4) Execute downloaded program          
Enter Choice:                          
    """
    
    
    def send_reboot_command(self):
        packet=chr(0x02)+ chr(0x44)
        packet+="01"  #self.__encodeHexByte(1)
        checksum=self.__checksum(REBOOT_COMMAND)
        packet+=REBOOT_COMMAND
        packet+=self.__encodeHexByte(checksum)
        packet+=chr(0x03)
       # print "send packet %s" % (packet)
        self.ser.write(packet)

    def reboot_mcu(self,send_cmd=True):
        for i in xrange(1,4):
            if send_cmd:
                print "sending reboot command"
                self.send_reboot_command()
            li=""
            enter_choice=False
            enter_password=False
            start=time.time()
            while True:
                #print "reading..."
                if time.time() - start > 15*i:
                    print "time out when receving bootloader's output"
                    break
                while self.ser.inWaiting():
                    li=li+self.ser.read()
                #print "read a line >>>> %s" %  (li)

                if li.find("Enter Choice:") != -1:
                   # print li
                    li=""
                    if not enter_choice:
                       # print "Enter Choice for password"
                        enter_choice=True
                        self.ser.write("1")
                    else:
                       # print "Enter Choice for download"
                        self.ser.write("3\n")
                        return 0
                    continue
                
                if enter_choice and li.find("Enter password:")!=-1:
                    #print li
                   # print "Enter password"
                    li=""
                    self.ser.write("123\n")
                    continue
                """
                if li.find("Send HEX file as raw ASCII or Binary")!=-1:
                    return 0
                """
        return -1
    
    def safe_write(self,buf):
        while True:
            try:
                errno.errorcode=0
                d=self.ser.write(buf)
            except:
                if errno.errorcode==errno.EINTR:
                    buf=buf[d:]
                    continue
                raise
            if d==len(buf):
                break
            buf=buf[d:]
    
    def safe_read(self):
        buf=""
        try:
            errno.errorcode=0
            buf=self.ser.read()
        except:
            if errno.errorcode!=errno.EINTR:
                raise
 
    def download(self):
        global batch_mode
        
        li=""
        start=time.time()
        begin=False
        while time.time() - start < 15:
            li=li+self.ser.read()
            if li.find("Send HEX file as raw ASCII or Binary")!=-1:
                begin=True
                break
        if not begin:
            print "error accured when downloading, please run this program again later"
            sys.exit(-3)
        print  li
        time.sleep(2)
        f=open(self._download_file)
        lines=0
        while True:
          if f.readline():
              lines=lines+1
          else:
              break
        #print "there are %d lines in the file" % lines
        
        if batch_mode==0:
            p = ProgressBar(color=GREEN)
        curline=0
        try:
           f.seek(0,0)
           while True:
               buf=""
               errno.errorcode=0
               try:
                   li=f.readline()
               except:
                   pass

               if li:
                   curline=curline+1
                   try:
                       if batch_mode==0:
                           p.render(int(curline*100/lines),"downloading %02d%%" % (int(curline*100/lines)) )
                   except:
                       pass
                  # print "send data:" + li
                   self.ser.write(li)
                   
                   time.sleep(0)
               else:
                   try:
                       if batch_mode==0:
                           p.render(101,"finished")
                   except:
                       pass
                   break
               if self.ser.inWaiting():
                   buf=buf+self.ser.read()
                   if buf.find("invalid")!=-1 or buf.find("error")!=-1 or buf.find("timeout")!=-1:
                       print "exception accured when downloading, make sure the image %s is well formed" % self._download_file
                       return -1
        except Exception,ex:
            print "exception %s accured when open file: %s" % (ex,self._download_file)
            return -1
        finally:
            f.close()

        li=self.ser.read()
        if li.find("invalid")!=-1 or li.find("error")!=-1:
            print li
            print "exception accured when downloading, make sure the image %s is well formed" % self._download_file
            return -1
      #  print "response from boot loader:" + li       
        return 0


def usage():
    print "Usage: %s [hex image]" % (sys.argv[0])

def __unlock():
    open("/tmp/thread-lock", "w+").write("0")

def __lock():
    open("/tmp/thread-lock", "w+").write("1")

import atexit
atexit.register(__unlock)


def sig_handler (signum,frame):
    print "you can not close downloader when the downloading progress has not been finished"

def isS250():
    if os.path.isfile("/etc/kioskcapacity"):
        file = open('/etc/kioskcapacity', 'r')
        capacity = file.readline().strip()
        if capacity == "500":
            return False
    
    return True

S250_URL = "http://update.cereson.com/~update/current"
S500_URL = "http://update.cereson.com/~update/S500"

def main():
    global batch_mode
    
    file_name="CONTROL.HEX"
    if len(sys.argv)>2 and sys.argv[2]=='-b':
        batch_mode=1
    if len(sys.argv)>1:
       if os.path.exists(sys.argv[1]):
           file_name=sys.argv[1]
       else:
           print "file %s does not exist" % (sys.argv[1])
           sys.exit(-1)
    else:
        if isS250():
            FIRMWARE_URL = S250_URL
        else:
            FIRMWARE_URL = S500_URL
        print "download from %s" % FIRMWARE_URL
        
        import urllib
        f=urllib.urlopen(os.path.join(FIRMWARE_URL, "CONTROL.HEX.MD5"))
        md=f.read()
        md=md.split()[0]
        #print md
        f=urllib.urlopen(os.path.join(FIRMWARE_URL, "CONTROL.HEX"))
        fd=open('./CONTROL.HEX','w')
        fd.truncate(0)
        import md5
        
        for i in xrange(0,2):
            m=md5.new()
            fmd=''
            while True:
                buf=f.read()
                if not buf or len(buf)==0:
                    fmd=m.hexdigest()
                    print fmd
                    break
                fd.write(buf)
                m.update(buf)
            if md==fmd:
                break
        fd.close()
        if md!=fmd:
            print "error accured when downloading file from update server, please try later"
            sys.exit(-5)
        #sys.exit(1)
        file_name='./CONTROL.HEX'
        
            
        """
        if os.path.exists('./CONTROL.HEX'):
            print "can not find hex image file"
            usage()
            sys.exit(-1)
        """
    __lock()
 #   os.system("/home/mm/kiosk/mkc2/mkc.py stop")
    os.system("fuser -k /dev/ttyS0")
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    signal.signal(signal.SIGHUP,signal.SIG_IGN)
    signal.signal(signal.SIGQUIT,signal.SIG_IGN)
    signal.signal(signal.SIGINT,signal.SIG_IGN)
    downloader=Downloader(file_name)
    downloader.run()
    __unlock()
    """
    ret=raw_input("Do you want to start mkc? [y/N]")
    if ret and ret.lower=='y':
        os.system("/home/mm/kiosk/mkc2/mkc.py start")
    """ 
    sys.exit(0)
 

if __name__=="__main__":
    try:
        main()
    except Exception,ex:
        sys.exit(-1)
