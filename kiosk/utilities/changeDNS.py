#!/usr/bin/python
#Filename:changeDNS.py

__VERSION__ = 'ChangeDNS-1.0-testing-2007-09-11 08:20'

import os
import sys
import pexpect
import logging, logging.handlers


##############constant############
LOG_LOCAL=2
LOG_REMOTE=1
#################################

##################switch config ##############

LOG_MODE=2
LOG_REMOTE_HOST='localhost'
LOG_REMOTE_PORT= logging.handlers.DEFAULT_TCP_LOGGING_PORT
DEBUG=0
LOG_LEVEL=logging.DEBUG
LOG_CONSOLE_LEVEL=logging.DEBUG
LOG_FORMAT='%(asctime)s %(levelname)s %(message)s'
LOG_FILE='/tmp/changDNS.log'
LOG_FILE_MODE='w'
###########################################

logging.basicConfig(level=LOG_LEVEL,
                    format=LOG_FORMAT,
                    filename=LOG_FILE,
                    filemode=LOG_FILE_MODE)

rootLogger = logging.getLogger('')
rootLogger.setLevel(LOG_LEVEL)

if LOG_MODE%2 ==1:
    socketHandler = logging.handlers.SocketHandler(LOG_REMOTE_HOST, LOG_REMOTE_PORT )
    rootLogger.addHandler(socketHandler)


if DEBUG==1:
    console = logging.StreamHandler()
    console.setLevel(LOG_CONSOLE_LEVEL)
    formatter = logging.Formatter(LOG_FORMAT)
    console.setFormatter(formatter)
    rootLogger.addHandler(console)
dnslogger=logging.getLogger('DNS change')


class ChangeDNS:
 def __init__ (self,dict1 = {},dict2 = {}):
     self.dict1 = {'1' : 'Default' , '2' : 'Opendns'}
     self.dict2 = {self.dict1['1'] : '' ,
                   self.dict1['2'] : '208.67.222.222,208.67.220.220'}
 
 def usage_ball(self):
    print '\nUsage: ./changeDNS.py [option]'
    print '\t--version show software version'
    print '\t-h print this help\n'


 def setdict(self,dict1,dict2):
     self.dict1 = dict1
     self.dict2 = dict2
     pass


 def CheckCurrentStatus(self,quantity):
  no = 2  
  status = 2
  while no <= quantity:
    dnsip = self.dict2[self.dict1[str(no)]]

    fd = open('/etc/resolv.conf','r')
    content = fd.read()
    fd.close()

    number = 0
    while number != -1:
         number = dnsip.find(',')
         if number == -1:
             ip = dnsip
             break
         ip = dnsip[:number]
         break

    keyword = ' ' + ip
    number = content.find(keyword)
    if number == -1:
       pass
    else:
       content = content[number+1:]
       number = content.find('nameserver')
       content = content[:number-1]
     
    if ip == content:
          status = no
          return self.dict1[str(status)]
    else:
          status = 1
    no = no + 1	   
  return self.dict1[str(status)]
 
 def selectdns(self):
   while 1:
    number = 1
    print '\nThere are ' + str(len(self.dict1)) + ' alternative DNS settings.\n\n'
    print 'Select DNS :\n'
    resolv = self.CheckCurrentStatus(len(self.dict1))

    for name,addr in self.dict2.items():
        if resolv == name:
           print '*\t%d %s' %(number,name)
        else:
           print ' \t%d %s' %(number,name)
        number = number + 1
    print ' \t' + str(len(self.dict1)+1) + ' Exit'	
    print '\nCurrent is ' + resolv
    print '\nPlease select one:'
    self.select = raw_input()
    if self.select == str(len(self.dict1)+1):
        sys.exit(0)
    else:	
        if self.select not in self.dict1:
               continue
        else:
            if self.dict1[self.select] not in self.dict2:
                print 'no this item!'
                continue
            else:
                break
   return self.select

 def checkfile(self):

    fd = open('/etc/resolv.conf','r')
    content = fd.read()
    fd.close()   
    if content == '':
      return(0)
    else:
      print 'Very thing\'s OK'
      return(1)

 def checkdns(self,dnsip):
     iplist = []
     number = 0
     while number != -1:
       number = dnsip.find(',')
       if number == -1:
         ip = dnsip
         cmd = 'dig www.baidu.com @' + ip + ' | grep ";; ANSWER SECTION:" > /dev/null'
         print 'Testing connect ' + ip + '....\n'
         resolv = os.system(cmd)
         if resolv == 0:
              iplist.append(ip)
         else:
              print 'The DNS can not connect!\n'
              os.abort()
         break
       ip = dnsip[:number]
       cmd = 'dig www.baidu.com @' + ip + ' | grep ";; ANSWER SECTION:" > /dev/null'
       print 'Testing connect ' + ip + '....\n'
       resolv = os.system(cmd)
       if resolv == 0:
            iplist.append(ip)
       else:
            print 'The DNS can not connect!\n'
            os.abort()
       dnsip = dnsip[number+1:]

     if len(iplist) == 0:
        print 'The DNS can not use!!'
        os.abort()
     else:
        count = 0
        ipstr = ''
        while  count < len(iplist):
          if ipstr == '':
             ipstr = ipstr + iplist[count]
          else:
             ipstr = ipstr + ',' + iplist[count]
          count = count + 1
        return ipstr 


 def changedns(self):
    count = 0
    line = ' '
    PASSWORD = 'howcute121'
   
    select = self.selectdns()
    
    if self.dict1[self.select] == 'Default':
         fd = open('/etc/dhcp3/dhclient.conf','r')
         fd1 = open('/tmp/dhclient.conf','w')
         while line != '':
           line = fd.readline()
           number = line.find('prepend')
           number1 = line.find('domain-name-servers')
           if number != -1 and number1 != -1:
             continue
           else:  
             fd1.write(line)
         fd1.close()   
         fd.close()

         cmd = 'echo ' + PASSWORD + ' | sudo -S sh -c "/bin/cp -f /tmp/dhclient.conf /etc/dhcp3/"' 
         os.system(cmd)

         print 'The setting has been restored to default\n'
    else:
         dnslist = self.checkdns(self.dict2[self.dict1[self.select]])
  
         print self.dict1[select] + ' can use!\n'

         addline = 'prepend domain-name-servers ' + dnslist + ';'
          
         fd = open('/etc/dhcp3/dhclient.conf','r')
         fd1 = open('/tmp/dhclient.conf','w')
         while line != '':
           line = fd.readline()
           number = line.find('prepend')
           number1 = line.find('domain-name-servers')
           if number != -1 and number1 != -1:
             continue
           else:  
             fd1.write(line)
         fd1.write(addline)
         fd1.close()   
         fd.close()
         
    
         cmd = 'echo ' + PASSWORD + ' | sudo -S sh -c "/bin/cp -f /tmp/dhclient.conf /etc/dhcp3/"' 

         os.system(cmd)
   
   
    cmd = 'echo ' + PASSWORD + ' |sudo -S sh -c "pkill -9 dhclient3"'
    os.system(cmd)
