#!/usr/bin/python
""" Used by kiosk side.

change log:
    2009-10-09 Modified by Tim
        Add pickup_code for reservations.
        The pickup code is formed by 6 digits.
    2009-09-27 Modified by Tim
        Change to get the dynamic pricePlan.
    2009-06-09 Modified by Tim
        1. For #1701, add 6 fields: upc, title, genre, coupon_code, coupon_plan,
           coupon_text for table reservations.
        2. Change the params of reserve.
        3. Change the heart beat time to 10 times.
    2009-02-27 Modified by Tim
        Change reconnect method to os.fork
    2008-12-31 Modified by Kitch
        1. add function upgradeSoftware
    2008-12-19 Modified by Kitch
        1. add class LinuxCmd
        2. add function _execCmd
        3. add function getKioskScreenShot
"""
#import nodeclient
# Import from standard library.
import base64
import time
import os
import sys
import signal
import pwd
import random

# Import from local.
import pyDCE.dceapp as dceapp
from pyDCE.exception import *
from pyDCE.adapter import Servant
from pyDCE.config import *

from mda import Db
from DCEConfig import MKC_DB_PATH, UPC_DB_PATH, SYNC_DB_PATH, MEDIA_DB_PATH, USER_ROOT

kioskId = open("/etc/hostname").read().strip()
LAST_ACCESS_TIME_PATH = os.path.join(USER_ROOT, "kiosk/tmp/.ACCESS_NODE_LAST_ACCESS_TIME")

CHILD_PID_PATH = os.path.join(USER_ROOT, "kiosk/tmp/.kiosk_side_child.pid")
PARENT_PID_PATH = os.path.join(USER_ROOT, "kiosk/tmp/.kiosk_side_parent.pid")

__version__ = "0.0.7"

def DCE_APP():
    # for log.
    return dceapp.DCEApp()

def setLastAccessTime():
    try:
        f = None
        try:
            f = open(LAST_ACCESS_TIME_PATH, "w")
            f.write(str(time.time()))
        finally:
            if hasattr(f, "close"):
                f.close()
    except Exception, ex:
        DCE_APP().ERROR("Error in setLastAccessTime: %s" % ex)


def getLastAccessTime():
    accessTime = 0
    try:
        f = None
        try:
            f = open(LAST_ACCESS_TIME_PATH)
            accessTime = float(f.read().strip())
        finally:
            if hasattr(f, "close"):
                f.close()
    except Exception, ex:
        DCE_APP().ERROR("Error in getLastAccessTime: %s" % ex)
    return accessTime

class LinuxCmd(object):
    """ Execute Linux Command.
    e.g. lc = LinuxCmd()
         lc.execute("ls") # Return the result of ls.
         lc.execute("pkill python", True)  # Return '0' or '1'.
    """

    def __init__(self):
        pass

    def execute(self, cmd, noResult=False):
        """ Execute a linux command line.
        @Params: cmd(String): Command line
                 noResult(Boolean): True: Return '0'(Success) or '1'(Failure)
                                    False: Return the result of cmd.
        @Return: '0', '1', "success" or "".
        """
        w = None
        r = None
        result = ""
        try:
            if noResult:
                result = os.system(cmd)
                result = str(result)
            else:
                w, r = os.popen2(cmd)
                result = r.read()
        except Exception, ex:
            result = "Error when execute cmd(%s): %s" % (cmd, str(ex))

        # Close the object handler.
        if hasattr(w, "close"):
            w.close()
        if hasattr(r, "close"):
            r.close()
        return result

