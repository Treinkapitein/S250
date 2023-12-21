#!/usr/bin/python

"""
Change Log: 
    2009-03-30 Vincent Add initRobot when test starts
    2009-02-18 Vincent For #1585
"""

import getopt
import traceback

# =================================================================
# =    def _testMobject
# -----------------------------------------------------------------
def _testMobject():
    from mobject import Coupon
    from mobject import Disc
    from mobject import ShoppingCart

    c1 = Coupon("19000", "<xml>testc1</xml>", "1 Dollar Free")
    c2 = Coupon("27300", "<xml>testc2</xml>", "24 Hours Free")
    c0 = Coupon("99999", "<xml>testc0</xml>", "Rent 1 Get 1 Free")

    d1 = Disc("rfid1", "upc1")
    d1.coupon = c1

    print "Disc after init: %s\n" % str(d1)

    d2 = Disc("rfid2", "upc2")
    d2.coupon = c2

    s = ShoppingCart()
    s.addDisc(d1)
    s.addDisc(d2) 
    s.coupon = c0
    
    print "Shopping Cart: %s(%s discs)\n" % (str(s), s.getSize())

    s.removeDisc(d2.rfid)
    print "Shopping Cart After d2 removed: %s\n" % s.getDiscs()

    s.addDisc(d1)
    s.addDisc(d2)
    print "Shopping Cart After d1, d2 added: %s\n" % s.getDiscs()

    s.ejectDisc(d1.rfid)
    print "Shopping Cart Discs after d1 ejected: %s(%s)\n" % (s.getDiscs(), s.getSize())
    print "Shopping Cart Ejected Discs: %s(%s)\n" % (s.getEjectedDiscs(), s.getEjectedDiscsSize())

    s.clear()
    print "Shopping Cart after clear: %s(%s)\n" % (str(s), s.getSize())

# =================================================================
# =    def _testMobject
# -----------------------------------------------------------------
def _testSetLanguage():
    import mcommon

    #LAN_LIST = ["cn", "en", "tw", "fr", "de", "es"] 2008-11-20 Chinese still get issues to fix.
    LAN_LIST = ["en", "fr", "de", "es", "ar"]

    for lang in LAN_LIST:
        mcommon.setLanguage(lang)
        print _("%s: Invalid security tag detected. Please take the disc back.") % lang.upper()