#    cmd = 'echo ' + PASSWORD + ' |sudo -S sh -c "/sbin/dhclient3"'
    cmd = 'echo ' + PASSWORD + 'sudo -S sh -c "/sbin/dhclient3"'
#    os.system(cmd)
#     cmd = 'sudo -S sh -c "dhclient3"'
 
    child = pexpect.spawn(cmd)
    index = child.expect([pexpect.TIMEOUT,'Password:',pexpect.EOF])
    if index == 0:
      print 'some things ERROR! (in try sudo)'
      os.abort()
    elif index == 1:
      child.sendline(PASSWORD)
      child.expect(pexpect.EOF)
    elif index == 1:
      pass
    child.close() 
         
#    cmd = 'echo ' + PASSWORD + ' |sudo -S sh -c "pkill -9 dhclient3"'
#    cmd = 'sudo -S sh -c "dhclient3"'

#    child = pexpect.spawn(cmd)
#    index = child.expect([pexpect.TIMEOUT,'Password:',pexpect.EOF])
#    if index == 0:
#      print 'some things ERROR! (in try sudo)'
#      os.abort()
#    elif index == 1:
#      child.sendline(PASSWORD)
#      child.expect(pexpect.EOF)
#    elif index == 1:
#      pass
#    child.close()          

    resolv = 0
    while count < 6 and resolv != 1:  
      resolv = self.checkfile()
      if resolv == 0:
        print 'retrying....'
      count = count + 1

if __name__=="__main__":
    
    chdns = ChangeDNS()
    if len(sys.argv) == 1:
        chdns.changedns()
    elif len(sys.argv) == 2:
        if sys.argv[1] == '--version':
                print 'VERSION:  ' + __VERSION__
        elif sys.argv[1] == '-h':
                chdns.usage_ball()
        else:
                chdns.usage_ball()
    else:
        chdns.usage_ball()

   
