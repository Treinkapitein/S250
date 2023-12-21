#!/usr/bin/python
#Filename:restart_rrs.py

"""
The Script handle rrs
usage:
      restart_rrs.py [1|2|3] or 
      restart_rrs.py without argv means all
"""

import os
import sys

# Get the home dir
def homePath():
    KIOSK_HOME = '/etc/kioskhome'
    fd = file(KIOSK_HOME, 'r')
    KIOSK_HOME_DIR = fd.readline().rstrip()
    fd.close()
    return KIOSK_HOME_DIR

def usage_ball():
      print 'usage:'
      print sys.argv[0] + ' [1|2|3]'
      print 'no argv means all'

def getHostname():
      fd = open('/proc/sys/kernel/hostname')
      all = fd.read()
      fd.close()
      return all[:-1]

def restart(id):
      HOSTDICT = {1:('remote.cereson.com',5), 2:('remote.cereson.com',4), 3:('72.51.42.37',3)}
      
      hostport = HOSTDICT.get(id)
      host = hostport[0]
      port = hostport[1]
      
      hostname = getHostname() # like S100-B037
      
      tmp = chr(ord(hostname[5]) - 0x10) # cover A to 1, B to 2, etc
      tmp += hostname[6:]

      port = str(port) + tmp
      
      ###findcmd = 'lsof -F -i :' + port
      findcmd = 'ps -eo pid,command | grep -w rrs | grep -v "grep" | grep p' + str(port)
      #print findcmd
      wfd, rfd = os.popen2(findcmd)
      all = rfd.read().split()
      wfd.close()
      rfd.close()
      if len(all) == 0:
            print 'no rrs to restart \n'
      else:
            pid = all[0]
            killcmd = 'kill -9 ' + str(pid)
            os.system(killcmd)
            #print killcmd

      startcmd = 'nohup '+homePath()+'/kiosk/bin/rrs ' + host +  ' -p' + port + ' -R 5 -t 5 &'
      #startcmd = 'nohup /home/mm/kiosk/rrs/rrs ' + host +  ' -p' + port + ' -R 5 -t 5 &'
      os.system(startcmd)
      #print startcmd

################
# Main Routine #
################
if __name__ == '__main__':
      if len(sys.argv) == 1:
            print 'restarting all rrs connector...'
            for i in range(1,4):
                  restart(i)
            print 'DONE!!! \n'
      elif sys.argv[1] in ('1','2','3'):
            print 'restarting one rrs connector: ', sys.argv[1], '...'
            restart(int(sys.argv[1]))
            print 'DONE! \n'
      else:
            usage_ball()
