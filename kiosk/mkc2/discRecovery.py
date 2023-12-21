#!/usr/bin/env python

import os
import sys
import logging
import time
import traceback

#from mcommon import *
from proxy.conn_proxy import ConnProxy
from RobotController import RobotController, NoDiscException, RobotException
from config import KIOSK_HOME
import proxy.tools as tools

INFO_WIDTH = 85

(S_OK, S_RECOVERED, S_LOAD, S_INVALID) = range(4)

class SlotInfo:
    def __init__(self, hasdisc = False, rfid = ""):
        self.dbHasDisc = hasdisc
        self.realHasDisc = False
        self.dbRfid = rfid
        self.realRfid = ""
        self.status = S_INVALID
        self.toSlot = 0
    
    def __str__(self):
        return "%s | %s | %s | %s | %s | %s" % (str(self.dbHasDisc).ljust(8), str(self.realHasDisc).ljust(8), self.dbRfid.ljust(18), self.realRfid.ljust(18), str(self.toSlot).ljust(7), str(self.status == S_LOAD).ljust(5))

class CheckBase(object):
    def __init__(self, logfile = "Base", disp = "Check Base", errcode = "CB-"):
        self.disp = disp
        self.log = self._initLog(logfile)
        self.proxy = ConnProxy.getInstance()
        self.controller = RobotController(self.log, errcode)
    
    def _initLog(self, name):
        log = logging.getLogger(name)
        logfile = os.path.join(KIOSK_HOME, "kiosk/var/log/%s.log" % name)
        handle = logging.FileHandler(logfile)
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s : %(levelname)-8s %(message)s')
        chf = logging.Formatter('%(levelname)-8s %(message)s')
        handle.setFormatter(formatter)
        ch.setFormatter(chf)
        log.addHandler(handle)
        log.addHandler(ch)
        log.setLevel(logging.INFO)
        
        return log
    
    def _lockMkc(self):
        tools._saveThreadLock(1)
    
    def _unlockMkc(self):
        tools._saveThreadLock(0)
    
    def _stopMkc(self):
        self.log.info("Stop MKC.")
        os.system("cd /home/mm/kiosk/mkc2;./mkc.py stop")
    
    def _startMkc(self):
        self.log.info("Start MKC.")
        os.system("cd /home/mm/kiosk/mkc2;./mkc.py start")
    
    def _isMkcLock(self):
        ret = tools.isLocked()
        if ret != 0:
            raise MkcLockException("mkc is running! quit!")
    
    def start(self):
        self._isMkcLock()
        self._stopMkc()
        self._lockMkc()
        
        self.starttime = time.strftime("%Y-%m-%d %H:%M:%S")
        s = " %s Start at %s " % (self.disp, self.starttime)
        self.log.info(s.center(INFO_WIDTH, '='))
        self.log.info("".center(INFO_WIDTH, '='))
    
    def end(self):
        self.endtime = time.strftime("%Y-%m-%d %H:%M:%S")
        s = " End at %s " % self.endtime
        self.log.info(s.center(INFO_WIDTH, '='))
        self.log.info("".center(INFO_WIDTH, '='))
        
        self._unlockMkc()
        self._startMkc()
    
    def run(self):
        pass

