#!/usr/bin/env python
'''
For solve gdm crash
created by Tavis
'''
import os

def change_file():
    print "change /etc/X11/default-display-manager"
    os.system("echo howcute121 | sudo -S sed -i 's/\/usr\/sbin\/gdm/false/' /etc/X11/default-display-manager")
    
    print "change /etc/rc.local"
    f = open("/etc/rc.local", "r")
    lines = f.readlines()
    f.close()
    if ("/home/mm/kiosk/bin/initscreen\n") in lines :
        print "rc.local has been changed!"
        return
    #cmd = "echo howcute121 | sudo -S sed -i 's/^exit 0/\/usr\/bin\/xinit\/\nsu mm -c '\/home\/mm\/kiosk\/bin\/initscreen\/'\nexit 0/' /etc/rc.local"
    cmd = "echo howcute121 |sudo -S sed -i '/^exit 0/d' /etc/rc.local"
    os.system(cmd)
    cmd = '''echo howcute121 | sudo -S sh -c "echo '/usr/bin/xinit & \nsu mm -c \'/home/mm/kiosk/bin/initscreen\'\nexit 0\n' >> /etc/rc.local"'''
    os.system(cmd) 
    print "/etc/rc.local: add xinit initscreen"
    os.system("echo howcute121 | sudo -S reboot")


if __name__ == "__main__":
    change_file()