class KioskClient(Servant):
    def __init__(self,name):
        Servant.__init__(self,name)
        setLastAccessTime()

    def callback(self,ctx,str1,*p,**pp):
        #print "GOOD*****GOT Callback", str1
        setLastAccessTime()
        return "Reply: I'm kiosk %s." % kioskId

    def _getDbPath(self, dbName):
        dbPaths = {"mkc":MKC_DB_PATH,
                   "upc":UPC_DB_PATH,
                   "media":MEDIA_DB_PATH,
                   "sync":SYNC_DB_PATH}
        return dbPaths[dbName.lower()]

    def doCommand(self, ctx, funcName, params):
        setLastAccessTime()
        func = getattr(self, funcName, None)
        if func:
            return func(*params)
        else:
            raise NoMethodException("Unkown function name '%s'" % str(funcName))

    def query(self, dbName, sql, fetch='all', params=()):
        db = Db(self._getDbPath(dbName))
        result = db.query(sql, fetch, params)
        del db
        return result

    def update(self, dbName, sql, params=()):
        db = Db(self._getDbPath(dbName))
        newId = db.update(sql, params)
        del db
        return newId

    def updateMany(self, dbName, sql, params=[]):
        db = Db(self._getDbPath(dbName))
        db.updateMany(sql, params)
        del db
        return

    def updateTrs(self, dbName, sqlList=[]):
        db = Db(self._getDbPath(dbName))
        db.updateTrs(sqlList)
        del db
        return

    def executeScript(self, dbName, sql):
        db = Db(self._getDbPath(dbName))
        db.executeScript(sql)
        del db
        return

    def isOnline(self):
        print "==========================isOnline:return"
        return "1"

    def _getPickupCode(self):
        """ The pickup code is formed by 6 digits.
        """
        code = ""
        db = Db(self._getDbPath("mkc"))
        sql = "SELECT id FROM reservations WHERE pickup_code=?;"
        while not code:
            code = str(random.randrange(100000, 999999))
            row = db.query(sql, "one", (code, ))
            if row and row[0]:
                code = ""
        del db
        return code

    def reserve(self, rfid, upclist, acctId, amount, gene, reserveMethod,
                cardNum, nameOnCard, expdate, trsCode, trsMsg, oid, memberId,
                preauthMethod, ccId=0):
        status = 0
        msg = ""
        pricePlan = ""
        upgId = 0
        reserveId = 0
        reserveTime = ""
        upc = ""
        db = None
        try:
            # Check the rental lock.
            rentalLock = True
            sql = "SELECT value FROM config WHERE variable='rental_lock';"
            db = Db(self._getDbPath("mkc"))
            row = db.query(sql, "one")
            if row and row[0] == "no":
                rentalLock = False

            # Check if the dvd release date of the upc is OK.
            db = Db(self._getDbPath("upc"))
            upcstr = "(%s)" % ",".join("'%s'"%u for u in upclist)
            sql = "SELECT upc FROM upc WHERE upc IN %s " % upcstr
            if rentalLock:
                dateNow = time.strftime("%Y-%m-%d 23:59:59")
                sql += "AND dvd_release_date<='%s' "%dateNow
            sql += ";"
            rows = db.query(sql)
            if rows:
                upcstr = "(%s)" % ",".join("'%s'"%u for u, in rows)

                db = Db(self._getDbPath("mkc"))
                # Get rfid by upc.
                sql = "SELECT r.rfid, p.data_text, r.upc FROM rfids as r," \
                      "price_plans as p,slots as s WHERE r.rfid=s.rfid " \
                      "AND r.price_plan_id=p.id AND r.state IN " \
                      "('in', 'unload') AND upc IN %s " \
                      "ORDER BY s.id DESC LIMIT 1;" % upcstr
                row = db.query(sql, "one")
                if row:
                    rfid, pricePlan, upc = row

                    display = "%s (%s)" % (nameOnCard, cardNum[-4:])

                    if ccId=="":
                        # Add to cc table.
                        cardNumEn = base64.b64encode(cardNum)
                        sql = "select id from cc where number=?;"
                        row = db.query(sql, "one", (cardNumEn, ))
                        if row:
                            ccId = row[0]
                        else:
                            sql = "insert into cc(number, name, expdate, track1," \
                                  " track2, display, member_id) values(?,?,?,?,?,?,?);"
                            p = (cardNumEn, nameOnCard, expdate, "", "", display, memberId)
                            ccId = db.update(sql, p)
                    else:
                        # Global cc.
                        sql = "SELECT id FROM cc WHERE id=?;"
                        row = db.query(sql, "one", (ccId, ))
                        if row:
                            # Update info.
                            sql = "UPDATE cc SET id=:cc_id "
                            if nameOnCard:
                                sql += ",name=:name "
                            if display:
                                sql += ",display=:display "
                            sql += "WHERE id=:cc_id;"
                            db.update(sql, {"cc_id":ccId, "name":nameOnCard, "display":display})
                        else:
                            # Insert info.
                            sql = "INSERT INTO cc(id, name, display) VALUES(?,?,?);"
                            db.update(sql, (ccId, nameOnCard, display))
                    # Add to preauthq.
                    reserveTime = time.strftime("%Y-%m-%d %H:%M:%S")
                    preauthqId = ""
                    # Add to upg.
                    sql = "insert into upg(acct_id, pq_id, type, oid, amount," \
                          " cc_id, result_code, result_msg, time, preauth_method," \
                          " notes) values(?,?,?,?,?,?,?,?,?,?,?);"
                    p = (acctId, preauthqId, "PREAUTH", oid, amount, ccId, \
                         trsCode, trsMsg, reserveTime, preauthMethod, kioskId)
                    upgId = db.update(sql, p)

                    sqls = []
                    # Update the rfids and insert into reservations.
                    sql = "update rfids set state='reserved' where rfid='%s';"%rfid
                    sqls.append(sql)
                    # Add to reservations.
                    sql = "insert into reservations(rfid, cc_id, reserve_time," \
                          " reserve_method, gene, upg_id) values('%s', '%s', " \
                          "'%s', '%s', '%s', '%s');"%(rfid, ccId, reserveTime, \
                                                      reserveMethod, gene, upgId)
                    sqls.append(sql)
                    db.updateTrs(sqls)
                    # Get reserve id.
                    sql = "SELECT id FROM reservations WHERE rfid=? AND cc_id=? AND " \
                          "reserve_time=? AND upg_id=? AND state='reserved';"
                    row = db.query(sql, "one", (rfid, ccId, reserveTime, upgId))
                    reserveId, = row
                    status = 1
                else:
                    status = 2
            else:
                status = 3
        except Exception, ex:
            if upgId!=0:
                try:
                    sql = "DELETE FROM upg WHERE id=?;"
                    db = Db(self._getDbPath("mkc"))
                    db.update(sql, (upgId, ))
                except Exception, ex:
                    print ex
            status = 0
            msg = "Error when reserve '%s': %s" % (rfid, str(ex))
        del db
        print status, msg, ccId, upgId, reserveTime, pricePlan, rfid, upc, reserveId

        return status, msg, ccId, upgId, reserveTime, pricePlan, rfid, upc, reserveId

    def reserveV2(self, params):
        """
        @Params: params(dict): {"acct_id":xxx,
                                "amount":xxx,
                                "cc_id":xxx,
                                "card_num":xxx,
                                "name_on_card":xxx,
                                "exp_date":xxx,
                                "card_display":xxx,
                                "oid":xxx,
                                "trs_code":xxx,
                                "trs_msg":xxx,
                                "member_id":xxx,
                                "reserve_method":xxx,
                                "preauth_method":xxx,
                                "shopping_cart":[{"upc_list":[],
                                                  "gene":xxx,
                                                  "movie_id":xxx,
                                                  "coupon_code":xxx,
                                                  "coupon_plan":xxx,
                                                  "coupon_text":xxx,}],}
        @Return: result(dict):
        """
        result = {}
        status = 0
        msg = ""
        pricePlan = ""
        reserveId = 0
        db = None
        try:
            upgId = 0
            result["status"] = 0
            reserveTime = time.strftime("%Y-%m-%d %H:%M:%S")
            result["reserve_time"] = reserveTime
            # Check the rental lock.
            rentalLock = True
            sql = "SELECT value FROM config WHERE variable='rental_lock';"
            db = Db(self._getDbPath("mkc"))
            row = db.query(sql, "one")
            if row and row[0] == "no":
                rentalLock = False

            # Add the cc into cc table.
            # Global cc.
            sql = "SELECT id FROM cc WHERE id=?;"
            row = db.query(sql, "one", (params["cc_id"], ))
            if row:
                # Update info.
                sql = "UPDATE cc SET id=:cc_id "
                if params["name_on_card"]:
                    sql += ",name=:name "
                if params["card_display"]:
                    sql += ",display=:display "
                sql += "WHERE id=:cc_id;"
                db.update(sql, {"cc_id":params["cc_id"],
                                "name":params["name_on_card"],
                                "display":params["card_display"]})
            else:
                # Insert info.
                sql = "INSERT INTO cc(id, name, display) VALUES(?,?,?);"
                db.update(sql, (params["cc_id"],
                                params["name_on_card"],
                                params["card_display"],))

            # Add upg into upg table.
            preauthqId = ""
            # Add to upg.
            sql = "insert into upg(acct_id, pq_id, type, oid, " \
                  "amount, cc_id, result_code, result_msg, time, " \
                  "preauth_method, notes) " \
                  "values(?,?,?,?,?,?,?,?,?,?,?);"
            p = (params["acct_id"], preauthqId, "PREAUTH", \
                 params["oid"], params["amount"], params["cc_id"], \
                 params["trs_code"], params["trs_msg"], \
                 reserveTime, params["preauth_method"], kioskId)
            upgId = db.update(sql, p)
            result["upg_id"] = upgId

            # Check if the dvd release date of the upc is OK.
            result["shopping_cart"] = []
            for itm in params["shopping_cart"]:
                tmp = {}
                tmp.update(itm)
                tmp["status"] = 0
                tmp["msg"] = ""
                rfid = ""
                try:
                    db = Db(self._getDbPath("upc"))
                    upcstr = "(%s)" % ",".join("'%s'"%u for u in itm["upc_list"])
                    sql = "SELECT upc FROM upc WHERE upc IN %s " % upcstr
                    if rentalLock:
                        dateNow = time.strftime("%Y-%m-%d 23:59:59")
                        sql += "AND dvd_release_date<='%s' "%dateNow
                    sql += ";"
                    rows = db.query(sql)

                    if rows:
                        upcstr = "(%s)" % ",".join("'%s'"%u for u, in rows)

                        db = Db(self._getDbPath("mkc"))
                        # Get rfid by upc.
                        sql = "SELECT r.rfid, p.data_text, r.upc, r.title, " \
                              "r.genre, p.data, r.price_plan_dynamic, s.id " \
                              "FROM rfids as r, price_plans as p, " \
                              "slots as s WHERE r.rfid=s.rfid AND " \
                              "r.price_plan_id=p.id AND r.state IN ('in', " \
                              "'unload') AND upc IN %s ORDER BY s.id DESC " \
                              "LIMIT 1;" % upcstr
                        row = db.query(sql, "one")
                        if row:
                            rfid, pricePlanText, upc, title, genre, pricePlan, \
                            dynamic, slotId = row
                            # Get dynamic price plan.
                            if str(dynamic) == "1":
                                weekday = time.strftime("%A")
                                sql = "SELECT price_plan, price_plan_text " \
                                      "FROM price_plans_week WHERE title LIKE ?;"
                                row = db.query(sql, "one", (weekday, ))
                                dypricePlan, dypricePlanText = "", ""
                                if row:
                                    dypricePlan, dypricePlanText = row
                                if dypricePlan:
                                    pricePlan = dypricePlan
                                if dypricePlanText:
                                    pricePlanText = dypricePlanText

                            trs = []
                            # Update the rfids and insert into reservations.
                            sql = "update rfids set state='reserved' where " \
                                  "rfid=?;"
                            trs.append({"sql":sql, "params":(rfid, )})
                            # Add to reservations.
                            sql = "insert into reservations(rfid, cc_id, " \
                                  "reserve_time, reserve_method, gene, upg_id," \
                                  "title, genre, upc, price_plan, " \
                                  "price_plan_text, coupon_code, coupon_plan," \
                                  "coupon_text, slot_id) values(?,?,?,?,?,?,?," \
                                  "?,?,?,?,?,?,?,?);"
                            p = (rfid, params["cc_id"], reserveTime, \
                                params["reserve_method"], itm["gene"], upgId,\
                                title, genre, upc, pricePlan, pricePlanText, \
                                itm["coupon_code"], itm["coupon_plan"], \
                                itm["coupon_text"], slotId)
                            trs.append({"sql":sql, "params": p})
                            db.updateTrs2(trs)
                            # Get reserve id.
                            sql = "SELECT id FROM reservations WHERE rfid=? " \
                                  "AND cc_id=? AND reserve_time=? AND upg_id=? " \
                                  "AND state='reserved';"
                            row = db.query(sql, "one", (rfid, params["cc_id"], \
                                                    reserveTime, upgId))
                            reserveId, = row
                            tmp["status"] = 1
                            tmp["rfid"] = rfid
                            tmp["upc"] = upc
                            tmp["title"] = title
                            tmp["genre"] = genre
                            tmp["reserve_id"] = reserveId
                            tmp["price_plan_text"] = pricePlanText
                            tmp["price_plan"] = pricePlan
                            tmp["slot_id"] = slotId
                            tmp["coupon_code"] = itm["coupon_code"]
                            tmp["coupon_plan"] = itm["coupon_plan"]
                            tmp["coupon_text"] = itm["coupon_text"]
                        else:
                            # No disc can be reserved.
                            tmp["status"] = 2
                    else:
                        # No upc can be reserved.
                        tmp["status"] = 3
                except Exception, ex:
                    tmp["status"] = 0
                    tmp["msg"] = "Error when reserve the disc: %s" % ex
                result["shopping_cart"].append(tmp)
            result["status"] = 1
            result["msg"] = "Reserve successfully."
        except Exception, ex:
            DCE_APP().ERROR("Error when reserve %s: %s"%(params, ex))
            if upgId!=0:
                try:
                    sql = "DELETE FROM upg WHERE id=?;"
                    db = Db(self._getDbPath("mkc"))
                    db.update(sql, (upgId, ))
                except Exception, ex:
                    print ex
            result["status"] = 0
            result["msg"] = "Error when reserve the shopping cart: %s" % ex
        del db

        return result

    def reserveV3(self, params):
        """
        @Params: params(dict): {"acct_id":xxx,
                                "amount":xxx,
                                "cc_id":xxx,
                                "card_num":xxx,
                                "name_on_card":xxx,
                                "exp_date":xxx,
                                "card_display":xxx,
                                "oid":xxx,
                                "trs_code":xxx,
                                "trs_msg":xxx,
                                "member_id":xxx,
                                "reserve_method":xxx,
                                "preauth_method":xxx,
                                "shopping_cart":[{"upc_list":[],
                                                  "gene":xxx,
                                                  "movie_id":xxx,
                                                  "coupon_code":xxx,
                                                  "coupon_plan":xxx,
                                                  "coupon_text":xxx,
                                                  "pickup_code":xxx,}],}
        @Return: result(dict):
        """
        result = {}
        status = 0
        msg = ""
        pricePlan = ""
        reserveId = 0
        db = None
        try:
            upgId = 0
            result["status"] = 0
            reserveTime = time.strftime("%Y-%m-%d %H:%M:%S")
            result["reserve_time"] = reserveTime
            # Check the rental lock.
            rentalLock = True
            sql = "SELECT value FROM config WHERE variable='rental_lock';"
            db = Db(self._getDbPath("mkc"))
            row = db.query(sql, "one")
            if row and row[0] == "no":
                rentalLock = False

            # Add the cc into cc table.
            # Global cc.
            sql = "SELECT id FROM cc WHERE id=?;"
            row = db.query(sql, "one", (params["cc_id"], ))
            if row:
                # Update info.
                sql = "UPDATE cc SET id=:cc_id "
                if params["name_on_card"]:
                    sql += ",name=:name "
                if params["card_display"]:
                    sql += ",display=:display "
                sql += "WHERE id=:cc_id;"
                db.update(sql, {"cc_id":params["cc_id"],
                                "name":params["name_on_card"],
                                "display":params["card_display"]})
            else:
                # Insert info.
                sql = "INSERT INTO cc(id, name, display) VALUES(?,?,?);"
                db.update(sql, (params["cc_id"],
                                params["name_on_card"],
                                params["card_display"],))

            # Add upg into upg table.
            preauthqId = ""
            # Add to upg.
            sql = "insert into upg(acct_id, pq_id, type, oid, " \
                  "amount, cc_id, result_code, result_msg, time, " \
                  "preauth_method, notes) " \
                  "values(?,?,?,?,?,?,?,?,?,?,?);"
            p = (params["acct_id"], preauthqId, "PREAUTH", \
                 params["oid"], params["amount"], params["cc_id"], \
                 params["trs_code"], params["trs_msg"], \
                 reserveTime, params["preauth_method"], kioskId)
            upgId = db.update(sql, p)
            result["upg_id"] = upgId

            # Check if the dvd release date of the upc is OK.
            result["shopping_cart"] = []
            for itm in params["shopping_cart"]:
                pickupCode = self._getPickupCode()
                tmp = {}
                tmp.update(itm)
                tmp["status"] = 0
                tmp["msg"] = ""
                tmp["pickup_code"] = ""
                rfid = ""
                try:
                    db = Db(self._getDbPath("upc"))
                    upcstr = "(%s)" % ",".join("'%s'"%u for u in itm["upc_list"])
                    sql = "SELECT upc FROM upc WHERE upc IN %s " % upcstr
                    if rentalLock:
                        dateNow = time.strftime("%Y-%m-%d 23:59:59")
                        sql += "AND dvd_release_date<='%s' "%dateNow
                    sql += ";"
                    rows = db.query(sql)
                    if rows:
                        upcstr = "(%s)" % ",".join("'%s'"%u for u, in rows)

                        db = Db(self._getDbPath("mkc"))
                        # Get rfid by upc.
                        sql = "SELECT r.rfid, p.data_text, r.upc, r.title, " \
                              "r.genre, p.data, r.price_plan_dynamic, s.id, " \
                              "r.category_id " \
                              "FROM rfids as r, price_plans as p, " \
                              "slots as s WHERE r.rfid=s.rfid AND " \
                              "r.price_plan_id=p.id AND r.state IN ('in', " \
                              "'unload') AND upc IN %s ORDER BY s.id DESC " \
                              "LIMIT 1;" % upcstr
                        row = db.query(sql, "one")
                        if row:
                            rfid, pricePlanText, upc, title, genre, pricePlan, \
                            dynamic, slotId, categoryId = row
                            # Get dynamic price plan.
                            if str(dynamic) == "1":
                                weekday = time.strftime("%A")
                                sql = "SELECT price_plan, price_plan_text " \
                                      "FROM price_plans_week WHERE title LIKE ?;"
                                row = db.query(sql, "one", (weekday, ))
                                dypricePlan, dypricePlanText = "", ""
                                if row:
                                    dypricePlan, dypricePlanText = row
                                if dypricePlan:
                                    pricePlan = dypricePlan
                                if dypricePlanText:
                                    pricePlanText = dypricePlanText

                            # Check category price plan for the disc.
                            if str(categoryId) != "":
                                sql = "SELECT price_plan_id FROM category " \
                                      "WHERE id=?;"
                                row = db.query(sql, "one", (categoryId, ))
                                if row and str(row[0]) != "":
                                    cppid = row[0] # category price plan id
                                    sql = "SELECT data, data_text " \
                                          "FROM price_plans " \
                                          "WHERE id=?;"
                                    row = db.query(sql, "one", (cppid, ))
                                    if row and row[0] and row[1]:
                                        pricePlan, pricePlanText = row

                            trs = []
                            # Update the rfids and insert into reservations.
                            sql = "update rfids set state='reserved' where " \
                                  "rfid=?;"
                            trs.append({"sql":sql, "params":(rfid, )})
                            # Add to reservations.
                            sql = "insert into reservations(rfid, cc_id, " \
                                  "reserve_time, reserve_method, gene, upg_id," \
                                  "title, genre, upc, price_plan, " \
                                  "price_plan_text, coupon_code, coupon_plan," \
                                  "coupon_text, slot_id, pickup_code) " \
                                  "values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);"
                            p = (rfid, params["cc_id"], reserveTime, \
                                params["reserve_method"], itm["gene"], upgId,\
                                title, genre, upc, pricePlan, pricePlanText, \
                                itm["coupon_code"], itm["coupon_plan"], \
                                itm["coupon_text"], slotId, pickupCode)
                            trs.append({"sql":sql, "params": p})
                            db.updateTrs2(trs)
                            # Get reserve id.
                            sql = "SELECT id FROM reservations WHERE rfid=? " \
                                  "AND cc_id=? AND reserve_time=? AND upg_id=? " \
                                  "AND state='reserved';"
                            row = db.query(sql, "one", (rfid, params["cc_id"], \
                                                    reserveTime, upgId))
                            reserveId, = row
                            tmp["status"] = 1
                            tmp["rfid"] = rfid
                            tmp["upc"] = upc
                            tmp["title"] = title
                            tmp["genre"] = genre
                            tmp["reserve_id"] = reserveId
                            tmp["price_plan_text"] = pricePlanText
                            tmp["price_plan"] = pricePlan
                            tmp["slot_id"] = slotId
                            tmp["coupon_code"] = itm["coupon_code"]
                            tmp["coupon_plan"] = itm["coupon_plan"]
                            tmp["coupon_text"] = itm["coupon_text"]
                            tmp["pickup_code"] = pickupCode
                        else:
                            # No disc can be reserved.
                            tmp["status"] = 2
                    else:
                        # No upc can be reserved.
                        tmp["status"] = 3
                    del db
                except Exception, ex:
                    tmp["status"] = 0
                    tmp["msg"] = "Error when reserve the disc: %s" % ex
                result["shopping_cart"].append(tmp)
            result["status"] = 1
            result["msg"] = "Reserve successfully."
        except Exception, ex:
            DCE_APP().ERROR("Error when reserve %s: %s"%(params, ex))
            if upgId!=0:
                try:
                    sql = "DELETE FROM upg WHERE id=?;"
                    db = Db(self._getDbPath("mkc"))
                    db.update(sql, (upgId, ))
                except Exception, ex:
                    print ex
            result["status"] = 0
            result["msg"] = "Error when reserve the shopping cart: %s" % ex
        del db

        return result

    def reserveV4(self, params):
        """
        @Params: params(dict): {"acct_id":xxx,
                                "amount":xxx,
                                "cc_id":xxx,
                                "card_num":xxx,
                                "name_on_card":xxx,
                                "exp_date":xxx,
                                "card_display":xxx,
                                "oid":xxx,
                                "trs_code":xxx,
                                "trs_msg":xxx,
                                "member_id":xxx,
                                "reserve_method":xxx,
                                "preauth_method":xxx,
                                "pickup_code":xxx,
                                "shopping_cart":[{"upc_list":[],
                                                  "gene":xxx,
                                                  "movie_id":xxx,
                                                  "coupon_code":xxx,
                                                  "coupon_plan":xxx,
                                                  "coupon_text":xxx,
                                                  "ms_id":xxx,
                                                  "ms_expr_time":xxx,
                                                  "ms_keep_days":xxx,}],}
        @Return: result(dict):
        """
        result = {}
        status = 0
        msg = ""
        pricePlan = ""
        reserveId = 0
        db = None
        try:
            upgId = 0
            result["status"] = 0
            reserveTime = time.strftime("%Y-%m-%d %H:%M:%S")
            result["reserve_time"] = reserveTime
            # Check the rental lock.
            rentalLock = True
            sql = "SELECT value FROM config WHERE variable='rental_lock';"
            db = Db(self._getDbPath("mkc"))
            row = db.query(sql, "one")
            if row and row[0] == "no":
                rentalLock = False

            # Add the cc into cc table.
            # Global cc.
            sql = "SELECT id FROM cc WHERE id=?;"
            row = db.query(sql, "one", (params["cc_id"], ))
            if row:
                # Update info.
                sql = "UPDATE cc SET id=:cc_id "
                if params["name_on_card"]:
                    sql += ",name=:name "
                if params["card_display"]:
                    sql += ",display=:display "
                sql += "WHERE id=:cc_id;"
                db.update(sql, {"cc_id":params["cc_id"],
                                "name":params["name_on_card"],
                                "display":params["card_display"]})
            else:
                # Insert info.
                sql = "INSERT INTO cc(id, name, display) VALUES(?,?,?);"
                db.update(sql, (params["cc_id"],
                                params["name_on_card"],
                                params["card_display"],))

            # Add upg into upg table.
            preauthqId = ""
            # Add to upg.
            upgId = 0
            if params["oid"]:
                sql = "insert into upg(acct_id, pq_id, type, oid, " \
                      "amount, cc_id, result_code, result_msg, time, " \
                      "preauth_method, notes) " \
                      "values(?,?,?,?,?,?,?,?,?,?,?);"
                p = (params["acct_id"], preauthqId, "PREAUTH", \
                     params["oid"], params["amount"], params["cc_id"], \
                     params["trs_code"], params["trs_msg"], \
                     reserveTime, params["preauth_method"], self.kioskId)
                upgId = db.update(sql, p)
            result["upg_id"] = upgId

            # Check if the dvd release date of the upc is OK.
            result["shopping_cart"] = []
            for itm in params["shopping_cart"]:
                pickupCode = self._getPickupCode()
                tmp = {}
                tmp.update(itm)
                tmp["status"] = 0
                tmp["msg"] = ""
                tmp["pickup_code"] = ""
                rfid = ""
                try:
                    db = Db(self._getDbPath("upc"))
                    upcstr = "(%s)" % ",".join("'%s'"%u for u in itm["upc_list"])
                    sql = "SELECT upc FROM upc WHERE upc IN %s " % upcstr
                    if rentalLock:
                        dateNow = time.strftime("%Y-%m-%d 23:59:59")
                        sql += "AND dvd_release_date<='%s' "%dateNow
                    sql += ";"
                    rows = db.query(sql)
                    if rows:
                        upcstr = "(%s)" % ",".join("'%s'"%u for u, in rows)

                        db = Db(self._getDbPath("mkc"))
                        # Get rfid by upc.
                        sql = "SELECT r.rfid, p.data_text, r.upc, r.title, " \
                              "r.genre, p.data, r.price_plan_dynamic, s.id, " \
                              "r.category_id " \
                              "FROM rfids as r, price_plans as p, " \
                              "slots as s WHERE r.rfid=s.rfid AND " \
                              "r.price_plan_id=p.id AND r.state IN ('in', " \
                              "'unload') AND upc IN %s ORDER BY s.id DESC " \
                              "LIMIT 1;" % upcstr
                        row = db.query(sql, "one")
                        if row:
                            rfid, pricePlanText, upc, title, genre, pricePlan, \
                            dynamic, slotId, categoryId = row
                            # Get dynamic price plan.
                            if str(dynamic) == "1":
                                weekday = time.strftime("%A")
                                sql = "SELECT price_plan, price_plan_text " \
                                      "FROM price_plans_week WHERE title LIKE ?;"
                                row = db.query(sql, "one", (weekday, ))
                                dypricePlan, dypricePlanText = "", ""
                                if row:
                                    dypricePlan, dypricePlanText = row
                                if dypricePlan:
                                    pricePlan = dypricePlan
                                if dypricePlanText:
                                    pricePlanText = dypricePlanText

                            # Check category price plan for the disc.
                            if str(categoryId) != "":
                                sql = "SELECT price_plan_id FROM category " \
                                      "WHERE id=?;"
                                row = db.query(sql, "one", (categoryId, ))
                                if row and str(row[0]) != "":
                                    cppid = row[0] # category price plan id
                                    sql = "SELECT data, data_text " \
                                          "FROM price_plans " \
                                          "WHERE id=?;"
                                    row = db.query(sql, "one", (cppid, ))
                                    if row and row[0] and row[1]:
                                        pricePlan, pricePlanText = row

                            trs = []
                            # Update the rfids and insert into reservations.
                            sql = "update rfids set state='reserved' where " \
                                  "rfid=?;"
                            trs.append({"sql":sql, "params":(rfid, )})
                            # Add to reservations.
                            sql = "insert into reservations(rfid, cc_id, " \
                                  "reserve_time, reserve_method, gene, upg_id," \
                                  "title, genre, upc, price_plan, " \
                                  "price_plan_text, coupon_code, coupon_plan," \
                                  "coupon_text, slot_id, pickup_code, ms_id, " \
                                  "ms_keep_days) " \
                                  "values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);"
                            p = (rfid, params["cc_id"], reserveTime, \
                                params["reserve_method"], itm["gene"], upgId,\
                                title, genre, upc, pricePlan, pricePlanText, \
                                itm["coupon_code"], itm["coupon_plan"], \
                                itm["coupon_text"], slotId, pickupCode, \
                                itm["ms_id"], itm["ms_keep_days"])
                            trs.append({"sql":sql, "params": p})
                            db.updateTrs2(trs)
                            # Get reserve id.
                            sql = "SELECT id FROM reservations WHERE rfid=? " \
                                  "AND cc_id=? AND reserve_time=? AND upg_id=? " \
                                  "AND state='reserved';"
                            row = db.query(sql, "one", (rfid, params["cc_id"], \
                                                    reserveTime, upgId))
                            reserveId, = row
                            tmp["status"] = 1
                            tmp["rfid"] = rfid
                            tmp["upc"] = upc
                            tmp["title"] = title
                            tmp["genre"] = genre
                            tmp["reserve_id"] = reserveId
                            tmp["price_plan_text"] = pricePlanText
                            tmp["price_plan"] = pricePlan
                            tmp["slot_id"] = slotId
                            tmp["coupon_code"] = itm["coupon_code"]
                            tmp["coupon_plan"] = itm["coupon_plan"]
                            tmp["coupon_text"] = itm["coupon_text"]
                            tmp["pickup_code"] = pickupCode
                            tmp["ms_id"] = itm["ms_id"]
                            tmp["ms_expr_time"] = itm["ms_expr_time"]
                            tmp["ms_keep_days"] = itm["ms_keep_days"]
                        else:
                            # No disc can be reserved.
                            tmp["status"] = 2
                    else:
                        # No upc can be reserved.
                        tmp["status"] = 3
                except Exception, ex:
                    tmp["status"] = 0
                    tmp["msg"] = "Error when reserve the disc: %s" % ex
                result["shopping_cart"].append(tmp)
            result["status"] = 1
            result["msg"] = "Reserve successfully."
        except Exception, ex:
            DCE_APP().ERROR("Error when reserveV4 %s: %s"%(params, ex))
            if upgId!=0:
                try:
                    sql = "DELETE FROM upg WHERE id=?;"
                    db = Db(self._getDbPath("mkc"))
                    db.update(sql, (upgId, ))
                except Exception, ex:
                    print ex
            result["status"] = 0
            result["msg"] = "Error when reserve the shopping cart: %s" % ex
        del db

        return result

    def _execCmd(self, cmd, noResult=False):
        lc = LinuxCmd()
        return lc.execute(cmd, noResult)

    def getKioskScreenShot(self):
        fileName = time.strftime("%Y-%m-%d_%H%M%S") + ".jpg"
        filePath = os.path.join(USER_ROOT, "kiosk/tmp/", fileName)
        #cmd = "su - mm -c 'DISPLAY=:0.0 /usr/bin/scrot /tmp/%s'" % fileName
        lc = LinuxCmd()
        cmd = "DISPLAY=:0.0 /usr/bin/scrot %s" % filePath
        result = lc.execute(cmd, True)

        content = ""
        if str(result) == "0":
            f = open(filePath)
            content = f.read()
            f.close()
            content = base64.b64encode(content)
        del lc
        return content

    def upgradeSoftware(self, softwareVersion):
        f = open("/tmp/upgrade_version", "w")
        f.write(str(softwareVersion))
        f.close()
        return 1

