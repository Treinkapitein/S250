#!/usr/bin/env python

import sys
import os
import commands

def get_hdmi_port():
    cmd = "echo 'howcute121' | sudo -S sh -c " \
          "\"dmidecode | grep -A8 'Base Board Information$' | grep 'Product Name'\""
    output = commands.getoutput(cmd)
    base_board = output.split(":")
    if base_board[-1].strip() == "DG45FC":
        hdmi_port = "HDMI-1"
    else:  # "G41"
        hdmi_port = "HDMI-2"
    return hdmi_port

if __name__ == "__main__":

    w,r = os.popen2("DISPLAY=:0.0 xrandr -q | grep %s | grep -w -i connected" % get_hdmi_port())
    data = r.read()
    w.close()
    r.close()

    if not data:
        print("HDMI not connected") 
    else:
        print("HDMI connected") 

    sys.exit(0)

