#!/usr/bin/python

import os
import sys
import time
import pexpect

try:
    import psyco
except:
    pass

PASSWORD = 'howcute121'

def usage():
    text = """usage:
    %s <-r or -t>
    """
    print text %(sys.argv[0])
    
    
def doscp(port, user, hostname, source, destination, type="put"):
    if type == "get":
        cmd = 'scp -r -P%s %s@%s:%s %s' %(port, user, hostname, source, destination)
    else:
        cmd = 'scp -r -P%s %s %s@%s:%s ' %(port, source, user, hostname, destination)
    print 'will do cmd ->', cmd
    
    child = pexpect.spawn(cmd,timeout=None)
    try:
        child.setlog(sys.stdout)
    except:
        child.logfile=sys.stdout
        
    index = child.expect([pexpect.TIMEOUT, 'RSA key', 'password:', pexpect.EOF])
    if index == 0: # timeout
        print 'cannot connect to remote host'
        return False
        
    elif index == 1: # no public key ready
        child.sendline('yes')
        index = child.expect([pexpect.TIMEOUT, 'Permission denied, please try again', 'password:'])
        if index == 0: # timeout
            print 'connection broken'
            return False
        elif index == 1: # password again?
            print 'password error'
            return False
    elif index == 3:
        #print 'cannot login'
        print child.before
        return False
    
    child.sendline(PASSWORD)
    index = child.expect([pexpect.EOF, 'Permission denied, please try again', pexpect.TIMEOUT])
    if index == 0:
        if child.before.find('No such file or directory') != -1 or child.before.find('Permission denied') != -1:
            print 'source or destination not usable'
            return False
        else:
            return True
    elif index == 1:
        print 'password error'
        child.close()
        return False
    elif index == 2:
        print 'connect broken..'
        return False

def main():
    global PASSWORD
    argc = len(sys.argv)
    if argc != 2: 
        usage()
        sys.exit(-1)
    if sys.argv[1] == "-r":
        hostname = "flora.cereson.com"
        PASSWORD = 'update5810'
    elif sys.argv[1] == "-t":
        hostname = "cereson.51vip.biz"
        PASSWORD = 'howcute121'
    else:
        usage()
        sys.exit(-1)
    

    doscp(22,"update",hostname,"~/kiosk/mkd2","/home/mm/kiosk","get")
    doscp(22,"update",hostname,"~/kiosk/mkd2.sys","/home/mm/kiosk","get")
    doscp(22,"update",hostname,"~/event.d","/tmp","get")
    os.system("echo howcute121 | sudo -S chown -R root.root /tmp/event.d/")
    os.system("echo howcute121 | sudo -S cp -rf /tmp/event.d/* /etc/event.d/")
    os.system("echo howcute121 | sudo -S rm -f /etc/event.d/hdmimonitor /etc/event.d/ks/hdmimonitor")
    os.system("mkdir /home/mm/kiosk/mkd2.data")
    os.system("rm -rf /home/mm/kiosk/hdmimonitor")
    os.system('/usr/bin/gconftool-2  --type string --set  /desktop/gnome/background/picture_options  "wallpaper"')
    os.system('/usr/bin/gconftool-2  --type string --set  /desktop/gnome/background/primary_color  "#000000"')
        


####################
### main routine ###
if __name__ == '__main__':
    main()