def needReconnect(pr):
    """ Check if the proxy is alive. """
    need = True
    try:
        if pr and hasattr(pr,"_conn") and hasattr(pr._conn,"_adapter") and hasattr(pr._conn._adapter,"connectionLost"):
            if pr._conn._adapter.connectionLost:
                print "====== connection lost, need reconnect ===="
                need = True
            else:
                print "====== =connect do not need reconnect====="
                need = False
        else:
            print '=============need connect ======'
            need = True

        if not need:
            # Check the last access time.
            if time.time()-getLastAccessTime() >= NODE_HEART_BEAT*10:
                need = True
    except Exception, ex:
        DCE_APP().ERROR("Error when check if need reconnect: %s"%ex)
    return need

def writePid(filePath, pid, uid):
    """ Write a pid and uid into the file. """
    fd = open(filePath, "w")
    fd.write("%s\n%s"%(pid, uid))
    fd.close()

def readPid(filePath):
    """ Read the pid from the file. """
    pid = ""
    try:
        fd = open(filePath)
        content = fd.read()
        pid = int(content.split("\n")[0])
    except Exception, ex:
        pid = ""
        print "Error when read pid: %s"%ex
    return pid

def killChild(parentPid=None):
    """ Kill child process. """
    pid = readPid(CHILD_PID_PATH)
    if pid:
        try:
            if parentPid and parentPid != pid:
                w, r = os.popen2("ps aux | grep %s | grep -v '%s'"%(pid, pid))
                if r.read().find("kiosk_side.py"):
                    os.kill(pid, signal.SIGKILL)
                w.close()
                r.close()
        except Exception, ex:
            print "Error when kill child process: %s"%ex

