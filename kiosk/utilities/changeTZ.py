#!/usr/bin/python
#Filename:changeTZ.py

__VERSION__ = '0.05'

import os
import sys
import pexpect

################
# Main Routine #
################

TZLIST = ('PRC','US/Alaska','US/Aleutian','US/Arizona','US/Central','US/Eastern',
'US/East-Indiana','US/Hawaii','US/Indiana-Starke','US/Michigan','US/Mountain',
'US/Pacific','US/Samoa', 'Africa/Johannesburg', 'Australia/Sydney', 'America/Puerto_Rico', 
'Canada/Saskatchewan', 'Asia/Dubai', 'Atlantic/Bermuda', 'Australia/Brisbane', 
'Australia/Queensland', 'GMT', 'Europe/Dublin', 'Europe/London', 'Europe/Copenhagen', 
'Europe/Oslo', 'Europe/Helsinki')

def current_tz():
    print 'Your Timezone now set to: ',
    print open('/etc/timezone').read()
    print 'option -h show all help'

def usage_ball():
    print __VERSION__
    print '\n ./changeTZ.py [-i | -h | <setto> | null]'
    print '\t-i go in to interaction interface'
    print '\t-h print this help'
    print '\tset timezone to <setto>'
    print '\tnull show current timezone'

def resetTZ(newTZ):

    if newTZ not in TZLIST:
        print 'Oooops!! I have no such TimeZone info!!!'
        os.abort()

    PASSWORD = 'howcute121'
    cmd = 'sudo sh -c "echo ' + newTZ + ' > /etc/timezone "'
    #print cmd

    child = pexpect.spawn(cmd)
    index = child.expect([pexpect.TIMEOUT,'[Pp]assword',pexpect.EOF])
    if index == 0:
        print 'some things ERROR! (in try sudo)'
        os.abort()
    elif index == 1:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF)
    elif index == 2:
        pass
    print 'STAGE 1 DONE'
    child.close()


    cmd = 'sudo ln -fs /usr/share/zoneinfo/' + newTZ + ' /etc/localtime'
    #print cmd

    child = pexpect.spawn(cmd)
    index = child.expect([pexpect.TIMEOUT,'Password:',pexpect.EOF])
    if index == 0:
        print 'some thins ERROR! (in try sudo)'
        os.abort()
    elif index == 1:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF)
    elif index == 2:
        pass
    print 'STAGE 2 DONE'
    child.close()

def interaction():
    os.system('clear')
    print 'which timezone do you like best ? Answer in Number pls!'
    for i in range(len(TZLIST)):
        print i, '\t->\t', TZLIST[i]
    input = raw_input()
    try:
        input = int(input)
    except:
        print 'DoNOT test me!! I am NOT baby!'
        print 'I just need a number'
        os.abort()
    if input < 0 or input > len(TZLIST) - 1:
        print 'the number is out of my range!'
        os.abort()

    print 'set to ', TZLIST[input], '...'
    resetTZ(TZLIST[input])


if __name__ == '__main__':

    if len(sys.argv) == 1:
        current_tz()
    elif len(sys.argv) == 2:
        if sys.argv[1] == '-i':
                interaction()
        elif sys.argv[1] == '-h':
                usage_ball()
        else:
                resetTZ(sys.argv[1])
    else:
        usage_ball()
