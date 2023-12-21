"""

MovieMate Kiosk Core V2.0
CopyRight MovieMate, Inc.

Created 2008-10-07 Vincent
vincent.chen@cereson.com

Filename: config.py
Global Constants

Change Log:
2009-03-03 Vincent, add 2 constant for register kiosk ID
"""

import os

def getHostID():
    try:
        file = open('/etc/hostname', 'r')
        hostname = file.readline().strip()
        i = hostname.index('A')
        return int(hostname[i + 1:])
    except:
        return 100

def getKioskId():
    file = open('/etc/hostname', 'r')
    hostname = file.readline().strip()
    
    return hostname

KIOSK_CONF = "/etc/kioskhome"
file = open(KIOSK_CONF, 'r')
KIOSK_HOME = file.readline().strip()

FMTTIME = '%Y-%m-%d %H:%M:%S'

LOGGING_STREAM_FORMAT = '%(asctime)s %(name)s %(levelname)s %(message)s'
LOGGING_FILE_FORMAT = '%(asctime)s %(name)s %(levelname)s %(message)s'
LOGGING_MAX_BYTES = 1024 * 1024 * 3
LOGGING_BACKUP_COUNT = 5

QTGUI = os.path.join(KIOSK_HOME, "kiosk/mkc2/gui/gui.py")

RESTART_INTERVAL = 60

machine_port = '/dev/ttyS0'
card_port = '/dev/ttyS0'
printer_port = '/dev/ttyS2'

flash_port = 50007

Q_UNEXPECTED_MAX_SIZE = 30

LOCALE_PATH = "./locale"
LOCALE_MODULE = "mkc"

CONN_SERVICE_URL = "atlas.cereson.com:7675"
#CONN_SERVICE_URL = "192.168.1.52:9675"
LOCK_FILE_PATH = os.path.join(KIOSK_HOME, "kiosk/needReg")
KIOSK_CAPACITY_PATH = "/etc/kioskcapacity"

MKC_HOME = os.path.join(KIOSK_HOME, "kiosk/mkc2")
ARRANGE_FATAL_LOG = os.path.join(KIOSK_HOME, "kiosk/var/log/fatalerror.log")
MVMOUSE = os.path.join(KIOSK_HOME, "kiosk/bin/mvmouse")

HDMI_PORT = "HDMI-2"
VGA_PORT = "VGA"
HDMI_CONNECT = os.path.join(KIOSK_HOME, "kiosk/tmp/hdmi.connected")
HDMI_LOCK_FILE = os.path.join(KIOSK_HOME, "kiosk/tmp/hdmi.lock")

HOST_ID = getHostID()
MKC_FLAG = 'flag'

NO_DISC_SBJ = "Notification - %(host_id)s - No Disc "
NO_DISC_ALERT = \
"""
<p><b> Warning - Empty Slot Detected </b></p><br\>
<p>You are receiving this email as kiosk <B>%(host_id)s</B> has experienced an empty slot error. What this means is that the kiosk attempted to retreive a disc from slot <B>slot %(slot_id)s</B> and found that it was empty.</p>
<p>There is a couple of reasons why this might have occured:</p>
<p>1. Someone manually removed a disc from the kiosk without following the correct unload proceedure.</p>
<p>2. The disc may have dropped to the floor of the kiosk</p>
<p>3. The kiosk was recently moved and some of the inventory is out of place.This is not an urgent situation but will require some operator intervention to correct. The next time you are at the kiosk you will want to visually inspect the slot and bottom of the kiosk. Depending on the outcome of this inspection follow either of these steps:</p>
<p>1. If you find the disc, simply hit the return button on the touch screen and return the disc.</p>
<p>2. If you can't locate the disc, contact Tech Support and have them erase the slot for you.<b></p>
<p>NOTE - This message is just an informational warning, it's important to remember that the kiosk is still functioning normally at this time.</b></p>
"""

RFID_FAIL_SBJ = "Notification - %(host_id)s - RFID READ FAIL"
RFID_FAIL_ALERT = \
"""
<p><b> Warning - RFID Error Detected </b></p><br\>
<p>You are receiving this emails as we have detected an RFID read failure on kiosk <B>%(host_id)s</B>. The disc that generated this error is in<B>slot %(slot_id)s</B>. </p>
<p>There is several reasons why the RFID tag on the disc will fail but typically it's because a customer has tampered with the tag itself and it has become unusable.</p>
<p>The kiosk has automatically marked the disc as BAD to prevent other renters from attempting to rent it. Please note, this is not an urgent situation but there is some steps you will need to take to remedy it:</p>
<p>1. Unload the disc from the kiosk.</p>
<p>.2. Remove the old RFID tag and apply a new RFID tag</p>
<p>3. Load the disc back into inventory using the normal loading proceedure.</p><br\>
<p>The slot will now be marked as usuable and the disc can be rented again.</p>
<p>NOTE - This message is just an informational warning, it's important to remember that the kiosk is still functioning normally at this time.</b></p>
"""

FATAL_ERROR_SBJ = "FATAL ERROR - %(host_id)s."
FATAL_ERROR_ALERT = \
"""
<p><b> Alert - Kiosk Jammed </b></p>
<p>You are receiving this email as kiosk <B>%(host_id)s</B> has experienced a jam and is currently not operating. For the kiosk to begin working again, operator intervention is required.</p>
<p>To correct the jam, please follow these steps:</p>
<p>1. Power down the kiosk, to do this simply unplug it from the outlet.</p>
<p>2. Open the front door of the kiosk.</p>
<p>3. Look inside the kiosk for any obvious jams, common jam locations are: 
<p>  a. Exchange Box - This is where the discs are inserted and ejected </p>
<p>  b. Carriage - This is the module that moves the discs from slot to slot </p>
<p>  c. Floor - Sometimes a disc will fall to the bottom of the kiosk and obstruct the robotics.</p>
<p>  d. Rack - Look for any discs sticking out from any of the 4 racks.</p>
<p>4. Clear the obstruction</p>
<p>5. Power on the kiosk, wait 2 mins for it to start-up.</p>
<p>6. Replace any cases that are damaged</p>
<p>7. Return any discs that were jammed or out of place.</p>
<p>The steps outlined above will fix the majority of jams, if you encoutner further problems please contact our tech support dept.</p>
<p><b>NOTE - This is an alert message, the kiosk is NOT functioning at this time.</b></p>
"""

PRINTER = "/dev/ttyS5"

#=============================================================================
# EOF
#-----------------------------------------------------------------------------