def main():
    pr = None
    ad = None
    while True:
        killChild(parentPid=os.getpid())
        pid = os.fork()
        if pid > 0:
            # Parent thread.
            try:
                os.getuid()
                writePid(PARENT_PID_PATH, os.getpid(), os.getuid())
                cpid, status = os.waitpid(pid, 0)
            except:
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception, ex:
                    print "Error when kill child process: %s"%ex
            time.sleep(5)
        else:
            # Child thread.
            try:
                obj = pwd.getpwnam("mm")
                mmuid = obj.pw_uid
                mmgid = obj.pw_gid
                writePid(CHILD_PID_PATH, os.getpid(), mmuid)
                os.setgid(mmgid)
                os.setegid(mmgid)
                os.setgroups([4, 20, 24, 25, 29, 30, 44, 46, 107, 109, 115, 1000])
                os.setuid(mmuid)
                os.seteuid(mmuid)
                os.putenv("HOME","/home/mm")

                # For scrot.
                #lc = LinuxCmd()
                #cmd = "sh -c 'DISPLAY=:0.0 /usr/bin/xhost +'"
                #print lc.execute(cmd, True)
                #del lc
                while True:
                    if needReconnect(pr):
                        print "===================Connect"
                        try:
                            # Connect from local port.
                            t=KioskClient(kioskId)
                            app=dceapp.DCEApp()

                            pr=app.stringToProxy(LOCAL_REGISTRY_URL)
                            ad=app.stringToAdapter("%s@" % kioskId)
                            ad.addObj(t)
                            pr._conn.setAdapter(ad)
                            pr.setCallback(kioskId,kioskId)
                        except Exception, ex:
                            DCE_APP().ERROR("Error when connect %s: %s"%(LOCAL_REGISTRY_URL, ex))
                            # Connect to remote port.
                            t=KioskClient(kioskId)

                            app=dceapp.DCEApp()

                            pr=app.stringToProxy(REGISTRY_URL)
                            ad=app.stringToAdapter("%s@" % kioskId)
                            ad.addObj(t)
                            pr._conn.setAdapter(ad)
                            pr.setCallback(kioskId,kioskId)
                    else:
                        print "==============connected"
                        time.sleep(NODE_HEART_BEAT)
            except Exception, ex:
                DCE_APP().ERROR("Error in child thread: %s" % ex)
                ad = None
                pr = None
                sys.exit()

if __name__ == "__main__":
    main()