class DiscRecovery(CheckBase):
    def __init__(self):
        super(DiscRecovery, self).__init__("discRecovery", "Disc Recovery", "DR-")
        
        self.slotList = {}
        self.allSlot = None
    
    def addSlot(self, id):
        self._validSlotID(id)
        
        rfid = self.proxy.getRfidBySlotId(id)
        slot = SlotInfo(True if rfid else False, rfid)
        self.slotList[id] = slot
    
    def _validSlotID(self, id):
        if self.allSlot == None:
            self.allSlot = self.proxy.getSlotIds()
        
        if id not in self.allSlot:
            raise SlotIDException("Invalid slot id")
    
    def _checkOneSlot(self, slot):
        item = self.slotList[slot]
        self.log.info("check slot %s" % slot)
        
        try:
            self.controller.rackToExchange(slot)
            item.realHasDisc = True
        except NoDiscException:
            item.realHasDisc = False
            self.log.info("slot %s has no disc" % slot)
            return
        
        try:
            item.realRfid = self.controller.readRfid()
        except RobotException:
            # invalid rfid
            pass
        
        self.log.info("slot %s has rfid %s" % (slot, item.realRfid))
        
        self.controller.exchangeToRack(slot)
        
        if item.realHasDisc == True and not item.realRfid:
            self.log.info("invalid rfid, pass")
            return
        
        if item.dbRfid != item.realRfid:
            slotid = self.proxy.getSlotIdByRfid(item.realRfid)
            if slotid:
                if slotid == "over_capacity":
                    item.status = S_LOAD
                    return
                else:
                    slotid = int(slotid)
                    item.toSlot = slotid
            else:
                # TODO: how to recovery it? should put it to an empty slot and reload
                item.status = S_LOAD
                return
            
            if not self.slotList.has_key(slotid):
                self.slotList[slotid] = SlotInfo(True, item.realRfid)
                self._checkOneSlot(slotid)
    
    def _checkAllSlots(self):
        slots = self.slotList.keys()
        for slot in slots:
            self._checkOneSlot(slot)
    
    def _aplan(self, plan, slot):
        item = self.slotList[slot]
        if item.status != S_RECOVERED and (item.toSlot != 0 or plan):
            plan.append(slot)
            
            if item.toSlot == 0 and plan:
                if item.realHasDisc == True:
                    # If there is a disc and does not know where to recovery it,
                    # a 0 will be inserted to plan and this plan will not be recovered.
                    plan.append(item.toSlot)
                    if item.status != S_LOAD:
                        item.status = S_RECOVERED
                
                return
            
            if item.toSlot not in plan:
                self._aplan(plan, item.toSlot)
            else:
                plan.append(223)
                plan.insert(0, 223)
            
            item.status = S_RECOVERED
        elif item.status == S_RECOVERED and plan and item.toSlot != 0:
            # This plan should append to other plan
            for tp in self.totalPlan:
                if tp[-1] == slot:
                    self.log.info("extend plan %s to %s" % (plan, tp))
                    tp.extend(plan)
                    del plan[:]  # clear plan list
                    break
    
    def _makePlan(self):
        self.totalPlan = []
        plan = []
        
        slots = self.slotList.keys()
        for slot in slots:
            self._aplan(plan, slot)
            if plan:
                plan.reverse()
                self.totalPlan.append(plan)
                plan = []
        
        self.log.info("FINAL PLAN: %s" % str(self.totalPlan))
    
    def _resetInfo(self, fslot, tslot):
        if tslot == 223:
            self.slotList[tslot] = SlotInfo()
        
        self.slotList[tslot].realHasDisc = self.slotList[fslot].realHasDisc
        self.slotList[tslot].realRfid = self.slotList[fslot].realRfid
        self.slotList[tslot].toSlot = 0
        self.slotList[fslot].realHasDisc = False
        self.slotList[fslot].realRfid = ""
        self.slotList[fslot].toSlot = 0
    
    def _doOnePlan(self, plan):
        if len(plan) < 2:
            self.log.error("Invalid recovery plan: %s" % str(plan))
            return
        
        dest = plan.pop(0)
        if dest == 0:
            # can not recovery
            return
        
        while plan:
            orig = plan[0]
            
            self.log.info("Disc Recovery: move from %s to %s" % (orig, dest))
            try:
                self.controller.rackToRack(orig, dest)
                self._resetInfo(orig, dest)
            except:
                self.log.error("Disc Recovery failed.\n%s" % traceback.format_exc())
                raise
            
            dest = plan.pop(0)
    
    def _recovery(self):
        for plan in self.totalPlan:
            self._doOnePlan(plan)
    
    def _reloadOne(self):
        slots = self.slotList.keys()
        for slot in slots:
            if self.slotList[slot].status == S_LOAD:
                self.controller.rackToRack(slot, 223)
                break
    
    def run(self):
        self._checkAllSlots()
        self._dostatis("Disc Check Result")
        self._makePlan()
        self._recovery()
        self._reloadOne()
        self._dostatis("Disc Recovery Result")
    
    def _dostatis(self, title):
        st = " %s " % title
        self.log.info(st.center(INFO_WIDTH, '='))
        xstr = "SLOT".ljust(4) + "| " + "DB DISC".center(8) + " | " + "REAL DISC".center(8) + "| " + "DB RFID".center(18) + " | " + "REAL RFID".center(18) + " | " + "TO SLOT".center(7) + " | " + "LOAD".ljust(5)
        self.log.info(xstr)
        
        slots = self.slotList.keys()
        slots.sort()
        for slot in slots:
            info = self.slotList[slot]
            self.log.info("%s| %s" % (str(slot).ljust(4), str(info)))
        
        self.log.info(" END ".center(INFO_WIDTH, '='))

class SlotIDException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)

class MkcLockException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)

if __name__ == "__main__":
    dr = DiscRecovery()
    
    if len(sys.argv) < 2:
        print "no slot id"
        sys.exit(-1)
    
    try:
        for id in sys.argv[1:]:
            dr.addSlot(int(id))
        
        dr.start()
        dr.run()
        dr.end()
    except MkcLockException, ex:
        print ex.message
        sys.exit(-2)
    except:
        print traceback.format_exc()
        sys.exit(-1)
    
    sys.exit(0)