from control import *
from mcommon import initRobot
#from test_control import *
# =================================================================
# =    class SelfTest
# -----------------------------------------------------------------
class SelfTest:

    def __init__(self, slots, times, random):
        robot = Robot()
        self.robot = robot.getInstance()

        initRobot()

        self._getTestSlots(slots)
        self._getTestTimes(times)
        self._isTestRandom(random)

        self.rfidWrongTime = 0
        self.loopCount = 0

    def _getTestSlots(self, slots):  
        a = range(101, 171) # Get 101 - 170 here
        b = range(228, 271)
        c = range(501, 571) # Get 501 - 570
        d = range(601, 671)

        self.needTestSlotList = []
        if slots:
            lstSlot = slots.split(",")
            for ele in lstSlot:
                if str(ele).lower() in ["a", "b", "c", "d"]:
                    statement = "self.needTestSlotList += %s" % str(ele).lower()
                    exec(statement)
                elif (ele.isdigit()) and (len(ele) == 3):
                    self.needTestSlotList.append(int(ele))
                elif ele.find("-") > -1:
                    lst = ele.split("-")
                    self.needTestSlotList += range(int(lst[0]), int(lst[1]) + 1)
        else:
            self.needTestSlotList = a + b + c + d  

        self.needTestSlotList.sort()
        print "Slots will be tested:\n%s" % self.needTestSlotList

    def _getTestTimes(self, times):
        self.testTimes = [1]
        n = times
        if str(n).isdigit():
            n = int(n) + 1
            self.testTimes = range(1, n)            
        print "Will Test %s Round" % max(self.testTimes)

    def _isTestRandom(self, random):
        print "=============="
        if random:
            import random
            random.shuffle(self.needTestSlotList)
            print "= Random ON  ="
        else:
            print "= Random OFF ="

        print "=============="

    def _getRfidErrorRate(self):
        return "%s%%" % (round(self.rfidWrongTime/float(self.loopCount), 4) * 100)

    def _rackToExchange(self, slotID):
        print "[Slot %s To Exchange]......" % slotID
        self.lastCmd = "rack_to_exchange: %s" % slotID
        r = self.robot.doCmdSync("rack_to_exchange", {"slot":slotID}, timeout = 300)
        if not (r.get("errno") == ROBOT_OK):
            raise Exception("rack_to_exchange result %s" % r)

    def _exchangeToRack(self, slotID):
        print "[Exchange To Slot %s]......" % slotID
        self.lastCmd = "exchange_to_rack: %s" % slotID
        r = self.robot.doCmdSync("exchange_to_rack", {"slot":slotID}, timeout = 300)
        if not (r.get("errno") == ROBOT_OK):
            raise Exception("exchange_to_rack result %s" % r)

    def _readRfid(self):
        print "[Reading RFID]......"              
        self.lastCmd = "read_rfid"      
        r = self.robot.doCmdSync("read_rfid", {})                  
        if not (r.get("errno") == ROBOT_OK):
            self.rfidWrongTime += 1
            print "[ERROR Reading RFID] Err Rate: %s" % self._getRfidErrorRate()

    def _exchangeOpenClose(self):
        print "[Exchange door open/close]......"              
        self.lastCmd = "exchange_open"      
        r = self.robot.doCmdSync("exchange_open", {})                  
        if not (r.get("errno") == ROBOT_OK):
            self.rfidWrongTime += 1
            print "[ERROR exchange door open]"

        self.lastCmd = "exchange_close"      
        r = self.robot.doCmdSync("exchange_close", {})                  
        if not (r.get("errno") == ROBOT_OK):
            self.rfidWrongTime += 1
            print "[ERROR exchange door close]"





    def _testOneSlot(self, slotID):
        print "==== [START] Testing Slot %s" % slotID
        self.loopCount += 1
        self._exchangeToRack(slotID)
        self._rackToExchange(slotID)
        self._readRfid()        
        self._exchangeOpenClose()
        print "==== [END] Slot %s Test End \n" % slotID        

    def run(self):         
        try:
            for i in self.testTimes:
                print "======== Test Start (Round %s) ========" % i
                self._rackToExchange(101)
                for slotID in self.needTestSlotList:
                    self._testOneSlot(slotID)
                self._exchangeToRack(101)
                print "======== Test End (Round %s) ========" % i

            print "\n\n\n======================================="
            print "RFID Read Fail Rate: %s\nTest Done!" % self._getRfidErrorRate()
        except Exception:
            print "[Error]: Test Failed: %s\nLast CMD: %s" % (traceback.format_exc(), self.lastCmd)

def printHelp():
    print "./test.py [-h] [-s slots] [-t times] [-r]"

# =================================================================
# =    def main
# -----------------------------------------------------------------
def main(argv):
    slots = ""
    times = ""
    random = False
    try:
        opts, args = getopt.getopt(argv, "hs:t:r", ["help", "slots=", "times=", "random"])
    except getopt.GetoptError:
        printHelp()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            printHelp()
            sys.exit()
        elif opt in ("-s", "--slots"):
            slots = arg
        elif opt in ("-t", "--times"):
            times = arg
        elif opt in ("-r", "--random"):
            random = True
    
    s = SelfTest(slots, times, random)
    s.run()

if __name__ == "__main__":
    main(sys.argv[1:])

"""
    while 1:
        cmd = raw_input("Please type the command:\n")
        if cmd.upper() == "TEST_MOBJECT":
            _testMobject()
        elif cmd.upper() == "EXIT":
            break
"""
#=============================================================================
# EOF
#-----------------------------------------------------------------------------

